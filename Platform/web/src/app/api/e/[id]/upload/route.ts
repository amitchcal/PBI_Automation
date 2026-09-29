import fs from "node:fs";
import path from "node:path";
import { NextRequest } from "next/server";
import { load, payload, bad, actor } from "@/lib/server/api";
import { engDir, saveEngagement, audit, statuses } from "@/lib/server/lib";
import { checkTemplate } from "@/lib/server/template-rules";

const MAX = 60 * 1024 * 1024;

export async function POST(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const r = await load(params, req);
  if (!r) return bad("Engagement not found.", 404);
  const { e, role } = r;
  if (role !== "owner") return bad("Only the owner can upload files.", 403);
  if (e.mode === "demo") return bad("The sample engagement is read-only. Create a new engagement to upload your own files.", 403);
  const st = statuses(e);
  if (st.consent !== "done") return bad("Confirm the agreement first: nothing can be uploaded before it.", 403);

  const form = await req.formData().catch(() => null);
  if (!form) return bad("No file received.");
  const kind = String(form.get("kind") || "data");
  if (kind === "data" && st.data === "locked") return bad("This step is locked until the steps before it are done.", 403);
  if ((kind === "logo" || kind === "template") && st.brand === "locked") return bad("This step is locked until the steps before it are done.", 403);
  const files = form.getAll("file").filter((f): f is File => f instanceof File);
  if (!files.length) return bad("Choose at least one file.");
  if (kind === "template" && files.length > 1) return bad("Upload one template file at a time.");

  const okExt = kind === "logo" ? [".png", ".jpg", ".jpeg", ".svg"] : kind === "template" ? [".png", ".jpg", ".jpeg", ".pdf"] : [".csv", ".xlsx"];
  const folder = path.join(engDir(e.id), kind === "logo" ? "logo" : kind === "template" ? "template" : "uploads");
  fs.mkdirSync(folder, { recursive: true });
  const saved: string[] = [];
  for (const f of files) {
    const ext = path.extname(f.name).toLowerCase();
    if (!okExt.includes(ext)) return bad(`${f.name}: this file type is not accepted. Use ${okExt.join(", ")}.`);
    if (f.size === 0) return bad(`${f.name} is empty.`);
    const buf = Buffer.from(await f.arrayBuffer());
    if (kind === "template") {
      // story I-04: a customer's own template is accepted only if it meets the template rules (type, size, minimum
      // resolution) -- checked here, on the real bytes, not just the filename.
      const check = checkTemplate(f.name, f.size, buf);
      if (!check.ok) return bad(check.error!);
    } else if (f.size > MAX) return bad(`${f.name} is larger than 60 MB.`);
    const clean = path.basename(f.name).replace(/[^A-Za-z0-9._-]/g, "_");
    fs.writeFileSync(path.join(folder, clean), buf);
    saved.push(clean);
    if (kind === "data") {
      e.files = e.files.filter((x) => x.name !== clean);
      e.files.push({ name: clean, size: f.size, uploaded: new Date().toISOString() });
      delete e.profile;
    } else {
      const base = e.brand ?? { name: "", tagline: "", primary: "#2563EB", secondary: "#0F172A", accent: "#F59E0B", heading: "Segoe UI Semibold", body: "Segoe UI", template: "Analyst dashboard" };
      if (kind === "template") { e.brand = { ...base, customTemplateFile: clean, template: "Custom template", approved: false }; }
      else { e.brand = { ...base, logoFile: clean, approved: false }; }
      delete e.brandResult;
    }
  }
  audit(e.id, actor(req), kind === "logo" ? "logo uploaded" : kind === "template" ? "custom template uploaded" : "data files uploaded", saved.join(", "));
  saveEngagement(e);
  return Response.json(payload(e));
}
