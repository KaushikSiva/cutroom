"use client";
import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import { useCallback, useEffect, useState } from "react";

let _sb: SupabaseClient | null = null;
export function sb(): SupabaseClient | null {
  if (_sb) return _sb;
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !key) return null;
  _sb = createClient(url, key, { auth: { persistSession: true, autoRefreshToken: true } });
  return _sb;
}

export type Me = { credits: number; api_key: string; user_id: string };

/** Anonymous Supabase session + the caller's Cutroom account. */
export function useSession() {
  const [token, setToken] = useState<string | null>(null);
  const [me, setMe] = useState<Me | null>(null);
  const [error, setError] = useState<string | null>(() =>
    process.env.NEXT_PUBLIC_SUPABASE_URL && process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ? null : "Supabase is not configured",
  );

  const refresh = useCallback(async (t?: string | null) => {
    const tok = t ?? token;
    if (!tok) return;
    const r = await fetch("/api/me", { headers: { authorization: `Bearer ${tok}` } });
    const j = await r.json().catch(() => ({}));
    if (r.ok) setMe(j as Me);
    else setError(j.error || "Could not load account");
  }, [token]);

  useEffect(() => {
    const client = sb();
    if (!client) return;
    let cancelled = false;
    (async () => {
      let { data } = await client.auth.getSession();
      if (!data.session) {
        const res = await client.auth.signInAnonymously();
        if (res.error) {
          if (!cancelled) setError(res.error.message);
          return;
        }
        data = { session: res.data.session! };
      }
      const t = data.session?.access_token ?? null;
      if (cancelled) return;
      setToken(t);
      await refresh(t);
    })();
    const { data: sub } = client.auth.onAuthStateChange((_e, s) => setToken(s?.access_token ?? null));
    return () => {
      cancelled = true;
      sub.subscription.unsubscribe();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { token, me, error, refresh };
}

export async function startCheckout(token: string | null, returnTo = "/") {
  const r = await fetch("/api/checkout", {
    method: "POST",
    headers: { "content-type": "application/json", ...(token ? { authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify({ returnTo }),
  });
  const j = await r.json().catch(() => ({}));
  if (j.url) window.location.href = j.url;
  else throw new Error(j.error || "Checkout failed");
}

export function timecode(sec: number) {
  const s = Math.max(0, sec);
  const m = Math.floor(s / 60);
  const ss = Math.floor(s % 60);
  const ff = Math.floor((s % 1) * 24);
  return `${String(m).padStart(2, "0")}:${String(ss).padStart(2, "0")}:${String(ff).padStart(2, "0")}`;
}

export function ytThumb(id: string) {
  return `https://i.ytimg.com/vi/${id}/hqdefault.jpg`;
}
