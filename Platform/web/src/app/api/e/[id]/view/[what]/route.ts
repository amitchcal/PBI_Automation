import { NextRequest } from "next/server";
import { load, bad } from "@/lib/server/api";
import { kpiList, segmentView, buildStatus, checksLog, openQuestions, readAudit, summaryOf, DEMO_FILES } from "@/lib/server/lib";

export async function GET(req: NextRequest, { params }: { params: Promise<{ id: string; what: string }> }) {
  const p = await params;
  const r = await load(Promise.resolve({ id: p.id }), req);
  if (!r) return bad("Engagement not found.", 404);
  const { e } = r;
  switch (p.what) {
    case "kpis": return Response.json({ kpis: kpiList(e) });
    case "segments": return Response.json(segmentView(e));
    case "build": return Response.json(buildStatus(e));
    case "checks": return Response.json(checksLog(e));
    case "questions": return Response.json({ questions: openQuestions(e) });
    case "audit": return Response.json({ entries: readAudit(e.id) });
    case "summary": return Response.json(summaryOf(e));
    case "docs": return Response.json({
      available: e.mode === "demo",
      files: e.mode === "demo" ? Object.entries(DEMO_FILES).filter(([k]) => k.startsWith("doc-")).map(([k, v]) => ({ key: k, label: v.label })) : [],
    });
    default: return bad("Unknown view.", 404);
  }
}
