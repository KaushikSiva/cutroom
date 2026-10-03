import { caller, checkoutUrl } from "@/lib/server";

export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  try {
    const acct = await caller(req);
    if (!acct) return Response.json({ error: "Not signed in" }, { status: 401 });
    const { returnTo } = (await req.json().catch(() => ({}))) as { returnTo?: string };
    const url = await checkoutUrl(req, acct, returnTo && returnTo.startsWith("/") ? returnTo : "/");
    return Response.json({ url });
  } catch (e) {
    return Response.json({ error: (e as Error).message }, { status: 500 });
  }
}
