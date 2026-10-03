import type Stripe from "stripe";
import { admin, CREDIT_PACK, ensureAccount, stripe } from "@/lib/server";

export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  const sig = req.headers.get("stripe-signature");
  const secret = process.env.STRIPE_WEBHOOK_SECRET;
  if (!sig || !secret) return Response.json({ error: "Webhook not configured" }, { status: 400 });
  const raw = await req.text();
  let event: Stripe.Event;
  try {
    event = stripe().webhooks.constructEvent(raw, sig, secret);
  } catch (e) {
    return Response.json({ error: `Bad signature: ${(e as Error).message}` }, { status: 400 });
  }
  if (event.type === "checkout.session.completed") {
    const s = event.data.object as Stripe.Checkout.Session;
    const userId = s.metadata?.user_id || s.client_reference_id;
    if (userId && s.payment_status === "paid") {
      const n = Number(s.metadata?.credits || CREDIT_PACK);
      await ensureAccount(userId);
      // spend_credits with a negative amount adds credits atomically
      await admin().rpc("spend_credits", { uid: userId, n: -n });
      if (s.customer) await admin().from("accounts").update({ stripe_customer: String(s.customer) }).eq("user_id", userId);
    }
  }
  return Response.json({ received: true });
}
