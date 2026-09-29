"use client";
/* eslint-disable @next/next/no-img-element */
import { useState } from "react";
import { useRouter } from "next/navigation";
import { CONSENT_STATEMENTS, QUESTIONNAIRE, REQUIRED_Q, STEPS, StepKey } from "@/lib/steps";
import { api, useEng, useRole, EngData } from "@/components/engagement";
import { Badge, Button, Card, Field, inputCls, Notice, PageTitle, useToast, fmtDate } from "@/components/ui";

export function useNext(from: StepKey) {
  const { id } = useEng(); const router = useRouter();
  return () => { const i = STEPS.findIndex((s) => s.key === from); router.push(i + 1 < STEPS.length ? `/e/${id}/${STEPS[i + 1].key}` : `/e/${id}`); };
}

export function DoneBanner({ step }: { step: StepKey }) {
  const { data } = useEng(); const d = data!.engagement.done[step];
  if (!d) return null;
  return <div className="mb-5"><Notice tone="good" title="This step is done">Recorded by {d.by} on {fmtDate(d.at)}{d.note ? `. ${d.note}` : ""}.</Notice></div>;
}

// ---------------------------------------------------------------- 1 consent
export function ConsentStep() {
  const { data, run, busy } = useEng(); const e = data!.engagement; const next = useNext("consent");
  const role = useRole(); const locked = !!e.done.consent || e.mode === "demo" || role === "reviewer";
  const [ticks, setTicks] = useState<boolean[]>(e.consent?.ticks ?? CONSENT_STATEMENTS.map(() => false));
  const [name, setName] = useState(e.consent?.name ?? "");
  async function submit(ev: React.FormEvent) { ev.preventDefault(); if (await run("consent.complete", { ticks, name }, "Agreement recorded")) next(); }
  return (
    <>
      <PageTitle eyebrow="Step 1" title="Agreement">Before anything is uploaded, please confirm the terms below. Your ticks and name are recorded in the activity log.</PageTitle>
      <DoneBanner step="consent" />
      <Card>
        <form onSubmit={submit} noValidate>
          <fieldset disabled={locked}>
            <legend className="text-sm font-semibold mb-3">I confirm that</legend>
            <ul className="space-y-3 mb-6">
              {CONSENT_STATEMENTS.map((t, i) => (
                <li key={i}><label className="flex gap-3 items-start rounded-xl border border-border p-4 cursor-pointer hover:bg-background has-[:checked]:border-primary has-[:checked]:bg-primary-soft/50">
                  <input type="checkbox" checked={ticks[i]} onChange={(ev) => setTicks(ticks.map((x, k) => (k === i ? ev.target.checked : x)))} className="mt-1 h-5 w-5 accent-[var(--color-primary)]" />
                  <span className="text-sm leading-relaxed">{t}</span></label></li>
              ))}
            </ul>
            <Field label="Your full name" htmlFor="cn" help="Typing your name is your signature for this agreement."><input id="cn" className={`${inputCls} sm:max-w-sm`} value={name} onChange={(ev) => setName(ev.target.value)} autoComplete="name" /></Field>
          </fieldset>
          {!locked && <Button type="submit" busy={busy === "consent.complete"}>I agree and continue</Button>}
        </form>
      </Card>
      <p className="text-sm text-muted mt-4">Wording here is a template. Replace it with the wording your legal team approves.</p>
    </>
  );
}

// ---------------------------------------------------------------- 2 questionnaire
export function QuestionnaireStep() {
  const { data, run, busy } = useEng(); const e = data!.engagement; const next = useNext("questionnaire");
  const role = useRole(); const locked = !!e.done.questionnaire || e.mode === "demo" || role === "reviewer";
  const [vals, setVals] = useState<Record<string, string>>(e.questionnaire);
  const [sec, setSec] = useState(0); const [missing, setMissing] = useState<string[]>([]);
  const S = QUESTIONNAIRE[sec]; const last = sec === QUESTIONNAIRE.length - 1;
  const set = (k: string, v: string) => { setVals({ ...vals, [k]: v }); setMissing(missing.filter((m) => m !== k)); };
  const secMissing = (s: typeof S) => s.fields.filter((f) => f.required && !(vals[f.key] || "").trim()).map((f) => f.key);
  async function go() {
    const m = secMissing(S); if (m.length) { setMissing(m); return; }
    if (last) { const all = REQUIRED_Q.filter((k) => !(vals[k] || "").trim()); if (all.length) { setMissing(all); return; } if (await run("questionnaire.complete", { values: vals }, "Your answers are saved")) next(); }
    else if (await run("questionnaire.save", { values: vals })) setSec(sec + 1);
  }
  const answered = (s: typeof S) => s.fields.filter((f) => f.required).every((f) => (vals[f.key] || "").trim());
  return (
    <>
      <PageTitle eyebrow="Step 2" title="Your needs">Plain answers are fine. Fields marked required are needed to build the report; everything else helps us do it better.</PageTitle>
      <DoneBanner step="questionnaire" />
      <div className="flex gap-2 mb-5 overflow-x-auto pb-1" role="tablist" aria-label="Sections">
        {QUESTIONNAIRE.map((s, i) => (
          <button key={s.id} role="tab" aria-selected={i === sec} onClick={() => setSec(i)} className={`shrink-0 rounded-full px-4 min-h-10 text-sm font-semibold border ${i === sec ? "bg-primary text-on-primary border-primary" : "bg-surface border-border text-muted hover:text-text"}`}>
            {answered(s) && <span aria-hidden className="mr-1">{"✓"}</span>}{s.title}</button>
        ))}
      </div>
      <Card>
        <h2 className="text-lg font-semibold">{S.title}</h2><p className="text-sm text-muted mb-5">{S.intro}</p>
        <fieldset disabled={locked}>
          {S.fields.map((f) => {
            const err = missing.includes(f.key) ? "This answer is required." : undefined; const idf = `q-${f.key}`;
            return (
              <Field key={f.key} htmlFor={idf} label={`${f.label}${f.required ? " (required)" : ""}`} help={f.help} error={err}>
                {f.type === "textarea" ? <textarea id={idf} rows={4} className={inputCls} value={vals[f.key] || ""} placeholder={f.placeholder} onChange={(ev) => set(f.key, ev.target.value)} aria-invalid={!!err} />
                  : f.type === "select" ? <select id={idf} className={inputCls} value={vals[f.key] || ""} onChange={(ev) => set(f.key, ev.target.value)} aria-invalid={!!err}><option value="">Choose</option>{f.options!.map((o) => <option key={o}>{o}</option>)}</select>
                  : <input id={idf} className={inputCls} value={vals[f.key] || ""} onChange={(ev) => set(f.key, ev.target.value)} aria-invalid={!!err} />}
              </Field>
            );
          })}
        </fieldset>
        <div className="flex flex-wrap gap-3 items-center">
          {sec > 0 && <Button kind="secondary" onClick={() => setSec(sec - 1)}>Back</Button>}
          {locked ? (last ? null : <Button onClick={() => setSec(sec + 1)}>Next</Button>) : <Button onClick={go} busy={!!busy && busy.startsWith("questionnaire")}>{last ? "Finish and continue" : "Save and continue"}</Button>}
          <span className="text-sm text-muted">Section {sec + 1} of {QUESTIONNAIRE.length}</span>
        </div>
      </Card>
    </>
  );
}

// ---------------------------------------------------------------- 3 brand
const FONTS_H = ["Segoe UI Semibold", "Georgia", "Calibri", "Arial"]; const FONTS_B = ["Segoe UI", "Calibri", "Arial"];
const TEMPLATES = [
  { id: "Executive dashboard", note: "Big headline numbers and one clear chart per page", bars: [3, 5, 4] },
  { id: "Analyst dashboard", note: "More charts and filters on every page, for exploring", bars: [2, 4, 3, 5, 2, 4] },
];

export function BrandStep() {
  const { id, data, set, run, busy } = useEng(); const e = data!.engagement; const next = useNext("brand"); const { toast } = useToast();
  const role = useRole(); const locked = !!e.done.brand || e.mode === "demo" || role === "reviewer";
  const [b, setB] = useState(e.brand ?? { name: "", tagline: "", primary: "#2563EB", secondary: "#0F172A", accent: "#F59E0B", heading: "Segoe UI Semibold", body: "Segoe UI", template: "Analyst dashboard" });
  const [working, setWorking] = useState(false); const [uploading, setUploading] = useState(false); const [tplUploading, setTplUploading] = useState(false); const [stamp, setStamp] = useState(0);
  const r = e.brandResult;
  async function preview() {
    setWorking(true);
    try { set(await api<EngData>(`/api/e/${id}/brand`, { method: "POST", json: b })); setStamp(Date.now()); } catch (x) { toast("error", (x as Error).message); } finally { setWorking(false); }
  }
  async function logo(f: File | undefined) {
    if (!f) return; setUploading(true);
    const fd = new FormData(); fd.append("kind", "logo"); fd.append("file", f);
    try { set(await api<EngData>(`/api/e/${id}/upload`, { method: "POST", body: fd })); toast("ok", "Logo uploaded. Build the preview to check it."); } catch (x) { toast("error", (x as Error).message); } finally { setUploading(false); }
  }
  async function customTemplate(f: File | undefined) {
    if (!f) return; setTplUploading(true);
    const fd = new FormData(); fd.append("kind", "template"); fd.append("file", f);
    try { const d = await api<EngData>(`/api/e/${id}/upload`, { method: "POST", body: fd }); set(d); setB(d.engagement.brand!); toast("ok", "Template accepted. It will need a person to match the layout by hand -- see the draft review notes."); }
    catch (x) { toast("error", (x as Error).message); } finally { setTplUploading(false); }
  }
  const color = (k: "primary" | "secondary" | "accent", label: string) => (
    <Field label={label} htmlFor={`c-${k}`}>
      <div className="flex gap-2 items-center"><input aria-label={`${label} picker`} type="color" value={b[k]} onChange={(ev) => setB({ ...b, [k]: ev.target.value })} className="h-11 w-14 rounded-lg border border-border bg-surface p-1" disabled={locked} />
        <input id={`c-${k}`} className={`${inputCls} font-mono`} value={b[k]} onChange={(ev) => setB({ ...b, [k]: ev.target.value })} disabled={locked} /></div>
    </Field>
  );
  const logoSrc = e.brand?.logoFile ? `/api/e/${id}/file/logo-upload?t=${stamp}` : r?.ok && e.mode === "live" ? `/api/e/${id}/file/brand-logo-full-light.png?t=${stamp}` : null;
  return (
    <>
      <PageTitle eyebrow="Step 3" title="Look and feel">Set your colours and layout. We build a preview and check that text is readable on your colours before you approve.</PageTitle>
      <DoneBanner step="brand" />
      <div className="grid xl:grid-cols-[1.1fr_1fr] gap-6">
        <Card>
          <fieldset disabled={locked}>
            <div className="grid sm:grid-cols-2 gap-x-6">
              <Field label="Brand name" htmlFor="bn"><input id="bn" className={inputCls} value={b.name} onChange={(ev) => setB({ ...b, name: ev.target.value })} placeholder="Your company" /></Field>
              <Field label="Tagline (optional)" htmlFor="bt"><input id="bt" className={inputCls} value={b.tagline} onChange={(ev) => setB({ ...b, tagline: ev.target.value })} /></Field>
              {color("primary", "Main colour")}{color("secondary", "Dark colour (headers)")}{color("accent", "Highlight colour")}
              <div className="grid grid-cols-2 gap-3">
                <Field label="Heading font" htmlFor="hf"><select id="hf" className={inputCls} value={b.heading} onChange={(ev) => setB({ ...b, heading: ev.target.value })}>{FONTS_H.map((f) => <option key={f}>{f}</option>)}</select></Field>
                <Field label="Body font" htmlFor="bf"><select id="bf" className={inputCls} value={b.body} onChange={(ev) => setB({ ...b, body: ev.target.value })}>{FONTS_B.map((f) => <option key={f}>{f}</option>)}</select></Field>
              </div>
            </div>
            <Field label="Logo (optional)" htmlFor="lg" help="PNG, JPG or SVG. Without one, we make a simple placeholder logo.">
              <input id="lg" type="file" accept=".png,.jpg,.jpeg,.svg" onChange={(ev) => logo(ev.target.files?.[0])} className="text-sm" disabled={uploading || locked} />{e.brand?.logoFile && <p className="text-sm text-muted mt-1">Uploaded: {e.brand.logoFile}</p>}
            </Field>
            <p className="text-sm font-semibold mb-2">Page layout</p>
            <p className="text-xs text-muted mb-2">Pick one of our two layouts, or upload your own for the builder to match by hand.</p>
            <div className="grid sm:grid-cols-3 gap-3 mb-2" role="radiogroup" aria-label="Page layout">
              {TEMPLATES.map((t) => (
                <label key={t.id} className={`rounded-xl border p-3 cursor-pointer ${b.template === t.id ? "border-primary bg-primary-soft/50" : "border-border hover:bg-background"}`}>
                  <input type="radio" name="tpl" className="sr-only" checked={b.template === t.id} onChange={() => setB({ ...b, template: t.id, customTemplateFile: undefined })} />
                  <svg viewBox="0 0 120 60" className="w-full h-16 mb-2" aria-hidden><rect width="120" height="60" rx="6" fill="#F1F5F9" />{t.bars.map((h, i) => <rect key={i} x={8 + i * (100 / t.bars.length)} y={54 - h * 8} width={Math.max(8, 80 / t.bars.length)} height={h * 8} rx="2" fill={b.primary} opacity={0.85} />)}</svg>
                  <span className="block text-sm font-semibold">{t.id}</span><span className="block text-xs text-muted">{t.note}</span></label>
              ))}
              <label className={`rounded-xl border p-3 ${b.customTemplateFile ? "border-primary bg-primary-soft/50 cursor-pointer" : "border-border border-dashed"}`}>
                <input type="radio" name="tpl" className="sr-only" checked={!!b.customTemplateFile} readOnly />
                <div className="w-full h-16 mb-2 rounded-lg bg-background border border-border flex items-center justify-center overflow-hidden">
                  {b.customTemplateFile ? (
                    /\.(png|jpe?g)$/i.test(b.customTemplateFile)
                      ? <img src={`/api/e/${id}/file/template-upload?t=${stamp}`} alt="Your uploaded template" className="w-full h-full object-cover" />
                      : <span className="text-xs text-muted">PDF uploaded</span>
                  ) : <span className="text-xs text-muted">No file yet</span>}
                </div>
                <span className="block text-sm font-semibold">Upload your own</span>
                <span className="block text-xs text-muted mb-2">PNG, JPG or PDF, at least {`800×450px`}, up to 15 MB. A person matches your layout by hand afterwards.</span>
                {!locked && <input type="file" accept=".png,.jpg,.jpeg,.pdf" onChange={(ev) => customTemplate(ev.target.files?.[0])} disabled={tplUploading} className="text-xs" />}
              </label>
            </div>
            {b.template === "Custom template" && <p className="text-xs text-muted mb-5">Using your uploaded template as the reference layout.</p>}
          </fieldset>
          {!locked && <div className="flex flex-wrap gap-3"><Button kind="secondary" onClick={preview} busy={working}>Build preview and check colours</Button>
            <Button onClick={async () => { if (await run("brand.approve", {}, "Look and feel approved")) next(); }} disabled={!r?.ok} busy={busy === "brand.approve"} title={r?.ok ? "" : "Build the preview first"}>Approve and continue</Button></div>}
        </Card>
        <div className="space-y-4">
          <Card>
            <p className="text-xs font-bold tracking-widest uppercase text-muted mb-3">Preview</p>
            <div className="rounded-xl overflow-hidden border border-border">
              <div className="px-4 py-3 flex items-center justify-between" style={{ background: b.secondary, color: "#fff" }}>
                {logoSrc ? /* eslint-disable-next-line @next/next/no-img-element */ <img src={logoSrc} alt="Your logo" className="h-8 w-auto" /> : <span className="font-semibold" style={{ fontFamily: b.heading }}>{b.name || "Your brand"}</span>}
                <span className="text-xs opacity-80">{b.tagline}</span></div>
              <div className="p-4 bg-white">
                <p className="font-semibold text-lg" style={{ fontFamily: b.heading, color: "#0F172A" }}>Sales overview</p>
                <div className="grid grid-cols-3 gap-2 my-3">{[["12.4K", b.primary], ["68%", "#059669"], ["4.2%", "#DC2626"]].map(([v, c]) => <div key={v} className="rounded-lg border p-2" style={{ borderTop: `4px solid ${c}` }}><p className="text-xl font-semibold" style={{ color: c, fontFamily: b.heading }}>{v}</p><p className="text-[11px] text-slate-500">Example</p></div>)}</div>
                <button type="button" tabIndex={-1} className="rounded-lg px-4 py-2 text-sm font-semibold" style={{ background: b.primary, color: "#fff", fontFamily: b.body }}>Review draft</button>
                <span className="inline-block ml-3 w-3 h-3 rounded-full align-middle" style={{ background: b.accent }} aria-hidden /></div>
            </div>
          </Card>
          <Card>
            <p className="text-xs font-bold tracking-widest uppercase text-muted mb-3">Readability check</p>
            {!r ? <p className="text-sm text-muted">Build the preview to check that text is readable on your colours.</p> : r.errors?.length ? <Notice tone="bad" title="Please fix">{r.errors.join(" ")}</Notice> : (
              <>
                <Notice tone={r.ok ? "good" : "bad"} title={r.ok ? "Readable, and the Power BI theme is valid" : "Some colours are hard to read"}>{r.ok ? "You can approve this look." : `Please adjust: ${(r.mandatory_failed || []).join("; ")}.`}</Notice>
                <ul className="mt-3 divide-y divide-border text-sm">{r.checks?.map((c) => (
                  <li key={c.name} className="py-2 flex items-center justify-between gap-3"><span>{c.name}</span><span className="flex items-center gap-2 shrink-0"><span className="tabular text-muted">{c.ratio.toFixed(1)}:1</span><Badge tone={c.pass ? "good" : c.mandatory ? "bad" : "warn"}>{c.pass ? "Pass" : c.mandatory ? "Fix" : "Check"}</Badge></span></li>))}</ul>
              </>
            )}
          </Card>
        </div>
      </div>
    </>
  );
}
