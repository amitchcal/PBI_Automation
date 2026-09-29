"use client";
/* eslint-disable @next/next/no-img-element */
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ACCEPTANCE_ITEMS, HANDOVER_ITEMS } from "@/lib/steps";
import { api, useEng, useRole } from "@/components/engagement";
import { DoneBanner, useNext } from "@/components/steps-a";
import { Badge, Button, Card, Field, inputCls, Notice, PageTitle, Skeleton, fmtDate } from "@/components/ui";

const PAGES = [["pages-overview", "Overview"], ["pages-funnel", "Offer Funnel"], ["pages-segmentation", "Customer Segmentation"], ["pages-performance", "Offer Performance"], ["pages-behavior", "Transaction Behavior"]];

interface Check { check: string; expected: unknown; actual: unknown; pass: boolean }
function Checks({ id }: { id: string }) {
  const [c, setC] = useState<{ available: boolean; rows: Check[]; refreshSeconds?: number } | null>(null);
  const [q, setQ] = useState(""); const [only, setOnly] = useState<"all" | "fail">("all"); const [open, setOpen] = useState(false);
  useEffect(() => { api<{ available: boolean; rows: Check[]; refreshSeconds?: number }>(`/api/e/${id}/view/checks`).then(setC); }, [id]);
  const shown = useMemo(() => (c?.rows || []).filter((r) => r.check.toLowerCase().includes(q.toLowerCase()) && (only === "all" || !r.pass)), [c, q, only]);
  if (!c) return <Skeleton h="h-24" />;
  if (!c.available) return <Notice>The checks appear here after the build.</Notice>;
  const pass = c.rows.filter((r) => r.pass).length;
  return (
    <div>
      <div className="flex flex-wrap items-center gap-3">
        <Badge tone={pass === c.rows.length ? "good" : "bad"}>{pass} of {c.rows.length} checks passed</Badge>
        <span className="text-sm text-muted">Each check compares a number in the report with one calculated independently. Full refresh {Math.round(c.refreshSeconds || 0)} seconds.</span>
        <Button kind="quiet" onClick={() => setOpen(!open)}>{open ? "Hide the list" : "Show every check"}</Button>
      </div>
      {open && (
        <div className="mt-4">
          <div className="flex flex-wrap gap-3 mb-3"><input aria-label="Search checks" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search" className="rounded-xl border border-border bg-surface px-3 min-h-11 text-sm w-full sm:w-72" />
            <select aria-label="Filter" value={only} onChange={(e) => setOnly(e.target.value as "all" | "fail")} className="rounded-xl border border-border bg-surface px-3 min-h-11 text-sm"><option value="all">All checks</option><option value="fail">Only failures</option></select></div>
          <div className="max-h-96 overflow-auto rounded-xl border border-border"><table className="w-full text-sm"><thead className="sticky top-0 bg-background text-left text-muted"><tr><th className="px-3 py-2 font-semibold">Check</th><th className="px-3 py-2 font-semibold text-right">Expected</th><th className="px-3 py-2 font-semibold text-right">In the report</th><th className="px-3 py-2 font-semibold">Result</th></tr></thead>
            <tbody className="divide-y divide-border">{shown.slice(0, 300).map((r, i) => <tr key={i}><td className="px-3 py-2">{r.check}</td><td className="px-3 py-2 text-right tabular">{String(r.expected)}</td><td className="px-3 py-2 text-right tabular">{String(r.actual ?? "")}</td><td className="px-3 py-2"><Badge tone={r.pass ? "good" : "bad"}>{r.pass ? "Pass" : "Fail"}</Badge></td></tr>)}</tbody></table>
            {shown.length === 0 && <p className="p-4 text-sm text-muted">No checks match.</p>}</div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- 10 draft review
export function ReviewStep() {
  const { id, data, run, busy } = useEng(); const e = data!.engagement; const next = useNext("review");
  // The feedback form and "finish the review" only appear for the demo below (the draft pack isn't wired up for a
  // live engagement in this prototype yet), and the demo's steps 10-12 are deliberately open to any visitor to
  // try -- so no reviewer-vs-owner gate belongs here; see act()'s own demo exemption for the server-side match.
  const locked = !!e.done.review; const demo = e.mode === "demo";
  const [qs, setQs] = useState<{ id: string; title: string; text: string; proposed: string }[]>([]); const [docs, setDocs] = useState<{ key: string; label: string }[]>([]);
  const [text, setText] = useState(""); const [page, setPage] = useState("General"); const [none, setNone] = useState(false);
  useEffect(() => { api<{ questions: typeof qs }>(`/api/e/${id}/view/questions`).then((d) => setQs(d.questions)); api<{ files: typeof docs }>(`/api/e/${id}/view/docs`).then((d) => setDocs(d.files)); }, [id]);
  async function add(ev: React.FormEvent) { ev.preventDefault(); if (await run("review.feedback", { text, page }, "Feedback logged")) setText(""); }
  return (
    <>
      <PageTitle eyebrow="Step 10" title="Draft review">Here is the first draft with the evidence behind it. Look through it, then tell us what to change.</PageTitle>
      <DoneBanner step="review" />
      {!demo && <Notice tone="warn" title="Nothing to review yet">The draft appears here after the build stage, which is not connected in this prototype. Open the sample to see a real draft pack.</Notice>}
      {demo && (
        <div className="space-y-6">
          <Card>
            <h2 className="font-semibold text-lg mb-1">The report, page by page</h2><p className="text-sm text-muted mb-4">Five pages, plus two drill-through pages and two hover cards. Select a picture to open it larger.</p>
            <ul className="grid sm:grid-cols-2 xl:grid-cols-3 gap-4">{PAGES.map(([k, label]) => (
              <li key={k}><a href={`/api/e/${id}/file/${k}`} target="_blank" rel="noreferrer" className="block group"><figure>{/* eslint-disable-next-line @next/next/no-img-element */}<img src={`/api/e/${id}/file/${k}`} alt={`${label} page of the report`} loading="lazy" className="rounded-xl border border-border group-hover:border-primary w-full" /><figcaption className="text-sm font-semibold mt-1.5">{label}</figcaption></figure></a></li>))}
              {[["evidence-tooltip", "Hover card on a chart"], ["evidence-drill", "Drill-through to one offer"]].map(([k, label]) => (
                <li key={k}><a href={`/api/e/${id}/file/${k}`} target="_blank" rel="noreferrer" className="block group"><figure>{/* eslint-disable-next-line @next/next/no-img-element */}<img src={`/api/e/${id}/file/${k}`} alt={label} loading="lazy" className="rounded-xl border border-border group-hover:border-primary w-full" /><figcaption className="text-sm font-semibold mt-1.5">{label}</figcaption></figure></a></li>))}
            </ul>
          </Card>
          <Card><h2 className="font-semibold text-lg mb-3">The checks</h2><Checks id={id} /></Card>
          <Card>
            <h2 className="font-semibold text-lg mb-3">Open questions we need you to look at</h2>
            <ul className="space-y-3">{qs.map((q) => <li key={q.id} className="rounded-xl border border-border p-4"><div className="flex items-start justify-between gap-3"><h3 className="font-semibold text-sm">{q.title}</h3><Badge tone="warn">Open</Badge></div><p className="text-sm text-muted mt-1 leading-relaxed">{q.text}</p><p className="text-xs mt-2"><span className="font-semibold">Proposed:</span> {q.proposed}</p></li>)}</ul>
          </Card>
          <Card><h2 className="font-semibold text-lg mb-3">Documents</h2>
            <ul className="grid sm:grid-cols-3 gap-3">{docs.map((d) => <li key={d.key}><a href={`/api/e/${id}/file/${d.key}`} className="flex items-center justify-between gap-2 rounded-xl border border-border p-4 text-sm font-semibold hover:border-primary hover:bg-background">{d.label}<span aria-hidden className="text-primary">{"↓"}</span></a></li>)}</ul></Card>
        </div>
      )}
      {demo && (
        <Card className="mt-6">
          <h2 className="font-semibold text-lg mb-1">Your feedback</h2><p className="text-sm text-muted mb-4">Each note becomes a change item. We tell you what it affects and re-run every check after changes.</p>
          {e.feedback.length > 0 && <ul className="mb-5 divide-y divide-border rounded-xl border border-border">{e.feedback.map((f) => <li key={f.id} className="p-3 text-sm"><div className="flex justify-between gap-2"><span className="font-semibold">{f.id} &middot; {f.page}</span><Badge>{f.status}</Badge></div><p className="text-muted mt-1">{f.text}</p><p className="text-xs text-muted mt-1">{f.by}, {fmtDate(f.at)}</p></li>)}</ul>}
          {!locked && (
            <form onSubmit={add} noValidate>
              <div className="grid sm:grid-cols-[220px_1fr] gap-x-4">
                <Field label="About" htmlFor="fp"><select id="fp" className={inputCls} value={page} onChange={(ev) => setPage(ev.target.value)}>{["General", ...PAGES.map((p) => p[1]), "Numbers or definitions", "Documents"].map((p) => <option key={p}>{p}</option>)}</select></Field>
                <Field label="What should change?" htmlFor="ft"><textarea id="ft" rows={3} className={inputCls} value={text} onChange={(ev) => setText(ev.target.value)} placeholder="Describe it in your own words" /></Field></div>
              <Button type="submit" kind="secondary" busy={busy === "review.feedback"}>Add feedback</Button>
            </form>
          )}
          {!locked && (
            <div className="mt-6 pt-5 border-t border-border">
              {e.feedback.length === 0 && <label className="flex gap-2 items-center text-sm mb-4"><input type="checkbox" checked={none} onChange={(ev) => setNone(ev.target.checked)} className="h-4 w-4 accent-[var(--color-primary)]" />I have looked through the draft and have no changes.</label>}
              <Button onClick={async () => { if (await run("review.complete", { noChanges: none }, "Review recorded")) next(); }} disabled={!e.feedback.length && !none} busy={busy === "review.complete"}>Finish the review</Button>
            </div>
          )}
        </Card>
      )}
    </>
  );
}

// ---------------------------------------------------------------- 11 and 12 checklists
function Checklist({ step, items, type, title, intro, button, done, doneText }: { step: "accept" | "publish"; items: string[]; type: string; title: string; intro: string; button: string; done?: { ticks: boolean[]; name: string }; doneText: string }) {
  const { data, run, busy } = useEng(); const e = data!.engagement; const next = useNext(step); const role = useRole();
  // Demo mode's steps 10-12 are deliberately open for a visitor to try (everyone resolves as "reviewer" there);
  // a real reviewer on a live engagement gets the fieldset disabled here too, not just rejected on submit.
  const locked = !!e.done[step] || (role === "reviewer" && e.mode !== "demo"); const [ticks, setTicks] = useState<boolean[]>(done?.ticks ?? items.map(() => false)); const [name, setName] = useState(done?.name ?? "");
  return (
    <>
      <PageTitle eyebrow={step === "accept" ? "Step 11" : "Step 12"} title={title}>{intro}</PageTitle>
      <DoneBanner step={step} />
      <Card>
        <fieldset disabled={locked}>
          <legend className="text-sm font-semibold mb-3">{doneText}</legend>
          <ul className="space-y-3 mb-6">{items.map((t, i) => (
            <li key={i}><label className="flex gap-3 items-start rounded-xl border border-border p-4 cursor-pointer hover:bg-background has-[:checked]:border-primary has-[:checked]:bg-primary-soft/50">
              <input type="checkbox" checked={ticks[i]} onChange={(ev) => setTicks(ticks.map((x, k) => (k === i ? ev.target.checked : x)))} className="mt-1 h-5 w-5 accent-[var(--color-primary)]" /><span className="text-sm leading-relaxed">{t}</span></label></li>))}</ul>
          <Field label="Your full name" htmlFor={`${step}-n`} help="Typing your name is your sign-off."><input id={`${step}-n`} className={`${inputCls} sm:max-w-sm`} value={name} onChange={(ev) => setName(ev.target.value)} autoComplete="name" /></Field>
        </fieldset>
        {!locked && <Button onClick={async () => { if (await run(type, { ticks, name }, "Recorded")) next(); }} busy={busy === type}>{button}</Button>}
      </Card>
    </>
  );
}
export const AcceptStep = () => { const { data } = useEng(); return <Checklist step="accept" items={ACCEPTANCE_ITEMS} type="accept.complete" title="Acceptance" intro="Before final sign-off, please check the key numbers against a source you trust. Your ticks and name are the sign-off." button="Sign off" done={data!.engagement.acceptance} doneText="I confirm that" />; };

export function PublishStep() {
  const { id, data } = useEng(); const e = data!.engagement; const [docs, setDocs] = useState<{ key: string; label: string }[]>([]);
  useEffect(() => { api<{ files: typeof docs }>(`/api/e/${id}/view/docs`).then((d) => setDocs(d.files)); }, [id]);
  return (
    <>
      <Checklist step="publish" items={HANDOVER_ITEMS} type="publish.complete" title="Publish and hand over" intro="The last step. Publishing happens in your own workspace. Please test as a viewer, then confirm that everything is in place." button="Confirm handover" done={e.handover} doneText="We confirm that" />
      {e.done.publish && (
        <Card className="mt-6 border-positive/40 bg-positive/5"><h2 className="text-lg font-semibold">The engagement is complete</h2><p className="text-sm text-muted mt-1">Thank you. Your handover pack is below, and the activity log keeps the full record.</p>
          <ul className="grid sm:grid-cols-3 gap-3 mt-4">{docs.map((d) => <li key={d.key}><a href={`/api/e/${id}/file/${d.key}`} className="flex items-center justify-between gap-2 rounded-xl border border-border bg-surface p-4 text-sm font-semibold hover:border-primary">{d.label}<span aria-hidden className="text-primary">{"↓"}</span></a></li>)}</ul>
          <p className="mt-4 text-sm"><Link href={`/e/${id}/log`} className="text-primary underline">Open the activity log</Link></p></Card>
      )}
    </>
  );
}
