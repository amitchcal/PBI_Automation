"""Story I-06: connect to a database or network data source instead of exporting files.

Two source kinds, chosen because both work with nothing beyond Python's own standard library (sqlite3) or the
`requests` package already used elsewhere in this kit -- no new driver to install for the demo:
  sqlite  A local or shared SQLite file. Opened in the driver's own read-only mode (sqlite3's URI "mode=ro"),
          which is enforced by SQLite itself, not just by this script -- a write attempt fails at the engine,
          not only at a query-text check.
  http    A file reachable over HTTP(S): an internal file server, a SharePoint/OneDrive direct-download link, or
          an API that returns CSV/Excel bytes. Read-only by nature (a GET request); optional basic-auth or a
          bearer token.

Adding a real server database (SQL Server, Postgres, MySQL) later is the same shape: install that database's
Python driver (pyodbc, psycopg2, pymysql -- none are installed here), add one more branch to `_connect_to` and
`_query`, using a connection string built the same way the sqlite branch is, and grant the account you connect
with SELECT-only permission at the database itself (the one guarantee this script cannot make on your behalf).

Two entry points, both read-only and side-effect-free except for `pull` writing one file:
  test(kind, config) -> {"ok": bool, "error": str|None, "preview": {...}}   -- connects, runs one lightweight
      check (list tables / a HEAD request), returns without pulling data.
  pull(kind, config, out_csv) -> {"ok": bool, "error": str|None, "rows": int}  -- runs the configured read and
      writes exactly one CSV, so every later stage (profiling, transform) sees a plain file and needs no changes.

Usage: the config (with any password/token already decrypted) is read from stdin as one JSON object, never from
argv, so a secret is never visible in a process listing on a shared machine:
       echo '<json config>' | python db_connect.py test
       echo '<json config>' | python db_connect.py pull <out_csv>
Config shape: {"kind": "sqlite", "path": "...", "query": "SELECT ... FROM ..." | "table": "..."}
           or {"kind": "http", "url": "...", "username": "...", "password": "...", "bearer": "...", "type": "csv"|"xlsx"}
"""
import io, json, os, re, sqlite3, sys

FORBIDDEN = re.compile(r"\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|attach|pragma)\b", re.IGNORECASE)


def _check_select_only(sql):
    """Defence in depth on top of the driver's own read-only mode: reject anything that isn't a plain read."""
    s = sql.strip().rstrip(";")
    if not re.match(r"^(select|with)\b", s, re.IGNORECASE):
        return "Only a SELECT (or a WITH ... SELECT) query is accepted."
    if FORBIDDEN.search(s):
        return "That query contains a word this tool never allows through a data-source connection (only reads are permitted)."
    if ";" in s:
        return "Only one statement at a time."
    return None


def _sqlite_query(cfg):
    path = cfg.get("path")
    if not path or not os.path.isfile(path):
        raise RuntimeError(f"SQLite file not found: {path}")
    sql = cfg.get("query") or (f"SELECT * FROM {cfg['table']}" if cfg.get("table") else None)
    if not sql:
        raise RuntimeError("Give either a table name or a SELECT query.")
    err = _check_select_only(sql)
    if err:
        raise RuntimeError(err)
    # uri=True + mode=ro: SQLite itself refuses any write on this connection, independent of the query-text check
    # above. This is the real read-only guarantee; the regex check is only a friendlier first error message.
    uri = f"file:{os.path.abspath(path)}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        cur = conn.cursor()
        cur.execute(sql)
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
        return cols, rows
    finally:
        conn.close()


def _sqlite_tables(path):
    uri = f"file:{os.path.abspath(path)}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        return [r[0] for r in cur.fetchall()]
    finally:
        conn.close()


def _http_fetch(cfg):
    import requests
    auth = None
    headers = {}
    if cfg.get("username"):
        auth = (cfg["username"], cfg.get("password", ""))
    if cfg.get("bearer"):
        headers["Authorization"] = f"Bearer {cfg['bearer']}"
    r = requests.get(cfg["url"], auth=auth, headers=headers, timeout=30)
    r.raise_for_status()
    return r.content


def test(kind, cfg):
    try:
        if kind == "sqlite":
            tables = _sqlite_tables(cfg["path"])
            if cfg.get("query") or cfg.get("table"):
                cols, rows = _sqlite_query(cfg)
                return {"ok": True, "preview": {"tables": tables, "columns": cols, "sample_rows": len(rows)}}
            return {"ok": True, "preview": {"tables": tables}}
        if kind == "http":
            import requests
            auth = (cfg["username"], cfg.get("password", "")) if cfg.get("username") else None
            headers = {"Authorization": f"Bearer {cfg['bearer']}"} if cfg.get("bearer") else {}
            r = requests.head(cfg["url"], auth=auth, headers=headers, timeout=15, allow_redirects=True)
            if r.status_code >= 400 or r.status_code == 405:  # some servers reject HEAD; fall back to a small GET
                r = requests.get(cfg["url"], auth=auth, headers=headers, timeout=15, stream=True)
            r.raise_for_status()
            return {"ok": True, "preview": {"status": r.status_code, "content_type": r.headers.get("content-type"), "content_length": r.headers.get("content-length")}}
        return {"ok": False, "error": f"Unknown source kind: {kind}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def pull(kind, cfg, out_csv):
    try:
        if kind == "sqlite":
            cols, rows = _sqlite_query(cfg)
            import csv
            os.makedirs(os.path.dirname(out_csv), exist_ok=True)
            with open(out_csv, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(cols)
                w.writerows(rows)
            return {"ok": True, "rows": len(rows)}
        if kind == "http":
            content = _http_fetch(cfg)
            ftype = cfg.get("type", "csv")
            os.makedirs(os.path.dirname(out_csv), exist_ok=True)
            if ftype == "csv":
                with open(out_csv, "wb") as f:
                    f.write(content)
                rows = content.count(b"\n")
            else:
                # keep the original extension for xlsx; out_csv is a suggested path, adjust if needed
                real_path = out_csv.rsplit(".", 1)[0] + ".xlsx" if ftype == "xlsx" else out_csv
                with open(real_path, "wb") as f:
                    f.write(content)
                rows = None
            return {"ok": True, "rows": rows}
        return {"ok": False, "error": f"Unknown source kind: {kind}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


if __name__ == "__main__":
    action = sys.argv[1]
    cfg = json.loads(sys.stdin.read())
    kind = cfg["kind"]
    if action == "test":
        print(json.dumps(test(kind, cfg)))
    elif action == "pull":
        print(json.dumps(pull(kind, cfg, sys.argv[2])))
    else:
        print(json.dumps({"ok": False, "error": f"Unknown action: {action}"}))
        sys.exit(1)
