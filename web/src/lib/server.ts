import "server-only";
import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import Stripe from "stripe";

export const CREDIT_PACK = 10;

let _admin: SupabaseClient | null = null;
export function admin(): SupabaseClient {
  if (!_admin) {
    const url = process.env.SUPABASE_URL || process.env.NEXT_PUBLIC_SUPABASE_URL;
    const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
    if (!url || !key) throw new Error("Supabase is not configured (SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY)");
    _admin = createClient(url, key, { auth: { persistSession: false, autoRefreshToken: false } });
  }
  return _admin;
}

let _stripe: Stripe | null = null;
export function stripe(): Stripe {
  if (!_stripe) {
    const key = process.env.STRIPE_SECRET_KEY;
    if (!key) throw new Error("Stripe is not configured (STRIPE_SECRET_KEY)");
    _stripe = new Stripe(key);
  }
  return _stripe;
}

export type Account = { user_id: string; credits: number; api_key: string; stripe_customer: string | null };

export async function ensureAccount(userId: string): Promise<Account> {
  const db = admin();
  const { data } = await db.from("accounts").select("*").eq("user_id", userId).maybeSingle();
  if (data) return data as Account;
  const { data: created, error } = await db.from("accounts").insert({ user_id: userId }).select("*").single();
  if (error) {
    // lost a race with a concurrent insert
    const { data: again } = await db.from("accounts").select("*").eq("user_id", userId).single();
    if (again) return again as Account;
    throw error;
  }
  return created as Account;
}

/** Resolve the caller from `Authorization: Bearer <supabase jwt>`, `x-api-key`, or `?key=`. */
export async function caller(req: Request): Promise<Account | null> {
  const db = admin();
  const url = new URL(req.url);
  const apiKey = req.headers.get("x-api-key") || url.searchParams.get("key");
  if (apiKey) {
    const { data } = await db.from("accounts").select("*").eq("api_key", apiKey).maybeSingle();
    return (data as Account) || null;
  }
  const auth = req.headers.get("authorization") || "";
  const token = auth.toLowerCase().startsWith("bearer ") ? auth.slice(7).trim() : "";
  if (token.startsWith("cr_")) {
    const { data } = await db.from("accounts").select("*").eq("api_key", token).maybeSingle();
    return (data as Account) || null;
  }
  if (!token) return null;
  const { data, error } = await db.auth.getUser(token);
  if (error || !data.user) return null;
  return ensureAccount(data.user.id);
}

export type Brief = {
  brief: string;
  aspect_ratio?: string;
  length_s?: number;
  style?: string;
  want_4k?: boolean;
};

const RATIOS = new Set(["16:9", "9:16", "1:1"]);

export async function createProject(account: Account, b: Brief, source: "web" | "mcp") {
  const brief = (b.brief || "").trim().slice(0, 2000);
  if (brief.length < 3) return { error: "Tell the studio what you want (brief)", status: 400 as const };
  const aspect = RATIOS.has(b.aspect_ratio || "") ? b.aspect_ratio! : "16:9";
  const length = Math.max(15, Math.min(240, Math.round(Number(b.length_s) || 60)));
  const cost = b.want_4k ? 2 : 1;
  const db = admin();
  const { data: ok, error: spendErr } = await db.rpc("spend_credits", { uid: account.user_id, n: cost });
  if (spendErr) return { error: spendErr.message, status: 500 as const };
  if (!ok) return { error: "Out of credits", status: 402 as const, cost };
  const { data, error } = await db
    .from("projects")
    .insert({
      owner: account.user_id,
      topic: brief.slice(0, 140),
      brief,
      aspect_ratio: aspect,
      length_s: length,
      style: (b.style || "").slice(0, 400) || null,
      want_4k: !!b.want_4k,
      source,
      status: "queued",
      stage: "brief",
      progress: 0,
    })
    .select("*")
    .single();
  if (error) {
    await db.rpc("spend_credits", { uid: account.user_id, n: -cost }); // refund
    return { error: error.message, status: 500 as const };
  }
  await db.from("events").insert({
    project_id: data.id,
    kind: "stage",
    message: "Brief received — waiting for a director",
    data: { stage: "brief", progress: 2 },
  });
  return { project: data };
}

export function siteUrl(req: Request) {
  if (process.env.NEXT_PUBLIC_SITE_URL) return process.env.NEXT_PUBLIC_SITE_URL.replace(/\/$/, "");
  const u = new URL(req.url);
  const host = req.headers.get("x-forwarded-host") || u.host;
  const proto = req.headers.get("x-forwarded-proto") || u.protocol.replace(":", "");
  return `${proto}://${host}`;
}

export async function checkoutUrl(req: Request, account: Account, returnTo = "/") {
  const s = stripe();
  const base = siteUrl(req);
  const session = await s.checkout.sessions.create({
    mode: "payment",
    line_items: [
      {
        quantity: 1,
        price_data: {
          currency: "usd",
          unit_amount: Number(process.env.STRIPE_PRICE_CENTS || 900),
          product_data: {
            name: `Cutroom — ${CREDIT_PACK} film credits`,
            description: "Each credit directs one film (4K costs two).",
          },
        },
      },
    ],
    metadata: { user_id: account.user_id, credits: String(CREDIT_PACK) },
    client_reference_id: account.user_id,
    success_url: `${base}${returnTo}${returnTo.includes("?") ? "&" : "?"}paid=1`,
    cancel_url: `${base}${returnTo}`,
  });
  return session.url!;
}
