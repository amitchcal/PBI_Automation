"use client";
import { createContext, useCallback, useContext, useEffect, useState, ReactNode } from "react";
import type { Engagement, Role, StepKey } from "@/lib/steps";
import { roleOf } from "@/lib/steps";
import { useToast } from "@/components/ui";

export type Status = "done" | "open" | "locked";
export interface EngData { engagement: Engagement; statuses: Record<StepKey, Status>; current: StepKey | null }

export const actorName = () => (typeof window !== "undefined" && localStorage.getItem("actor")) || "Amit Chakraborty";

export async function api<T = unknown>(url: string, init?: RequestInit & { json?: unknown }): Promise<T> {
  const headers: Record<string, string> = { "x-actor": actorName() };
  let body = init?.body;
  if (init?.json !== undefined) { headers["content-type"] = "application/json"; body = JSON.stringify(init.json); }
  const res = await fetch(url, { ...init, headers: { ...headers, ...(init?.headers as Record<string, string>) }, body, cache: "no-store" });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || data.ok === false) throw new Error(data.error || "Something went wrong. Please try again.");
  return data as T;
}

interface Ctx { id: string; data: EngData | null; error: string | null; reload: () => Promise<void>; set: (d: EngData) => void;
  run: (type: string, payload?: Record<string, unknown>, ok?: string) => Promise<boolean>; busy: string | null }
const C = createContext<Ctx | null>(null);
export const useEng = () => { const c = useContext(C); if (!c) throw new Error("useEng outside provider"); return c; };

// Story W-03: the current viewer's role on this engagement, for the UI to soften itself around (the server is
// still what actually enforces it -- see act() and every mutating route).
export function useRole(): Role | null {
  const { data } = useEng(); if (!data) return null;
  return roleOf(data.engagement, actorName());
}

export function EngagementProvider({ id, children }: { id: string; children: ReactNode }) {
  const [data, setData] = useState<EngData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const { toast } = useToast();
  const reload = useCallback(async () => {
    try { setData(await api<EngData>(`/api/e/${id}`)); setError(null); } catch (e) { setError((e as Error).message); }
  }, [id]);
  useEffect(() => {
    let alive = true;
    api<EngData>(`/api/e/${id}`).then((d) => { if (alive) { setData(d); setError(null); } }).catch((e: Error) => { if (alive) setError(e.message); });
    return () => { alive = false; };
  }, [id]);
  const run = useCallback(async (type: string, payload: Record<string, unknown> = {}, ok?: string) => {
    setBusy(type);
    try { setData(await api<EngData>(`/api/e/${id}/act`, { method: "POST", json: { type, ...payload } })); if (ok) toast("ok", ok); return true; }
    catch (e) { toast("error", (e as Error).message); return false; }
    finally { setBusy(null); }
  }, [id, toast]);
  return <C.Provider value={{ id, data, error, reload, set: setData, run, busy }}>{children}</C.Provider>;
}
