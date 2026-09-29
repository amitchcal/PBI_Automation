"""Runs the generic first-draft pipeline for one engagement: transform -> model -> report.
Assumes generate_configs.py has already written <platform>/configs/<eid>_{transform,model,report}.json.
Does not touch Power BI Desktop -- that is a separate, explicit step (desktop_check.py) because it opens a
window on whichever machine runs this.

Writes <platform>/outputs/<eid>/build_status.json: per-stage ok/error and a short result line, plus overall "ok".
Usage: python run_build.py <engagement_id>
"""
import datetime as dt
import json, os, sys, traceback

HERE = os.path.dirname(os.path.abspath(__file__))
PLAT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(PLAT, "kit", "transform"))
sys.path.insert(0, os.path.join(PLAT, "kit", "model"))
sys.path.insert(0, os.path.join(PLAT, "kit", "report"))


def run_stage(name, fn, *args):
    try:
        code = fn(*args)
        return {"name": name, "ok": (code or 0) == 0}
    except Exception as e:
        return {"name": name, "ok": False, "error": f"{type(e).__name__}: {e}", "trace": traceback.format_exc()[-2000:]}


def main(eid):
    cfgdir = os.path.join(PLAT, "configs")
    out = os.path.join(PLAT, "outputs", eid)
    stages = []

    import generic_transform
    stages.append(run_stage("transform", generic_transform.main, os.path.join(cfgdir, f"{eid}_transform.json")))
    if stages[-1]["ok"]:
        import generic_model
        stages.append(run_stage("model", generic_model.main, os.path.join(cfgdir, f"{eid}_model.json")))
    if len(stages) == 2 and stages[-1]["ok"]:
        import report_agent
        stages.append(run_stage("report", report_agent.main, os.path.join(cfgdir, f"{eid}_report.json")))

    ok = all(s["ok"] for s in stages)
    status = {"eid": eid, "ran_at": dt.datetime.now().isoformat(timespec="seconds"), "ok": ok, "stages": stages,
              "report_pbip": os.path.join(out, "report", "pbip", "") if ok else None,
              "model_pbip": os.path.join(out, "model", "pbip", "") if ok else None}
    json.dump(status, open(os.path.join(out, "build_status.json"), "w"), indent=2)
    for s in stages: print(("OK   " if s["ok"] else "FAIL ") + s["name"] + (f": {s.get('error', '')}" if not s["ok"] else ""))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
