"""Transform agent (stories T-01 to T-05).

From a config (table specs), the profile findings and the customer's decisions it writes:
  queries/*.m                 Power Query (M) for every staging and model query           (T-01 to T-04)
  transform_plan.json/.md     every step in words, with the decision or issue behind it   (documentation)
  replica/*.csv               independent pandas replica of every model table             (T-05)
  expected_checks.json        counts and sums the replica produces (used against Power BI)
  transform_gate.json         replica vs reference totals from the raw files              (T-05 gate)
  pbip/RewardsNext.*          a Power BI project holding the queries as tables            (loads in Desktop)

Every step type is defined once with both its M code and its pandas equivalent, so the two are written side by side.
Usage: python transform_agent.py <config.json>
"""
import ast, json, os, re, shutil, sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "profiling"))
import profile_agent as pa

SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item"
M_TYPE = {"text": "type text", "int": "Int64.Type", "number": "type number", "date": "type date", "logical": "type logical"}
TMDL_TYPE = {"text": "string", "int": "int64", "number": "double", "date": "dateTime", "logical": "boolean"}
TMDL_FMT = {"int": "0", "number": "#,0.00", "date": "Long Date"}

def q(s): return '"' + str(s).replace('"', '""') + '"'          # M string literal
def col(c): return "[" + c + "]"                                  # M column reference

# ------------------------------------------------------------------ step types: (M code, pandas function, description)
def step_index(s):
    n = s["name"]
    return ((lambda p: f'Table.AddIndexColumn({p}, {q(n)}, 1, 1, Int64.Type)'),
            (lambda df: df.assign(**{n: np.arange(1, len(df) + 1)})), f"Add a row number '{n}' in file order.")

def step_date_yyyymmdd(s):
    f, n = s["from"], s["name"]
    return ((lambda p: f'Table.AddColumn({p}, {q(n)}, each try Date.FromText(Text.From({col(f)}), [Format = "yyyyMMdd", Culture = "en-US"]) otherwise null, type date)'),
            (lambda df: df.assign(**{n: pd.to_datetime(df[f].astype("Int64").astype(str), format="%Y%m%d", errors="coerce").dt.normalize()})),
            f"Convert '{f}' (YYYYMMDD number) to a date column '{n}'.")

def step_year(s):
    f, n = s["from"], s["name"]
    return ((lambda p: f'Table.AddColumn({p}, {q(n)}, each Date.Year({col(f)}), Int64.Type)'),
            (lambda df: df.assign(**{n: df[f].dt.year.astype("Int64")})), f"Take the year of '{f}' as '{n}'.")

def step_null_if_equals(s):
    f, v, n = s["from"], s["value"], s["name"]
    return ((lambda p: f'Table.AddColumn({p}, {q(n)}, each if {col(f)} = {json.dumps(v)} then null else {col(f)}, Int64.Type)'),
            (lambda df: df.assign(**{n: df[f].where(df[f] != v).astype("Int64")})), f"Treat {v} in '{f}' as unknown (blank), stored in '{n}'.")

def step_flag(s):
    f, v, n, op = s["from"], s["value"], s["name"], s["op"]
    m_op = "=" if op == "equals" else "<>"
    return ((lambda p: f'Table.AddColumn({p}, {q(n)}, each {col(f)} {m_op} {json.dumps(v)}, type logical)'),
            (lambda df: df.assign(**{n: (df[f] == v) if op == "equals" else (df[f] != v)})), f"Flag '{n}': '{f}' {op.replace('_', ' ')} {v}.")

def step_map_labels(s):
    f, n, mp, nl = s["from"], s["name"], s["mapping"], s["null_label"]
    keys = "{" + ", ".join(q(k) for k in mp) + "}"; vals = "{" + ", ".join(q(v) for v in mp.values()) + "}"
    return ((lambda p: f'Table.AddColumn({p}, {q(n)}, each let v = {col(f)} in if v = null or v = "" then {q(nl)} else Record.FieldOrDefault(Record.FromList({vals}, {keys}), v, v), type text)'),
            (lambda df: df.assign(**{n: df[f].apply(lambda v: nl if (pd.isna(v) or str(v) == "") else mp.get(v, v))})),
            f"Label '{f}' as {mp}; blanks become '{nl}' (no imputation).")

def step_int_divide(s):
    f, by, n = s["from"], s["by"], s["name"]
    return ((lambda p: f'Table.AddColumn({p}, {q(n)}, each Number.IntegerDivide({col(f)}, {by}), Int64.Type)'),
            (lambda df: df.assign(**{n: (df[f] // by).astype("Int64")})), f"'{n}' = '{f}' divided by {by}, rounded down.")

def step_count_list(s):
    f, n = s["from"], s["name"]
    return ((lambda p: f'Table.AddColumn({p}, {q(n)}, each List.Count(Json.Document(Text.Replace({col(f)}, "\'", """"))), Int64.Type)'),
            (lambda df: df.assign(**{n: df[f].apply(lambda x: len(ast.literal_eval(x))).astype("Int64")})), f"Count the items in the list in '{f}' as '{n}'.")

def step_label(s):
    n, tpl = s["name"], s["template"]
    parts = re.split(r"(\{[^}]+\})", tpl); mexpr = []
    for p_ in parts:
        if not p_: continue
        if p_.startswith("{"): mexpr.append(f'Text.From({col(p_[1:-1])})')
        else: mexpr.append(q(p_))
    return ((lambda p: f'Table.AddColumn({p}, {q(n)}, each {" & ".join(mexpr)}, type text)'),
            (lambda df: df.assign(**{n: df.apply(lambda r: tpl.format(**{k: (r[k] if not isinstance(r[k], (float, np.floating)) or r[k] != int(r[k]) else int(r[k])) for k in re.findall(r"\{([^}]+)\}", tpl)}), axis=1)})),
            f"Build the label '{n}' from {re.findall(r'{([^}]+)}', tpl)}.")

def step_parse_fields(s):
    f, fields = s["from"], s["fields"]
    def pandas_fn(df):
        objs = df[f].apply(pa.parse_struct).apply(lambda t: t[0])
        for fld in fields:
            def get(o, keys=fld["keys"]):
                for k in keys:
                    if isinstance(o, dict) and k in o: return o[k]
                return None
            vals = objs.apply(get)
            df = df.assign(**{fld["name"]: (pd.to_numeric(vals) if fld["type"] == "number" else vals.astype("object"))})
        return df
    return ("PARSE", (fields, f), pandas_fn, f"Parse the fields inside '{f}' (single quotes normalised to JSON): " + ", ".join(f"{x['name']} from {x['keys']}" for x in fields) + ".")

def step_repeat_flag(s):
    n, keys, idc = s["name"], s["keys"], s["id_col"]
    return ("REPEAT", (n, keys, idc), (lambda df: df.assign(**{n: df.duplicated(keys, keep="first")})),
            f"Flag '{n}': true for the second and later rows with identical {keys}.")

def step_null_if_in(s):
    f, vals, n = s["from"], s["values"], s["name"]
    lits = "{" + ", ".join(q(v) for v in vals) + "}"
    return ((lambda p: f'Table.AddColumn({p}, {q(n)}, each if List.Contains({lits}, {col(f)}) then null else {col(f)}, type text)'),
            (lambda df: df.assign(**{n: df[f].where(~df[f].astype(str).isin(vals))})), f"Treat {vals} in '{f}' as unknown (blank), stored in '{n}'.")

def step_dedupe(s):
    keys = s.get("keys")
    if keys:
        return ("DEDUPE", keys, (lambda df: df.drop_duplicates(subset=keys, keep="first").reset_index(drop=True)), f"Remove rows that repeat an earlier row's {keys}.")
    return ("DEDUPE", None, (lambda df: df.drop_duplicates(keep="first").reset_index(drop=True)), "Remove rows that exactly repeat an earlier row.")

def step_expand_list(s):
    f, n = s["from"], s["name"]
    def pandas_fn(df):
        rows = []
        for _, r in df.iterrows():
            for it in ast.literal_eval(r[f]): rows.append({**r.to_dict(), n: str(it).strip().title()})
        return pd.DataFrame(rows)
    return ((lambda p: f'Table.TransformColumns(Table.ExpandListColumn(Table.AddColumn({p}, {q(n)}, each Json.Document(Text.Replace({col(f)}, "\'", """"))), {q(n)}), {{{{{q(n)}, each Text.Proper(Text.Trim(_)), type text}}}})'),
            pandas_fn, f"Split the list in '{f}' into one row per item '{n}' (trimmed, first letter capital).")

def step_null_label(s):
    f, lab = s["from"], s["label"]
    return ((lambda p: f'Table.TransformColumns({p}, {{{{{q(f)}, each if _ = null or _ = "" then {q(lab)} else _, type text}}}})'),
            (lambda df: df.assign(**{f: df[f].where(df[f].notna() & (df[f].astype(str) != ""), lab)})), f"Blank '{f}' becomes '{lab}'.")

STEPS = {"index": step_index, "date_yyyymmdd": step_date_yyyymmdd, "year": step_year, "null_if_equals": step_null_if_equals, "flag": step_flag,
         "map_labels": step_map_labels, "int_divide": step_int_divide, "count_list": step_count_list, "label": step_label,
         "parse_fields": step_parse_fields, "repeat_flag": step_repeat_flag, "expand_list": step_expand_list, "null_label": step_null_label,
         "null_if_in": step_null_if_in, "dedupe": step_dedupe}

# ------------------------------------------------------------------ staging
def staging_m(sid, df_profile, info):
    cols = df_profile["columns"]
    def mt(c):
        d = cols[c]["dtype"]
        return "Int64.Type" if d.startswith("int") else ("type number" if d.startswith("float") else "type text")
    types = ", ".join(f'{{{q(c)}, {mt(c)}}}' for c in cols)
    return (f'let\n    Source = Csv.Document(File.Contents(SourceFolder & "\\{os.path.basename(info["path"])}"), [Delimiter = {q(info.get("delimiter", ","))}, Columns = {len(cols)}, Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),\n'
            f'    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),\n    Typed = Table.TransformColumnTypes(Promoted, {{{types}}}, "en-US")\nin\n    Typed')

# ------------------------------------------------------------------ build tables
def build_table(tspec, stg_df):
    """Return (M text, pandas DataFrame, step descriptions)."""
    steps = [STEPS[s["type"]](s) for s in tspec["steps"]]
    lines, prev, n, desc = [f'    Source = Stg_{tspec["source"]}'], "Source", 0, []
    df = stg_df.copy()
    for spec, st in zip(tspec["steps"], steps):
        n += 1; name = f"Step{n}"
        if st[0] == "PARSE":
            fields, f = st[1]
            lines.append(f'    {name}a = Table.AddColumn({prev}, "_v", each Json.Document(Text.Replace({col(f)}, "\'", """")))')
            cur = f"{name}a"
            for i, fld in enumerate(fields):
                keys = fld["keys"]; expr = "null"
                for k in reversed(keys): expr = f'Record.FieldOrDefault([_v], {q(k)}, {expr})'
                lines.append(f'    {name}b{i} = Table.AddColumn({cur}, {q(fld["name"])}, each {expr}, {M_TYPE[fld["type"]]})'); cur = f"{name}b{i}"
            lines.append(f'    {name} = Table.RemoveColumns({cur}, {{"_v"}})'); prev = name; df = st[2](df); desc.append(st[3])
        elif st[0] == "REPEAT":
            nm, keys, idc = st[1]
            kexpr = " & \"|\" & ".join(f'(if {col(k)} = null then "" else Text.From({col(k)}))' for k in keys)
            lines += [f'    {name}k = Table.AddColumn({prev}, "_k", each {kexpr}, type text)',
                      f'    {name}g = Table.Group({name}k, {{"_k"}}, {{{{"_first", each List.Min({col(idc)}), Int64.Type}}}})',
                      f'    {name}j = Table.NestedJoin({name}k, {{"_k"}}, {name}g, {{"_k"}}, "_f", JoinKind.LeftOuter)',
                      f'    {name}e = Table.ExpandTableColumn({name}j, "_f", {{"_first"}})',
                      f'    {name}f = Table.AddColumn({name}e, {q(nm)}, each {col(idc)} <> [_first], type logical)',
                      f'    {name} = Table.RemoveColumns({name}f, {{"_k", "_first"}})']
            prev = name; df = st[2](df); desc.append(st[3])
        elif st[0] == "DEDUPE":
            keys = st[1]
            if keys: lines.append(f'    {name} = Table.Distinct({prev}, {{{", ".join(q(k) for k in keys)}}})')
            else: lines.append(f'    {name} = Table.Distinct({prev})')
            prev = name; df = st[2](df); desc.append(st[3])
        else:
            mfn, pfn, d = st
            lines.append(f'    {name} = {mfn(prev)}'); prev = name; df = pfn(df); desc.append(d)
    sel = tspec["select"]
    raw = [c["from"] if "from" in c else c["name"] for c in sel]
    lines.append(f'    Selected = Table.SelectColumns({prev}, {{{", ".join(q(r) for r in raw)}}})')
    ren = [(c["from"], c["name"]) for c in sel if "from" in c and c["from"] != c["name"]]
    cur = "Selected"
    if ren:
        lines.append(f'    Renamed = Table.RenameColumns(Selected, {{{", ".join("{" + q(a) + ", " + q(b) + "}" for a, b in ren)}}})'); cur = "Renamed"
    lines.append(f'    Typed = Table.TransformColumnTypes({cur}, {{{", ".join("{" + q(c["name"]) + ", " + M_TYPE[c["type"]] + "}" for c in sel)}}}, "en-US")')
    m = "let\n" + ",\n".join(lines) + "\nin\n    Typed"
    out = df[raw].rename(columns=dict(ren)).reset_index(drop=True)
    for c in sel:
        t = c["type"]
        if t == "int": out[c["name"]] = out[c["name"]].astype("Int64")
        elif t == "number": out[c["name"]] = pd.to_numeric(out[c["name"]])
        elif t == "logical": out[c["name"]] = out[c["name"]].astype(bool)
        elif t == "date": out[c["name"]] = pd.to_datetime(out[c["name"]])
        else: out[c["name"]] = out[c["name"]].astype("object")
    return m, out, desc

# ------------------------------------------------------------------ TMDL / PBIP
def w(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f: f.write(text)

def indent(m, n): return "\n".join(("\t" * n + ln) if ln else ln for ln in m.split("\n"))

def emit_pbip(out, project, tables, expressions, source_folder):
    root = os.path.join(out, "pbip")
    if os.path.isdir(root): shutil.rmtree(root)
    sm = os.path.join(root, f"{project}.SemanticModel"); rp = os.path.join(root, f"{project}.Report")
    j = lambda p, o: w(p, json.dumps(o, indent=2))
    j(os.path.join(root, f"{project}.pbip"), {"version": "1.0", "artifacts": [{"report": {"path": f"{project}.Report"}}], "settings": {"enableAutoRecovery": True}})
    j(os.path.join(sm, "definition.pbism"), {"$schema": f"{SCHEMA}/semanticModel/definitionProperties/1.0.0/schema.json", "version": "4.0", "settings": {}})
    w(os.path.join(sm, "definition", "database.tmdl"), "database\n\tcompatibilityLevel: 1600\n")
    refs = "".join(f"ref expression {n}\n" for n in expressions) + "\n" + "".join(f"ref table {t['name']}\n" for t in tables)
    w(os.path.join(sm, "definition", "model.tmdl"), "model Model\n\tculture: en-US\n\tdefaultPowerBIDataSourceVersion: powerBI_V3\n\tsourceQueryCulture: en-US\n\n" + refs)
    ex = [f'expression SourceFolder = {q(source_folder)} meta [IsParameterQuery = true, Type = "Text", IsParameterQueryRequired = true]\n\tannotation PBI_ResultType = Text\n']
    for n, m in expressions.items():
        if n == "SourceFolder": continue
        ex.append(f"expression {n} =\n{indent(m, 2)}\n\tannotation PBI_ResultType = Table\n")
    w(os.path.join(sm, "definition", "expressions.tmdl"), "\n".join(ex))
    for t in tables:
        L = [f"table {t['name']}", ""]
        for c in t["columns"]:
            L += [f"\tcolumn '{c['name']}'", f"\t\tdataType: {TMDL_TYPE[c['type']]}"]
            if c["type"] in TMDL_FMT: L.append(f"\t\tformatString: {TMDL_FMT[c['type']]}")
            L += [f"\t\tsourceColumn: {c['name']}", f"\t\tsummarizeBy: {'sum' if c.get('sum') else 'none'}", ""]
        L += [f"\tpartition {t['name']} = m", "\t\tmode: import", "\t\tsource =", indent(t["m"], 4), ""]
        w(os.path.join(sm, "definition", "tables", f"{t['name']}.tmdl"), "\n".join(L))
    j(os.path.join(rp, "definition.pbir"), {"$schema": f"{SCHEMA}/report/definitionProperties/2.0.0/schema.json", "version": "4.0", "datasetReference": {"byPath": {"path": f"../{project}.SemanticModel"}}})
    d = os.path.join(rp, "definition")
    j(os.path.join(d, "version.json"), {"$schema": f"{SCHEMA}/report/definition/versionMetadata/1.0.0/schema.json", "version": "2.0.0"})
    j(os.path.join(d, "report.json"), {"$schema": f"{SCHEMA}/report/definition/report/3.1.0/schema.json", "themeCollection": {"baseTheme": {"name": "CY24SU10", "reportVersionAtImport": {"visual": "1.8.0", "report": "2.0.0", "page": "1.3.0"}, "type": "SharedResources"}}})
    j(os.path.join(d, "pages", "pages.json"), {"$schema": f"{SCHEMA}/report/definition/pagesMetadata/1.0.0/schema.json", "pageOrder": ["page01"], "activePageName": "page01"})
    j(os.path.join(d, "pages", "page01", "page.json"), {"$schema": f"{SCHEMA}/report/definition/page/2.0.0/schema.json", "name": "page01", "displayName": "Data check", "displayOption": "FitToPage", "height": 720, "width": 1280})
    return root

# ------------------------------------------------------------------ main
def main(cfg_path):
    cfg = json.load(open(cfg_path, encoding="utf-8"))
    cdir = os.path.dirname(os.path.abspath(cfg_path))
    root = os.path.normpath(os.path.join(cdir, cfg.get("data_root", ".")))
    eid = cfg["engagement"]["id"]; out = os.path.normpath(os.path.join(cdir, "..", "outputs", eid, "transform"))
    prof_dir = os.path.normpath(os.path.join(cdir, "..", "outputs", eid, "profile"))
    if os.path.isdir(out): shutil.rmtree(out)
    profile = json.load(open(os.path.join(prof_dir, "profile.json"), encoding="utf-8"))["sources"]
    ref = json.load(open(os.path.join(prof_dir, "reference_totals.json"), encoding="utf-8"))
    dec = json.load(open(os.path.join(prof_dir, "..", "decisions.json"), encoding="utf-8"))
    assert all(x.get("decision") for x in dec["profile_issue_decisions"]), "every profile decision must be recorded before transforming"
    stg = {}; expressions = {"SourceFolder": None}
    for s in cfg["sources"]:
        df, path, info = pa.load_source(s, root); stg[s["id"]] = df
        expressions[f"Stg_{s['id']}"] = staging_m(s["id"], profile[s["id"]], dict(info, path=path))
        w(os.path.join(out, "queries", f"Stg_{s['id']}.m"), expressions[f"Stg_{s['id']}"] + "\n")
    tables, plan, expected = [], [], {}
    for t in cfg["tables"]:
        m, df, desc = build_table(t, stg[t["source"]])
        w(os.path.join(out, "queries", f"{t['name']}.m"), m + "\n")
        os.makedirs(os.path.join(out, "replica"), exist_ok=True); df.to_csv(os.path.join(out, "replica", f"{t['name']}.csv"), index=False)
        tables.append({"name": t["name"], "m": m, "columns": [dict(c) for c in t["select"]]})
        plan.append({"table": t["name"], "source": t["source"], "role": t.get("role"), "rows": len(df), "steps": desc, "reason": t.get("reason", "")})
        expected[t["name"]] = df
    json.dump(plan, open(os.path.join(out, "transform_plan.json"), "w"), indent=2)
    md = ["# Transform plan", ""] + sum([[f"## {p['table']} ({p['role']}, from {p['source']}, {p['rows']:,} rows)", ""] + [f"{i + 1}. {d}" for i, d in enumerate(p["steps"])] + [""] for p in plan], [])
    w(os.path.join(out, "transform_plan.md"), "\n".join(md))
    # ---- expected checks (used against Power BI) and the T-05 gate (replica vs raw reference totals)
    E = {n: df for n, df in expected.items()}
    fe, fc, fo, fb, dd = E["FactEvents"], E["DimCustomer"], E["DimOffer"], E["OfferChannel"], E["DataDictionary"]
    checks = [("Rows in DimCustomer", "COUNTROWS(DimCustomer)", len(fc)), ("Rows in DimOffer", "COUNTROWS(DimOffer)", len(fo)),
              ("Rows in OfferChannel", "COUNTROWS(OfferChannel)", len(fb)), ("Rows in FactEvents", "COUNTROWS(FactEvents)", len(fe)),
              ("Rows in DataDictionary", "COUNTROWS(DataDictionary)", len(dd))]
    for ev, n in fe["Event"].value_counts().items(): checks.append((f"FactEvents rows: {ev}", f'COUNTROWS(FILTER(FactEvents, FactEvents[Event] = "{ev}"))', int(n)))
    checks += [("Sum of Amount", "SUM(FactEvents[Amount])", round(float(fe["Amount"].sum()), 2)), ("Sum of Reward", "SUM(FactEvents[Reward])", float(fe["Reward"].sum())),
               ("Repeated rows flagged", "COUNTROWS(FILTER(FactEvents, FactEvents[Is Repeated Row] = TRUE()))", int(fe["Is Repeated Row"].sum())),
               ("Offer ID blank on offer events", 'COUNTROWS(FILTER(FactEvents, FactEvents[Event] <> "transaction" && ISBLANK(FactEvents[Offer ID]))) + 0', int(((fe["Event"] != "transaction") & fe["Offer ID"].isna()).sum())),
               ("Amount blank on transactions", 'COUNTROWS(FILTER(FactEvents, FactEvents[Event] = "transaction" && ISBLANK(FactEvents[Amount]))) + 0', int(((fe["Event"] == "transaction") & fe["Amount"].isna()).sum())),
               ("Distinct Offer IDs in FactEvents", "DISTINCTCOUNTNOBLANK(FactEvents[Offer ID])", int(fe["Offer ID"].nunique())),
               ("Highest Observation Day", "MAX(FactEvents[Observation Day])", int(fe["Observation Day"].max())),
               ("Customers with age blank", "COUNTROWS(FILTER(DimCustomer, ISBLANK(DimCustomer[Age])))", int(fc["Age"].isna().sum())),
               ("Customers 'Not disclosed'", 'COUNTROWS(FILTER(DimCustomer, DimCustomer[Gender] = "Not disclosed"))', int((fc["Gender"] == "Not disclosed").sum())),
               ("Customers profile not disclosed", "COUNTROWS(FILTER(DimCustomer, DimCustomer[Profile Disclosed] = FALSE()))", int((~fc["Profile Disclosed"]).sum())),
               ("Sum of Income", "SUM(DimCustomer[Income])", float(fc["Income"].sum())),
               ("Sum of Age", "SUM(DimCustomer[Age])", int(fc["Age"].sum())),
               ("Earliest member date (as number)", "VALUE(MIN(DimCustomer[Member Since]))", float((fc["Member Since"].min() - pd.Timestamp("1899-12-30")).days)),
               ("Latest member date (as number)", "VALUE(MAX(DimCustomer[Member Since]))", float((fc["Member Since"].max() - pd.Timestamp("1899-12-30")).days)),
               ("Informational offers", "COUNTROWS(FILTER(DimOffer, DimOffer[Is Informational] = TRUE()))", int(fo["Is Informational"].sum())),
               ("Distinct offer labels", "DISTINCTCOUNT(DimOffer[Offer Label])", int(fo["Offer Label"].nunique())),
               ("Distinct channels", "DISTINCTCOUNT(OfferChannel[Channel])", int(fb["Channel"].nunique())),
               ("Data dictionary table-description rows", 'COUNTROWS(FILTER(DataDictionary, DataDictionary[Field] = "(table description)"))', int((dd["Field"] == "(table description)").sum()))]
    json.dump([{"name": n, "dax": d, "expected": e} for n, d, e in checks], open(os.path.join(out, "expected_checks.json"), "w"), indent=2)
    R = ref["sources"]; P = ref["parsed_numeric_fields"]
    gate = [("customers rows", len(fc), R["customers"]["rows"]), ("offers rows", len(fo), R["offers"]["rows"]), ("events rows (FactEvents)", len(fe), R["events"]["rows"]),
            ("data dictionary rows", len(dd), R["data_dictionary"]["rows"]),
            ("event count: transaction", int((fe["Event"] == "transaction").sum()), R["events"]["category_counts"]["event"]["transaction"]),
            ("event count: offer received", int((fe["Event"] == "offer received").sum()), R["events"]["category_counts"]["event"]["offer received"]),
            ("event count: offer viewed", int((fe["Event"] == "offer viewed").sum()), R["events"]["category_counts"]["event"]["offer viewed"]),
            ("event count: offer completed", int((fe["Event"] == "offer completed").sum()), R["events"]["category_counts"]["event"]["offer completed"]),
            ("parsed amounts: count", int(fe["Amount"].notna().sum()), P["events.value.amount"]["count"]), ("parsed amounts: sum", round(float(fe["Amount"].sum()), 2), round(P["events.value.amount"]["sum"], 2)),
            ("parsed rewards: count", int(fe["Reward"].notna().sum()), P["events.value.reward"]["count"]), ("parsed rewards: sum", float(fe["Reward"].sum()), P["events.value.reward"]["sum"]),
            ("customers with blank gender", int((fc["Gender"] == "Not disclosed").sum()), R["customers"]["nulls"]["gender"]), ("customers with blank income", int(fc["Income"].isna().sum()), R["customers"]["nulls"]["income"]),
            ("sum of income", float(fc["Income"].sum()), R["customers"]["sums"]["income"]),
            ("age placeholders (118) removed", int(fc["Age"].isna().sum()), int((stg["customers"]["age"] == 118).sum())),
            ("repeated rows flagged", int(fe["Is Repeated Row"].sum()), profile["events"]["duplicate_rows"]),
            ("channel rows (list items in offers)", len(fb), sum(len(ast.literal_eval(x)) for x in stg["offers"]["channels"]))]
    res = [{"check": n, "replica": a, "raw": b, "pass": bool(abs(float(a) - float(b)) < 0.01)} for n, a, b in gate]
    json.dump({"passed": all(r["pass"] for r in res), "checks": res}, open(os.path.join(out, "transform_gate.json"), "w"), indent=2)
    for r in res: print(("PASS " if r["pass"] else "FAIL ") + f"{r['check']}: replica {r['replica']} vs raw {r['raw']}")
    proj = cfg["engagement"].get("project", "RewardsNext")
    p = emit_pbip(out, proj, tables, {**{"SourceFolder": None}, **{k: v for k, v in expressions.items() if k != "SourceFolder"}}, root)
    print("gate passed:", all(r["pass"] for r in res), "| project:", os.path.join(p, proj + ".pbip"))
    return 0 if all(r["pass"] for r in res) else 1

if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
