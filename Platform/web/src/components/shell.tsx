"use client";
import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { STEPS } from "@/lib/steps";
import { useEng, useRole } from "@/components/engagement";
import { Badge, PageSkeleton } from "@/components/ui";

export function Header({ right }: { right?: React.ReactNode }) {
  return (
    <header className="bg-secondary text-on-secondary">
      <div className="mx-auto max-w-[1400px] px-4 sm:px-6 h-16 flex items-center justify-between gap-4">
        <Link href="/engagements" className="flex items-center gap-3 min-h-11" aria-label="Meridian Insight Studio, all engagements">
          <Image src="/brand/logo-mark.png" alt="" width={34} height={34} priority />
          <span className="font-semibold text-[15px] leading-tight">Meridian<span className="hidden sm:inline"> Insight Studio</span></span>
        </Link>
        <div className="flex items-center gap-3 text-sm">{right}</div>
      </div>
    </header>
  );
}

function StepList({ onNavigate }: { onNavigate?: () => void }) {
  const { id, data } = useEng(); const path = usePathname();
  if (!data) return null;
  return (
    <nav aria-label="Steps">
      <ol className="space-y-1">
        {STEPS.map((s) => {
          const st = data.statuses[s.key]; const active = path === `/e/${id}/${s.key}`; const locked = st === "locked";
          const dot = st === "done" ? "bg-positive text-white" : st === "open" ? "bg-primary text-on-primary" : "bg-background text-muted border border-border";
          const inner = (
            <>
              <span aria-hidden className={`h-7 w-7 shrink-0 rounded-full grid place-items-center text-xs font-bold ${dot}`}>{st === "done" ? "✓" : s.n}</span>
              <span className="min-w-0 flex-1"><span className="block text-sm font-semibold leading-tight truncate">{s.title}</span>
                <span className="block text-xs text-muted">{st === "done" ? "Done" : st === "open" ? "Your turn" : "Locked"}</span></span>
            </>
          );
          return (
            <li key={s.key}>
              {locked ? (
                <div aria-disabled="true" title={`Finish step ${s.n - 1} first`} className="flex items-center gap-3 rounded-xl px-3 py-2 opacity-55 cursor-not-allowed">{inner}</div>
              ) : (
                <Link href={`/e/${id}/${s.key}`} onClick={onNavigate} aria-current={active ? "step" : undefined}
                  className={`flex items-center gap-3 rounded-xl px-3 py-2 transition ${active ? "bg-primary-soft" : "hover:bg-background"}`}>{inner}</Link>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

export function Shell({ children }: { children: React.ReactNode }) {
  const { id, data, error } = useEng(); const path = usePathname(); const [open, setOpen] = useState(false);
  const role = useRole();
  const cur = STEPS.find((s) => path === `/e/${id}/${s.key}`);
  const done = data ? STEPS.filter((s) => data.statuses[s.key] === "done").length : 0;
  return (
    <div className="min-h-screen flex flex-col">
      <Header right={<>
        {data && <Badge tone={data.engagement.mode === "demo" ? "info" : "good"}>{data.engagement.mode === "demo" ? "Sample" : "Live"}</Badge>}
        {data && data.engagement.mode !== "demo" && role && <Badge tone={role === "owner" ? "neutral" : "warn"}>{role === "owner" ? "Owner" : "Reviewer"}</Badge>}
        <Link href={`/e/${id}/log`} className="underline underline-offset-4 decoration-white/40 hover:decoration-white min-h-11 inline-flex items-center">Activity</Link>
      </>} />
      <div className="mx-auto w-full max-w-[1400px] flex-1 px-4 sm:px-6 py-5 lg:py-8 grid lg:grid-cols-[288px_1fr] gap-6 lg:gap-10">
        <aside className="lg:sticky lg:top-6 lg:self-start">
          <div className="lg:hidden mb-3">
            <button onClick={() => setOpen(!open)} aria-expanded={open} className="w-full flex items-center justify-between rounded-xl border border-border bg-surface px-4 min-h-12 text-sm font-semibold">
              <span>{cur ? `Step ${cur.n} of ${STEPS.length}: ${cur.title}` : "All steps"}</span><span aria-hidden>{open ? "−" : "+"}</span>
            </button>
            {open && <div className="mt-2 rounded-2xl border border-border bg-surface p-2"><StepList onNavigate={() => setOpen(false)} /></div>}
          </div>
          <div className="hidden lg:block rounded-2xl border border-border bg-surface p-3 shadow-card">
            <div className="px-3 pt-2 pb-3">
              <p className="text-xs uppercase tracking-widest font-bold text-muted">Engagement</p>
              <p className="font-semibold leading-snug mt-1">{data?.engagement.name ?? " "}</p>
              <div className="mt-3 h-2 rounded-full bg-background overflow-hidden" role="progressbar" aria-valuenow={done} aria-valuemin={0} aria-valuemax={STEPS.length} aria-label="Steps done">
                <div className="h-full bg-primary transition-all" style={{ width: `${(done / STEPS.length) * 100}%` }} /></div>
              <p className="text-xs text-muted mt-1.5">{done} of {STEPS.length} steps done</p>
              {role === "reviewer" && data?.engagement.mode !== "demo" && <p className="text-xs text-muted mt-2 leading-relaxed">You&apos;re a reviewer here: look around and leave feedback on the draft, but every step stays with the owner.</p>}
            </div>
            <StepList />
          </div>
        </aside>
        <main id="main" className="min-w-0">
          {error ? <div role="alert" className="rounded-xl border border-negative/40 bg-negative/10 p-4 text-sm">{error} <Link href="/engagements" className="underline">Back to engagements</Link></div>
            : !data ? <PageSkeleton /> : children}
        </main>
      </div>
    </div>
  );
}
