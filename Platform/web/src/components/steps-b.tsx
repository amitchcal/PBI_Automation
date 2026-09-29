"use client";
import { useEffect, useRef, useState } from "react";
import { api, useEng, useRole, EngData } from "@/components/engagement";
import { DoneBanner, useNext } from "@/components/steps-a";
import { Badge, Button, Card, Field, inputCls, Notice, PageTitle, Skeleton, useToast, fmtNum, fmtSize } from "@/components/ui";
import type { DataConnection, Issue, SourceKind } from "@/lib/steps";

// ---------------------------------------------------------------- 4 data, connect-to-a-source (story I-06)
type TestResult = { ok: boolean; error?: string; preview?: Record<string, unknown> };

function ConnectPanel() {
  const { id, data, set } = useEng(); const e = data!.engagement; const { toast } = useToast();
  const [kind, setKind] = useState<SourceKind>("sqlite");
  const [path, setPath] = useState(""); const [table, setTable] = useState(""); const [query, setQuery] = useState("");
  const [url, setUrl] = useState(""); const [username, setUsername] = useState(""); const [password, setPassword] = useState(""); const [bearer, setBearer] = useState(""); const [ftype, setFtype] = useState<"csv" | "xlsx">("csv");
  const [label, setLabel] = useState(""); const [testing, setTesting] = useState(false); const [pulling, setPulling] = useState(false); const [busyId, setBusyId] = useState<string | null>(null);
  const [result, setResult] = useState<TestResult | null>(null);

  const config = (): Record<string, unknown> => kind === "sqlite"
    ? { path, ...(table ? { table } : {}), ...(query ? { query } : {}) }
    : { url, ...(username ? { username, password } : {}), ...(bearer ? { bearer } : {}), type: ftype };

  async function test() {
    setTesting(true); setResult(null);
    try { setResult(await api<TestResult>(`/api/e/${id}/connect`, { json: { op: "test", kind, config: config() } })); }
    catch (x) { setResult({ ok: false, error: (x as Error).message }); } finally { setTesting(false); }
  }
  async function pull() {
    setPulling(true);
    try { set(await api<EngData>(`/api/e/${id}/connect`, { json: { op: "pull", kind, config: config(), label: label || kind } })); toast("ok", "Pulled and added as a file. Check it below."); setResult(null); setLabel(""); }
    catch (x) { toast("error", (x as Error).message); } finally { setPulling(false); }
  }
  async function repull(c: DataConnection) {
    setBusyId(c.id);
    try { set(await api<EngData>(`/api/e/${id}/connect`, { json: { op: "repull", connectionId: c.id } })); toast("ok", "Pulled again."); }
    catch (x) { toast("error", (x as Error).message); } finally { setBusyId(null); }
  }
  async function remove(c: DataConnection) {
    setBusyId(c.id);
    try { set(await api<EngData>(`/api/e/${id}/connect`, { json: { op: "remove", connectionId: c.id } })); toast("ok", "Connection removed."); }
    catch (x) { toast("error", (x as Error).message); } finally { setBusyId(null); }
  }

  return (
    <Card className="mb-5">
      <h2 className="font-semibold mb-1">Or connect to a data source</h2>
      <p className="text-sm text-muted mb-4">A database file or a link reachable over your network, instead of uploading. Every connection is read-only, checked before anything is saved, and any password or token is encrypted, never shown again.</p>
      {e.connections.length > 0 && (
        <ul className="mb-5 divide-y divide-border rounded-xl border border-border">{e.connections.map((c) => (
          <li key={c.id} className="p-3 text-sm flex flex-wrap items-center justify-between gap-2">
            <span><Badge tone={c.lastTest?.ok ? "good" : "bad"}>{c.kind}</Badge> <span className="font-semibold ml-2">{c.label}</span> {c.pulledAs && <span className="text-muted">&rarr; {c.pulledAs}</span>}</span>
            <span className="flex gap-2"><Button kind="quiet" onClick={() => repull(c)} busy={busyId === c.id}>Pull again</Button><Button kind="quiet" onClick={() => remove(c)} busy={busyId === c.id}>Remove</Button></span>
          </li>
        ))}</ul>
      )}
      <div className="flex gap-2 mb-4" role="radiogroup" aria-label="Source kind">
        {(["sqlite", "http"] as const).map((k) => (
          <button key={k} type="button" onClick={() => { setKind(k); setResult(null); }} aria-pressed={kind === k}
            className={`rounded-full px-4 min-h-10 text-sm font-semibold border ${kind === k ? "bg-primary text-on-primary border-primary" : "bg-surface border-border text-muted hover:text-text"}`}>
            {k === "sqlite" ? "Database (SQLite file)" : "Network file (HTTP/HTTPS link)"}
          </button>
        ))}
      </div>
      {kind === "sqlite" ? (
        <div className="grid sm:grid-cols-2 gap-x-6">
          <Field label="Path to the .db file" htmlFor="cn-path" help="A file this computer can read, for example on a shared drive."><input id="cn-path" className={inputCls} value={path} onChange={(ev) => setPath(ev.target.value)} placeholder="\\server\share\data.db" /></Field>
          <Field label="Table name" htmlFor="cn-table" help="Or leave blank and give a query instead."><input id="cn-table" className={inputCls} value={table} onChange={(ev) => setTable(ev.target.value)} placeholder="customers" /></Field>
          <div className="sm:col-span-2"><Field label="Or a SELECT query (optional)" htmlFor="cn-query" help="Read-only: only SELECT is accepted, enforced by the database driver itself, not only checked here."><input id="cn-query" className={inputCls} value={query} onChange={(ev) => setQuery(ev.target.value)} placeholder="SELECT * FROM customers WHERE ..." /></Field></div>
        </div>
      ) : (
        <div className="grid sm:grid-cols-2 gap-x-6">
          <div className="sm:col-span-2"><Field label="URL" htmlFor="cn-url"><input id="cn-url" className={inputCls} value={url} onChange={(ev) => setUrl(ev.target.value)} placeholder="https://files.example.com/customers.csv" /></Field></div>
          <Field label="Username (optional)" htmlFor="cn-user"><input id="cn-user" className={inputCls} value={username} onChange={(ev) => setUsername(ev.target.value)} /></Field>
          <Field label="Password (optional)" htmlFor="cn-pass"><input id="cn-pass" type="password" className={inputCls} value={password} onChange={(ev) => setPassword(ev.target.value)} autoComplete="off" /></Field>
          <Field label="Bearer token instead (optional)" htmlFor="cn-bearer"><input id="cn-bearer" type="password" className={inputCls} value={bearer} onChange={(ev) => setBearer(ev.target.value)} autoComplete="off" /></Field>
          <Field label="File type" htmlFor="cn-type"><select id="cn-type" className={inputCls} value={ftype} onChange={(ev) => setFtype(ev.target.value as "csv" | "xlsx")}><option value="csv">CSV</option><option value="xlsx">Excel</option></select></Field>
        </div>
      )}
      <div className="flex flex-wrap items-end gap-3 mt-4">
        <Field label="Name this source" htmlFor="cn-label"><input id="cn-label" className={`${inputCls} sm:max-w-xs`} value={label} onChange={(ev) => setLabel(ev.target.value)} placeholder="e.g. crm_customers" /></Field>
        <Button kind="secondary" onClick={test} busy={testing}>Test connection</Button>
        <Button onClick={pull} disabled={!result?.ok} busy={pulling} title={result?.ok ? "" : "Test the connection first"}>Pull this data</Button>
      </div>
      {result && (result.ok
        ? <div className="mt-3"><Notice tone="good" title="Connected">{JSON.stringify(result.preview)}</Notice></div>
        : <div className="mt-3"><Notice tone="bad" title="Could not connect">{result.error}</Notice></div>)}
    </Card>
  );
}

export function DataStep() {
  const { id, data, set, run, busy } = useEng(); const e = data!.engagement; const next = useNext("data"); const { toast } = useToast();
  const role = useRole(); const locked = !!e.done.data || e.mode === "demo" || role === "reviewer";
  const [up, setUp] = useState(false); const [chk, setChk] = useState(false); const [drag, setDrag] = useState(false); const input = useRef<HTMLInputElement>(null);
  async function upload(files: FileList | File[] | null) {
    if (!files || !files.length) return; setUp(true);
    const fd = new FormData(); fd.append("kind", "data"); Array.from(files).forEach((f) => fd.append("file", f));
    try { set(await api<EngData>(`/api/e/${id}/upload`, { method: "POST", body: fd })); toast("ok", "Files uploaded. Now check them."); } catch (x) { toast("error", (x as Error).message); } finally { setUp(false); }
  }
  async function check() { setChk(true); try { set(await api<EngData>(`/api/e/${id}/profile`, { method: "POST" })); } catch (x) { toast("error", (x as Error).message); } finally { setChk(false); } }
  const p = e.profile; const need = p?.issues.filter((i) => i.needs_decision).length ?? 0;
  return (
    <>
      <PageTitle eyebrow="Step 4" title="Your data">Upload CSV or Excel files. We read them right away and tell you what we find, before anything is built.</PageTitle>
      <DoneBanner step="data" />
      {e.mode === "live" && !locked && (
        <Card className="mb-5">
          <div onDragOver={(ev) => { ev.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)} onDrop={(ev) => { ev.preventDefault(); setDrag(false); upload(ev.dataTransfer.files); }}
            className={`rounded-xl border-2 border-dashed p-8 text-center transition ${drag ? "border-primary bg-primary-soft/50" : "border-border"}`}>
            <p className="font-semibold">Drop your files here</p>
            <p className="text-sm text-muted mb-4">CSV or Excel, up to 60 MB each</p>
            <input ref={input} type="file" multiple accept=".csv,.xlsx" className="sr-only" id="files" onChange={(ev) => { upload(ev.target.files); ev.target.value = ""; }} />
            <Button kind="secondary" onClick={() => input.current?.click()} busy={up}>Choose files</Button>
          </div>
        </Card>
      )}
      {e.mode === "live" && !locked && <ConnectPanel />}
      {e.files.length > 0 && (
        <Card className="mb-5" pad={false}>
          <ul className="divide-y divide-border">{e.files.map((f) => (
            <li key={f.name} className="px-5 py-3 flex items-center justify-between gap-3 text-sm"><span className="font-medium break-all">{f.name}</span><span className="text-muted tabular shrink-0">{fmtSize(f.size)}</span></li>))}</ul>
        </Card>
      )}
      {!locked && e.files.length > 0 && <div className="mb-5"><Button onClick={check} busy={chk}>{p ? "Check the files again" : "Check my files"}</Button></div>}
      {p?.error && <Notice tone="bad" title="We could not read the files">{p.error}</Notice>}
      {p && !p.error && (
        <>
          <Card pad={false} className="mb-5 overflow-x-auto">
            <table className="w-full text-sm"><caption className="sr-only">What we found in each file</caption>
              <thead><tr className="text-left text-muted border-b border-border"><th className="px-5 py-3 font-semibold">File</th><th className="px-3 py-3 font-semibold text-right">Rows</th><th className="px-3 py-3 font-semibold text-right">Columns</th><th className="px-5 py-3 font-semibold text-right">Exact repeats</th></tr></thead>
              <tbody className="divide-y divide-border">{p.sources.map((s) => (
                <tr key={s.id}><td className="px-5 py-3 font-medium">{s.id}</td><td className="px-3 py-3 text-right tabular">{fmtNum(s.rows)}</td><td className="px-3 py-3 text-right tabular">{s.columns}</td><td className="px-5 py-3 text-right tabular">{fmtNum(s.duplicate_rows)}</td></tr>))}</tbody></table>
          </Card>
          <Notice tone={need ? "warn" : "good"} title={`${p.issues.length} things noticed, ${need} need your decision`}>You will decide each one in step 6. A recommended answer is ready for every question.</Notice>
          {!locked && <div className="mt-5"><Button onClick={async () => { if (await run("data.complete", {}, "Files checked")) next(); }} busy={busy === "data.complete"}>Continue</Button></div>}
        </>
      )}
    </>
  );
}

// ---------------------------------------------------------------- 5 summary
interface Summary { config: Record<string, unknown>; missing: string[]; flags: string[] }
export function SummaryStep() {
  const { id, data, run, busy } = useEng(); const e = data!.engagement; const next = useNext("summary");
  const role = useRole(); const locked = !!e.done.summary || e.mode === "demo" || role === "reviewer";
  const [s, setS] = useState<Summary | null>(null);
  useEffect(() => { api<Summary>(`/api/e/${id}/view/summary`).then(setS); }, [id, e]);
  const q = e.questionnaire;
  return (
    <>
      <PageTitle eyebrow="Step 5" title="Confirm the plan">This is what we understood. Please read it and tell us if anything is missing or wrong before we go on.</PageTitle>
      <DoneBanner step="summary" />
      {!s ? <Skeleton h="h-48" /> : (
        <>
          {s.missing.length > 0 && <div className="mb-4"><Notice tone="bad" title="Still missing"><ul className="list-disc pl-5">{s.missing.map((m) => <li key={m}>{m}</li>)}</ul></Notice></div>}
          {s.flags.length > 0 && <div className="mb-4"><Notice tone="warn" title="Please check"><ul className="list-disc pl-5">{s.flags.map((m) => <li key={m}>{m}</li>)}</ul></Notice></div>}
          <div className="grid md:grid-cols-2 gap-4 mb-5">
            <Card><h2 className="font-semibold mb-2">The problem</h2><p className="text-sm text-muted leading-relaxed">{q.problem || "Not answered"}</p><p className="text-sm mt-3"><span className="font-semibold">For:</span> {q.audience || "n/a"} &middot; <span className="font-semibold">looked at:</span> {q.frequency || "n/a"}</p></Card>
            <Card><h2 className="font-semibold mb-2">Your data</h2><ul className="text-sm text-muted space-y-1">{e.files.map((f) => <li key={f.name}>{f.name}</li>)}</ul><p className="text-sm mt-3"><span className="font-semibold">Updates:</span> {q.refresh || "n/a"} &middot; <span className="font-semibold">owner:</span> {q.data_owner || "n/a"}</p></Card>
            <Card><h2 className="font-semibold mb-2">Your key numbers</h2><ul className="text-sm text-muted space-y-1 list-disc pl-5">{(q.kpis || "").split("\n").filter(Boolean).map((l) => <li key={l}>{l}</li>)}</ul></Card>
            <Card><h2 className="font-semibold mb-2">Look, security and publishing</h2><p className="text-sm text-muted leading-relaxed">Brand: {e.brand?.name || "not set"} ({e.brand?.template}). Row-level security: {q.rls || "n/a"}. Publishing to {q.workspace || "n/a"}; licence: {q.licences || "n/a"}.</p></Card>
          </div>
          <details className="mb-5 rounded-xl border border-border bg-surface p-4"><summary className="cursor-pointer text-sm font-semibold">For the technically curious: the configuration file this becomes</summary>
            <pre className="mt-3 text-xs overflow-x-auto bg-background rounded-lg p-3">{JSON.stringify(s.config, null, 2)}</pre></details>
          {!locked && <Button onClick={async () => { if (await run("summary.confirm", {}, "Plan confirmed")) next(); }} disabled={s.missing.length > 0} busy={busy === "summary.confirm"}>This is right, continue</Button>}
        </>
      )}
    </>
  );
}

// ---------------------------------------------------------------- 6 data decisions
const recommended = (i: Issue) => i.options.find((o) => /recommended/i.test(o)) ?? i.options[0];
export function IssuesStep() {
  const { data, run, busy } = useEng(); const e = data!.engagement; const next = useNext("issues");
  const role = useRole(); const locked = !!e.done.issues || e.mode === "demo" || role === "reviewer";
  const issues = e.profile?.issues ?? []; const need = issues.filter((i) => i.needs_decision); const other = issues.filter((i) => !i.needs_decision);
  const decided = need.filter((i) => e.decisions[i.id]).length;
  async function useAllRecommended() { for (const i of need) if (!e.decisions[i.id]) await run("issues.decide", { id: i.id, decision: recommended(i) }); }
  return (
    <>
      <PageTitle eyebrow="Step 6" title="Data decisions">Each question below is about how to treat a problem we found. The recommended answer is marked; choose another if it suits you better.</PageTitle>
      <DoneBanner step="issues" />
      <div className="flex flex-wrap items-center gap-3 mb-5"><Badge tone={decided === need.length ? "good" : "info"}>{decided} of {need.length} decided</Badge>
        {!locked && decided < need.length && <Button kind="secondary" onClick={useAllRecommended}>Use the recommended answer for all open questions</Button>}</div>
      {need.length === 0 && <Notice tone="good">Nothing needs your decision.</Notice>}
      <ul className="space-y-4">
        {need.map((i) => {
          const cur = e.decisions[i.id]?.decision; const ex = i.examples?.[0] as Record<string, unknown> | undefined;
          return (
            <li key={i.id}><Card>
              <div className="flex items-start justify-between gap-3"><h2 className="font-semibold leading-snug">{i.title}</h2>{cur ? <Badge tone="good">Decided</Badge> : <Badge tone="warn">Open</Badge>}</div>
              <p className="text-sm text-muted mt-2 leading-relaxed">{i.evidence}</p>
              {ex && Object.keys(ex).length > 0 && <p className="mt-2 text-xs text-muted bg-background rounded-lg px-3 py-2 break-all"><span className="font-semibold">Example:</span> {Object.entries(ex).slice(0, 4).map(([k, v]) => `${k}: ${String(v).slice(0, 40)}`).join(" | ")}</p>}
              <p className="text-sm mt-3"><span className="font-semibold">Proposed:</span> {i.proposed_rule}</p>
              <fieldset className="mt-3" disabled={locked}><legend className="sr-only">Your decision for {i.title}</legend>
                <div className="grid sm:grid-cols-2 gap-2">{i.options.map((o) => (
                  <label key={o} className={`flex gap-2 items-start rounded-xl border p-3 text-sm cursor-pointer ${cur === o ? "border-primary bg-primary-soft/50" : "border-border hover:bg-background"}`}>
                    <input type="radio" name={i.id} checked={cur === o} onChange={() => run("issues.decide", { id: i.id, decision: o })} className="mt-0.5 h-4 w-4 accent-[var(--color-primary)]" /><span>{o}</span></label>))}</div></fieldset>
              {cur && e.decisions[i.id] && <p className="text-xs text-muted mt-2">Decided by {e.decisions[i.id].by}</p>}
            </Card></li>
          );
        })}
      </ul>
      {other.length > 0 && <details className="mt-6 rounded-xl border border-border bg-surface p-4"><summary className="cursor-pointer text-sm font-semibold">Other things we noticed ({other.length}), handled automatically</summary>
        <ul className="mt-3 text-sm text-muted space-y-1 list-disc pl-5">{other.map((i) => <li key={i.id}>{i.title}</li>)}</ul></details>}
      {!locked && <div className="mt-6"><Button onClick={async () => { if (await run("issues.complete", {}, "Decisions recorded")) next(); }} disabled={decided < need.length} busy={busy === "issues.complete"}>Continue</Button></div>}
    </>
  );
}
