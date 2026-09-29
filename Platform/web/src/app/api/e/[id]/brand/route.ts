import fs from "node:fs";
import path from "node:path";
import { NextRequest } from "next/server";
import { load, payload, bad, actor } from "@/lib/server/api";
import { engDir, PLATFORM, runPython, saveEngagement, audit, readJson, statuses } from "@/lib/server/lib";
import type { Engagement } from "@/lib/steps";

const HEX = /^#[0-9A-Fa-f]{6}$/;

export async function POST(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const r = await load(params, req);
  if (!r) return bad("Engagement not found.", 404);
  const { e, role } = r;
  if (role !== "owner") return bad("Only the owner can change this.", 403);
  if (e.mode === "demo") return bad("The sample engagement is read-only.", 403);
  if (statuses(e).brand === "locked") return bad("This step is locked until the steps before it are done.", 403);
  const b = (await req.json().catch(() => null)) as Engagement["brand"] | null;
  if (!b) return bad("Missing look and feel settings.");
  for (const k of ["primary", "secondary", "accent"] as const) if (!HEX.test(b[k])) return bad(`${k}: use a colour like #2563EB.`);
  if ((b.name || "").trim().length < 2) return bad("Give the brand a name.");
  // logoFile and customTemplateFile are owned by the upload route, not this one: carried forward here so that
  // saving colours/fonts never silently drops an uploaded logo or custom template (I-04).
  e.brand = { ...b, logoFile: e.brand?.logoFile, customTemplateFile: b.template === "Custom template" ? e.brand?.customTemplateFile : undefined, approved: false };

  // The kit's brand builder turns these settings into web styles, a Power BI theme, deck colours and logo files, and checks readability.
  const kit = {
    name: b.name, tagline: b.tagline || "",
    logo: e.brand.logoFile ? { path: path.join(engDir(e.id), "logo", e.brand.logoFile) } : { generate: true, mark: "bars" },
    palette: {
      primary: b.primary, secondary: b.secondary, accent: b.accent, positive: "#059669", warning: "#B45309", negative: "#DC2626",
      background: "#F8FAFC", surface: "#FFFFFF", border: "#E2E8F0", text: "#0F172A", muted: "#475569",
      dataColors: [b.primary, "#0F766E", b.accent, "#7C3AED", "#DB2777", "#0891B2", "#65A30D", "#64748B"],
    },
    fonts: { heading: b.heading || "Segoe UI Semibold", body: b.body || "Segoe UI", webStack: "Inter, 'Segoe UI', system-ui, sans-serif" },
    shape: { radius: 12 },
  };
  const work = path.join(engDir(e.id), "work", "brand");
  fs.mkdirSync(work, { recursive: true });
  const kitPath = path.join(work, "kit.json");
  fs.writeFileSync(kitPath, JSON.stringify(kit, null, 2));
  const run = await runPython([path.join(PLATFORM, "kit", "brand", "build_brand.py"), kitPath, path.join(work, "out")], path.join(PLATFORM, "kit", "brand"));
  const rep = path.join(work, "out", "kit", "report.json");
  if (fs.existsSync(rep)) e.brandResult = readJson(rep);
  else e.brandResult = { ok: false, errors: [(run.stderr || run.stdout).split("\n").filter(Boolean).slice(-2).join(" ") || "The preview could not be built."] };
  audit(e.id, actor(req), "look and feel previewed", e.brandResult?.ok ? "readable, theme valid" : `needs changes: ${(e.brandResult?.mandatory_failed || e.brandResult?.errors || []).join("; ")}`);
  saveEngagement(e);
  return Response.json(payload(e));
}
