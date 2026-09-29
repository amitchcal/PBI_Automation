"""Facts registry (story D-04: every number in the documents and deck traces to a validated value).

Numbers come only from expected_model_checks.json: the values that were computed in pandas and matched by Power BI Desktop in the check run
(desktop_check.json, all checks passed). A document asks for a fact by key; a missing key stops the build, and every fact used is written to
traceability.json with its source check name.
"""
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
PLAT = os.path.normpath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(PLAT, "outputs", "rewardsnext")

class Facts:
    def __init__(self):
        chk = json.load(open(os.path.join(OUT, "model", "expected_model_checks.json"), encoding="utf-8"))
        self.by_name = {x["name"]: x["expected"] for x in chk["scalar"]}
        run = json.load(open(os.path.join(OUT, "model", "desktop_check.json"), encoding="utf-8-sig"))
        self.desktop_ok = bool(run.get("all_passed")); self.desktop_checks = len(run.get("checks", []))
        assert self.desktop_ok, "the last Desktop check run did not pass; documents are only built from verified values"
        self.used = {}

    def raw(self, check_name, label=None):
        if check_name not in self.by_name: raise KeyError(f"no verified value named '{check_name}'")
        v = self.by_name[check_name]; self.used[label or check_name] = {"value": v, "source_check": check_name}
        return v

    def derived(self, label, formula, **parts):
        vals = {k: self.raw(v) for k, v in parts.items()}
        v = eval(formula, {}, vals); self.used[label] = {"value": v, "formula": formula, "from": parts}
        return v

    # formatting
    @staticmethod
    def n(v): return f"{int(round(v)):,}"
    @staticmethod
    def pct(v, d=1): return f"{v * 100:.{d}f}%"
    @staticmethod
    def usd(v, d=2): return f"${v:,.{d}f}"

    def save(self, path):
        json.dump({"desktop_check_passed": self.desktop_ok, "desktop_checks": self.desktop_checks, "facts_used": self.used}, open(path, "w", encoding="utf-8"), indent=2)
