import { caller } from "@/lib/server";

export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  try {
    const acct = await caller(req);
    if (!acct) return Response.json({ error: "Not signed in" }, { status: 401 });
    return Response.json({ credits: acct.credits, api_key: acct.api_key, user_id: acct.user_id });
  } catch (e) {
    return Response.json({ error: (e as Error).message }, { status: 500 });
  }
}
