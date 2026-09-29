"""Model and measures agent (stories M-01 to M-05, and the calculation part of the 100-customer sample check).

Takes the Power BI project produced by the transform stage and adds, from the config's model section:
  relationships, a calculated time table, calculated columns, hidden technical columns and the measures table.
Also writes:
  measure_dictionary.md          every measure with its plain-words description and formula (for the KPI cards, M-03)
  expected_model_checks.json     what Power BI must return for each measure (computed independently in pandas)
Usage: python model_agent.py <model_config.json>
"""
import json, os, re, shutil, sys, uuid
import numpy as np
import pandas as pd

TMDL_TYPE = {"text": "string", "int": "int64", "number": "double", "date": "dateTime", "logical": "boolean"}

def w(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as f: f.write(text)

def qn(name): return "'" + name + "'" if re.search(r"[^A-Za-z0-9_]", name) else name
def ref(table_col):
    t, c = table_col.split(".", 1); return f"{qn(t)}.{qn(c)}"

def dax_block(lines, indent):
    return "\n".join("\t" * indent + ln for ln in lines)

# ------------------------------------------------------------------ TMDL edits
def add_relationships(defdir, rels):
    out = []
    for r in rels:
        rid = str(uuid.uuid5(uuid.NAMESPACE_URL, r["from"] + ">" + r["to"]))
        out += [f"relationship {rid}", f"\tfromColumn: {ref(r['from'])}", f"\ttoColumn: {ref(r['to'])}"]
        if r.get("both"): out.append("\tcrossFilteringBehavior: bothDirections")
        out.append("")
    w(os.path.join(defdir, "relationships.tmdl"), "\n".join(out))

def add_calculated_tables(defdir, tables):
    for t in tables:
        L = [f"table {t['name']}", ""]
        for c in t["columns"]:
            L += [f"\tcolumn {qn(c['name'])}", f"\t\tdataType: {TMDL_TYPE[c['type']]}", f"\t\tsourceColumn: [{c['name']}]", "\t\tsummarizeBy: none", ""]
        L += [f"\tpartition {t['name']} = calculated", "\t\tmode: import", "\t\tsource =", dax_block(t["dax"], 4), ""]
        w(os.path.join(defdir, "tables", f"{t['name']}.tmdl"), "\n".join(L))

def add_calculated_columns(defdir, cols):
    for tname in sorted({c["table"] for c in cols}):
        p = os.path.join(defdir, "tables", f"{tname}.tmdl"); s = open(p, encoding="utf-8").read()
        add = ""
        for c in [c for c in cols if c["table"] == tname]:
            extra = ("\t\tisHidden\n" if c.get("hidden") else "") + (f"\t\tsortByColumn: {qn(c['sortBy'])}\n" if c.get("sortBy") else "")
            add += (f"\tcolumn {qn(c['name'])} =\n{dax_block(c['dax'], 3)}\n\t\tdataType: {TMDL_TYPE[c['type']]}\n{extra}\t\tsummarizeBy: none\n\n")
        marker = f"\tpartition {tname} = m"
        assert marker in s, f"partition of {tname} not found"
        w(p, s.replace(marker, add + marker, 1))

def build_segments(segs):
    """Segment definitions (config) -> calculated columns for DimCustomer, plus a pandas function that assigns the same columns.
    One definition drives both the DAX and the expected values."""
    cols, steps = [], []
    T = "DimCustomer"
    for b in segs.get("bands", []):
        src, edges, labels, unk, name = b["source"], b["edges"], b["labels"], b["unknown"], b["name"]; assert len(labels) == len(edges) + 1
        for suffix, vals, typ in (("", labels, "text"), (" Order", list(range(1, len(labels) + 1)), "int")):
            lit = (lambda v: '"' + v + '"') if typ == "text" else str
            lines = ["SWITCH(TRUE(),", f"    ISBLANK({T}[{src}]), {lit(unk if typ == 'text' else len(labels) + 1)},"]
            lines += [f"    {T}[{src}] < {e}, {lit(vals[i])}," for i, e in enumerate(edges)] + [f"    {lit(vals[-1])}", ")"]
            c = {"table": T, "name": name + suffix, "type": typ, "dax": lines}
            if suffix: c["hidden"] = True
            else: c["sortBy"] = name + " Order"
            cols.append(c)
        steps.append(("band", b))
    if "tenure" in segs:
        t = segs["tenure"]
        cols.append({"table": T, "name": t["name"], "type": "text", "dax": [f'"{t["prefix"]}" & {T}[{t["source"]}]'], "sortBy": t["source"]}); steps.append(("tenure", t))
    if "engagement" in segs:
        e = segs["engagement"]
        for nm, ev in (("received", "offer received"), ("viewed", "offer viewed"), ("completed", "offer completed")):
            cols.append({"table": T, "name": e[nm], "type": "int", "dax": [f'CALCULATE(COUNTROWS(FactEvents), FactEvents[Event] = "{ev}") + 0']})
        R, V, C = (f"{T}[{e[k]}]" for k in ("received", "viewed", "completed"))
        tiers = [("Heavy completer", f"{C} >= {e['heavy_min']}"), ("Light completer", f"{C} >= {e['light_min']}"), ("Viewer only", f"{V} >= 1"), ("Ignored", f"{R} >= 1")]
        names = [t_[0] for t_ in tiers] + ["Not reached"]
        for suffix, typ, vals in (("", "text", names), (" Order", "int", list(range(1, len(names) + 1)))):
            lit = (lambda v: '"' + v + '"') if typ == "text" else str
            lines = ["SWITCH(TRUE(),"] + [f"    {cond}, {lit(vals[i])}," for i, (_, cond) in enumerate(tiers)] + [f"    {lit(vals[-1])}", ")"]
            c = {"table": T, "name": e["tier_name"] + suffix, "type": typ, "dax": lines}
            if suffix: c["hidden"] = True
            else: c["sortBy"] = e["tier_name"] + " Order"
            cols.append(c)
        lv = ["High", "Medium", "Low"]
        for suffix, typ, vals in (("", "text", lv), (" Order", "int", [1, 2, 3])):
            lit = (lambda v: '"' + v + '"') if typ == "text" else str
            lines = ["SWITCH(TRUE(),", f"    {C} >= {e['heavy_min']}, {lit(vals[0])},", f"    {C} >= {e['light_min']}, {lit(vals[1])},", f"    {lit(vals[2])}", ")"]
            c = {"table": T, "name": e["level_name"] + suffix, "type": typ, "dax": lines}
            if suffix: c["hidden"] = True
            else: c["sortBy"] = e["level_name"] + " Order"
            cols.append(c)
        steps.append(("engagement", e))
    def apply(fc, fe):
        fc = fc.copy()
        for kind, s in steps:
            if kind == "band":
                x = fc[s["source"]]; lab = np.select([x < e_ for e_ in s["edges"]], s["labels"][:-1], default=s["labels"][-1]).astype(object)
                fc[s["name"]] = np.where(x.isna(), s["unknown"], lab)
            elif kind == "tenure": fc[s["name"]] = s["prefix"] + fc[s["source"]].astype(str)
            else:
                g = fe.groupby(["Customer ID", "Event"]).size().unstack(fill_value=0).reindex(fc["Customer ID"], fill_value=0)
                for nm, ev in (("received", "offer received"), ("viewed", "offer viewed"), ("completed", "offer completed")): fc[s[nm]] = g[ev].values if ev in g else 0
                c_, v_, r_ = fc[s["completed"]], fc[s["viewed"]], fc[s["received"]]
                fc[s["tier_name"]] = np.select([c_ >= s["heavy_min"], c_ >= s["light_min"], v_ >= 1, r_ >= 1], ["Heavy completer", "Light completer", "Viewer only", "Ignored"], default="Not reached")
                fc[s["level_name"]] = np.select([c_ >= s["heavy_min"], c_ >= s["light_min"]], ["High", "Medium"], default="Low")
        return fc
    return cols, apply

def hide_columns(defdir, hidden):
    for h in hidden:
        p = os.path.join(defdir, "tables", f"{h['table']}.tmdl"); s = open(p, encoding="utf-8").read()
        line = next((cand for cand in (f"\tcolumn '{h['column']}'\n", f"\tcolumn {h['column']}\n") if cand in s), None)   # transform stage always quotes names
        assert line, f"column {h}"
        w(p, s.replace(line, line + "\t\tisHidden\n", 1))

def add_measures(defdir, measures, table="Key Measures"):
    # Desktop 2.156 refused to open the project when this table was named plain "Measures" ("Unsupported Table name"), so the name is configurable.
    L = [f"table {qn(table)}", ""]
    for m in measures:
        if m.get("description"): L.append(f"\t/// {m['description']}")
        if len(m["dax"]) == 1: L.append(f"\tmeasure {qn(m['name'])} = {m['dax'][0]}")
        else: L += [f"\tmeasure {qn(m['name'])} =", dax_block(m["dax"], 3)]
        L += [f"\t\tformatString: {m['format']}", f"\t\tdisplayFolder: {m['folder']}", ""]
    L += ["\tcolumn Value", "\t\tisHidden", "\t\tdataType: int64", "\t\tsourceColumn: [Value]", "\t\tsummarizeBy: none", "",
          f"\tpartition {qn(table)} = calculated", "\t\tmode: import", "\t\tsource = {1}", ""]
    w(os.path.join(defdir, "tables", f"{table}.tmdl"), "\n".join(L))

def update_model_file(defdir, extra_tables):
    p = os.path.join(defdir, "model.tmdl"); s = open(p, encoding="utf-8").read()
    s = s.replace("\tsourceQueryCulture: en-US\n", "\tsourceQueryCulture: en-US\n\tdiscourageImplicitMeasures\n\tannotation __PBI_TimeIntelligenceEnabled = 0\n", 1)
    s = s.rstrip("\n") + "\n" + "".join(f"ref table {qn(t)}\n" for t in extra_tables)
    w(p, s)

# ------------------------------------------------------------------ expected values (pandas, independent of the DAX)
def load_replica(rdir):
    fe = pd.read_csv(os.path.join(rdir, "FactEvents.csv"), dtype={"Offer ID": "object"})
    fc = pd.read_csv(os.path.join(rdir, "DimCustomer.csv")); fo = pd.read_csv(os.path.join(rdir, "DimOffer.csv")); fb = pd.read_csv(os.path.join(rdir, "OfferChannel.csv"))
    for d, cols in ((fe, ["Is Repeated Row"]), (fc, ["Profile Disclosed"]), (fo, ["Is Informational"])):
        for c in cols: d[c] = d[c].astype(str).str.lower().eq("true")
    return fe, fc, fo, fb

def expected_checks(rdir, segs=None, apply_segs=None, seed=42, sample_n=100):
    fe, fc, fo, fb = load_replica(rdir)
    if apply_segs: fc = apply_segs(fc, fe)
    ev = fe.merge(fo[["Offer ID", "Offer Type", "Is Informational"]], on="Offer ID", how="left").merge(fc, on="Customer ID", how="left")
    S = lambda d: int((d.Event == "offer received").sum()); V = lambda d: int((d.Event == "offer viewed").sum()); C = lambda d: int((d.Event == "offer completed").sum())
    redeem = lambda d: C(d[d["Is Informational"] == False]) / S(d[d["Is Informational"] == False])
    txn = fe[fe.Event == "transaction"]
    engaged = set(fe[fe.Event.isin(["offer viewed", "offer completed"])]["Customer ID"])
    fch = fe[fe.Event == "offer completed"].groupby("Customer ID")["Hours Since Start"].min().rename("fch")
    t2 = txn.merge(fch, left_on="Customer ID", right_index=True, how="left")
    before = t2[t2.fch.notna() & (t2["Hours Since Start"] < t2.fch)]; after = t2[t2.fch.notna() & (t2["Hours Since Start"] > t2.fch)]
    X = []
    def add(name, dax, val, tol=0.011): X.append({"name": name, "dax": dax, "expected": float(val), "tol": tol})
    add("Total Customers", "[Total Customers]", len(fc))
    add("Offers Sent", "[Offers Sent]", S(fe)); add("Offers Viewed", "[Offers Viewed]", V(fe)); add("Offers Completed", "[Offers Completed]", C(fe))
    add("Redeemable Offers Sent", "[Redeemable Offers Sent]", S(ev[ev["Is Informational"] == False]))
    add("Repeated Completion Rows", "[Repeated Completion Rows]", int(((fe.Event == "offer completed") & fe["Is Repeated Row"]).sum()))
    add("Customers Who Completed", "[Customers Who Completed]", len(fch))
    add("View Rate", "[View Rate]", V(fe) / S(fe), 1e-9)
    add("Redemption Rate", "[Redemption Rate]", redeem(ev), 1e-9)
    add("Transactions", "[Transactions]", len(txn)); add("Total Spend", "[Total Spend]", round(float(txn.Amount.sum()), 2))
    add("Average Transaction Amount", "[Average Transaction Amount]", txn.Amount.sum() / len(txn), 1e-9)
    add("Customers Who Transacted", "[Customers Who Transacted]", txn["Customer ID"].nunique())
    add("Transactions per Customer", "[Transactions per Customer]", len(txn) / txn["Customer ID"].nunique(), 1e-9)
    add("Rewards Paid", "[Rewards Paid]", float(fe.Reward.sum()))
    add("Funnel Transactions (viewed or completed customers)", "[Funnel Transactions]", int(txn["Customer ID"].isin(engaged).sum()))
    add("Transactions Before First Completion", "[Transactions Before First Completion]", len(before))
    add("Transactions After First Completion", "[Transactions After First Completion]", len(after))
    add("Spend Before First Completion", "[Spend Before First Completion]", round(float(before.Amount.sum()), 2))
    add("Spend After First Completion", "[Spend After First Completion]", round(float(after.Amount.sum()), 2))
    add("Average Amount Before Completion", "[Average Amount Before Completion]", before.Amount.sum() / len(before), 1e-9)
    add("Average Amount After Completion", "[Average Amount After Completion]", after.Amount.sum() / len(after), 1e-9)
    for ot in sorted(fo["Offer Type"].unique()):
        d = ev[ev["Offer Type"] == ot]
        add(f"Offers Sent, {ot} offers", f'CALCULATE([Offers Sent], DimOffer[Offer Type] = "{ot}")', S(d))
        if ot != "Informational": add(f"Redemption Rate, {ot} offers", f'CALCULATE([Redemption Rate], DimOffer[Offer Type] = "{ot}")', redeem(d), 1e-9)
    for ch in sorted(fb.Channel.unique()):
        ids = set(fb[fb.Channel == ch]["Offer ID"]); d = ev[ev["Offer ID"].isin(ids)]
        add(f"Offers Sent, channel {ch}", f'CALCULATE([Offers Sent], OfferChannel[Channel] = "{ch}")', S(d))
        add(f"Redemption Rate, channel {ch}", f'CALCULATE([Redemption Rate], OfferChannel[Channel] = "{ch}")', redeem(d), 1e-9)
    for g in ("Female", "Male", "Other", "Not disclosed"):
        d = ev[ev.Gender == g]
        add(f"Redemption Rate, gender {g}", f'CALCULATE([Redemption Rate], DimCustomer[Gender] = "{g}")', redeem(d), 1e-9)
    add("Offers Sent on observation day 0", "CALCULATE([Offers Sent], DimObservationDay[Observation Day] = 0)", S(fe[fe["Observation Day"] == 0]))
    add("Transactions in week 2", 'CALCULATE([Transactions], DimObservationDay[Week Number] = 2)', int((txn["Observation Day"].between(7, 13)).sum()))
    add("Observation days in time table", "COUNTROWS(DimObservationDay)", 30)
    for step, val in (("1 Offers received", S(fe)), ("2 Offers viewed", V(fe)), ("3 Offers completed", C(fe)),
                      ("4 Purchases (viewed or completed)", int(txn["Customer ID"].isin(engaged).sum()))):
        add(f"Funnel Value, {step}", f'CALCULATE([Funnel Value], FunnelSteps[Step] = "{step}")', val)
    # segmentation (G-01, G-02): every customer in exactly one group per dimension, and each group's size and redemption
    seg_tables = []
    if segs:
        dims = [b["name"] for b in segs.get("bands", [])] + ([segs["tenure"]["name"]] if "tenure" in segs else []) + \
               ([segs["engagement"]["tier_name"], segs["engagement"]["level_name"]] if "engagement" in segs else [])
        overall = redeem(ev)
        for dim in dims:
            add(f"Customers with no {dim}", f"COUNTROWS(FILTER(DimCustomer, ISBLANK(DimCustomer[{dim}]))) + 0", 0)
            add(f"Customer counts across {dim} add up", f"SUMX(VALUES(DimCustomer[{dim}]), [Total Customers])", len(fc))
            add(f"Customer shares across {dim} add up to 100%", f"SUMX(VALUES(DimCustomer[{dim}]), [Share of Customers])", 1.0, 1e-9)
            for lab in sorted(fc[dim].unique(), key=str):
                d = ev[ev[dim] == lab]; n = int((fc[dim] == lab).sum()); flt = f'DimCustomer[{dim}] = "{lab}"'
                add(f"Customers, {dim} = {lab}", f"CALCULATE([Total Customers], {flt})", n)
                add(f"Share of customers, {dim} = {lab}", f"CALCULATE([Share of Customers], {flt})", n / len(fc), 1e-9)
                if S(d): add(f"View Rate, {dim} = {lab}", f"CALCULATE([View Rate], {flt})", V(d) / S(d), 1e-9)
                if S(d[d["Is Informational"] == False]):
                    add(f"Redemption Rate, {dim} = {lab}", f"CALCULATE([Redemption Rate], {flt})", redeem(d), 1e-9)
                    add(f"Redemption vs all customers, {dim} = {lab}", f"CALCULATE([Redemption Rate vs All Customers], {flt})", redeem(d) - overall, 1e-9)
        if len(segs.get("bands", [])) >= 2:
            a, b = segs["bands"][0]["name"], segs["bands"][1]["name"]
            cnt, red = {}, {}
            for (x, y), grp in fc.groupby([a, b]): cnt[f"{x}|{y}"] = [len(grp)]
            for (x, y), grp in ev.groupby([a, b]):
                nn = S(grp[grp["Is Informational"] == False]); red[f"{x}|{y}"] = [redeem(grp) if nn else 0.0]
            base = f"EVALUATE SUMMARIZECOLUMNS(DimCustomer[{a}], DimCustomer[{b}], "
            seg_tables.append({"name": f"Heatmap cells {a} x {b}: customers", "dax": base + '"Customers", [Total Customers])', "columns": ["Customers"], "key_cols": 2, "expected": cnt, "tol": 0.011})
            seg_tables.append({"name": f"Heatmap cells {a} x {b}: redemption rate", "dax": base + '"Redemption", [Redemption Rate])', "columns": ["Redemption"], "key_cols": 2, "expected": red, "tol": 1e-6})
    # offer performance page: per offer, per reward, and offer difficulty
    fo2 = fo.assign(**{"Reward Label": "$" + fo["Reward Amount"].astype(str)})
    ev2 = ev.merge(fo2[["Offer ID", "Offer Label", "Reward Label"]], on="Offer ID", how="left")
    for lab in sorted(fo2["Offer Label"].unique()):
        d = ev2[ev2["Offer Label"] == lab]
        add(f"Offers Sent, offer {lab}", f'CALCULATE([Offers Sent], DimOffer[Offer Label] = "{lab}")', S(d))
        if S(d[d["Is Informational"] == False]): add(f"Redemption Rate, offer {lab}", f'CALCULATE([Redemption Rate], DimOffer[Offer Label] = "{lab}")', redeem(d), 1e-9)
    for rl in sorted(fo2["Reward Label"].unique()):
        d = ev2[ev2["Reward Label"] == rl]
        if S(d[d["Is Informational"] == False]): add(f"Redemption Rate, reward {rl}", f'CALCULATE([Redemption Rate], DimOffer[Reward Label] = "{rl}")', redeem(d), 1e-9)
    for ot in sorted(fo2["Offer Type"].unique()):
        add(f"Minimum spend, {ot} offers", f'CALCULATE([Minimum Spend of Selected Offers], DimOffer[Offer Type] = "{ot}")', float(fo2[fo2["Offer Type"] == ot]["Minimum Spend"].mean()), 1e-9)
    # transaction behaviour page: customers who completed at least one offer against those who never did
    grp = {"Completed at least one offer": set(fch.index), "Never completed an offer": set(fc["Customer ID"]) - set(fch.index)}
    for gname, ids_ in grp.items():
        gt = txn[txn["Customer ID"].isin(ids_)]; flt = f'DimCustomer[Offer Completion Group] = "{gname}"'
        add(f"Customers, {gname}", f"CALCULATE([Total Customers], {flt})", len(ids_))
        add(f"Average Transaction Amount, {gname}", f"CALCULATE([Average Transaction Amount], {flt})", gt.Amount.sum() / len(gt), 1e-9)
        add(f"Daily Transactions per Customer overall, {gname}", f"CALCULATE([Daily Transactions per Customer], {flt})", len(gt) / len(ids_), 1e-9)
        for day in (0, 10, 20):
            gd = gt[gt["Observation Day"] == day]
            if len(gd):
                dflt = f"{flt}, DimObservationDay[Observation Day] = {day}"
                add(f"Average Transaction Amount, {gname}, day {day}", f"CALCULATE([Average Transaction Amount], {dflt})", gd.Amount.sum() / len(gd), 1e-9)
                add(f"Daily Transactions per Customer, {gname}, day {day}", f"CALCULATE([Daily Transactions per Customer], {dflt})", len(gd) / len(ids_), 1e-9)
    # model integrity (M-05)
    add("Events with no matching customer", "COUNTROWS(FILTER(FactEvents, ISBLANK(RELATED(DimCustomer[Customer ID])))) + 0", 0)
    add("Offer events with no matching offer", 'COUNTROWS(FILTER(FactEvents, NOT ISBLANK(FactEvents[Offer ID]) && ISBLANK(RELATED(DimOffer[Offer ID])))) + 0', 0)
    add("Events with no matching observation day", "COUNTROWS(FILTER(FactEvents, ISBLANK(RELATED(DimObservationDay[Observation Day])))) + 0", 0)
    add("Offers with no channel", "COUNTROWS(FILTER(DimOffer, ISEMPTY(RELATEDTABLE(OfferChannel)))) + 0", 0)
    # 100-customer sample (Q-02 part): per-customer measures against pandas
    rng = np.random.RandomState(seed); ids = sorted(rng.choice(fc["Customer ID"].values, size=sample_n, replace=False).tolist())
    g = fe[fe["Customer ID"].isin(ids)]
    exp = {}
    for cid in ids:
        d = g[g["Customer ID"] == cid]; t = d[d.Event == "transaction"]
        exp[cid] = [S(d), V(d), C(d), len(t), round(float(t.Amount.sum()), 2)]
    idlist = ", ".join('"' + i + '"' for i in ids)
    table = {"name": f"{sample_n} seeded customers (seed {seed}): sent, viewed, completed, transactions, spend",
             "dax": f'EVALUATE SUMMARIZECOLUMNS(FactEvents[Customer ID], TREATAS({{{idlist}}}, FactEvents[Customer ID]), "Sent", [Offers Sent], "Viewed", [Offers Viewed], "Completed", [Offers Completed], "Txn", [Transactions], "Spend", [Total Spend])',
             "columns": ["Sent", "Viewed", "Completed", "Transactions", "Spend"], "expected": exp}
    return X, [table] + seg_tables, ids

# ------------------------------------------------------------------ main
def main(cfg_path):
    cfg = json.load(open(cfg_path, encoding="utf-8")); cdir = os.path.dirname(os.path.abspath(cfg_path))
    eid = cfg["engagement"]["id"]; proj = cfg["engagement"]["project"]
    base = os.path.normpath(os.path.join(cdir, "..", "outputs", eid)); src = os.path.join(base, "transform", "pbip"); out = os.path.join(base, cfg.get("output_dir", "model"))
    os.makedirs(out, exist_ok=True); dst = os.path.join(out, "pbip")      # only the generated project is replaced; result notes and check records stay
    if os.path.isdir(dst): shutil.rmtree(dst)
    shutil.copytree(src, dst)
    defdir = os.path.join(dst, f"{proj}.SemanticModel", "definition")
    add_relationships(defdir, cfg["relationships"]); add_calculated_tables(defdir, cfg["calculated_tables"])
    seg_cols, apply_segs = build_segments(cfg.get("segments", {}))
    add_calculated_columns(defdir, cfg["calculated_columns"] + seg_cols); hide_columns(defdir, cfg["hidden_columns"]); mt = cfg.get("measures_table", "Key Measures"); add_measures(defdir, cfg["measures"], mt)
    update_model_file(defdir, [t["name"] for t in cfg["calculated_tables"]] + [mt])
    # measure dictionary
    L = ["# Measure dictionary", "", f"{len(cfg['measures'])} measures, all in the Measures table.", ""]
    for folder in sorted({m["folder"] for m in cfg["measures"]}):
        L += [f"## {folder}", ""]
        for m in [m for m in cfg["measures"] if m["folder"] == folder]:
            L += [f"### {m['name']}", m.get("description", ""), "", "```dax", "\n".join(m["dax"]), "```", ""]
    L += ["## Relationships", ""] + [f"- {r['from']} -> {r['to']}{' (filters both ways)' if r.get('both') else ''}: {r.get('note', '')}" for r in cfg["relationships"]]
    w(os.path.join(out, "measure_dictionary.md"), "\n".join(L) + "\n")
    X, tables, ids = expected_checks(os.path.join(base, "transform", "replica"), cfg.get("segments"), apply_segs)
    n_hidden = len(cfg["hidden_columns"]) + 1 + sum(1 for c in cfg["calculated_columns"] + seg_cols if c.get("hidden"))   # +1: the Measures table's own column
    dmv = [{"name": "Relationships in the model", "query": "SELECT [ID] FROM $SYSTEM.TMSCHEMA_RELATIONSHIPS", "expected_rows": len(cfg["relationships"])},
           {"name": "Relationships that filter both ways", "query": "SELECT [ID] FROM $SYSTEM.TMSCHEMA_RELATIONSHIPS WHERE [CrossFilteringBehavior] = 2", "expected_rows": sum(1 for r in cfg["relationships"] if r.get("both"))},
           {"name": "Measures in the model", "query": "SELECT [ID] FROM $SYSTEM.TMSCHEMA_MEASURES", "expected_rows": len(cfg["measures"])},
           {"name": "Hidden columns", "query": "SELECT [IsHidden], [Type] FROM $SYSTEM.TMSCHEMA_COLUMNS", "filter": {"IsHidden": True}, "not_equal": {"Type": 3}, "expected_rows": n_hidden}]
    json.dump({"scalar": X, "table": tables, "dmv": dmv}, open(os.path.join(out, "expected_model_checks.json"), "w"), indent=1)
    json.dump({"sample_customer_ids": ids}, open(os.path.join(out, "sample_customers.json"), "w"), indent=1)
    print(f"model project: {os.path.join(dst, proj + '.pbip')}\n  relationships {len(cfg['relationships'])}, measures {len(cfg['measures'])}, expected scalar checks {len(X)}, sample customers {len(ids)}")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
