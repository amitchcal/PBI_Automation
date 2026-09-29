import { NextRequest } from "next/server";
import { load, payload, bad } from "@/lib/server/api";

export async function GET(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const r = await load(params, req);
  if (!r) return bad("Engagement not found.", 404);
  return Response.json(payload(r.e));
}
