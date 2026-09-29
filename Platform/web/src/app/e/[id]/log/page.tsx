"use client";
import { useEffect, useState } from "react";
import { api, useEng } from "@/components/engagement";
import { Card, PageTitle, Skeleton, fmtDate } from "@/components/ui";

interface Entry { ts: string; actor: string; action: string; detail: string }

export default function Log() {
  const { id } = useEng();
  const [rows, setRows] = useState<Entry[] | null>(null);
  const [q, setQ] = useState("");
  useEffect(() => { api<{ entries: Entry[] }>(`/api/e/${id}/view/audit`).then((d) => setRows(d.entries)); }, [id]);
  const shown = (rows || []).filter((r) => (r.action + r.detail + r.actor).toLowerCase().includes(q.toLowerCase()));
  return (
    <>
      <PageTitle eyebrow="Activity" title="Everything that happened">
        Every decision, upload and approval is recorded with who and when. The log can be read and searched but not edited.
      </PageTitle>
      <input aria-label="Search the activity log" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search"
        className="w-full sm:w-80 mb-4 rounded-xl border border-border bg-surface px-3 min-h-11 text-sm" />
      <Card pad={false}>
        {!rows ? <div className="p-5 space-y-3">{[1, 2, 3, 4].map((i) => <Skeleton key={i} h="h-8" />)}</div>
          : shown.length === 0 ? <p className="p-6 text-muted">Nothing matches.</p> : (
            <ul className="divide-y divide-border">
              {shown.map((r, i) => (
                <li key={i} className="px-5 py-3 grid sm:grid-cols-[190px_170px_1fr] gap-x-4 gap-y-0.5 text-sm">
                  <span className="text-muted tabular">{fmtDate(r.ts)}</span>
                  <span className="font-semibold">{r.actor}</span>
                  <span><span className="font-medium">{r.action}</span>{r.detail && <span className="text-muted"> &middot; {r.detail}</span>}</span>
                </li>
              ))}
            </ul>
          )}
      </Card>
    </>
  );
}
