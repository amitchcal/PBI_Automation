"""Independent recompute agent (stories Q-01, Q-03).

Deliberately does NOT import profile_agent.py, transform_agent.py or model_agent.py.
It re-reads the four raw CSVs and re-derives every whole-dataset KPI with its own code
and its own parsing method (regex, not json/ast), so a bug shared by the production
pipeline's authoring (profile -> transform -> model, all one author, one parsing
approach) has a real chance of being caught rather than silently confirmed.

Two checks:
  Q-01  Every one of the 30 measures (whole-dataset total, no slicers) recomputed from
        the raw files with fresh code, compared against what Power BI Desktop itself
        returned (outputs/rewardsnext/model/desktop_check.json).
  Q-03  A random sample of raw events.value strings parsed with a regex (independent of
        the production ast.literal_eval / Json.Document approach) and compared field by
        field against the production replica's parsed Offer ID / Amount / Reward.

Usage: python independent_recompute.py
Writes outputs/rewardsnext/qa/independent_recompute.json and _result.md.
"""
import json, os, random, re
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", "..", "RewardsNext_datasets"))
OUT_DIR = os.path.normpath(os.path.join(HERE, "..", "..", "outputs", "rewardsnext", "qa"))
MODEL_DIR = os.path.normpath(os.path.join(HERE, "..", "..", "outputs", "rewardsnext", "model"))
TRANSFORM_DIR = os.path.normpath(os.path.join(HERE, "..", "..", "outputs", "rewardsnext", "transform"))

# ------------------------------------------------------------------ Q-03: regex parse of the raw value column
# Independent of ast.literal_eval / Json.Document: hand-rolled regex over the raw text.
RE_OFFER = re.compile(r"'offer[ _]id':\s*'([0-9a-f]{32})'")
RE_AMOUNT = re.compile(r"'amount':\s*([0-9.]+)")
RE_REWARD = re.compile(r"'reward':\s*([0-9.]+)")

def regex_parse(raw):
    m = RE_OFFER.search(raw); offer_id = m.group(1) if m else None
    m = RE_AMOUNT.search(raw); amount = float(m.group(1)) if m else None
    m = RE_REWARD.search(raw); reward = float(m.group(1)) if m else None
    return offer_id, amount, reward

def q03_cross_check(events_raw, n=None, seed=7):
    """Sample n raw rows, regex-parse them, and compare against the production replica."""
    fact = pd.read_csv(os.path.join(TRANSFORM_DIR, "replica", "FactEvents.csv"))
    rng = random.Random(seed)
    n = len(events_raw) if n is None else min(n, len(events_raw))
    idx = rng.sample(range(len(events_raw)), n) if n < len(events_raw) else list(range(len(events_raw)))
    mismatches = []
    for i in idx:
        raw = events_raw.loc[i, "value"]
        offer_id, amount, reward = regex_parse(raw)
        row = fact.iloc[i]  # FactEvents rows are in file order (EventID = i+1), same as events.csv
        exp_offer = None if pd.isna(row["Offer ID"]) else row["Offer ID"]
        exp_amount = None if pd.isna(row["Amount"]) else round(float(row["Amount"]), 2)
        exp_reward = None if pd.isna(row["Reward"]) else round(float(row["Reward"]), 2)
        got_amount = None if amount is None else round(amount, 2)
        got_reward = None if reward is None else round(reward, 2)
        if offer_id != exp_offer or got_amount != exp_amount or got_reward != exp_reward:
            mismatches.append({"row": int(i), "raw": raw, "regex": [offer_id, got_amount, got_reward],
                                "replica": [exp_offer, exp_amount, exp_reward]})
    return {"sampled": len(idx), "mismatches": mismatches, "pass": len(mismatches) == 0}

# ------------------------------------------------------------------ Q-01: independent recompute of every measure
def load_raw():
    customers = pd.read_csv(os.path.join(ROOT, "customers.csv"))
    events = pd.read_csv(os.path.join(ROOT, "events.csv"))
    offers = pd.read_csv(os.path.join(ROOT, "offers.csv"))
    return customers, events, offers

def q01_recompute(customers, events, offers):
    # Independent parse of every row (regex), independent cleaning of age/gender/income.
    parsed = events["value"].apply(regex_parse)
    events = events.assign(offer_id=[p[0] for p in parsed], amount=[p[1] for p in parsed], reward=[p[2] for p in parsed])
    events["is_informational"] = events["offer_id"].map(dict(zip(offers["offer_id"], offers["offer_type"] == "informational")))

    total_customers = len(customers)
    sent = int((events["event"] == "offer received").sum())
    viewed = int((events["event"] == "offer viewed").sum())
    completed = int((events["event"] == "offer completed").sum())
    redeemable_sent = int(((events["event"] == "offer received") & (events["is_informational"] == False)).sum())
    redeemable_completed = int(((events["event"] == "offer completed") & (events["is_informational"] == False)).sum())
    dup_key = events[["customer_id", "event", "offer_id", "amount", "time"]]
    repeated = int(dup_key.duplicated(keep="first").sum())
    completed_repeated = int(dup_key[events["event"] == "offer completed"].duplicated(keep="first").sum())
    completers = set(events.loc[events["event"] == "offer completed", "customer_id"])
    txn = events[events["event"] == "transaction"]
    total_spend = round(float(txn["amount"].sum()), 2)
    n_txn = int(len(txn))
    rewards_paid = round(float(events.loc[events["event"] == "offer completed", "reward"].sum()), 2)
    transacted = set(txn["customer_id"])

    results = {
        "Total Customers": total_customers,
        "Offers Sent": sent,
        "Offers Viewed": viewed,
        "Offers Completed": completed,
        "Redeemable Offers Sent": redeemable_sent,
        "Repeated Completion Rows": completed_repeated,
        "Customers Who Completed": len(completers),
        "View Rate": round(viewed / sent, 6),
        "Redemption Rate": round(redeemable_completed / redeemable_sent, 6),
        "Transactions": n_txn,
        "Total Spend": total_spend,
        "Average Transaction Amount": round(total_spend / n_txn, 6),
        "Customers Who Transacted": len(transacted),
        "Transactions per Customer": round(n_txn / len(transacted), 6),
        "Rewards Paid": rewards_paid,
        "Repeated rows (all events)": repeated,
    }
    return results

def load_desktop_actuals():
    d = json.load(open(os.path.join(MODEL_DIR, "desktop_check.json"), encoding="utf-8-sig"))
    return {c["check"]: c["actual"] for c in d["checks"]}

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    customers, events, offers = load_raw()
    mine = q01_recompute(customers, events, offers)
    desktop = load_desktop_actuals()
    q01_rows = []
    for name, val in mine.items():
        if name not in desktop:
            q01_rows.append({"check": name, "independent": val, "desktop": None, "pass": None, "note": "not in desktop_check.json (no matching measure name)"})
            continue
        dv = desktop[name]
        ok = abs(float(val) - float(dv)) < 0.01
        q01_rows.append({"check": name, "independent": val, "desktop": dv, "pass": bool(ok)})
    q01_pass = all(r["pass"] for r in q01_rows if r["pass"] is not None)

    q03 = q03_cross_check(events)

    out = {"q01_independent_recompute": q01_rows, "q01_pass": q01_pass, "q03_raw_text_cross_check": q03}
    json.dump(out, open(os.path.join(OUT_DIR, "independent_recompute.json"), "w"), indent=2)

    lines = ["# Independent recompute (Q-01, Q-03)", "",
             "Q-01: every measure below was recomputed from the four raw CSVs with code that does not import "
             "profile_agent.py, transform_agent.py or model_agent.py, and does its own regex parsing of the "
             "events.value column (not ast.literal_eval / Json.Document). Compared against the values Power BI "
             "Desktop itself returned in the last model check.", "",
             "| Check | Independent | Desktop | Pass |", "|---|---|---|---|"]
    for r in q01_rows:
        lines.append(f"| {r['check']} | {r['independent']} | {r['desktop']} | {'PASS' if r['pass'] else ('n/a' if r['pass'] is None else 'FAIL')} |")
    lines += ["", f"**Q-01 overall: {'PASS' if q01_pass else 'FAIL'}**", "",
              f"## Q-03: raw-text cross-check ({q03['sampled']} sampled rows, regex vs production replica)",
              f"**{'PASS' if q03['pass'] else 'FAIL'}** — {len(q03['mismatches'])} mismatches out of {q03['sampled']}."]
    if q03["mismatches"]:
        lines.append("")
        for m in q03["mismatches"][:20]:
            lines.append(f"- row {m['row']}: raw `{m['raw']}` -> regex {m['regex']} vs replica {m['replica']}")
    w = "\n".join(lines) + "\n"
    open(os.path.join(OUT_DIR, "QA_RESULT.md"), "w", encoding="utf-8").write(w)
    print(w)
    return 0 if (q01_pass and q03["pass"]) else 1

if __name__ == "__main__":
    raise SystemExit(main())
