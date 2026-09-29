"use client";
import { useEffect, useMemo, useState } from "react";
import { api, useEng, useRole, EngData } from "@/components/engagement";
import { DoneBanner, useNext } from "@/components/steps-a";
import { useToast } from "@/components/ui";
import { Badge, Button, Card, Notice, PageTitle, Skeleton, fmtNum } from "@/components/ui";

// ---------------------------------------------------------------- 7 KPI definitions
interface Kpi { name: string; folder?: string; description: string; dax?: string; format?: string; example?: string }
export function KpisStep() {
  const { id, data, run, busy } = useEng(); const e = data!.engagement; const next = useNext("kpis");
  const role = useRole(); const locked = !!e.done.kpis || e.mode === "demo" || role === "reviewer";
  const [k, setK] = useState<Kpi[] | null>(null); const [q, setQ] = useState("");
  useEffect(() => { api<{ kpis: Kpi[] }>(`/api/e/${id}/view/kpis`).then((d) => setK(d.kpis)); }, [id]);
  const approved = k ? k.filter((x) => e.kpiApprovals[x.name]).length : 0;
  const shown = useMemo(() => (k || []).filter((x) => (x.name + x.description).toLowerCase().includes(q.toLowerCase())), [k, q]);
  async function all() { for (const x of k || []) if (!e.kpiApprovals[x.name]) await run("kpis.approve", { name: x.name }); }
  return (
    <>
      <PageTitle eyebrow="Step 7" title="KPI definitions">Every number that will appear in your report is defined here in plain words. Approve each one, or tell us what to change in the next steps.</PageTitle>
      <DoneBanner step="kpis" />
      {!k ? <div className="grid sm:grid-cols-2 gap-4">{[1, 2, 3, 4].map((i) => <Skeleton key={i} h="h-36" />)}</div> : (
        <>
          <div className="flex flex-wrap items-center gap-3 mb-5">
            <Badge tone={approved === k.length ? "good" : "info"}>{approved} of {k.length} approved</Badge>
            <input aria-label="Search KPIs" value={q} onChange={(ev) => setQ(ev.target.value)} placeholder="Search" className="rounded-xl border border-border bg-surface px-3 min-h-11 text-sm w-full sm:w-64" />
            {!locked && approved < k.length && <Button kind="secondary" onClick={all}>Approve all</Button>}
          </div>
          {k.length === 0 && <Notice tone="warn">No key numbers were listed in step 2. Go back and add them.</Notice>}
          <ul className="grid sm:grid-cols-2 gap-4">
            {shown.map((x) => {
              const ok = !!e.kpiApprovals[x.name];
              return (
                <li key={x.name}><Card className="h-full">
                  <div className="flex items-start justify-between gap-2"><h2 className="font-semibold leading-snug">{x.name}</h2>{ok ? <Badge tone="good">Approved</Badge> : <Badge tone="warn">To approve</Badge>}</div>
                  {x.folder && <p className="text-xs text-muted mt-0.5">{x.folder}</p>}
                  <p className="text-sm text-muted mt-2 leading-relaxed">{x.description || "No definition given. Add one in step 2."}</p>
                  {x.example && <p className="mt-3 text-sm"><span className="text-muted">Worked example on your data: </span><span className="font-semibold tabular">{x.example}</span></p>}
                  {x.dax && <details className="mt-3"><summary className="text-xs text-primary cursor-pointer">Formula, for the technically curious</summary><pre className="mt-2 text-xs bg-background rounded-lg p-2 overflow-x-auto">{x.dax}</pre></details>}
                  {!locked && <div className="mt-4"><Button kind={ok ? "quiet" : "secondary"} onClick={() => run("kpis.approve", { name: x.name, approve: !ok })}>{ok ? "Withdraw approval" : "Approve this definition"}</Button></div>}
                </Card></li>
              );
            })}
          </ul>
          {!locked && <div className="mt-6"><Button onClick={async () => { if (await run("kpis.complete", {}, "KPI definitions approved")) next(); }} disabled={approved < k.length || k.length === 0} busy={busy === "kpis.complete"}>Continue</Button></div>}
        </>
      )}
    </>
  );
}

// ---------------------------------------------------------------- 8 segments
interface SegView { available: boolean; dims: { name: string; rule: string; groups: { label: string; n: number }[] }[] }
export function SegmentsStep() {
  const { id, data, run, busy } = useEng(); const e = data!.engagement; const next = useNext("segments");
  const role = useRole(); const locked = !!e.done.segments || e.mode === "demo" || role === "reviewer";
  const [s, setS] = useState<SegView | null>(null);
  useEffect(() => { api<SegView>(`/api/e/${id}/view/segments`).then(setS); }, [id]);
  return (
    <>
      <PageTitle eyebrow="Step 8" title="Customer groups">Groups let you compare people, for example by age or income. Check that the groups make sense and that none is too small to trust.</PageTitle>
      <DoneBanner step="segments" />
      {!s ? <Skeleton h="h-56" /> : !s.available ? (
        <Card><Notice tone="info" title="No customer groups proposed yet">For a new engagement, groups are proposed from your data after the build stage profiles it. If you do not need groups in the first version, confirm below.</Notice>
          {!locked && <div className="mt-5"><Button onClick={async () => { if (await run("segments.approve", {}, "Recorded: no groups in the first version")) next(); }} busy={busy === "segments.approve"}>Continue without groups</Button></div>}</Card>
      ) : (
        <>
          <div className="grid lg:grid-cols-2 gap-4">
            {s.dims.map((d) => { const total = d.groups.reduce((a, g) => a + g.n, 0) || 1; const max = Math.max(...d.groups.map((g) => g.n), 1);
              return (
                <Card key={d.name}>
                  <h2 className="font-semibold">{d.name}</h2><p className="text-xs text-muted mb-3">{d.rule}</p>
                  <ul className="space-y-1.5">{d.groups.map((g) => (
                    <li key={g.label} className="grid grid-cols-[120px_1fr_86px] items-center gap-2 text-sm"><span className="truncate" title={g.label}>{g.label}</span>
                      <span className="h-3 rounded-full bg-background overflow-hidden" aria-hidden><span className="block h-full bg-primary rounded-full" style={{ width: `${(g.n / max) * 100}%` }} /></span>
                      <span className="text-right tabular text-muted">{fmtNum(g.n)}</span></li>))}</ul>
                  <p className="text-xs text-muted mt-3">Groups add up to {fmtNum(total)} customers. Every customer is in exactly one group.</p>
                </Card>
              ); })}
          </div>
          <div className="mt-4"><Notice tone="warn" title="One thing to know">Engagement groups are defined from completions, so their redemption rate is true by construction. Use them to describe customers, not to explain redemption.</Notice></div>
          {!locked && <div className="mt-6"><Button onClick={async () => { if (await run("segments.approve", {}, "Groups approved")) next(); }} busy={busy === "segments.approve"}>Approve these groups</Button></div>}
        </>
      )}
    </>
  );
}

// ---------------------------------------------------------------- 9 build
interface BuildView { available: boolean; ranAt?: string; reviewItems?: string[]; stages: { name: string; what: string; result: string; ok: boolean }[] }
export function BuildStep() {
  const { id, data, set, run, busy } = useEng(); const e = data!.engagement; const next = useNext("build"); const { toast } = useToast(); const role = useRole();
  const [b, setB] = useState<BuildView | null>(null);
  const [working, setWorking] = useState(false);
  const [checking, setChecking] = useState(false);
  useEffect(() => { api<BuildView>(`/api/e/${id}/view/build`).then(setB); }, [id]);
  const steps = [
    ["Read and profile the data", "Types, blanks, duplicates, hidden structure; raw totals captured."],
    ["Clean and shape the data", "Cleaning rules from your decisions; an independent copy of every table."],
    ["Build the model and measures", "Relationships, customer groups, KPI measures, all checked in Power BI."],
    ["Build the report", "Theme, pages, slicers, tooltips and drill-through from a specification."],
    ["Write the documents", "User guide, technical document and findings deck."],
  ];
  async function startBuild() {
    setWorking(true);
    try {
      const d = await api<EngData>(`/api/e/${id}/build`, { method: "POST" });
      set(d); setB(await api<BuildView>(`/api/e/${id}/view/build`));
      toast(d.engagement.build?.ok ? "ok" : "error", d.engagement.build?.ok ? "Build finished. Every stage passed." : "The build ran but a stage failed; see the list below.");
    } catch (x) { toast("error", (x as Error).message); } finally { setWorking(false); }
  }
  async function desktopCheck() {
    if (!window.confirm("This opens Power BI Desktop on the computer running this app, refreshes the project and runs its checks there. It takes a few minutes and will take over a Desktop window -- don't use that computer until it finishes. Continue?")) return;
    setChecking(true);
    try {
      const d = await api<EngData>(`/api/e/${id}/build/desktop-check`, { method: "POST" });
      set(d); toast(d.engagement.build?.desktopCheck?.ok ? "ok" : "error", d.engagement.build?.desktopCheck?.ok ? "Checked in Power BI Desktop. Everything passed." : "Checked in Power BI Desktop; something did not pass. See the details below.");
    } catch (x) { toast("error", (x as Error).message); } finally { setChecking(false); }
  }
  if (e.mode === "live") {
    const built = e.build; const dc = built?.desktopCheck;
    return (
      <>
        <PageTitle eyebrow="Step 9" title="Build">This runs the automated pipeline on your data: clean and shape it, build a model with measures, then a report. Checking the result in Power BI Desktop itself is a separate, explicit step below, because it takes over a Desktop window on this computer for a few minutes.</PageTitle>
        <DoneBanner step="build" />
        <Notice tone="info" title="What this first draft can do on its own">Without you writing any formulas, it can pass your files through as tables, detect relationships between them from matching values, and add a row-count and simple sum/average measure per number column. It cannot yet guess the KPI formulas from your needs form, or build customer groups -- those still need your builder&apos;s judgement, listed below as things to review.</Notice>
        <div className="mt-5">{role === "reviewer" ? <Notice tone="warn">Only the owner can run the build.</Notice> :
          <Button onClick={startBuild} busy={working} disabled={!!e.done.build}>{built ? "Run again" : "Run the automated build"}</Button>}</div>
        {!b ? <Skeleton h="h-40" /> : b.stages.length > 0 && (
          <ol className="mt-5 space-y-3">
            {b.stages.map((s, i) => (
              <li key={s.name}><Card className="flex gap-4 items-start">
                <span aria-hidden className={`h-8 w-8 rounded-full grid place-items-center text-sm font-bold shrink-0 ${s.ok ? "bg-positive text-white" : "bg-negative text-white"}`}>{s.ok ? "✓" : "!"}</span>
                <div className="min-w-0"><h2 className="font-semibold">{i + 1}. {s.name}</h2><p className="text-sm text-muted">{s.what}</p><p className="text-sm mt-1.5 font-medium">{s.result}</p></div>
              </Card></li>
            ))}
          </ol>
        )}
        {!!b?.reviewItems?.length && (
          <Card className="mt-5"><h2 className="font-semibold mb-2">Things to review before this goes further</h2>
            <ul className="text-sm space-y-1.5 list-disc pl-5">{b.reviewItems.map((it, i) => <li key={i}>{it}</li>)}</ul></Card>
        )}
        {built?.ok && (
          <Card className="mt-5">
            <h2 className="font-semibold">Check it in Power BI Desktop</h2>
            <p className="text-sm text-muted mt-1">The stages above are checked against independent numbers in Python. This step goes further: it opens the actual project in Power BI Desktop on this computer, refreshes it and runs the same checks there. Optional, but recommended before you rely on this draft.</p>
            {role !== "reviewer" && <div className="mt-3"><Button kind="secondary" onClick={desktopCheck} busy={checking}>{dc ? "Run again in Power BI Desktop" : "Run Power BI Desktop check"}</Button></div>}
            {dc && (
              <div className="mt-4 text-sm">
                <p className="font-medium flex items-center gap-2"><span aria-hidden className={`h-6 w-6 rounded-full grid place-items-center text-xs font-bold shrink-0 ${dc.ok ? "bg-positive text-white" : "bg-negative text-white"}`}>{dc.ok ? "✓" : "!"}</span>
                  {dc.modelChecks.passed} of {dc.modelChecks.total} checks passed in Desktop{dc.refreshSeconds ? `, refresh took ${Math.round(dc.refreshSeconds)}s` : ""}{dc.reportOpened ? "; the report opened too" : "; the report did not open"}.</p>
                {dc.error && <p className="text-negative mt-2">{dc.error}</p>}
                {!!dc.mismatches.length && <ul className="mt-2 space-y-1 list-disc pl-5 text-muted">{dc.mismatches.map((m, i) => <li key={i}>{m}</li>)}</ul>}
              </div>
            )}
          </Card>
        )}
        {!e.done.build && role !== "reviewer" && (
          <div className="mt-6"><Button onClick={async () => { if (await run("build.complete", {}, "Build recorded")) next(); }} disabled={!built?.ok} busy={busy === "build.complete"} title={built?.ok ? "" : "Run the automated build and make sure every stage passes"}>Continue</Button></div>
        )}
      </>
    );
  }
  return (
    <>
      <PageTitle eyebrow="Step 9" title="Build">This step runs by itself. Each stage is checked against independent numbers before the next one starts.</PageTitle>
      <DoneBanner step="build" />
      {!b ? <Skeleton h="h-64" /> : !b.available ? (
        <ol className="mt-5 space-y-3">{steps.map(([n, w], i) => <li key={n}><Card className="flex gap-4 items-start"><span aria-hidden className="h-8 w-8 rounded-full bg-background border border-border grid place-items-center text-sm font-bold text-muted shrink-0">{i + 1}</span><div><h2 className="font-semibold">{n}</h2><p className="text-sm text-muted">{w}</p></div></Card></li>)}</ol>
      ) : (
        <ol className="space-y-3">
          {b.stages.map((s, i) => (
            <li key={s.name}><Card className="flex gap-4 items-start">
              <span aria-hidden className={`h-8 w-8 rounded-full grid place-items-center text-sm font-bold shrink-0 ${s.ok ? "bg-positive text-white" : "bg-negative text-white"}`}>{s.ok ? "✓" : "!"}</span>
              <div className="min-w-0"><h2 className="font-semibold">{i + 1}. {s.name}</h2><p className="text-sm text-muted">{s.what}</p><p className="text-sm mt-1.5 font-medium">{s.result}</p></div>
            </Card></li>
          ))}
        </ol>
      )}
      <p className="text-sm text-muted mt-4">These results were recorded when the sample was built.</p>
    </>
  );
}
