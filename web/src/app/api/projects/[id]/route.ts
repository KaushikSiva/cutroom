import { admin } from "@/lib/server";

export const dynamic = "force-dynamic";

export async function GET(_req: Request, ctx: RouteContext<"/api/projects/[id]">) {
  const { id } = await ctx.params;
  try {
    const db = admin();
    const { data: project } = await db.from("projects").select("*").eq("id", id).maybeSingle();
    if (!project) return Response.json({ error: "Not found" }, { status: 404 });
    const { data: events } = await db.from("events").select("*").eq("project_id", id).order("id").limit(1000);
    return Response.json({ project, events: events || [] });
  } catch (e) {
    return Response.json({ error: (e as Error).message }, { status: 500 });
  }
}
