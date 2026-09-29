"""Generic model driver, for a live engagement with no hand-authored measures yet.

Reuses model_agent's proven TMDL writers (add_relationships, add_measures, update_model_file), which are
already generic, but not its expected_checks()/load_replica(), which are written for RewardsNext's specific
tables. Instead this derives a plain but real first draft directly from the transform stage's own replica
CSVs: one row-count measure per table, and a sum/average measure for numeric columns that are not an ID.
Relationships come from the transform config (generate_configs.py already filtered them to zero-orphan links
found by the profiler). Every measure is checked against the same pandas values used to generate it.

Usage: python generic_model.py <config.json>   ({"engagement":{"id","project"}, "measures_table", "relationships"})
"""
import json, os, re, shutil, sys
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import model_agent as M

ID_LIKE = re.compile(r"(^|\s)(id|key|code)$", re.I)


def is_measure_worthy(df, col):
    if not pd.api.types.is_numeric_dtype(df[col]): return False
    if pd.api.types.is_bool_dtype(df[col]): return False
    if ID_LIKE.search(col): return False
    return df[col].nunique(dropna=True) > 5


def main(cfg_path):
    cfg = json.load(open(cfg_path, encoding="utf-8"))
    cdir = os.path.dirname(os.path.abspath(cfg_path))
    eid = cfg["engagement"]["id"]; proj = cfg["engagement"]["project"]
    base = os.path.normpath(os.path.join(cdir, "..", "outputs", eid))
    src = os.path.join(base, "transform", "pbip"); out = os.path.join(base, "model"); dst = os.path.join(out, "pbip")
    os.makedirs(out, exist_ok=True)
    if os.path.isdir(dst): shutil.rmtree(dst)
    shutil.copytree(src, dst)
    defdir = os.path.join(dst, f"{proj}.SemanticModel", "definition")
    mt = cfg.get("measures_table", "Key Measures")

    M.add_relationships(defdir, cfg.get("relationships", []))
    M.add_calculated_tables(defdir, [])
    M.add_calculated_columns(defdir, [])
    M.hide_columns(defdir, [])

    rdir = os.path.join(base, "transform", "replica")
    measures, scalar = [], []
    for fn in sorted(os.listdir(rdir)):
        table = fn[:-4]
        df = pd.read_csv(os.path.join(rdir, fn), low_memory=False)
        measures.append({"name": f"{table} Row Count", "folder": "Auto-generated\\Row counts", "format": "#,0", "dax": [f"COUNTROWS('{table}')"],
                          "description": f"Number of rows in {table}, auto-generated (no manual definition given yet)."})
        scalar.append({"name": f"{table} Row Count", "dax": f"COUNTROWS('{table}')", "expected": len(df)})
        for col in df.columns:
            if not is_measure_worthy(df, col): continue
            total = df[col].dropna()
            is_float = pd.api.types.is_float_dtype(df[col])
            fmt = "#,0.00" if is_float else "#,0"
            s = round(float(total.sum()), 2) if is_float else int(total.sum())
            a = round(float(total.mean()), 4) if len(total) else 0
            measures.append({"name": f"Sum of {col} ({table})", "folder": f"Auto-generated\\{table}", "format": fmt, "dax": [f"SUM('{table}'[{col}])"],
                              "description": f"Total {col} across {table}, auto-generated. Replace with a business definition if this needs a filter (e.g. excluding a category)."})
            scalar.append({"name": f"Sum of {col} ({table})", "dax": f"SUM('{table}'[{col}])", "expected": s})
            measures.append({"name": f"Average {col} ({table})", "folder": f"Auto-generated\\{table}", "format": "#,0.00", "dax": [f"AVERAGE('{table}'[{col}])"],
                              "description": f"Average {col} across {table}, auto-generated."})
            scalar.append({"name": f"Average {col} ({table})", "dax": f"AVERAGE('{table}'[{col}])", "expected": a, "tol": max(abs(a) * 0.001, 0.01)})

    M.add_measures(defdir, measures, mt)
    M.update_model_file(defdir, [mt])
    L = ["# Measure dictionary (auto-generated first draft)", "", f"{len(measures)} measures. These are mechanical row counts and sums, not the customer's own KPI",
         "definitions -- the approved KPI list from the questionnaire is a separate, unauthored checklist the builder still needs to turn into formulas.", ""]
    for m in measures: L += [f"### {m['name']}", m["description"], "", "```dax", "\n".join(m["dax"]), "```", ""]
    M.w(os.path.join(out, "measure_dictionary.md"), "\n".join(L) + "\n")
    json.dump({"scalar": scalar, "table": [], "dmv": []}, open(os.path.join(out, "expected_model_checks.json"), "w"), indent=1)
    print(f"generic model project: {os.path.join(dst, proj + '.pbip')}\n  relationships {len(cfg.get('relationships', []))}, measures {len(measures)}, expected scalar checks {len(scalar)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
