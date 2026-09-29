"""Config generator for the generic (config-free) build path.

Turns one engagement's profile, issue decisions and questionnaire KPI list into a first-draft transform
config, model config and report config -- the same declarative shapes the hand-authored RewardsNext configs
use, so they run through generic_transform.py / generic_model.py / report_agent.py unchanged. No domain
knowledge is assumed: relationships come only from the profiler's own key-matching (zero-orphan column
matches), and the customer's own KPI definitions are added to the model as named, unfinished placeholders
for the builder to turn into real formulas -- they are not guessed.

Reads, under <platform>/outputs/<eid>/: profile/profile.json, profile/issues.json, decisions.json, engagement.json
Writes: <platform>/configs/<eid>_transform.json, <eid>_model.json, <eid>_report.json
Also writes manual_review.json listing what a person still needs to look at (columns/issues not auto-handled).

Usage: python generate_configs.py <engagement_id>
"""
import ast, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
PLAT = os.path.normpath(os.path.join(HERE, "..", ".."))


def titleize(name):
    s = re.sub(r"[_\-]+", " ", str(name)).strip()
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", s)
    words = [w for w in s.split(" ") if w]
    out = [("ID" if w.lower() == "id" else w[:1].upper() + w[1:]) for w in words]
    return " ".join(out) if out else str(name)


def pascalize(name):
    words = re.split(r"[_\-\s]+", str(name))
    return "".join(w[:1].upper() + w[1:] for w in words if w) or "Table"


def sentinel_value_from_title(title):
    m = re.search(r": (-?\d+(?:\.\d+)?) looks like a placeholder", title)
    return ast.literal_eval(m.group(1)) if m else None


def sentinel_text_from_evidence(evidence):
    m = re.search(r"mean 'missing': (\[.*?\])", evidence)
    return ast.literal_eval(m.group(1)) if m else []


def col_type(info):
    if info.get("date_int"): return "date_int"
    d = info.get("dtype", "")
    if d.startswith("int"): return "int"
    if d.startswith("float"): return "number"
    return "text"


def main(eid):
    out_dir = os.path.join(PLAT, "outputs", eid)
    profile = json.load(open(os.path.join(out_dir, "profile", "profile.json"), encoding="utf-8"))
    issues = json.load(open(os.path.join(out_dir, "profile", "issues.json"), encoding="utf-8"))
    dec = json.load(open(os.path.join(out_dir, "decisions.json"), encoding="utf-8"))
    meta = json.load(open(os.path.join(out_dir, "engagement.json"), encoding="utf-8"))
    decisions = {d["issue_id"]: d["decision"] for d in dec.get("profile_issue_decisions", [])}
    by_id = {i["id"]: i for i in issues}
    structured = set(profile.get("structured_columns", {}).keys())  # keys are "source.column"

    review = []
    tables, colmap = [], {}   # colmap["source.raw_col"] = (TableName, "Display Name")
    for s in meta["sources"]:
        sid = s["id"]
        src_profile = profile["sources"][sid]
        tname = pascalize(sid)
        steps, select = [], []
        needs_row_id = False
        row_id_reason = None
        # duplicate-row decision for this source (issue kind "duplicate_rows", source == sid)
        dup_issue = next((i for i in issues if i["kind"] == "duplicate_rows" and i["source"] == sid), None)
        if dup_issue:
            d = decisions.get(dup_issue["id"], dup_issue["proposed_rule"])
            all_cols = list(src_profile["columns"].keys())
            if "remove" in d.lower():
                steps.append({"type": "dedupe"})
                review.append(f"{sid}: duplicate rows removed per decision ({dup_issue['id']}).")
            else:
                needs_row_id = True; row_id_reason = (all_cols, dup_issue["id"])

        for raw, info in src_profile["columns"].items():
            key = f"{sid}.{raw}"
            if key in structured:
                review.append(f"{key}: holds structured (JSON/Python-literal) data; not automatically parsed. Add a parse_fields step by hand.")
                continue
            disp = titleize(raw)
            ct = col_type(info)
            sv_issue = next((i for i in issues if i["kind"] == "sentinel_value" and i["source"] == sid and raw in i["columns"]), None)
            st_issue = next((i for i in issues if i["kind"] == "sentinel_text" and i["source"] == sid and raw in i["columns"]), None)
            if sv_issue and "unknown" in decisions.get(sv_issue["id"], sv_issue["proposed_rule"]).lower():
                v = sentinel_value_from_title(sv_issue["title"])
                if v is not None:
                    steps.append({"type": "null_if_equals", "from": raw, "value": v, "name": disp})
                    select.append({"name": disp, "type": "int" if ct != "number" else "number"})
                    colmap[key] = (tname, disp); continue
            if st_issue and "unknown" in decisions.get(st_issue["id"], st_issue["proposed_rule"]).lower():
                bad = sentinel_text_from_evidence(st_issue["evidence"])
                if bad:
                    steps.append({"type": "null_if_in", "from": raw, "values": bad, "name": disp})
                    select.append({"name": disp, "type": "text"})
                    colmap[key] = (tname, disp); continue
            if ct == "date_int":
                dname = disp + " Date"
                steps.append({"type": "date_yyyymmdd", "from": raw, "name": dname})
                select.append({"name": dname, "type": "date"})
                colmap[key] = (tname, dname)
                review.append(f"{key}: converted from a YYYYMMDD number to a date column '{dname}' automatically.")
                continue
            select.append({"from": raw, "name": disp, "type": ct if ct != "date_int" else "int"})
            colmap[key] = (tname, disp)

        if needs_row_id:
            all_cols, iid = row_id_reason
            steps.append({"type": "index", "name": "Row ID"})
            select.insert(0, {"name": "Row ID", "type": "int"})
            steps.append({"type": "repeat_flag", "name": "Is Repeated Row", "keys": all_cols, "id_col": "Row ID"})
            select.append({"name": "Is Repeated Row", "type": "logical"})
            review.append(f"{sid}: duplicate rows kept and flagged 'Is Repeated Row' per decision ({iid}).")

        tables.append({"name": tname, "source": sid, "role": "table", "reason": "Passthrough table, auto-generated from the uploaded file and your data decisions.", "steps": steps, "select": select})

    transform_cfg = {"engagement": {"id": eid, "project": meta["project"]}, "data_root": meta["data_root"],
                      "sources": meta["sources"], "tables": tables}

    # relationships: zero-orphan links the profiler found, translated through colmap; skip anything touching a structured/list sub-field
    rels, seen = [], set()
    for link in profile.get("links", []):
        if link.get("orphans"): continue
        f, t = link["from"], link["to"]
        if "[" in f or "[" in t: continue
        if f not in colmap or t not in colmap: continue
        fk, tk = f, t
        ft, fd = colmap[fk]; tt, td = colmap[tk]
        if ft == tt: continue
        pair = tuple(sorted([f"{ft}.{fd}", f"{tt}.{td}"]))
        if pair in seen: continue
        seen.add(pair)
        rels.append({"from": f"{ft}.{fd}", "to": f"{tt}.{td}", "note": "Detected automatically: matching values, no orphans."})
    model_cfg = {"engagement": {"id": eid, "project": meta["project"]}, "measures_table": meta.get("measures_table", "Key Measures"), "relationships": rels}

    # report: an overview page (cards for row counts, capped) + one table page per source.
    # Story I-04: the customer's chosen page layout changes this, not just the label on it. "Executive dashboard"
    # keeps the first draft to a headline page and one combined detail page, in line with its own description
    # ("big headline numbers, one clear chart per page"); the generic builder has no domain knowledge to draw a
    # real chart per table, so "one clear chart" here means one focused overview, not a literal chart per page --
    # that gap is named below rather than faked. "Analyst dashboard" (the default) keeps the denser one-page-per-
    # table layout for exploring. A customer's own uploaded template cannot be auto-matched, so it falls back to
    # the analyst layout and is flagged for a person to lay out by hand.
    template = meta.get("template", "Analyst dashboard")
    executive = template == "Executive dashboard"
    card_w, card_h = (280, 120) if executive else (200, 90)
    n_cards = min(len(tables), 4 if executive else 6)
    pages = [{"name": "overview", "displayName": "Overview", "visuals": [
        {"id": "title", "type": "textbox", "pos": [24, 6, 640, 40], "runs": [{"text": meta["name"], "fontFamily": "Segoe UI Semibold", "fontSize": "18pt", "fontWeight": "bold"}]},
        {"id": "sub", "type": "textbox", "pos": [24, 46, 640, 26], "runs": [{"text": "Automated first draft. Row counts only -- your KPI definitions are listed but not yet built as measures.", "fontFamily": "Segoe UI", "fontSize": "10pt"}]},
    ]}]
    for i in range(n_cards):
        t = tables[i]
        per_row = 2 if executive else 3
        pages[0]["visuals"].append({"id": f"card{i}", "type": "card", "pos": [24 + (i % per_row) * (card_w + 20), 84 + (i // per_row) * (card_h + 10), card_w, card_h], "measure": f"{t['name']} Row Count", "title": f"{t['name']} rows"})
    if executive:
        # one combined detail page instead of one per table, to keep an executive draft short
        pages.append({"name": "detail", "displayName": "Detail", "visuals": [
            {"id": "title", "type": "textbox", "pos": [24, 6, 640, 34], "runs": [{"text": "All sources", "fontFamily": "Segoe UI Semibold", "fontSize": "14pt", "fontWeight": "bold"}]},
        ]})
        y = 46
        for t in tables:
            cols = [f"{t['name']}.{c['name']}" for c in t["select"]][:6]
            h = 140
            pages[-1]["visuals"].append({"id": f"tbl_{t['name'].lower()}", "type": "tableEx", "pos": [24, y, 1220, h], "columns": cols, "measures": [], "title": t["name"]})
            y += h + 14
    else:
        for t in tables:
            cols = [f"{t['name']}.{c['name']}" for c in t["select"]][:12]
            pages.append({"name": t["name"].lower(), "displayName": t["name"], "visuals": [
                {"id": "title", "type": "textbox", "pos": [24, 6, 640, 34], "runs": [{"text": t["name"], "fontFamily": "Segoe UI Semibold", "fontSize": "14pt", "fontWeight": "bold"}]},
                {"id": "table", "type": "tableEx", "pos": [24, 46, 1220, 650], "columns": cols, "measures": []},
            ]})
    report_cfg = {"engagement": {"id": eid, "project": meta["project"]}, "brand_kit": meta.get("brand_kit", eid), "images": meta.get("images", []),
                  "measures_table": meta.get("measures_table", "Key Measures"), "pages": pages}

    cfgdir = os.path.join(PLAT, "configs")
    json.dump(transform_cfg, open(os.path.join(cfgdir, f"{eid}_transform.json"), "w"), indent=2)
    json.dump(model_cfg, open(os.path.join(cfgdir, f"{eid}_model.json"), "w"), indent=2)
    json.dump(report_cfg, open(os.path.join(cfgdir, f"{eid}_report.json"), "w"), indent=2)
    for k in meta.get("kpis", []):
        review.append(f"KPI \"{k['name']}\" from your needs form still needs a real formula: {k.get('description', '(no definition given)')}")
    if template == "Custom template":
        review.append("The customer uploaded their own page layout as a reference. This draft used the standard analyst layout instead -- a person needs to lay out the report pages to match the uploaded file by hand.")
    json.dump({"items": review}, open(os.path.join(out_dir, "manual_review.json"), "w"), indent=2)
    print(f"generated configs for {eid}: {len(tables)} tables, {len(rels)} relationships, {len(review)} items need manual review")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
