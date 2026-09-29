import { NextRequest } from "next/server";
import { load, payload, bad, actor } from "@/lib/server/api";
import { act } from "@/lib/server/lib";

export async function POST(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const r = await load(params, req);
  if (!r) return bad("Engagement not found.", 404);
  const body = await req.json().catch(() => null);
  if (!body || typeof body.type !== "string") return bad("Missing action.");
  const { type, ...rest } = body;
  const res = act(r.e, type, rest, actor(req));
  return res.ok ? Response.json(payload(res.engagement)) : bad(res.error, 422);
}
