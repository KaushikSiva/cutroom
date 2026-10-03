import { createMcpHandler } from "mcp-handler";
import { z } from "zod";
import { admin, caller, checkoutUrl, createProject, siteUrl, type Account } from "@/lib/server";

export const dynamic = "force-dynamic";
export const maxDuration = 60;

const text = (obj: unknown) => ({ content: [{ type: "text" as const, text: typeof obj === "string" ? obj : JSON.stringify(obj, null, 2) }] });

function build(req: Request, acct: Account | null) {
  const base = siteUrl(req);
  const need = () => {
    if (!acct) throw new Error("Unauthorized: pass your Cutroom API key as the x-api-key header or ?key= (get one at " + base + ")");
    return acct;
  };
  return createMcpHandler(
    (server) => {
      server.registerTool(
        "make_video",
        {
          title: "Make a video",
          description:
            "Commission a short film from the Cutroom studio. A Claude Code director plans the script, generates keyframes and shots, pulls Creative Commons footage, renders motion graphics, records an emotive voiceover, scores music, assembles, captions, self-critiques and publishes. Costs 1 credit (2 with 4K). Returns a project id; poll get_status.",
          inputSchema: z.object({
            brief: z.string().describe("What you want the film to be about and say"),
            aspect_ratio: z.enum(["16:9", "9:16", "1:1"]).default("16:9"),
            length_s: z.number().int().min(15).max(240).default(60),
            style: z.string().optional().describe("Style preferences: tone, look, pacing, music"),
            want_4k: z.boolean().default(false),
          }),
        },
        async (args) => {
          const a = need();
          const r = await createProject(a, args, "mcp");
          if ("error" in r) {
            if (r.status === 402) {
              const url = await checkoutUrl(req, a).catch(() => null);
              return text({ error: "Out of credits", buy_credits_url: url });
            }
            return text({ error: r.error });
          }
          return text({ project_id: r.project.id, status: r.project.status, watch_live: `${base}/p/${r.project.id}` });
        },
      );
      server.registerTool(
        "get_status",
        {
          title: "Get film status",
          description: "Status, stage, progress and (when done) the video URLs and credits ledger for a project.",
          inputSchema: z.object({ project_id: z.string() }),
        },
        async ({ project_id }) => {
          const db = admin();
          const { data: p } = await db
            .from("projects")
            .select("id,status,stage,progress,title,logline,video_url,video_4k_url,credits,error,owner,is_public")
            .eq("id", project_id)
            .maybeSingle();
          if (!p || (!p.is_public && p.owner !== acct?.user_id)) return text({ error: "Not found" });
          const { data: last } = await db.from("events").select("kind,message,created_at").eq("project_id", project_id).order("id", { ascending: false }).limit(5);
          const { owner: _o, is_public: _p, ...rest } = p;
          void _o; void _p;
          return text({ ...rest, recent: last || [], watch_live: `${base}/p/${project_id}` });
        },
      );
      server.registerTool(
        "get_credits",
        { title: "Get credits", description: "How many film credits this API key has left.", inputSchema: z.object({}) },
        async () => {
          const a = need();
          const { data } = await admin().from("accounts").select("credits").eq("user_id", a.user_id).single();
          return text({ credits: data?.credits ?? 0 });
        },
      );
      server.registerTool(
        "list_videos",
        { title: "List videos", description: "Your recent films (newest first).", inputSchema: z.object({ limit: z.number().int().min(1).max(50).default(10) }) },
        async ({ limit }) => {
          const a = need();
          const { data } = await admin()
            .from("projects")
            .select("id,title,status,progress,video_url,video_4k_url,created_at")
            .eq("owner", a.user_id)
            .order("created_at", { ascending: false })
            .limit(limit);
          return text({ videos: (data || []).map((v) => ({ ...v, watch: `${base}/p/${v.id}` })) });
        },
      );
      server.registerTool(
        "buy_credits",
        { title: "Buy credits", description: "Returns a Stripe Checkout link for a 10-credit pack (a human completes payment).", inputSchema: z.object({}) },
        async () => text({ checkout_url: await checkoutUrl(req, need()) }),
      );
    },
    { serverInfo: { name: "cutroom", version: "1.0.0" } },
  );
}

async function handle(req: Request) {
  let acct: Account | null = null;
  try {
    acct = await caller(req);
  } catch {
    acct = null;
  }
  return build(req, acct)(req);
}

export { handle as GET, handle as POST, handle as DELETE };
