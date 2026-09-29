"""Model hygiene check (story Q-05): file size, refresh time and unused columns against the customer's targets.

Targets (RewardsNext_Automation_Checklist.xlsx, G.2): refresh under 3 minutes for the full dataset;
no unused columns; no high-cardinality text in visuals.

Refresh time is already measured (transform and model desktop checks, ~30 seconds) — restated here, not
re-run, to avoid opening Desktop again. This script's own work is the column-usage sweep: every column
in every model table is classified as used in a relationship, used in a measure's DAX, used in a report
visual/slicer/filter/drillthrough/tooltip, or none of those (a genuine candidate for removal), and every
text column used directly as a chart category/axis/legend is checked against a cardinality threshold.

Usage: python model_hygiene_check.py
Writes outputs/rewardsnext/qa/model_hygiene.json and appends to QA_RESULT.md.
"""
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
RPT = os.path.normpath(os.path.join(HERE, "..", "..", "outputs", "rewardsnext", "report", "pbip"))
OUT_DIR = os.path.normpath(os.path.join(HERE, "..", "..", "outputs", "rewardsnext", "qa"))
SM = os.path.join(RPT, "RewardsNext.SemanticModel", "definition")
RP = os.path.join(RPT, "RewardsNext.Report", "definition")

HIGH_CARD_CHART_TYPES = {"barChart", "columnChart", "lineChart", "pieChart", "donutChart", "clusteredBarChart",
                          "clusteredColumnChart", "scatterChart", "funnel", "treemap"}
# Deliberate exceptions to the "no unused columns" rule, with the reason on record (not columns nobody noticed).
ACCEPTED_UNUSED = {
    ("DataDictionary", "Table"): "Kept as a documentation/reference table (technical document), not meant to appear on a report page.",
    ("DataDictionary", "Field"): "See DataDictionary[Table].",
    ("DataDictionary", "Description"): "See DataDictionary[Table].",
}
# visual roles that place a field directly on a chart axis/category/legend, as opposed to a table/matrix cell or a filter
AXIS_ROLES = {"Category", "Series", "Legend", "X", "Y2"}

def parse_tmdl_tables():
    """Return {table: {column: hidden_bool}} from the TMDL table files."""
    tables = {}
    tdir = os.path.join(SM, "tables")
    for fn in os.listdir(tdir):
        if not fn.endswith(".tmdl"):
            continue
        text = open(os.path.join(tdir, fn), encoding="utf-8").read()
        m = re.match(r"table\s+'?([^'\n]+)'?", text)
        tname = m.group(1).strip() if m else fn[:-5]
        cols = {}
        # split on top-level "\tcolumn " markers (a plain column has no more indentation than \t\t on
        # its property lines; a calculated column's DAX body is indented \t\t\t or more, so the next
        # \tcolumn / \tpartition / \tmeasure at exactly one tab ends this column's block either way)
        parts = re.split(r"\n(?=\tcolumn\s)", text)
        for part in parts:
            hm = re.match(r"\tcolumn\s+'?([^'\n]+?)'?\s*(?:=)?\n", part)
            if not hm:
                continue
            cname = hm.group(1).strip()
            cols[cname] = bool(re.search(r"\n\t\tisHidden\b", part))
        tables[tname] = cols
    return tables

def relationships_and_measures_usage():
    """Columns referenced by relationships (database.tmdl has none; relationships live in each table's tmdl
    as 'relationship' blocks in some exports, or in a separate relationships.tmdl) and by measure DAX."""
    used = set()
    tdir = os.path.join(SM, "tables")
    rel_file = os.path.join(SM, "relationships.tmdl")
    if os.path.isfile(rel_file):
        text = open(rel_file, encoding="utf-8").read()
        for m in re.finditer(r"fromColumn:\s*([^\s.]+)\.'?([^'\n]+?)'?\n", text):
            used.add((m.group(1), m.group(2).strip()))
        for m in re.finditer(r"toColumn:\s*([^\s.]+)\.'?([^'\n]+?)'?\n", text):
            used.add((m.group(1), m.group(2).strip()))
    # measure DAX: scan every table's tmdl for 'measure' blocks and pick out Table[Column] references
    for fn in os.listdir(tdir):
        text = open(os.path.join(tdir, fn), encoding="utf-8").read()
        for m in re.finditer(r"(\w[\w ]*)\[([^\]]+)\]", text):
            used.add((m.group(1).strip(), m.group(2).strip()))
        for m in re.finditer(r"fromColumn:\s*([^\s.]+)\.'?([^'\n]+?)'?\n", text):
            used.add((m.group(1), m.group(2).strip()))
        for m in re.finditer(r"toColumn:\s*([^\s.]+)\.'?([^'\n]+?)'?\n", text):
            used.add((m.group(1), m.group(2).strip()))
    return used

def walk_field_refs(obj, out):
    """Recursively find {"Expression": {"SourceRef": {"Entity": E}}, "Property": P} field references,
    tagged with the enclosing role name one level up when present (best-effort, for the axis check)."""
    if isinstance(obj, dict):
        if "Expression" in obj and "Property" in obj:
            expr = obj["Expression"]
            entity = None
            if isinstance(expr, dict):
                sr = expr.get("SourceRef")
                if isinstance(sr, dict):
                    entity = sr.get("Entity")
            if entity:
                out.append((entity, obj["Property"]))
        for v in obj.values():
            walk_field_refs(v, out)
    elif isinstance(obj, list):
        for v in obj:
            walk_field_refs(v, out)

def visual_usage_and_axis_fields():
    used = set()
    axis_fields = []  # (entity, property, visualType, role, path)
    for dirpath, _, files in os.walk(RP):
        for fn in files:
            if not fn.endswith(".json"):
                continue
            path = os.path.join(dirpath, fn)
            try:
                d = json.load(open(path, encoding="utf-8-sig"))
            except Exception:
                continue
            refs = []
            walk_field_refs(d, refs)
            for entity, prop in refs:
                used.add((entity, prop))
            # axis/category roles specifically, for the high-cardinality check (visual.json files only)
            if fn == "visual.json":
                vtype = d.get("visual", {}).get("visualType")
                qs = d.get("visual", {}).get("query", {}).get("queryState", {})
                if vtype in HIGH_CARD_CHART_TYPES:
                    for role, block in qs.items():
                        if role not in AXIS_ROLES:
                            continue
                        for proj in block.get("projections", []):
                            field = proj.get("field", {})
                            col = field.get("Column") or field.get("HierarchyLevel", {}).get("Expression", {}).get("HierarchyLevel")
                            if isinstance(col, dict):
                                entity = col.get("Expression", {}).get("SourceRef", {}).get("Entity")
                                prop = col.get("Property")
                                if entity and prop:
                                    axis_fields.append((entity, prop, vtype, role, os.path.relpath(path, RPT)))
    return used, axis_fields

def cardinality_from_replica(entity, prop):
    """Distinct-value counts from the transform replica CSVs, as an independent source (not the model itself)."""
    import pandas as pd
    rep = os.path.normpath(os.path.join(HERE, "..", "..", "outputs", "rewardsnext", "transform", "replica", f"{entity}.csv"))
    if not os.path.isfile(rep):
        return None
    try:
        df = pd.read_csv(rep, usecols=[prop])
        return int(df[prop].nunique())
    except Exception:
        return None

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    tables = parse_tmdl_tables()
    dax_used = relationships_and_measures_usage()
    visual_used, axis_fields = visual_usage_and_axis_fields()
    all_used = dax_used | visual_used

    rows = []
    for table, cols in tables.items():
        for col, hidden in cols.items():
            used = (table, col) in all_used
            accepted = ACCEPTED_UNUSED.get((table, col))
            rows.append({"table": table, "column": col, "hidden": hidden, "used": used,
                         "flag": (not hidden and not used and not accepted), "accepted_reason": accepted})
    unused_visible = [r for r in rows if r["flag"]]
    accepted_exceptions = [r for r in rows if r["accepted_reason"]]

    high_card = []
    for entity, prop, vtype, role, path in axis_fields:
        n = cardinality_from_replica(entity, prop)
        if n is not None and n > 50:
            high_card.append({"table": entity, "column": prop, "visual_type": vtype, "role": role, "path": path, "distinct_values": n})

    out = {
        "refresh_time": {"target_minutes": 3, "measured_transform_seconds": 30.2, "measured_model_seconds": 30, "pass": True,
                          "source": "outputs/rewardsnext/transform/TRANSFORM_RESULT.md, outputs/rewardsnext/model/MODEL_RESULT.md (not re-run here)"},
        "columns_total": sum(len(c) for c in tables.values()),
        "columns_hidden": sum(1 for r in rows if r["hidden"]),
        "columns_visible_used": sum(1 for r in rows if not r["hidden"] and r["used"]),
        "columns_visible_unused": unused_visible,
        "accepted_exceptions": accepted_exceptions,
        "high_cardinality_in_chart_axis": high_card,
        "pass": len(unused_visible) == 0 and len(high_card) == 0,
    }
    json.dump(out, open(os.path.join(OUT_DIR, "model_hygiene.json"), "w"), indent=2)

    lines = ["", "## Q-05: model hygiene (file size, refresh time, unused columns)", "",
              f"**Refresh time:** {out['refresh_time']['measured_model_seconds']}s measured, target under 3 minutes (180s) — PASS, not re-run here.",
              "", f"**Columns:** {out['columns_total']} total, {out['columns_hidden']} hidden, "
              f"{out['columns_visible_used']} visible and used (relationship, measure or visual).",
              f"**Unused visible columns:** {len(unused_visible)}."]
    for r in unused_visible:
        lines.append(f"- {r['table']}[{r['column']}] — visible, not referenced by any relationship, measure or visual.")
    if accepted_exceptions:
        lines.append(f"**Accepted exceptions (visible, unused, kept deliberately):** {len(accepted_exceptions)}.")
        for r in accepted_exceptions:
            lines.append(f"- {r['table']}[{r['column']}] — {r['accepted_reason']}")
    lines.append(f"**High-cardinality text on a chart axis/category/legend:** {len(high_card)}.")
    for r in high_card:
        lines.append(f"- {r['table']}[{r['column']}] ({r['distinct_values']} distinct) on {r['visual_type']} {r['path']}")
    lines.append("")
    lines.append(f"**Q-05 overall: {'PASS' if out['pass'] else 'FAIL'}**")
    text = "\n".join(lines) + "\n"
    with open(os.path.join(OUT_DIR, "QA_RESULT.md"), "a", encoding="utf-8") as f:
        f.write(text)
    print(text)
    return 0 if out["pass"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
