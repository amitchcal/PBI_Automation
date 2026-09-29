"use client";
import { useState } from "react";
import Link from "next/link";
import { STEPS } from "@/lib/steps";
import { useEng, useRole } from "@/components/engagement";
import { Badge, Button, Card, Field, inputCls, Notice, PageTitle, useToast } from "@/components/ui";

function AccessCard() {
  const { data, run, busy } = useEng(); const { toast } = useToast(); const [name, setName] = useState("");
  const e = data!.engagement;
  async function invite() {
    const n = name.trim(); if (n.length < 2) { toast("error", "Type a name."); return; }
    if (await run("access.invite", { name: n }, `${n} can now view this engagement and leave draft feedback`)) setName("");
  }
  return (
    <Card className="mb-8">
      <h2 className="font-semibold mb-1">Who has access</h2>
      <p className="text-sm text-muted mb-4">You (the owner) can do everything. Anyone you add here can look around and leave feedback on the draft, but cannot change any step, upload files or run the build.</p>
      <div className="flex flex-wrap gap-2 mb-4">
        <span className="inline-flex items-center gap-1 rounded-full border border-border bg-background px-3 py-1.5 text-sm"><Badge tone="neutral">Owner</Badge>{e.owner}</span>
        {e.reviewers.map((r) => (
          <span key={r} className="inline-flex items-center gap-2 rounded-full border border-border bg-background px-3 py-1.5 text-sm">
            <Badge tone="warn">Reviewer</Badge>{r}
            <button type="button" onClick={() => run("access.remove", { name: r }, `${r} no longer has access`)} disabled={busy === "access.remove"} className="text-muted hover:text-negative" aria-label={`Remove ${r}`}>&times;</button>
          </span>
        ))}
      </div>
      <div className="flex flex-wrap items-end gap-3">
        <Field label="Add a reviewer by name" htmlFor="rv-name"><input id="rv-name" className={`${inputCls} sm:max-w-xs`} value={name} onChange={(ev) => setName(ev.target.value)} placeholder="Full name" /></Field>
        <Button kind="secondary" onClick={invite} busy={busy === "access.invite"}>Add</Button>
      </div>
    </Card>
  );
}

export default function Home() {
  const { id, data } = useEng(); const role = useRole();
  if (!data) return null;
  const e = data.engagement;
  const next = STEPS.find((s) => s.key === data.current);
  return (
    <>
      <PageTitle eyebrow={e.mode === "demo" ? "Sample engagement" : "Your engagement"} title={e.name}>
        {next ? "Every step is required and they run in order. You always see what is needed from you next." : "Every step is done. The engagement is complete."}
      </PageTitle>
      {role === "owner" && e.mode !== "demo" && <AccessCard />}
      {e.mode === "demo" && (
        <div className="mb-6">
          <Notice tone="info" title="You are looking at a completed sample">
            Steps 1 to 9 were recorded from the real RewardsNext build and are read-only. Steps 10 to 12 are open so you can try the review, acceptance and handover.
          </Notice>
        </div>
      )}
      {next ? (
        <Card className="mb-8 border-primary/40 bg-primary-soft/40">
          <p className="text-xs font-bold tracking-widest uppercase text-primary">Your next step</p>
          <h2 className="text-xl font-semibold mt-1">Step {next.n}: {next.title}</h2>
          <p className="text-muted mt-1 max-w-2xl">{next.blurb}</p>
          <Link href={`/e/${id}/${next.key}`} className="inline-flex mt-4 items-center rounded-xl bg-primary text-on-primary px-5 min-h-11 font-semibold hover:bg-primary-hover">Continue &rarr;</Link>
        </Card>
      ) : (
        <Card className="mb-8"><h2 className="text-xl font-semibold">All done</h2><p className="text-muted mt-1">Thank you. The activity log holds a record of everything that happened.</p></Card>
      )}
      <ol className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {STEPS.map((s) => {
          const st = data.statuses[s.key];
          const d = e.done[s.key];
          const body = (
            <Card className={`h-full ${st === "locked" ? "opacity-60" : "hover:border-primary transition"}`}>
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm font-bold text-muted">Step {s.n}</span>
                <Badge tone={st === "done" ? "good" : st === "open" ? "info" : "neutral"}>{st === "done" ? "Done" : st === "open" ? "Your turn" : "Locked"}</Badge>
              </div>
              <h3 className="font-semibold mt-2">{s.title}</h3>
              <p className="text-sm text-muted mt-1 leading-relaxed">{s.blurb}</p>
              <p className="text-xs text-muted mt-3">{s.who === "Automatic" ? "Automatic" : s.who === "Both" ? "You and us" : "You"} &middot; {s.minutes}{d?.note ? ` · ${d.note}` : ""}</p>
            </Card>
          );
          return <li key={s.key}>{st === "locked" ? <div aria-disabled="true">{body}</div> : <Link href={`/e/${id}/${s.key}`} className="block">{body}</Link>}</li>;
        })}
      </ol>
    </>
  );
}
