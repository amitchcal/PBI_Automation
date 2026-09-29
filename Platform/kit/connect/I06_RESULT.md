# I-06 result: connect to a database or network data source

**Date:** 29 Sep 2026.

## Scope chosen
Two source kinds, both usable with nothing already installed beyond this project's own Python (`sqlite3` is
standard library; `requests` is already used elsewhere in the kit):
- **SQLite** — a real database. A file, plus a table name or a `SELECT` query.
- **HTTP(S)** — a real network data source: an internal file server, a SharePoint/OneDrive direct link, or an
  API that returns CSV/Excel bytes, with optional basic-auth or a bearer token.

A production server database (SQL Server, Postgres, MySQL) needs that database's Python driver installed, which
isn't present in this environment (checked: `pyodbc`, `psycopg2`, `pymysql`, `sqlalchemy` are all missing). Adding
one is meant to be a small addition to `kit/connect/db_connect.py` (one more branch, same shape as the SQLite one)
plus `SECRET_FIELDS` in `web/src/lib/server/secrets.ts` — not a redesign.

## Acceptance criteria, checked one by one
- **"Connection form with a test button"** — built into the "Your data" step: pick a kind, fill the fields, Test
  connection (nothing is saved yet), then Pull this data once the test passes.
- **"Credentials stored securely"** — a password or bearer token is encrypted at rest (AES-256-GCM, a key
  generated on first use and never sent to the browser) before the engagement record is saved, and only decrypted
  in memory, server-side, right before the Python connector runs. The one API response function every route uses
  (`payload()`) redacts these fields on the way out, so a stored secret cannot leak back to the client even by
  accident — verified: a real password was pulled, confirmed encrypted (not plaintext) in the saved state file,
  confirmed redacted to dots in every API response, and confirmed it still decrypts correctly for a later re-pull.
  Honest limit: the encryption key lives on the same disk as the data it protects (there is no separate secret
  vault in this local prototype), so it guards against a stray read of the data folder or a copied backup, not
  against someone with full access to the machine. A real deployment should move the key to the platform's own
  secret store; only `secrets.ts` would need to change.
- **"Read-only access verified"** — for SQLite, verified two ways: the connection is opened in the driver's own
  `mode=ro`, so a write is refused by SQLite itself (proved directly: a `DELETE` attempted on a `mode=ro`
  connection failed with `OperationalError: attempt to write a readonly database`, and the row count was
  unchanged afterwards) — not only a text check on the query, which is also there as a second, friendlier layer
  and was confirmed to reject `DELETE`/`UPDATE`/`INSERT`/etc. For HTTP, the mechanism is a GET/HEAD request, which
  has no way to write to the far end at all.

## Tested end to end
Through the real API (and the real UI form, checked in the browser): tested and pulled a SQLite table into a new
CSV file, which then flowed into the existing profiling step unchanged (it just looks like an uploaded file from
that point on); tested and pulled an HTTP source with a username and password; re-pulled an existing connection
(proving the stored, encrypted credential round-trips correctly); removed a connection (its file and the
connection record both disappeared). Also confirmed a reviewer (not the owner) is refused at this route, matching
story W-03, and that a malicious query is refused before it ever reaches the database.

## Not done
- No connector-management screen beyond the "Your data" step's own list (no edit-in-place; removing and adding
  again is the only way to change one).
- No scheduled/automatic re-pull; a person clicks "Pull again."
- Real server databases (SQL Server, Postgres, MySQL, Oracle) are not implemented, only the mechanism and pattern
  for adding one, as described above.
