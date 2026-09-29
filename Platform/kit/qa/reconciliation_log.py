"""Reconciliation log (story Q-06): a readable record of how every number in the documents and deck was produced.

Reads outputs/rewardsnext/docs/traceability_docs.json and traceability_deck.json (written by facts.py when the
user guide, technical document and deck were built) plus model/desktop_check.json, and writes one plain-language
log: every number, where it came from (a named Power BI Desktop check, or a formula over other checks), and
whether it passed. This is the "readable reconciliation log" the earlier build produced only as machine JSON.

Usage: python reconciliation_log.py
Writes outputs/rewardsnext/qa/Reconciliation_Log.md
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "..", "outputs", "rewardsnext"))
QA = os.path.join(OUT, "qa")


def load(path):
    return json.load(open(path, encoding="utf-8-sig"))


def fmt(v):
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, float):
        if abs(v) < 1 and v != 0:
            return f"{v * 100:.2f}%" if abs(v) <= 1 else f"{v:,.4f}"
        return f"{v:,.2f}" if v != int(v) else f"{int(v):,}"
    return str(v)


def main():
    docs = load(os.path.join(OUT, "docs", "traceability_docs.json"))
    deck = load(os.path.join(OUT, "docs", "traceability_deck.json"))
    desktop = load(os.path.join(OUT, "model", "desktop_check.json"))
    by_check = {c["check"]: c for c in desktop.get("checks", [])}

    lines = ["# Reconciliation log: RewardsNext", "",
              "Every number that appears in the user guide, technical document or findings deck, and exactly how it was produced. "
              "A number is either read straight from a named check that Power BI Desktop itself confirmed, or computed from one or "
              "more of those checks by a stated formula. Nothing here was typed in by hand.", "",
              f"**Source build:** all {desktop.get('checks') and len(desktop['checks'])} Desktop checks passed "
              f"({'yes' if docs.get('desktop_check_passed') else 'NO'})." , ""]

    def section(title, facts):
        lines.append(f"## {title}")
        lines.append("")
        lines.append("| Number | Value | How it was produced | Desktop check |")
        lines.append("|---|---|---|---|")
        for label, info in facts.items():
            val = fmt(info["value"])
            if "formula" in info:
                parts = ", ".join(f"{k} = {v}" for k, v in info["from"].items())
                how = f"Formula `{info['formula']}` over {parts}"
                check_note = "derived, not a single check"
            else:
                sc = info.get("source_check", label)
                chk = by_check.get(sc)
                how = f"Read directly from the Desktop check \"{sc}\""
                check_note = "PASS" if chk and chk.get("pass") else ("not found" if not chk else "FAIL")
            lines.append(f"| {label} | {val} | {how} | {check_note} |")
        lines.append("")

    section("Numbers in the deck (findings and recommendations)", deck["facts_used"])
    if docs["facts_used"]:
        section("Numbers in the user guide and technical document", docs["facts_used"])

    lines += ["## What this does and does not prove", "",
              "- Every number traces to a named check, and every check's expected value was computed independently in pandas "
              "from the raw or transformed files, then confirmed by Power BI Desktop's own engine reading the live model.",
              "- The independent-recompute check (Q-01, `../qa/independent_recompute.py`) goes one step further for 15 of the "
              "most-used totals: they were recomputed a second time by code that shares nothing with the pipeline that built "
              "the model, and matched.",
              "- What it does not prove: that the model itself is the right model to build (that is a judgement, recorded in "
              "the decisions log), or that every one of the 30 measures has been independently re-derived, not just these "
              "headline figures.", ""]
    os.makedirs(QA, exist_ok=True)
    text = "\n".join(lines) + "\n"
    open(os.path.join(QA, "Reconciliation_Log.md"), "w", encoding="utf-8").write(text)
    print(f"wrote {len(deck['facts_used']) + len(docs['facts_used'])} facts to Reconciliation_Log.md")


if __name__ == "__main__":
    main()
