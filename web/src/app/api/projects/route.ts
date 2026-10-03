import { caller, createProject, type Brief } from "@/lib/server";

export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  try {
    const acct = await caller(req);
    if (!acct) return Response.json({ error: "Not signed in" }, { status: 401 });
    const body = (await req.json().catch(() => ({}))) as Brief;
    const r = await createProject(acct, body, req.headers.get("x-api-key") ? "mcp" : "web");
    if ("error" in r) return Response.json({ error: r.error }, { status: r.status });
    return Response.json({ project: r.project });
  } catch (e) {
    return Response.json({ error: (e as Error).message }, { status: 500 });
  }
}
