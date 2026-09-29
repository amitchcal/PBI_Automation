"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Header } from "@/components/shell";
import { api } from "@/components/engagement";
import { Badge, Button, Card, Field, inputCls, PageTitle, Skeleton, useToast, fmtDate } from "@/components/ui";

interface Row { id: string; name: string; customer: string; mode: "demo" | "live"; created: string; doneCount: number; total: number; next: string }

export default function Engagements() {
  const [rows, setRows] = useState<Row[] | null>(null);
  const [name, setName] = useState("");
  const [customer, setCustomer] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const router = useRouter();
  const { toast } = useToast();

  useEffect(() => {
    api<{ engagements: Row[] }>("/api/engagements").then((d) => setRows(d.engagements)).catch((e) => toast("error", e.message));
  }, [toast]);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setErr("");
    try {
      const r = await api<{ engagement: { id: string } }>("/api/engagements", { method: "POST", json: { name, customer } });
      router.push(`/e/${r.engagement.id}`);
    } catch (x) { setErr((x as Error).message); } finally { setBusy(false); }
  }

  return (
    <div className="min-h-screen flex flex-col">
      <Header />
      <main id="main" className="mx-auto w-full max-w-5xl px-4 sm:px-6 py-8 flex-1">
        <PageTitle eyebrow="Your engagements" title="Choose where to work">
          Open the completed sample to see every step with real results, or start a new engagement with your own data.
        </PageTitle>
        <div className="grid gap-4 sm:grid-cols-2 mb-10">
          {!rows && [1, 2].map((i) => <Skeleton key={i} h="h-40" />)}
          {rows?.map((r) => (
            <Link key={r.id} href={`/e/${r.id}`} className="block group">
              <Card className="h-full group-hover:border-primary transition">
                <div className="flex items-start justify-between gap-3">
                  <h2 className="font-semibold text-lg leading-snug">{r.name}</h2>
                  <Badge tone={r.mode === "demo" ? "info" : "good"}>{r.mode === "demo" ? "Sample" : "Live"}</Badge>
                </div>
                <p className="text-sm text-muted mt-1">{r.customer} &middot; started {fmtDate(r.created)}</p>
                <div className="mt-5 h-2 rounded-full bg-background overflow-hidden"><div className="h-full bg-primary" style={{ width: `${(r.doneCount / r.total) * 100}%` }} /></div>
                <p className="text-sm mt-2"><span className="font-semibold">{r.doneCount} of {r.total}</span> steps done &middot; next: {r.next}</p>
              </Card>
            </Link>
          ))}
        </div>
        <Card>
          <h2 className="text-lg font-semibold mb-1">Start a new engagement</h2>
          <p className="text-sm text-muted mb-5">You will be asked to confirm the agreement before anything is uploaded.</p>
          <form onSubmit={create} className="grid sm:grid-cols-2 gap-x-6" noValidate>
            <Field label="Engagement name" htmlFor="n" error={err}>
              <input id="n" className={inputCls} value={name} onChange={(e) => setName(e.target.value)} placeholder="For example: Regional sales dashboard" />
            </Field>
            <Field label="Customer" htmlFor="c">
              <input id="c" className={inputCls} value={customer} onChange={(e) => setCustomer(e.target.value)} placeholder="Company name" />
            </Field>
            <div className="sm:col-span-2"><Button type="submit" busy={busy}>Create engagement</Button></div>
          </form>
        </Card>
      </main>
    </div>
  );
}
