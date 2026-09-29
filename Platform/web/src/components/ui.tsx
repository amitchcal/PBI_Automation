"use client";
import { createContext, useCallback, useContext, useState, ReactNode } from "react";

// ---------------------------------------------------------------- toasts
type Toast = { id: number; kind: "ok" | "error"; text: string };
const ToastCtx = createContext<{ toast: (kind: Toast["kind"], text: string) => void }>({ toast: () => {} });
export const useToast = () => useContext(ToastCtx);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const toast = useCallback((kind: Toast["kind"], text: string) => {
    const id = Date.now() + Math.random();
    setItems((x) => [...x, { id, kind, text }]);
    setTimeout(() => setItems((x) => x.filter((t) => t.id !== id)), kind === "error" ? 7000 : 3500);
  }, []);
  return (
    <ToastCtx.Provider value={{ toast }}>
      {children}
      <div aria-live="polite" className="fixed bottom-4 right-4 left-4 sm:left-auto z-50 flex flex-col gap-2 sm:w-96">
        {items.map((t) => (
          <div key={t.id} role="status"
            className={`rounded-xl px-4 py-3 text-sm shadow-card border flex gap-3 items-start bg-surface ${t.kind === "error" ? "border-negative/40" : "border-positive/40"}`}>
            <span aria-hidden className={`mt-1 h-2.5 w-2.5 rounded-full shrink-0 ${t.kind === "error" ? "bg-negative" : "bg-positive"}`} />
            <span>{t.text}</span>
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}

// ---------------------------------------------------------------- primitives
export function Card({ children, className = "", pad = true }: { children: ReactNode; className?: string; pad?: boolean }) {
  return <section className={`bg-surface border border-border rounded-2xl shadow-card ${pad ? "p-5 sm:p-6" : ""} ${className}`}>{children}</section>;
}

export function Button({ children, onClick, kind = "primary", disabled, busy, type = "button", className = "", title }:
  { children: ReactNode; onClick?: () => void; kind?: "primary" | "secondary" | "quiet" | "danger"; disabled?: boolean; busy?: boolean; type?: "button" | "submit"; className?: string; title?: string }) {
  const style = {
    primary: "bg-primary text-on-primary hover:bg-primary-hover",
    secondary: "bg-surface text-text border border-border hover:bg-background",
    quiet: "bg-transparent text-primary hover:bg-primary-soft",
    danger: "bg-negative text-white hover:opacity-90",
  }[kind];
  return (
    <button type={type} onClick={onClick} disabled={disabled || busy} title={title}
      className={`inline-flex items-center justify-center gap-2 rounded-xl px-4 min-h-11 text-sm font-semibold transition disabled:opacity-50 disabled:cursor-not-allowed ${style} ${className}`}>
      {busy && <span aria-hidden className="h-4 w-4 rounded-full border-2 border-current border-t-transparent animate-spin" />}
      {children}
    </button>
  );
}

export function Badge({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "good" | "warn" | "bad" | "info" }) {
  const t = { neutral: "bg-background text-muted border-border", good: "bg-positive/10 text-positive border-positive/30", warn: "bg-warning/10 text-warning border-warning/30", bad: "bg-negative/10 text-negative border-negative/30", info: "bg-primary-soft text-primary border-primary/30" }[tone];
  return <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold ${t}`}>{children}</span>;
}

export function PageTitle({ eyebrow, title, children }: { eyebrow?: string; title: string; children?: ReactNode }) {
  return (
    <header className="mb-6">
      {eyebrow && <p className="text-xs font-bold tracking-widest uppercase text-primary mb-1">{eyebrow}</p>}
      <h1 className="text-2xl sm:text-3xl font-semibold text-text">{title}</h1>
      {children && <p className="mt-2 text-muted max-w-3xl leading-relaxed">{children}</p>}
    </header>
  );
}

export function Field({ label, help, error, children, htmlFor }: { label: string; help?: string; error?: string; children: ReactNode; htmlFor: string }) {
  return (
    <div className="mb-5">
      <label htmlFor={htmlFor} className="block text-sm font-semibold mb-1">{label}</label>
      {help && <p id={`${htmlFor}-help`} className="text-sm text-muted mb-2">{help}</p>}
      {children}
      {error && <p role="alert" className="text-sm text-negative mt-1">{error}</p>}
    </div>
  );
}
export const inputCls = "w-full rounded-xl border border-border bg-surface px-3 py-2.5 text-sm min-h-11 focus:border-primary";

export function Skeleton({ h = "h-6", w = "w-full", className = "" }: { h?: string; w?: string; className?: string }) {
  return <div aria-hidden className={`skeleton ${h} ${w} ${className}`} />;
}
export function PageSkeleton() {
  return (
    <div aria-busy="true" aria-label="Loading">
      <Skeleton h="h-4" w="w-32" className="mb-3" /><Skeleton h="h-9" w="w-2/3" className="mb-4" /><Skeleton h="h-4" w="w-1/2" className="mb-8" />
      <div className="grid gap-4 sm:grid-cols-2"><Skeleton h="h-32" /><Skeleton h="h-32" /><Skeleton h="h-32" /><Skeleton h="h-32" /></div>
    </div>
  );
}

export function Notice({ tone = "info", title, children }: { tone?: "info" | "warn" | "bad" | "good"; title?: string; children: ReactNode }) {
  const t = { info: "border-primary/30 bg-primary-soft", warn: "border-warning/40 bg-warning/10", bad: "border-negative/40 bg-negative/10", good: "border-positive/40 bg-positive/10" }[tone];
  return (
    <div role={tone === "bad" ? "alert" : "note"} className={`rounded-xl border px-4 py-3 text-sm leading-relaxed ${t}`}>
      {title && <p className="font-semibold mb-0.5">{title}</p>}
      <div>{children}</div>
    </div>
  );
}

export const fmtDate = (iso?: string) => (iso ? new Date(iso).toLocaleString("en-GB", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "");
export const fmtNum = (n: number) => n.toLocaleString("en-US");
export const fmtSize = (b: number) => (b > 1e6 ? `${(b / 1e6).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1e3))} KB`);
