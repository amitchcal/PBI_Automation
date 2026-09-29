// Server-only code: file-based engagement store, audit log, the Python runner, the demo engagement and the step rules.
import fs from "node:fs";
import path from "node:path";
import { spawn } from "node:child_process";
import { STEPS, StepKey, Engagement, Issue, BuildResult, DesktopCheckResult, CONSENT_STATEMENTS, ACCEPTANCE_ITEMS, HANDOVER_ITEMS, REQUIRED_Q, stepIndex, roleOf } from "@/lib/steps";

export const WEB = process.cwd();
export const PLATFORM = path.resolve(WEB, "..");
export const OUT = path.join(PLATFORM, "outputs", "rewardsnext");
export const DATA = path.join(WEB, "data", "engagements");
export const DEMO_ID = "rewardsnext-demo";
const PYTHON = process.env.PYTHON || "python";

// ---------------------------------------------------------------- store
const now = () => new Date().toISOString();
const dir = (id: string) => path.join(DATA, id);
const safeId = (id: string) => /^[a-z0-9-]{3,60}$/.test(id);
const readJson = <T,>(p: string, fallback?: T): T => { try { return JSON.parse(fs.readFileSync(p, "utf8").replace(/^﻿/, "")) as T; } catch { if (fallback !== undefined) return fallback; throw new Error(`cannot read ${p}`); } };
const writeJson = (p: string, o: unknown) => { fs.mkdirSync(path.dirname(p), { recursive: true }); fs.writeFileSync(p, JSON.stringify(o, null, 2)); };

export function audit(id: string, actor: string, action: string, detail = "") {
  fs.mkdirSync(dir(id), { recursive: true });
  fs.appendFileSync(path.join(dir(id), "audit.jsonl"), JSON.stringify({ ts: now(), actor, action, detail }) + "\n");   // append-only: no route edits or deletes it
}
export function readAudit(id: string) {
  const p = path.join(dir(id), "audit.jsonl"); if (!fs.existsSync(p)) return [];
  return fs.readFileSync(p, "utf8").split("\n").filter(Boolean).map((l) => JSON.parse(l)).reverse();
}
export function listEngagements(who: string): Engagement[] {
  ensureDemo(); fs.mkdirSync(DATA, { recursive: true });
  return fs.readdirSync(DATA).filter((d) => fs.existsSync(path.join(DATA, d, "state.json")))
    .map((d) => readJson<Engagement>(path.join(DATA, d, "state.json"))).filter((e) => roleOf(e, who) !== null);
}
export function getEngagement(id: string): Engagement | null {
  if (!safeId(id)) return null; if (id === DEMO_ID) ensureDemo();
  const p = path.join(dir(id), "state.json"); return fs.existsSync(p) ? readJson<Engagement>(p) : null;
}
export const saveEngagement = (e: Engagement) => writeJson(path.join(dir(e.id), "state.json"), e);
export const engDir = dir;

export function createEngagement(name: string, customer: string, actor: string): Engagement {
  const slug = name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 40) || "engagement";
  let id = slug.length >= 3 ? slug : slug + "-eng"; let k = 2; while (fs.existsSync(dir(id))) id = `${slug}-${k++}`;
  const e: Engagement = { id, name, customer, mode: "live", created: now(), owner: actor, reviewers: [], done: {}, questionnaire: {}, files: [], connections: [], decisions: {}, kpiApprovals: {}, feedback: [] };
  saveEngagement(e); audit(id, actor, "engagement created", name); return e;
}

// ---------------------------------------------------------------- python
export function runPython(args: string[], cwd: string, stdin?: string): Promise<{ code: number; stdout: string; stderr: string }> {
  return new Promise((resolve) => {
    const p = spawn(/*turbopackIgnore: true*/ PYTHON, args, { cwd, env: { ...process.env, PYTHONIOENCODING: "utf-8" } });
    let stdout = "", stderr = ""; p.stdout.on("data", (d) => (stdout += d)); p.stderr.on("data", (d) => (stderr += d));
    const timer = setTimeout(() => { p.kill(); }, 240000);
    p.on("close", (code) => { clearTimeout(timer); resolve({ code: code ?? 1, stdout, stderr }); });
    p.on("error", (err) => { clearTimeout(timer); resolve({ code: 1, stdout, stderr: String(err) }); });
    // story I-06: a data-source password or token is written here, to the child's stdin, never as a command-line
    // argument -- argv is visible to any other process on the machine that can list processes; stdin is not.
    if (stdin !== undefined) { p.stdin.write(stdin); }
    p.stdin.end();
  });
}

// A separate, longer-running runner: this opens Power BI Desktop on whichever machine runs the server, so it is
// only ever called from an explicit, user-confirmed action (never from the automated build above).
export function runPowerShell(scriptPath: string, args: string[]): Promise<{ code: number; stdout: string; stderr: string }> {
  return new Promise((resolve) => {
    const p = spawn(/*turbopackIgnore: true*/ "powershell.exe", ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", scriptPath, ...args]);
    let stdout = "", stderr = ""; p.stdout.on("data", (d) => (stdout += d)); p.stderr.on("data", (d) => (stderr += d));
    // Desktop cold-start (no cached workspace) plus a full refresh plus checks can legitimately take several
    // minutes; a live test on this machine ran past 10 minutes and was killed mid-check, leaving Desktop open
    // with no result written, so this is deliberately generous.
    const timer = setTimeout(() => { p.kill(); }, 1200000);
    p.on("close", (code) => { clearTimeout(timer); resolve({ code: code ?? 1, stdout, stderr }); });
    p.on("error", (err) => { clearTimeout(timer); resolve({ code: 1, stdout, stderr: String(err) }); });
  });
}

// ---------------------------------------------------------------- demo engagement (the completed RewardsNext build)
const A = (...p: string[]) => path.join(OUT, ...p);
export const DEMO_FILES: Record<string, { path: string; type: string; label: string }> = {
  "pages-overview": { path: A("docs", "deck_overview_v3.png"), type: "image/png", label: "Overview" },
  "pages-funnel": { path: A("docs", "deck_funnel_v3.png"), type: "image/png", label: "Offer Funnel" },
  "pages-segmentation": { path: A("docs", "deck_segmentation_v3.png"), type: "image/png", label: "Customer Segmentation" },
  "pages-performance": { path: A("docs", "deck_performance_v3.png"), type: "image/png", label: "Offer Performance" },
  "pages-behavior": { path: A("docs", "deck_behavior_v2.png"), type: "image/png", label: "Transaction Behavior" },
  "evidence-tooltip": { path: A("report", "evidence_tooltip_hover.png"), type: "image/png", label: "Tooltip on hover" },
  "evidence-drill": { path: A("report", "evidence_drill_offer_detail.png"), type: "image/png", label: "Drill-through to one offer" },
  "doc-guide": { path: A("docs", "RewardsNext_User_Guide.pdf"), type: "application/pdf", label: "User guide (1 page)" },
  "doc-tech": { path: A("docs", "RewardsNext_Technical_Document.pdf"), type: "application/pdf", label: "Technical document" },
  "doc-deck": { path: A("docs", "RewardsNext_Findings_Deck.pptx"), type: "application/vnd.openxmlformats-officedocument.presentationml.presentation", label: "Findings deck" },
};

export function ensureDemo() {
  if (fs.existsSync(path.join(dir(DEMO_ID), "state.json"))) return;
  const profile = readJson<{ sources: Record<string, { rows: number; columns_count: number; duplicate_rows: number }> }>(A("profile", "profile.json"));
  const issues = readJson<Issue[]>(A("profile", "issues.json"));
  const dec = readJson<{ approved_by: string; approved_on: string; profile_issue_decisions: { issue_id: string; decision: string }[]; business_rules: { id: string; topic: string; decision: string }[] }>(A("decisions.json"));
  const t = "2026-09-28T10:00:00.000Z", who = "Amit Chakraborty";
  const done: Engagement["done"] = {}; for (const s of STEPS.slice(0, 9)) done[s.key] = { at: t, by: who, note: "Recorded from the completed RewardsNext build" };
  const decisions: Engagement["decisions"] = {}; for (const d of dec.profile_issue_decisions) decisions[d.issue_id] = { decision: d.decision, by: who, at: t };
  const model = readJson<{ measures: { name: string }[] }>(path.join(PLATFORM, "configs", "rewardsnext_model.json"));
  const kpiApprovals: Engagement["kpiApprovals"] = {}; for (const m of model.measures) kpiApprovals[m.name] = { at: t, by: who };
  const e: Engagement = {
    id: DEMO_ID, name: "RewardsNext: Customer Offer Engagement", customer: "RewardsNext (sample customer)", mode: "demo", created: t, owner: who, reviewers: [], done,
    consent: { ticks: CONSENT_STATEMENTS.map(() => true), name: who },
    questionnaire: {
      problem: "Marketing teams want to understand how customers engage with promotional offers, which offers, channels and rewards work best, and how spending changes after an offer is completed.",
      decisions: "Which offers to repeat, which customer groups to target, and how to design thresholds and rewards.", audience: "Marketing team", frequency: "Weekly",
      kpis: "Total customers - customers in the current selection\nOffers sent - number of offer received events\nOffers completed - number of offer completed events\nRedemption rate - offers completed divided by offers sent, excluding informational offers\nAverage transaction amount - total spend divided by number of purchases",
      insights: "Redemption by offer type, channel and reward; who redeems by age, income and gender; spending before and after completing an offer.", targets: "",
      sources: "Four CSV files: customers, events, offers and a data dictionary.", refresh: "Weekly", data_owner: "Data team (sample)",
      who_sees: "Marketing team and analysts; no restricted views in this sample.", rls: "No", sensitive: "None identified; no names or contact details in the files.",
      workspace: "My workspace (sample)", licences: "Not sure", restrictions: "Map visuals are blocked by tenant policy.", future: "Extend the window beyond 30 days and record channel per event.",
    },
    brand: { name: "Meridian Analytics", tagline: "Insight you can act on", primary: "#2563EB", secondary: "#0F172A", accent: "#F59E0B", heading: "Segoe UI Semibold", body: "Segoe UI", template: "Analyst dashboard", approved: true },
    brandResult: { ok: true, name: "Meridian Analytics", checks: readJson<{ checks: NonNullable<Engagement["brandResult"]>["checks"] }>(path.join(PLATFORM, "kit", "brand", "out", "meridian", "report.json"), { checks: [] }).checks, mandatory_failed: [], theme_errors: [] },
    files: ["customers.csv", "events.csv", "offers.csv", "data_dictionary.csv"].map((n) => ({ name: n, size: fs.statSync(path.join(PLATFORM, "..", "RewardsNext_datasets", n)).size, uploaded: t })),
    connections: [],
    profile: { ran: t, sources: Object.entries(profile.sources).map(([id, s]) => ({ id, rows: s.rows, columns: s.columns_count, duplicate_rows: s.duplicate_rows })), issues },
    decisions, kpiApprovals, segmentsApproved: { at: t, by: who }, summaryConfirmed: { at: t, by: who }, feedback: [],
  };
  saveEngagement(e);
  audit(DEMO_ID, "system", "sample engagement loaded", "Built from the real RewardsNext project outputs");
  for (const b of dec.business_rules) audit(DEMO_ID, b.id === "D4a" ? "system" : who, `decision ${b.id} recorded`, `${b.topic}: ${b.decision}`.slice(0, 200));
}

// ---------------------------------------------------------------- views used by the screens
export function kpiList(e: Engagement): { name: string; folder?: string; description: string; dax?: string; format?: string; example?: string }[] {
  if (e.mode === "demo") {
    const cfg = readJson<{ measures: { name: string; folder: string; description: string; dax: string[]; format: string }[] }>(path.join(PLATFORM, "configs", "rewardsnext_model.json"));
    const checks = readJson<{ scalar: { name: string; expected: number }[] }>(A("model", "expected_model_checks.json")).scalar;
    return cfg.measures.map((m) => {
      const c = checks.find((x) => x.name === m.name); let example: string | undefined;
      if (c) example = m.format.includes("%") ? `${(c.expected * 100).toFixed(1)}%` : m.format.startsWith("$") ? `$${c.expected.toLocaleString("en-US", { maximumFractionDigits: 2 })}` : c.expected.toLocaleString("en-US", { maximumFractionDigits: 3 });
      return { name: m.name, folder: m.folder.slice(2), description: m.description, dax: m.dax.join("\n"), format: m.format, example };
    });
  }
  return (e.questionnaire.kpis || "").split("\n").map((l) => l.trim()).filter(Boolean).map((l) => {
    const m = l.split(/\s+[-–—:]\s+/); return { name: m[0], description: m.slice(1).join(" - ") || "" };
  });
}

export function segmentView(e: Engagement) {
  if (e.mode !== "demo") return { available: false, dims: [] as { name: string; rule: string; groups: { label: string; n: number }[] }[] };
  const cfg = readJson<{ segments: { bands: { name: string; source: string; labels: string[]; edges: number[]; unknown: string }[]; engagement: { tier_name: string; level_name: string; heavy_min: number; light_min: number } } }>(path.join(PLATFORM, "configs", "rewardsnext_model.json")).segments;
  const chk = readJson<{ scalar: { name: string; expected: number }[] }>(A("model", "expected_model_checks.json")).scalar;
  const size = (dim: string, lab: string) => chk.find((c) => c.name === `Customers, ${dim} = ${lab}`)?.expected ?? 0;
  const dims = cfg.bands.map((b) => ({ name: b.name, rule: `${b.source} split at ${b.edges.join(", ")}; blank shown as ${b.unknown}`, groups: [...b.labels, b.unknown].map((l) => ({ label: l, n: size(b.name, l) })) }));
  dims.push({ name: "Tenure Cohort", rule: "Year the customer joined", groups: [2013, 2014, 2015, 2016, 2017, 2018].map((y) => ({ label: `Joined ${y}`, n: size("Tenure Cohort", `Joined ${y}`) })) });
  const en = cfg.engagement;
  dims.push({ name: en.tier_name, rule: `Heavy completer: ${en.heavy_min}+ completed; Light: ${en.light_min}-${en.heavy_min - 1}; Viewer only; Ignored; Not reached`, groups: ["Heavy completer", "Light completer", "Viewer only", "Ignored", "Not reached"].map((l) => ({ label: l, n: size(en.tier_name, l) })) });
  return { available: true, dims };
}

export function buildStatus(e: Engagement) {
  if (e.mode !== "demo") {
    if (!e.build) return { available: false, stages: [] as { name: string; what: string; result: string; ok: boolean }[] };
    const b = e.build;
    return { available: true, ranAt: b.ranAt, reviewItems: b.reviewItems, stages: [
      { name: "Clean and shape the data", what: "One table per file, passthrough columns, your data decisions applied where they map to a generic rule.", result: b.stages.find((s) => s.name === "transform")?.ok ? `${b.tables} tables built` : `failed: ${b.stages.find((s) => s.name === "transform")?.error || ""}`, ok: !!b.stages.find((s) => s.name === "transform")?.ok },
      { name: "Build the model and measures", what: "Relationships detected from matching, orphan-free columns; a row count and simple sum/average measure per numeric column.", result: b.stages.find((s) => s.name === "model")?.ok ? `${b.relationships} relationships, ${b.measures} measures` : `failed: ${b.stages.find((s) => s.name === "model")?.error || ""}`, ok: !!b.stages.find((s) => s.name === "model")?.ok },
      { name: "Build the report", what: "An overview page and one table page per source, in your look and feel.", result: b.stages.find((s) => s.name === "report")?.ok ? `${b.pages} pages` : `failed: ${b.stages.find((s) => s.name === "report")?.error || ""}`, ok: !!b.stages.find((s) => s.name === "report")?.ok },
    ] };
  }
  const gate = readJson<{ passed: boolean; checks: unknown[] }>(A("transform", "transform_gate.json"));
  const run = readJson<{ all_passed: boolean; checks: unknown[]; refresh: { seconds: number } }>(A("model", "desktop_check.json"));
  const plan = readJson<{ table: string; rows: number }[]>(A("transform", "transform_plan.json"));
  const rep = readJson<{ pages: { name: string; visuals: unknown[] }[] }>(path.join(PLATFORM, "configs", "rewardsnext_report.json"));
  const prof = e.profile!;
  return { available: true, stages: [
    { name: "Read and profile the data", what: "Types, blanks, duplicates, hidden structure; raw totals captured with file fingerprints.", result: `${prof.sources.length} files, ${prof.issues.length} findings, ${prof.issues.filter((i) => i.needs_decision).length} needed a decision`, ok: true },
    { name: "Clean and shape the data", what: "Staging queries, parsing, cleaning rules from your decisions; an independent Python copy of every table.", result: `${plan.length} tables built; ${gate.checks.length} of ${gate.checks.length} totals match the raw files`, ok: gate.passed },
    { name: "Build the model and measures", what: "Relationships, time table, customer groups, KPI measures.", result: `${run.checks.length} checks in Power BI Desktop, all passed; refresh ${Math.round(run.refresh.seconds)} seconds`, ok: run.all_passed },
    { name: "Build the report", what: "Theme, pages, slicers, tooltips and drill-through, generated from a specification.", result: `${rep.pages.length} pages, ${rep.pages.reduce((a, p) => a + p.visuals.length, 0)} visuals`, ok: true },
    { name: "Write the documents", what: "User guide, technical document and findings deck; every number traced to a checked value.", result: "3 documents, 71 traced numbers", ok: true },
  ] };
}

export function checksLog(e: Engagement) {
  if (e.mode !== "demo") return { available: false, rows: [] as { check: string; expected: unknown; actual: unknown; pass: boolean }[] };
  const run = readJson<{ checks: { check: string; expected: unknown; actual: unknown; pass: boolean }[]; refresh: { seconds: number } }>(A("model", "desktop_check.json"));
  return { available: true, rows: run.checks.map((c) => ({ check: c.check, expected: c.expected, actual: c.actual, pass: c.pass })), refreshSeconds: run.refresh.seconds };
}

// ---------------------------------------------------------------- generic build (live engagements)
const platformOut = (id: string) => path.join(PLATFORM, "outputs", id);

export async function runBuild(e: Engagement, actorName: string): Promise<{ ok: boolean; error?: string; preflight?: boolean }> {
  // preflight: true on every guard below means "never even started a new run" -- e.build (if any) is from an
  // earlier attempt and must not be reported as this one's result (a real bug this line replaced: uploading a new
  // template resets brand.approved, which used to fail here silently while the route kept returning the old,
  // now-stale successful build as if it were current).
  if (e.mode !== "live") return { ok: false, error: "The sample engagement is read-only.", preflight: true };
  if (!e.profile || e.profile.error || !e.profile.sources.length) return { ok: false, error: "Upload and check your data first.", preflight: true };
  const openIssues = (e.profile.issues || []).filter((i) => i.needs_decision && !e.decisions[i.id]);
  if (openIssues.length) return { ok: false, error: `${openIssues.length} data decisions are still open.`, preflight: true };
  if (!e.brand?.approved) return { ok: false, error: "Approve your look and feel first.", preflight: true };

  const out = platformOut(e.id);
  fs.mkdirSync(out, { recursive: true });

  // decisions.json, in the shape the kit's agents already read
  const byId = new Map((e.profile.issues || []).map((i) => [i.id, i]));
  const profile_issue_decisions = Object.entries(e.decisions).map(([issue_id, d]) => ({
    issue_id, title: byId.get(issue_id)?.title || issue_id, decision: d.decision, decided_by: d.by, decided_at: d.at,
  }));
  writeJson(path.join(out, "decisions.json"), { engagement: e.id, approved_by: actorName, approved_on: now().slice(0, 10), profile_issue_decisions, business_rules: [] });

  // brand kit output, copied so the report agent can find it under the engagement's own id
  const brandSrc = path.join(engDir(e.id), "work", "brand", "out", "kit");
  const brandDst = path.join(PLATFORM, "kit", "brand", "out", e.id);
  if (fs.existsSync(brandSrc)) {
    fs.rmSync(brandDst, { recursive: true, force: true });
    fs.cpSync(brandSrc, brandDst, { recursive: true });
  }
  const hasMark = fs.existsSync(path.join(brandDst, "logo-mark.png"));

  const project = (e.name || e.id).replace(/[^A-Za-z0-9]+/g, "").slice(0, 40) || "Project";
  writeJson(path.join(out, "engagement.json"), {
    id: e.id, name: e.name, project,
    data_root: path.join(engDir(e.id), "uploads"),
    sources: e.files.map((f) => ({ id: f.name.replace(/\.[^.]+$/, "").replace(/[^A-Za-z0-9_]/g, "_").toLowerCase(), path: f.name, type: f.name.toLowerCase().endsWith(".xlsx") ? "xlsx" : "csv" })),
    brand_kit: e.id, images: hasMark ? ["logo-mark.png"] : [],
    measures_table: "Key Measures",
    kpis: kpiList(e).map((k) => ({ name: k.name, description: k.description })),
    // story I-04: the customer's chosen page layout is passed through so the generic config generator actually
    // builds a different draft for it, not just a label (see generate_configs.py).
    template: e.brand?.template || "Analyst dashboard",
  });

  const gen = await runPython([path.join(PLATFORM, "kit", "runner", "generate_configs.py"), e.id], PLATFORM);
  if (gen.code !== 0) return { ok: false, error: (gen.stderr || gen.stdout).split("\n").filter(Boolean).slice(-4).join(" ") || "Could not prepare the build configuration." };

  const run = await runPython([path.join(PLATFORM, "kit", "runner", "run_build.py"), e.id], PLATFORM);
  const statusPath = path.join(out, "build_status.json");
  if (!fs.existsSync(statusPath)) return { ok: false, error: (run.stderr || run.stdout).split("\n").filter(Boolean).slice(-4).join(" ") || "The build did not produce a result." };
  const status = readJson<{ ranAt: string; ok: boolean; stages: { name: string; ok: boolean; error?: string }[]; modelPbip: string | null; reportPbip: string | null }>(statusPath);
  const review = fs.existsSync(path.join(out, "manual_review.json")) ? readJson<{ items: string[] }>(path.join(out, "manual_review.json")).items : [];
  let relCount = 0, measCount = 0, pageCount = 0, tableCount = 0;
  try {
    tableCount = readJson<{ tables: unknown[] }>(path.join(PLATFORM, "configs", `${e.id}_transform.json`)).tables.length;
    relCount = readJson<{ relationships: unknown[] }>(path.join(PLATFORM, "configs", `${e.id}_model.json`)).relationships.length;
    pageCount = readJson<{ pages: unknown[] }>(path.join(PLATFORM, "configs", `${e.id}_report.json`)).pages.length;
    measCount = readJson<{ scalar: unknown[] }>(path.join(out, "model", "expected_model_checks.json")).scalar.length;
  } catch { /* best-effort counts for display only */ }
  const build: BuildResult = {
    ranAt: status.ranAt, ok: status.ok, stages: status.stages, tables: tableCount, relationships: relCount,
    measures: measCount, pages: pageCount, reviewItems: review, modelPbip: status.modelPbip || undefined, reportPbip: status.reportPbip || undefined,
  };
  e.build = build;
  audit(e.id, actorName, status.ok ? "automated build completed" : "automated build failed", status.stages.map((s) => `${s.name}: ${s.ok ? "ok" : "failed"}`).join(", "));
  saveEngagement(e);
  return { ok: status.ok, error: status.ok ? undefined : "One of the build stages failed; see the stage list below." };
}

// Opens Power BI Desktop, refreshes the generated project and runs its checks there -- the automated build above
// only proves the numbers agree with pandas; this proves they also agree inside Power BI itself. Only ever called
// from an explicit, user-confirmed button, because it takes over a Desktop window on this machine for a few minutes.
export async function runDesktopCheck(e: Engagement, actorName: string): Promise<{ ok: boolean; error?: string; preflight?: boolean }> {
  // preflight: true has the same meaning as in runBuild above: nothing new ran, so any e.build.desktopCheck
  // already on the engagement is from an earlier attempt and must not be reported as this one's result.
  if (e.mode !== "live") return { ok: false, error: "The sample engagement is read-only.", preflight: true };
  if (!e.build?.ok) return { ok: false, error: "Run the automated build first, and make sure every stage passed.", preflight: true };
  const out = platformOut(e.id);
  let project: string;
  try { project = readJson<{ engagement: { project: string } }>(path.join(PLATFORM, "configs", `${e.id}_model.json`)).engagement.project; }
  catch { return { ok: false, error: "The build configuration was not found; run the automated build again.", preflight: true }; }

  // The script confirms a refresh actually loaded rows by counting one real data table; RewardsNext's is
  // "FactEvents" (the script's default), a generic build's is whatever its first generated table is called.
  let probeTable = "FactEvents";
  try { probeTable = readJson<{ tables: { name: string }[] }>(path.join(PLATFORM, "configs", `${e.id}_transform.json`)).tables[0].name; } catch { /* keep the default */ }

  const script = path.join(PLATFORM, "kit", "common", "desktop_verify.ps1"); // moved here in story F-03; this path was left stale once before
  const modelPbip = path.join(out, "model", "pbip", `${project}.pbip`);
  if (!fs.existsSync(modelPbip)) return { ok: false, error: "The model project was not found; run the automated build again.", preflight: true };
  const checksPath = path.join(out, "model", "expected_model_checks.json");
  const modelOutPath = path.join(out, "model", "desktop_check.json");
  const r1 = await runPowerShell(script, ["-Pbip", modelPbip, "-Checks", checksPath, "-Out", modelOutPath, "-ProbeTable", probeTable]);
  if (!fs.existsSync(modelOutPath)) return { ok: false, error: (r1.stderr || r1.stdout).split("\n").filter(Boolean).slice(-4).join(" ") || "The Desktop check did not produce a result.", preflight: true };
  const modelResult = readJson<{ all_passed?: boolean; checks?: { check: string; expected: unknown; actual: unknown; pass: boolean }[]; refresh?: { ok: boolean; seconds: number }; error?: string }>(modelOutPath);

  let reportOpened = false;
  const reportPbip = path.join(out, "report", "pbip", `${project}.pbip`);
  if (fs.existsSync(reportPbip)) {
    const reportOutPath = path.join(out, "report", "desktop_render.json");
    await runPowerShell(script, ["-Pbip", reportPbip, "-Out", reportOutPath, "-ProbeTable", probeTable]);
    if (fs.existsSync(reportOutPath)) {
      try { reportOpened = !!readJson<{ refresh?: { ok: boolean } }>(reportOutPath).refresh?.ok; } catch { /* leave false */ }
    }
  }

  const checks = modelResult.checks || [];
  const passed = checks.filter((c) => c.pass).length;
  const mismatches = checks.filter((c) => !c.pass).slice(0, 8).map((c) => `${c.check}: expected ${JSON.stringify(c.expected)}, got ${JSON.stringify(c.actual)}`);
  const desktopCheck: DesktopCheckResult = {
    ranAt: new Date().toISOString(), ok: !!modelResult.all_passed && reportOpened,
    modelChecks: { total: checks.length, passed }, reportOpened, refreshSeconds: modelResult.refresh?.seconds, error: modelResult.error, mismatches,
  };
  e.build.desktopCheck = desktopCheck;
  audit(e.id, actorName, desktopCheck.ok ? "Power BI Desktop check passed" : "Power BI Desktop check found problems",
    `${passed} of ${checks.length} checks passed; report opened: ${reportOpened}`);
  saveEngagement(e);
  return { ok: desktopCheck.ok, error: desktopCheck.ok ? undefined : "Some checks did not pass in Power BI Desktop; see the details." };
}

export const openQuestions = (e: Engagement) => e.mode !== "demo" ? [] : [
  { id: "D4a", title: "Funnel purchases shown separately", text: "The funnel shows three offer steps. Purchases by customers who viewed or completed an offer are a separate card, because purchases are not offers and the count is larger than offers sent.", proposed: "Keep separate" },
  { id: "R1", title: "Customer drill-through re-test", text: "The customer drill-through was fixed to ignore the offer carried over from the previous page; the click-through has not been repeated yet.", proposed: "Builder to re-test" },
  { id: "R2", title: "Published report", text: "Slicers, drill-through and tooltips have not been tested in the published report.", proposed: "Test after publishing" },
];

// ---------------------------------------------------------------- step rules
export type Status = "done" | "open" | "locked";
export function statuses(e: Engagement): Record<StepKey, Status> {
  const out = {} as Record<StepKey, Status>; let open = false;
  for (const s of STEPS) { if (e.done[s.key]) out[s.key] = "done"; else if (!open) { out[s.key] = "open"; open = true; } else out[s.key] = "locked"; }
  return out;
}
export const currentStep = (e: Engagement): StepKey | null => STEPS.find((s) => !e.done[s.key])?.key ?? null;

const missingRequired = (e: Engagement) => REQUIRED_Q.filter((k) => !(e.questionnaire[k] || "").trim());

export function summaryOf(e: Engagement) {
  const missing = missingRequired(e).map((k) => `Answer the required question: ${k}`);
  const flags: string[] = [];
  const q = e.questionnaire;
  if (q.rls === "No" && /only|restrict|own region|their own|limited/i.test(q.who_sees || "")) flags.push("You said nobody needs a restricted view, but your answer about who sees the report mentions restrictions. Please check.");
  if (q.rls === "Not sure") flags.push("Row-level security is undecided. This affects how the model is built; please decide before the build.");
  const k = kpiList(e); if (!k.length) missing.push("List at least one key number."); k.filter((x) => !x.description).forEach((x) => flags.push(`The key number "${x.name}" has no definition. Add how you calculate it.`));
  if (!e.files.length) missing.push("Upload at least one data file."); if (!e.brand) missing.push("Set your look and feel.");
  if (e.profile && e.profile.issues.some((i) => i.needs_decision)) flags.push(`${e.profile.issues.filter((i) => i.needs_decision).length} data problems need your decision in a later step.`);
  return { config: { engagement: { name: e.name, customer: e.customer }, audience: q.audience, refresh: q.refresh, kpis: k.map((x) => x.name), sources: e.files.map((f) => f.name), brand: e.brand ? { name: e.brand.name, primary: e.brand.primary, template: e.brand.template } : null, security: { rowLevelSecurity: q.rls, sensitiveFields: q.sensitive || "none stated" }, publish: { workspace: q.workspace, licence: q.licences } }, missing, flags };
}

export type ActResult = { ok: true; engagement: Engagement } | { ok: false; error: string };
export function act(e: Engagement, type: string, p: Record<string, unknown>, actor: string): ActResult {
  const fail = (m: string): ActResult => ({ ok: false, error: m });

  // Story W-03: who has access is managed here, not as a numbered step -- the owner can do it at any time, and
  // it is the one thing a reviewer can never do to themselves or anyone else.
  if (type === "access.invite" || type === "access.remove") {
    if (e.mode === "demo") return fail("The sample engagement is read-only.");
    if (actor !== e.owner) return fail("Only the owner can manage who has access.");
    const name = String(p.name || "").trim();
    if (name.length < 2) return fail("Type a name.");
    if (name === e.owner) return fail("The owner already has full access.");
    if (type === "access.invite") { if (!e.reviewers.includes(name)) e.reviewers.push(name); audit(e.id, actor, "reviewer added", name); }
    else { e.reviewers = e.reviewers.filter((r) => r !== name); audit(e.id, actor, "reviewer removed", name); }
    saveEngagement(e); return { ok: true, engagement: e };
  }
  // A reviewer may look at everything but change nothing except leaving feedback on the draft; every other
  // step-changing action stays owner-only. Enforced here so every route that calls act() gets this for free.
  // The demo always resolves as "reviewer" (anyone signed in may look at it) but its steps 10-12 are deliberately
  // open for a visitor to try, so the real reviewer restriction only applies to a live engagement's real reviewers.
  if (e.mode !== "demo" && roleOf(e, actor) === "reviewer" && type !== "review.feedback") return fail("Reviewers can leave feedback on the draft, but cannot change any step. Ask the owner to make this change.");

  const st = statuses(e); const step = type.split(".")[0] as StepKey; const idx = stepIndex(step);
  if (idx < 0) return { ok: false, error: "Unknown step." };
  if (st[step] === "locked") return { ok: false, error: `Step ${idx + 1} is locked until the steps before it are done.` };
  const finish = (s: StepKey, note?: string) => { e.done[s] = { at: now(), by: actor, note }; audit(e.id, actor, `step ${stepIndex(s) + 1} done: ${STEPS[stepIndex(s)].title}`, note || ""); };
  if (e.mode === "demo" && idx < 9) return fail("This step was recorded from the completed sample build and is read-only.");
  switch (type) {
    case "consent.complete": {
      const ticks = p.ticks as boolean[]; const name = String(p.name || "").trim();
      if (!Array.isArray(ticks) || ticks.length !== CONSENT_STATEMENTS.length || !ticks.every(Boolean)) return fail("Please tick every statement.");
      if (name.length < 3) return fail("Please type your full name.");
      e.consent = { ticks, name }; finish("consent", `Agreed by ${name}`); break;
    }
    case "questionnaire.save": { e.questionnaire = { ...e.questionnaire, ...(p.values as Record<string, string>) }; audit(e.id, actor, "needs form saved"); break; }
    case "questionnaire.complete": {
      e.questionnaire = { ...e.questionnaire, ...(p.values as Record<string, string>) };
      const miss = missingRequired(e); if (miss.length) return fail(`Please answer the required questions (${miss.length} left).`); finish("questionnaire"); break;
    }
    case "brand.save": { e.brand = { ...(p.brand as NonNullable<Engagement["brand"]>), approved: false }; delete e.brandResult; audit(e.id, actor, "look and feel changed"); break; }
    case "brand.approve": {
      if (!e.brand || !e.brandResult?.ok) return fail("Build the preview first; the colours must pass the readability check.");
      e.brand.approved = true; finish("brand", `${e.brand.name}, template ${e.brand.template}`); break;
    }
    case "data.complete": {
      if (!e.profile || e.profile.error || !e.profile.sources.length) return fail("Upload files and run the check first."); finish("data", `${e.profile.sources.length} files checked`); break;
    }
    case "summary.confirm": {
      const s = summaryOf(e); if (s.missing.length) return fail("Some required information is missing; see the list."); e.summaryConfirmed = { at: now(), by: actor }; finish("summary"); break;
    }
    case "issues.decide": {
      const id = String(p.id), d = String(p.decision); const is = e.profile?.issues.find((i) => i.id === id);
      if (!is || !is.needs_decision) return fail("Unknown issue."); if (!is.options.includes(d)) return fail("Choose one of the listed options.");
      e.decisions[id] = { decision: d, by: actor, at: now() }; audit(e.id, actor, `data decision ${id}`, `${is.title}: ${d}`); break;
    }
    case "issues.complete": {
      const need = (e.profile?.issues || []).filter((i) => i.needs_decision && !e.decisions[i.id]); if (need.length) return fail(`${need.length} decisions are still open.`); finish("issues"); break;
    }
    case "kpis.approve": {
      const name = String(p.name); if (!kpiList(e).some((k) => k.name === name)) return fail("Unknown KPI.");
      if (p.approve === false) delete e.kpiApprovals[name]; else e.kpiApprovals[name] = { at: now(), by: actor };
      audit(e.id, actor, `KPI ${p.approve === false ? "approval withdrawn" : "approved"}`, name); break;
    }
    case "kpis.complete": {
      const left = kpiList(e).filter((k) => !e.kpiApprovals[k.name]); if (left.length) return fail(`${left.length} KPI definitions are not approved yet.`); finish("kpis", `${kpiList(e).length} definitions approved`); break;
    }
    case "segments.approve": { e.segmentsApproved = { at: now(), by: actor }; finish("segments"); break; }
    case "build.complete": {
      if (!e.build?.ok) return fail("Run the automated build first, and make sure every stage passed.");
      finish("build", `${e.build.tables} tables, ${e.build.relationships} relationships, ${e.build.measures} measures, ${e.build.pages} report pages`);
      break;
    }
    case "review.feedback": {
      const text = String(p.text || "").trim(); if (text.length < 5) return fail("Please describe the change."); e.feedback.push({ id: `F${e.feedback.length + 1}`, text, page: String(p.page || "General"), at: now(), by: actor, status: "Logged" });
      audit(e.id, actor, "feedback logged", text.slice(0, 160)); break;
    }
    case "review.complete": {
      if (!e.feedback.length && p.noChanges !== true) return fail("Add feedback, or confirm that you have no changes."); finish("review", e.feedback.length ? `${e.feedback.length} change items` : "No changes requested"); break;
    }
    case "accept.complete": {
      const ticks = p.ticks as boolean[]; const name = String(p.name || "").trim();
      if (!Array.isArray(ticks) || ticks.length !== ACCEPTANCE_ITEMS.length || !ticks.every(Boolean)) return fail("Please tick every item."); if (name.length < 3) return fail("Please type your full name.");
      e.acceptance = { ticks, name }; finish("accept", `Signed off by ${name}`); break;
    }
    case "publish.complete": {
      const ticks = p.ticks as boolean[]; const name = String(p.name || "").trim();
      if (!Array.isArray(ticks) || ticks.length !== HANDOVER_ITEMS.length || !ticks.every(Boolean)) return fail("Please tick every item."); if (name.length < 3) return fail("Please type your full name.");
      e.handover = { ticks, name }; finish("publish", `Handover confirmed by ${name}`); break;
    }
    default: return fail("Unknown action.");
  }
  saveEngagement(e); return { ok: true, engagement: e };
}

export function contentType(name: string) {
  const ext = path.extname(name).toLowerCase();
  return ({ ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".svg": "image/svg+xml", ".pdf": "application/pdf", ".css": "text/css", ".json": "application/json" } as Record<string, string>)[ext] || "application/octet-stream";
}
export { readJson, writeJson, safeId };
