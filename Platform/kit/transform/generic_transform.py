"""Generic transform driver, for a live engagement with no hand-authored table spec yet.

Reuses transform_agent's proven step functions and PBIP writer unchanged (build_table, staging_m, emit_pbip),
but replaces its RewardsNext-specific main() with a generic one: every table is one source, passed through
as-is except for the steps that generate_configs.py added from the customer's own decisions (sentinel values,
duplicates). Checks and the raw-vs-replica gate are computed generically from profile_agent's reference_totals,
not from any known column meaning.

Usage: python generic_transform.py <config.json>   (same "sources"/"tables" shape as transform_agent's config)
"""
import json, os, shutil, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import transform_agent as T


def main(cfg_path):
    cfg = json.load(open(cfg_path, encoding="utf-8"))
    cdir = os.path.dirname(os.path.abspath(cfg_path))
    root = os.path.normpath(os.path.join(cdir, cfg.get("data_root", ".")))
    eid = cfg["engagement"]["id"]
    out = os.path.normpath(os.path.join(cdir, "..", "outputs", eid, "transform"))
    prof_dir = os.path.normpath(os.path.join(cdir, "..", "outputs", eid, "profile"))
    if os.path.isdir(out): shutil.rmtree(out)
    profile = json.load(open(os.path.join(prof_dir, "profile.json"), encoding="utf-8"))["sources"]
    ref = json.load(open(os.path.join(prof_dir, "reference_totals.json"), encoding="utf-8"))["sources"]

    stg, expressions = {}, {"SourceFolder": None}
    for s in cfg["sources"]:
        df, path, info = T.pa.load_source(s, root)
        stg[s["id"]] = df
        expressions[f"Stg_{s['id']}"] = T.staging_m(s["id"], profile[s["id"]], dict(info, path=path))
        T.w(os.path.join(out, "queries", f"Stg_{s['id']}.m"), expressions[f"Stg_{s['id']}"] + "\n")

    tables, plan, checks, gate = [], [], [], []
    for t in cfg["tables"]:
        m, df, desc = T.build_table(t, stg[t["source"]])
        T.w(os.path.join(out, "queries", f"{t['name']}.m"), m + "\n")
        os.makedirs(os.path.join(out, "replica"), exist_ok=True)
        df.to_csv(os.path.join(out, "replica", f"{t['name']}.csv"), index=False)
        tables.append({"name": t["name"], "m": m, "columns": [dict(c) for c in t["select"]]})
        plan.append({"table": t["name"], "source": t["source"], "role": t.get("role", "table"), "rows": len(df), "steps": desc, "reason": t.get("reason", "")})
        checks.append({"name": f"Rows in {t['name']}", "dax": f"COUNTROWS('{t['name']}')", "expected": len(df)})
        R = ref.get(t["source"], {})
        for c in t["select"]:
            raw = c.get("from", c["name"])
            if c["type"] in ("int", "number") and raw in R.get("sums", {}):
                checks.append({"name": f"Sum of {t['name']}[{c['name']}]", "dax": f"SUM('{t['name']}'[{c['name']}])", "expected": round(float(df[c["name"]].sum()), 2)})
        deduped = any(s["type"] == "dedupe" for s in t["steps"])
        raw_rows = R.get("rows", len(df))
        expected_rows = raw_rows - (int(profile[t["source"]].get("duplicate_rows", 0)) if deduped else 0)
        gate.append({"check": f"{t['name']} rows vs {t['source']} rows", "replica": len(df), "raw": expected_rows, "pass": len(df) == expected_rows})

    T.w(os.path.join(out, "transform_plan.md"),
        "\n".join(["# Transform plan (generic, first draft)", ""] +
                   sum([[f"## {p['table']} (from {p['source']}, {p['rows']:,} rows)", ""] + [f"{i + 1}. {d}" for i, d in enumerate(p["steps"])] + [""] for p in plan], [])))
    json.dump(plan, open(os.path.join(out, "transform_plan.json"), "w"), indent=2)
    json.dump(checks, open(os.path.join(out, "expected_checks.json"), "w"), indent=2)
    res_gate = {"passed": all(g["pass"] for g in gate), "checks": gate}
    json.dump(res_gate, open(os.path.join(out, "transform_gate.json"), "w"), indent=2)
    proj = cfg["engagement"].get("project", eid)
    p = T.emit_pbip(out, proj, tables, expressions, root)
    print(f"generic transform: {len(tables)} tables, gate passed: {res_gate['passed']} | project: {os.path.join(p, proj + '.pbip')}")
    return 0 if res_gate["passed"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
