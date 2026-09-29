import fs from "node:fs";
import path from "node:path";
import { NextRequest } from "next/server";
import { load, bad } from "@/lib/server/api";
import { DEMO_FILES, engDir, contentType } from "@/lib/server/lib";

// Only whitelisted files are served: the sample's recorded outputs, and an engagement's own logo and brand preview.
export async function GET(req: NextRequest, { params }: { params: Promise<{ id: string; key: string }> }) {
  const p = await params;
  const r = await load(Promise.resolve({ id: p.id }), req);
  if (!r) return bad("Engagement not found.", 404);
  const { e } = r;
  let file: string | null = null;
  let type = "application/octet-stream";
  let name = p.key;
  if (e.mode === "demo" && DEMO_FILES[p.key]) {
    file = DEMO_FILES[p.key].path; type = DEMO_FILES[p.key].type; name = path.basename(file);
  } else if (e.mode === "live" && /^brand-(logo-full|logo-full-light|logo-mark)\.png$/.test(p.key)) {
    file = path.join(engDir(e.id), "work", "brand", "out", "kit", p.key.replace("brand-", "")); type = "image/png";
  } else if (e.mode === "live" && p.key === "logo-upload" && e.brand?.logoFile) {
    file = path.join(engDir(e.id), "logo", e.brand.logoFile); type = contentType(file);
  } else if (e.mode === "live" && p.key === "template-upload" && e.brand?.customTemplateFile) {
    file = path.join(engDir(e.id), "template", e.brand.customTemplateFile); type = contentType(file);
  }
  if (!file || !fs.existsSync(file)) return bad("File not found.", 404);
  const isDoc = p.key.startsWith("doc-");
  return new Response(fs.readFileSync(file), { headers: { "content-type": type, ...(isDoc ? { "content-disposition": `attachment; filename="${name}"` } : {}) } });
}
