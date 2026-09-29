"""Profiling agent (stories P-01 to P-04).

Reads the sources listed in a config file and writes, to <output>/:
  profile.json           per-source, per-column profile (P-01)
  issues.json            data issues with evidence, a proposed rule and options (P-02, P-03 input)
  decisions_template.json  one blank decision per issue that needs a person (P-03 input)
  reference_totals.json  counts and sums captured from the raw files, with file hashes (P-04)
  profile_report.md      readable summary

Usage: python profile_agent.py <config.json> [output_dir]
Nothing is changed in the source files. Checks are generic; dataset-specific meaning comes from the config's
'expected' and 'assumptions_to_check' sections.
"""
import ast, hashlib, json, math, os, re, sys, datetime as dt
from collections import Counter, defaultdict
import numpy as np
import pandas as pd

SENTINEL_TEXT = {"unknown", "n/a", "na", "none", "null", "nan", "-", "--", "?", "not disclosed", "not available", "missing", "tbd"}
ENCODINGS = ("utf-8-sig", "cp1252", "latin-1")

# ------------------------------------------------------------------ loading
def load_source(src, root):
    path = src["path"] if os.path.isabs(src["path"]) else os.path.join(root, src["path"])
    kind = src.get("type") or os.path.splitext(path)[1].lower().lstrip(".")
    if kind in ("xlsx", "xls"):
        return pd.read_excel(path, sheet_name=src.get("sheet", 0)), path, {"type": kind}
    last = None
    for enc in ENCODINGS:
        try:
            df = pd.read_csv(path, sep=src.get("delimiter", ","), encoding=enc, low_memory=False)
            return df, path, {"type": "csv", "encoding": enc, "delimiter": src.get("delimiter", ",")}
        except Exception as e:  # try next encoding
            last = e
    raise RuntimeError(f"cannot read {path}: {last}")

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""): h.update(chunk)
    return h.hexdigest()

def num(x):
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))): return None
    if isinstance(x, (np.integer,)): return int(x)
    if isinstance(x, (np.floating,)): return float(x)
    return x

# ------------------------------------------------------------------ structured text
def parse_struct(v):
    """Return (obj, style) where style is 'json', 'python' or None."""
    if not isinstance(v, str): return None, None
    s = v.strip()
    if not s or s[0] not in "{[": return None, None
    try: return json.loads(s), "json"
    except Exception: pass
    try:
        o = ast.literal_eval(s)
        if isinstance(o, (dict, list)): return o, "python"
    except Exception: pass
    return None, None

def norm_key(k): return re.sub(r"[\s_\-]+", "_", str(k).strip().lower())

# ------------------------------------------------------------------ column profile
def is_date_int(s):
    if s.dtype.kind not in "iu": return False
    v = s.dropna()
    if v.empty or v.min() < 19000101 or v.max() > 21001231: return False
    sample = v.sample(min(len(v), 500), random_state=1)
    try:
        d = pd.to_datetime(sample.astype(str), format="%Y%m%d", errors="coerce")
        return d.notna().mean() > 0.99
    except Exception: return False

def is_date_string(s):
    if s.dtype.kind != "O" and str(s.dtype) not in ("string", "str"): return False
    v = s.dropna().astype(str)
    if v.empty: return False
    sample = v.sample(min(len(v), 300), random_state=1)
    if not sample.str.contains(r"\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}").mean() > 0.9: return False
    try: return pd.to_datetime(sample, errors="coerce").notna().mean() > 0.95
    except Exception: return False

def profile_column(s, n_rows, top_n):
    nn = int(s.notna().sum())
    p = {"dtype": str(s.dtype), "non_null": nn, "nulls": int(n_rows - nn), "null_pct": round(100 * (n_rows - nn) / max(n_rows, 1), 3),
         "distinct": int(s.nunique(dropna=True))}
    p["is_unique"] = bool(nn == n_rows and p["distinct"] == n_rows)
    p["samples"] = [str(x)[:80] for x in s.dropna().head(3).tolist()]
    if s.dtype.kind in "iuf":
        v = s.dropna()
        if len(v):
            q1, q3 = float(v.quantile(.25)), float(v.quantile(.75))
            p["numeric"] = {"min": num(v.min()), "max": num(v.max()), "mean": num(round(float(v.mean()), 4)), "median": num(v.median()),
                            "p01": num(v.quantile(.01)), "p99": num(v.quantile(.99)), "sum": num(float(v.sum())),
                            "upper_fence": q3 + 3 * (q3 - q1)}
            p["numeric"]["above_fence"] = int((v > p["numeric"]["upper_fence"]).sum())
        p["date_int"] = bool(is_date_int(s))
    else:
        v = s.dropna().astype(str)
        if len(v):
            p["text"] = {"min_len": int(v.str.len().min()), "max_len": int(v.str.len().max()),
                         "padded": int((v != v.str.strip()).sum()),
                         "distinct_normalised": int(v.str.strip().str.lower().nunique())}
        p["date_string"] = bool(is_date_string(s))
    if p["distinct"] <= top_n and nn:
        vc = s.value_counts(dropna=True).head(top_n)
        p["top_values"] = {str(k): int(c) for k, c in vc.items()}
    return p

# ------------------------------------------------------------------ main profile + issues
def analyse(cfg, root):
    top_n = cfg.get("profiling", {}).get("max_top_values", 30)
    data, meta, profile, issues, ref = {}, {}, {}, [], {"sources": {}}
    for src in cfg["sources"]:
        df, path, info = load_source(src, root)
        data[src["id"]] = df; meta[src["id"]] = dict(info, path=path)
    counter = [0]
    def issue(kind, source, cols, severity, title, evidence, rule, options, decision=True, examples=None):
        counter[0] += 1
        issues.append({"id": f"I{counter[0]:02d}", "kind": kind, "source": source, "columns": cols, "severity": severity, "title": title,
                       "evidence": evidence, "proposed_rule": rule, "options": options, "needs_decision": decision, "examples": examples or []})

    # ---------------- per source
    struct_cols = {}   # (source, col) -> info
    for sid, df in data.items():
        n = len(df)
        cols = {c: profile_column(df[c], n, top_n) for c in df.columns}
        profile[sid] = {"file": meta[sid], "rows": n, "columns_count": len(df.columns), "duplicate_rows": int(df.duplicated().sum()), "columns": cols}
        # nulls and null coincidence
        nullcols = [c for c in df.columns if cols[c]["nulls"] > 0]
        for c in nullcols:
            issue("nulls", sid, [c], "info", f"{sid}.{c}: {cols[c]['nulls']:,} blank values ({cols[c]['null_pct']}%)",
                  f"{cols[c]['nulls']:,} of {n:,} rows are blank.", "Keep blanks visible; label as 'Unknown' in visuals, do not fill with zero.",
                  ["Keep as blank / Unknown", "Fill with a value (state which)"], decision=cols[c]["null_pct"] >= 1)
        masks = {c: df[c].isna() for c in nullcols}
        seen = set()
        for a in nullcols:
            grp = [b for b in nullcols if masks[b].equals(masks[a])]
            if len(grp) > 1 and tuple(grp) not in seen:
                seen.add(tuple(grp))
                issue("null_coincidence", sid, grp, "info", f"{sid}: {', '.join(grp)} are blank on exactly the same rows",
                      f"{int(masks[a].sum()):,} rows have all of these blank together.", "Treat as one 'profile not disclosed' group.", ["One group flag", "Handle each column separately"], decision=False)
        # sentinel numbers
        for c in df.columns:
            if df[c].dtype.kind in "iu" and cols[c]["distinct"] > 5 and "numeric" in cols[c]:
                vc = df[c].value_counts(); m, f = vc.index[0], int(vc.iloc[0])
                rest = df[c][df[c] != m]
                if len(rest) and f / n >= 0.005 and m == df[c].max() and m > rest.max() * 1.05 and not cols[c]["date_int"]:
                    co = [b for b in nullcols if masks[b][df[c] == m].mean() > 0.95]
                    ev = f"Value {m} appears {f:,} times ({100 * f / n:.1f}%); the next highest value is {rest.max()}."
                    if co: ev += f" On those rows {', '.join(co)} is also blank."
                    issue("sentinel_value", sid, [c], "decision", f"{sid}.{c}: {m} looks like a placeholder for 'unknown'", ev,
                          f"Treat {m} as unknown (blank) and show an 'Unknown' group.", ["Treat as unknown (recommended)", "Keep as a real value"],
                          examples=df[df[c] == m].head(2).astype(str).to_dict("records"))
        for c in df.columns:
            if cols[c].get("text") and cols[c]["distinct"] <= 200:
                bad = [v for v in df[c].dropna().astype(str).unique() if v.strip().lower() in SENTINEL_TEXT]
                if bad:
                    issue("sentinel_text", sid, [c], "decision", f"{sid}.{c}: text placeholders {bad[:5]}", f"Values that mean 'missing': {bad[:5]}.",
                          "Treat as unknown (blank).", ["Treat as unknown", "Keep as text"])
        # date-like
        for c in df.columns:
            if cols[c].get("date_int"):
                issue("date_integer", sid, [c], "info", f"{sid}.{c}: dates stored as numbers (YYYYMMDD)", f"Range {cols[c]['numeric']['min']} to {cols[c]['numeric']['max']}.",
                      "Convert to a real date column.", ["Convert to date"], decision=False)
            if cols[c].get("date_string"):
                issue("date_text", sid, [c], "info", f"{sid}.{c}: dates stored as text", "Looks like a date in text form.", "Convert to a date column; confirm day/month order.", ["Convert to date"], decision=False)
        # case / whitespace variants (like 'AEG refrigerator' vs 'aeg refrigerator')
        for c in df.columns:
            t = cols[c].get("text")
            if t and cols[c]["distinct"] <= 500 and t["distinct_normalised"] < cols[c]["distinct"]:
                issue("case_variants", sid, [c], "warn", f"{sid}.{c}: values that differ only by case or spaces",
                      f"{cols[c]['distinct']:,} distinct values collapse to {t['distinct_normalised']:,} when case and spaces are ignored.",
                      "Standardise case and trim spaces before removing duplicates or building relationships.", ["Standardise (recommended)", "Leave as is"],
                      examples=[{"value_counts_sample": True}])
        if profile[sid]["duplicate_rows"]:
            d = profile[sid]["duplicate_rows"]
            dd = df[df.duplicated(keep=False)]
            ev = f"{d:,} rows repeat an earlier row exactly."
            if len(dd) and dd.shape[1] <= 8:
                for c in df.columns:
                    if cols[c]["distinct"] <= 12 and dd[c].nunique() == 1: ev += f" All are {c} = {dd[c].iloc[0]}."
            issue("duplicate_rows", sid, list(df.columns), "decision", f"{sid}: {d:,} exact duplicate rows", ev,
                  "Keep by default and flag; confirm with the customer whether repeats are real events.", ["Keep all", "Remove duplicates"],
                  examples=dd.head(2).astype(str).to_dict("records"))
        # structured text
        for c in df.columns:
            if cols[c].get("text") is None: continue
            v = df[c].dropna()
            if v.empty: continue
            head = v.astype(str).str.strip().str[0].isin(["{", "["]).mean()
            if head < 0.9: continue
            parsed = [parse_struct(x) for x in v.sample(min(len(v), 5000), random_state=1)]
            styles = Counter(st for o, st in parsed if st)
            struct_cols[(sid, c)] = {"kind": "dict" if isinstance(next((o for o, s2 in parsed if s2), None), dict) else "list", "styles": styles}
            if styles.get("python") and not styles.get("json"):
                issue("not_valid_json", sid, [c], "warn", f"{sid}.{c}: looks like JSON but uses single quotes (Python style)",
                      f"{styles['python']:,} of {len(parsed):,} sampled values parse only as Python dictionaries/lists, not as JSON.",
                      "Normalise quotes, then parse in Power Query.", ["Normalise quotes then parse (recommended)"], decision=False, examples=[{"sample": str(v.iloc[0])[:120]}])
            if struct_cols[(sid, c)]["kind"] == "list":
                allv = Counter()
                for o, st in parsed:
                    if isinstance(o, list): allv.update(str(x) for x in o)
                struct_cols[(sid, c)]["list_values"] = dict(allv)
                allitems = Counter()
                for x in v.sample(min(len(v), 20000), random_state=1):
                    o2, st2 = parse_struct(x)
                    if isinstance(o2, list): allitems.update(str(y) for y in o2)
                groups = defaultdict(set)
                for it in allitems: groups[it.strip().lower()].add(it)
                clash = {k: sorted(g) for k, g in groups.items() if len(g) > 1}
                if clash:
                    ex = list(clash.values())[:3]
                    issue("case_variants", sid, [c], "warn", f"{sid}.{c}: {len(clash)} list items appear in more than one spelling of case or spaces",
                          f"For example {ex}. Power Query treats these as different, Power BI's relationship engine treats them as the same.",
                          "Standardise case (and trim) on each item before removing duplicates or creating a bridge table.", ["Standardise (recommended)", "Leave as is"])
                issue("list_column", sid, [c], "info", f"{sid}.{c}: a list stored in one cell ({len(allv)} distinct items)", f"Items: {sorted(allv)[:10]}.",
                      "Expand into a bridge table (one row per record and item).", ["Bridge table (recommended)", "One yes/no column per item"], decision=False)
            else:
                # key variants overall and by a low-cardinality grouping column
                keysets = Counter(tuple(sorted(o.keys())) for o, st in parsed if isinstance(o, dict))
                struct_cols[(sid, c)]["keysets"] = {"|".join(k): n2 for k, n2 in keysets.items()}
                grp = [g for g in df.columns if g != c and 2 <= cols[g]["distinct"] <= 20 and cols[g].get("top_values")]
                by_group = {}
                if grp:
                    g = grp[0]
                    for gv, sub in df.groupby(g):
                        ks = Counter(tuple(sorted(o.keys())) for o, st in (parse_struct(x) for x in sub[c].dropna().sample(min(len(sub), 2000), random_state=1)) if isinstance(o, dict))
                        by_group[str(gv)] = {"|".join(k): n2 for k, n2 in ks.items()}
                    struct_cols[(sid, c)]["group_column"] = g; struct_cols[(sid, c)]["keys_by_group"] = by_group
                allkeys = {k for ks in keysets for k in ks}
                variants = defaultdict(set)
                for k in allkeys: variants[norm_key(k)].add(k)
                dup_v = {k: sorted(v2) for k, v2 in variants.items() if len(v2) > 1}
                ev = f"Key sets found: {dict(struct_cols[(sid, c)]['keysets'])}."
                if by_group: ev += f" By {struct_cols[(sid, c)]['group_column']}: {by_group}."
                issue("structured_keys", sid, [c], "warn" if dup_v or len(keysets) > 1 else "info",
                      f"{sid}.{c}: values hold fields that differ by {struct_cols[(sid, c)].get('group_column', 'row')}",
                      ev + (f" Same field spelled differently: {dup_v}." if dup_v else ""),
                      "Parse per group and write each field to one typed column; map spelling variants to one name.", ["Parse per group (recommended)"], decision=False)
    # ---------------- parsed numeric fields inside structured text (e.g. transaction amounts)
    parsed_numeric = {}
    for (sid, c), info in struct_cols.items():
        if info["kind"] != "dict": continue
        vals = defaultdict(list)
        for x in data[sid][c].dropna():
            o, st = parse_struct(x)
            if isinstance(o, dict):
                for k, v in o.items():
                    if isinstance(v, (int, float)) and not isinstance(v, bool): vals[k].append(float(v))
        for k, arr in vals.items():
            a = np.array(arr); q1, q3 = np.percentile(a, [25, 75]); fence = q3 + 3 * (q3 - q1)
            parsed_numeric[f"{sid}.{c}.{k}"] = {"count": int(len(a)), "sum": float(a.sum()), "min": float(a.min()), "max": float(a.max()), "median": float(np.median(a)),
                                              "above_fence": int((a > fence).sum())}
            if (a > fence).sum():
                issue("outliers", sid, [c, k], "info", f"{sid}.{c}[{k}]: {(a > fence).sum():,} unusually large values (max {a.max():,.2f}, median {np.median(a):,.2f})",
                      "Values beyond three times the interquartile range above the third quartile.", "Keep; show a typical-range view and label outliers.", ["Keep and label (recommended)", "Exclude"], decision=False)
    for sid, df in data.items():
        for c, p in profile[sid]["columns"].items():
            if re.search(r"lat|lon|lng|zip|postal|code|(^|_)id$|number", c.lower()): continue
            if "numeric" in p and p["numeric"]["above_fence"] and not p["date_int"] and not p["is_unique"] and p["distinct"] > 20:
                issue("outliers", sid, [c], "info", f"{sid}.{c}: {p['numeric']['above_fence']:,} unusually large values (max {p['numeric']['max']:,})",
                      "Beyond three times the interquartile range above the third quartile.", "Keep; label outliers rather than remove.", ["Keep and label (recommended)", "Exclude"], decision=False)
    # ---------------- keys and links between sources
    uniq = {(sid, c) for sid in data for c, p in profile[sid]["columns"].items() if p["is_unique"] and p["non_null"] > 1}
    links = []
    for sid, df in data.items():
        for c in df.columns:
            for (tsid, tc) in uniq:
                if tsid == sid or norm_key(tc) != norm_key(c) or c == "id": continue
                vals = df[c].dropna().unique(); orphan = int((~pd.Series(vals).isin(data[tsid][tc])).sum())
                links.append({"from": f"{sid}.{c}", "to": f"{tsid}.{tc}", "distinct_values": int(len(vals)), "orphans": orphan})
                if orphan:
                    issue("orphans", sid, [c], "warn", f"{sid}.{c}: {orphan:,} values not found in {tsid}.{tc}", f"{orphan:,} of {len(vals):,} distinct values have no match.",
                          "List and decide: drop, keep as unknown, or ask the owner.", ["Keep as unknown", "Drop rows", "Ask data owner"])
    for (sid, c), info in struct_cols.items():
        if info["kind"] != "dict": continue
        keyvals = defaultdict(set)
        for x in data[sid][c].dropna():
            o, st = parse_struct(x)
            if isinstance(o, dict):
                for k, v in o.items():
                    if isinstance(v, str): keyvals[k].add(v)
        for k, vs in keyvals.items():
            for (tsid, tc) in uniq:
                if norm_key(tc) == norm_key(k):
                    orphan = len(vs - set(data[tsid][tc].astype(str)))
                    links.append({"from": f"{sid}.{c}[{k}]", "to": f"{tsid}.{tc}", "distinct_values": len(vs), "orphans": orphan})
                    if orphan: issue("orphans", sid, [c, k], "warn", f"{sid}.{c}[{k}]: {orphan} ids not found in {tsid}.{tc}", "", "List and decide.", ["Keep as unknown", "Drop rows"])
    # ---------------- expected volumes from the requirements
    for sid, e in cfg.get("expected", {}).items():
        if sid in profile:
            n, exp, tol = profile[sid]["rows"], e["rows"], e.get("tolerance", 0.2)
            if abs(n - exp) / exp > tol:
                issue("volume_mismatch", sid, [], "decision", f"{sid}: {n:,} rows, but the requirements say about {exp:,}",
                      f"Actual is {n / exp:.1f} times the stated volume.", "Use the file provided; note the difference and confirm it is the intended extract.",
                      ["Use this file", "Ask for the intended extract"])
    for a in cfg.get("assumptions_to_check", []):
        issue("assumption", a.get("source", ""), a.get("columns", []), "decision", a["title"], a.get("evidence", "From the data description."), a["proposed_rule"], a.get("options", ["Confirm", "Change"]))

    # ---------------- reference totals (P-04)
    for sid, df in data.items():
        cols = profile[sid]["columns"]
        ref["sources"][sid] = {"file": os.path.basename(meta[sid]["path"]), "sha256": sha256(meta[sid]["path"]), "rows": len(df),
                                "distinct": {c: p["distinct"] for c, p in cols.items() if p["distinct"] == len(df) or p["distinct"] <= 50},
                                "nulls": {c: p["nulls"] for c, p in cols.items() if p["nulls"]},
                                "sums": {c: p["numeric"]["sum"] for c, p in cols.items() if "numeric" in p and not p["date_int"] and not p["is_unique"]},
                                "category_counts": {c: p["top_values"] for c, p in cols.items() if p.get("top_values") and 1 < p["distinct"] <= 20}}
    ref["parsed_numeric_fields"] = parsed_numeric
    ref["locked_at"] = dt.datetime.now().isoformat(timespec="seconds")
    return meta, profile, issues, ref, struct_cols, links

# ------------------------------------------------------------------ report
def write_outputs(cfg, meta, profile, issues, ref, struct_cols, links, out):
    os.makedirs(out, exist_ok=True)
    def clean(o):   # NaN and infinity are not valid JSON; browsers and other readers reject them, so write null instead
        if isinstance(o, float) and (math.isnan(o) or math.isinf(o)): return None
        if isinstance(o, dict): return {k: clean(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)): return [clean(v) for v in o]
        return o
    def dump(name, obj):
        with open(os.path.join(out, name), "w", encoding="utf-8", newline="\n") as f: json.dump(clean(obj), f, indent=2, default=str, allow_nan=False)
    prof_json = {"engagement": cfg.get("engagement", {}), "sources": profile, "structured_columns": {f"{s}.{c}": {k: v for k, v in i.items()} for (s, c), i in struct_cols.items()}, "links": links}
    dump("profile.json", prof_json); dump("issues.json", issues); dump("reference_totals.json", ref)
    dump("decisions_template.json", [{"issue_id": i["id"], "title": i["title"], "options": i["options"], "proposed_rule": i["proposed_rule"], "decision": None, "decided_by": None, "decided_at": None}
                                    for i in issues if i["needs_decision"]])
    L = [f"# Data profile: {cfg.get('engagement', {}).get('name', '')}", ""]
    L += ["| Source | Rows | Columns | Exact duplicate rows | File |", "|---|---|---|---|---|"]
    for sid, p in profile.items(): L.append(f"| {sid} | {p['rows']:,} | {p['columns_count']} | {p['duplicate_rows']:,} | {os.path.basename(p['file']['path'])} |")
    L += ["", "## Issues that need a decision", ""]
    for i in issues:
        if i["needs_decision"]: L += [f"**{i['id']}** {i['title']}  ", f"Evidence: {i['evidence']}  ", f"Proposed: {i['proposed_rule']}  ", f"Options: {' / '.join(i['options'])}", ""]
    L += ["## Other findings", ""] + [f"- **{i['id']}** {i['title']}" for i in issues if not i["needs_decision"]]
    L += ["", "## Links between sources", ""] + [f"- {l['from']} -> {l['to']}: {l['distinct_values']:,} distinct values, {l['orphans']} without a match" for l in links]
    with open(os.path.join(out, "profile_report.md"), "w", encoding="utf-8", newline="\n") as f: f.write("\n".join(L) + "\n")

def verify_lock(ref_path, cfg, root):
    """Q-gate helper: confirm the source files are unchanged since the reference totals were captured."""
    ref = json.load(open(ref_path, encoding="utf-8")); bad = []
    for src in cfg["sources"]:
        path = src["path"] if os.path.isabs(src["path"]) else os.path.join(root, src["path"])
        if sha256(path) != ref["sources"][src["id"]]["sha256"]: bad.append(src["id"])
    return bad

def main(cfg_path, out=None):
    cfg = json.load(open(cfg_path, encoding="utf-8"))
    root = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(cfg_path)), cfg.get("data_root", ".")))
    out = out or os.path.join(os.path.dirname(os.path.abspath(cfg_path)), "..", "outputs", cfg.get("engagement", {}).get("id", "run"), "profile")
    meta, profile, issues, ref, struct_cols, links = analyse(cfg, root)
    write_outputs(cfg, meta, profile, issues, ref, struct_cols, links, os.path.normpath(out))
    dec = sum(1 for i in issues if i["needs_decision"])
    print(f"profiled {len(profile)} sources; {len(issues)} findings ({dec} need a decision) -> {os.path.normpath(out)}")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None))
