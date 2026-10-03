"use client";
import { AnimatePresence, motion } from "framer-motion";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState, useSyncExternalStore } from "react";
import { startCheckout, timecode, useSession } from "@/lib/client";

type GalleryItem = {
  id: string;
  title: string | null;
  logline: string | null;
  brief: string | null;
  topic: string | null;
  aspect_ratio: string | null;
  length_s: number | null;
  status: string;
  stage: string | null;
  progress: number;
  video_url: string | null;
  video_4k_url: string | null;
  poster_url: string | null;
  created_at: string;
};

const STYLES = ["Documentary", "Explainer", "Noir", "Archival", "Nature", "Retro-futurist", "Cinematic trailer", "Kinetic type"];
const PIPELINE = [
  ["Brief", "a) what b) ratio c) length d) style"],
  ["Plan", "script-planning skill"],
  ["References", "consistency anchors"],
  ["Animatic", "keyframes + scratch VO"],
  ["Shots", "Veo 3.1 · Seedance 2.5"],
  ["Footage", "yt-dlp · Creative Commons"],
  ["Motion", "Hyperframes · Manim · Motion Canvas · Blender"],
  ["Voice", "Gemini TTS, with emotion"],
  ["Score", "ElevenLabs music"],
  ["Cut", "OpenTimelineIO → ffmpeg"],
  ["Captions", "word-level ASR"],
  ["Critique", "screenshots + transcript · Jev"],
  ["4K", "Real-ESRGAN"],
] as const;

export default function Home() {
  const router = useRouter();
  const { token, me, error: sessionError, refresh } = useSession();
  const [brief, setBrief] = useState("");
  const [ratio, setRatio] = useState<"16:9" | "9:16" | "1:1">("16:9");
  const [length, setLength] = useState(60);
  const [styles, setStyles] = useState<string[]>(["Documentary"]);
  const [styleText, setStyleText] = useState("");
  const [want4k, setWant4k] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [gallery, setGallery] = useState<GalleryItem[]>([]);
  const [paid, setPaid] = useState(false);

  useEffect(() => {
    fetch("/api/gallery").then((r) => r.json()).then((j) => setGallery(j.projects || [])).catch(() => {});
    const t = setTimeout(() => setPaid(!!new URLSearchParams(window.location.search).get("paid")), 0);
    return () => clearTimeout(t);
  }, []);
  useEffect(() => {
    if (paid && token) {
      const t = setTimeout(() => refresh(), 1500);
      return () => clearTimeout(t);
    }
  }, [paid, token, refresh]);

  const reel = useMemo(() => gallery.find((g) => g.video_url), [gallery]);
  const cost = want4k ? 2 : 1;

  async function roll() {
    if (!brief.trim()) {
      setMsg("Tell the studio what you want first.");
      return;
    }
    setBusy(true);
    setMsg(null);
    try {
      const r = await fetch("/api/projects", {
        method: "POST",
        headers: { "content-type": "application/json", ...(token ? { authorization: `Bearer ${token}` } : {}) },
        body: JSON.stringify({ brief, aspect_ratio: ratio, length_s: length, style: [...styles, styleText].filter(Boolean).join(", "), want_4k: want4k }),
      });
      const j = await r.json().catch(() => ({}));
      if (r.status === 402) {
        setMsg("Out of credits — opening checkout…");
        await startCheckout(token, "/");
        return;
      }
      if (!r.ok) throw new Error(j.error || "Could not start the film");
      router.push(`/p/${j.project.id}`);
    } catch (e) {
      setMsg((e as Error).message);
      setBusy(false);
    }
  }

  return (
    <main className="relative flex-1">
      {/* top bar */}
      <header className="fixed inset-x-0 top-0 z-50 border-b border-white/5 bg-bg/70 backdrop-blur-md">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 sm:px-6">
          <Link href="/" className="flex items-center gap-2">
            <span className="relative grid h-7 w-7 place-items-center rounded-full border border-amber/60">
              <span className="h-2.5 w-2.5 rounded-full bg-rec rec-dot" />
            </span>
            <span className="font-display text-2xl tracking-tight">Cutroom</span>
          </Link>
          <div className="flex items-center gap-2 font-mono text-xs">
            <span className="hidden rounded-full border border-line px-3 py-1 text-muted sm:inline">
              {me ? <><span className="text-amber">{me.credits}</span> credits</> : sessionError ? "offline" : "…"}
            </span>
            <button
              onClick={() => startCheckout(token).catch((e) => setMsg(e.message))}
              className="rounded-full bg-ink px-3 py-1 font-medium text-bg transition hover:bg-amber"
            >
              Buy credits
            </button>
          </div>
        </div>
      </header>

      {/* hero */}
      <section className="relative isolate min-h-[92vh] overflow-hidden pt-16">
        <div className="absolute inset-0 -z-10 aurora" />
        {reel?.video_url && (
          <video
            className="absolute inset-0 -z-10 h-full w-full object-cover opacity-40"
            src={reel.video_url}
            autoPlay
            muted
            loop
            playsInline
          />
        )}
        <div className="absolute inset-x-0 top-16 -z-10 h-[6vh] bg-black" />
        <div className="absolute inset-x-0 bottom-0 -z-10 h-[6vh] bg-black" />
        <div className="absolute inset-0 -z-10 bg-gradient-to-b from-transparent via-bg/30 to-bg" />

        <div className="mx-auto flex max-w-7xl flex-col gap-10 px-4 pb-16 pt-[12vh] sm:px-6 lg:flex-row lg:items-end">
          <div className="flex-1">
            <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="mb-5 flex items-center gap-3 font-mono text-[11px] uppercase tracking-[0.25em] text-muted">
              <span className="h-1.5 w-1.5 rounded-full bg-rec rec-dot" /> REC · {timecode(length)} · {ratio}
            </motion.div>
            <motion.h1
              initial={{ opacity: 0, y: 30, filter: "blur(10px)" }}
              animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
              transition={{ duration: 1.1, ease: [0.2, 0.7, 0.2, 1] }}
              className="font-display text-[13vw] leading-[0.88] tracking-tight sm:text-7xl lg:text-[7.5rem]"
            >
              A film studio
              <br />
              <span className="italic text-amber text-glow">your agents</span> can hire.
            </motion.h1>
            <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.5 }} className="mt-6 max-w-xl text-base text-muted sm:text-lg">
              Brief it like a director. Claude Code writes the script, shoots the keyframes, pulls real Creative Commons footage,
              animates the graphics, records a voice with feeling, scores it, cuts it, captions it — then watches its own cut and fixes it.
            </motion.p>
          </div>

          {/* composer */}
          <motion.div
            initial={{ opacity: 0, y: 40 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.25, duration: 0.8 }}
            className="w-full rounded-2xl border border-white/10 bg-panel/80 p-4 shadow-2xl backdrop-blur-xl sm:p-5 lg:w-[460px]"
          >
            <div className="mb-3 flex items-center justify-between font-mono text-[11px] uppercase tracking-widest text-muted">
              <span>Slate · Scene 1 · Take 1</span>
              <span className="text-amber">{cost} credit{cost > 1 ? "s" : ""}</span>
            </div>
            <label className="mb-1 block font-mono text-[11px] uppercase tracking-widest text-muted">a) What you want</label>
            <textarea
              value={brief}
              onChange={(e) => setBrief(e.target.value)}
              rows={3}
              placeholder="A 90-second explainer on how neoclouds rent GPUs to AI labs — and why it matters."
              className="w-full resize-none rounded-xl border border-line bg-bg/70 p-3 text-sm outline-none transition placeholder:text-muted/60 focus:border-amber/60"
            />
            <div className="mt-3 grid grid-cols-2 gap-3">
              <div>
                <label className="mb-1 block font-mono text-[11px] uppercase tracking-widest text-muted">b) Aspect</label>
                <div className="flex gap-1.5">
                  {(["16:9", "9:16", "1:1"] as const).map((r) => (
                    <button
                      key={r}
                      onClick={() => setRatio(r)}
                      className={`flex flex-1 items-center justify-center gap-1.5 rounded-lg border px-2 py-2 font-mono text-xs transition ${ratio === r ? "border-amber bg-amber/10 text-amber" : "border-line text-muted hover:text-ink"}`}
                    >
                      <span
                        className="inline-block border border-current"
                        style={{ width: r === "9:16" ? 7 : r === "1:1" ? 10 : 14, height: r === "9:16" ? 12 : r === "1:1" ? 10 : 8 }}
                      />
                      {r}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <label className="mb-1 flex justify-between font-mono text-[11px] uppercase tracking-widest text-muted">
                  <span>c) Length</span>
                  <span className="text-ink">{length >= 60 ? `${Math.floor(length / 60)}m${length % 60 ? ` ${length % 60}s` : ""}` : `${length}s`}</span>
                </label>
                <input type="range" min={30} max={240} step={15} value={length} onChange={(e) => setLength(+e.target.value)} className="mt-3 w-full" />
              </div>
            </div>
            <label className="mb-1 mt-3 block font-mono text-[11px] uppercase tracking-widest text-muted">d) Style</label>
            <div className="flex flex-wrap gap-1.5">
              {STYLES.map((s) => (
                <button
                  key={s}
                  onClick={() => setStyles((cur) => (cur.includes(s) ? cur.filter((x) => x !== s) : [...cur, s]))}
                  className={`rounded-full border px-2.5 py-1 text-xs transition ${styles.includes(s) ? "border-amber/70 bg-amber/10 text-amber" : "border-line text-muted hover:text-ink"}`}
                >
                  {s}
                </button>
              ))}
            </div>
            <input
              value={styleText}
              onChange={(e) => setStyleText(e.target.value)}
              placeholder="narrated like a university professor, warm archival grade…"
              className="mt-2 w-full rounded-lg border border-line bg-bg/70 px-3 py-2 text-xs outline-none placeholder:text-muted/60 focus:border-amber/60"
            />
            <div className="mt-4 flex items-center justify-between">
              <button onClick={() => setWant4k((v) => !v)} className="flex items-center gap-2 text-xs text-muted">
                <span className={`relative h-5 w-9 rounded-full transition ${want4k ? "bg-amber" : "bg-line"}`}>
                  <motion.span layout className="absolute top-0.5 h-4 w-4 rounded-full bg-ink" style={{ left: want4k ? 18 : 2 }} />
                </span>
                <span className={want4k ? "text-ink" : ""}>4K upscale</span>
              </button>
              <motion.button
                whileHover={{ scale: 1.03 }}
                whileTap={{ scale: 0.97 }}
                disabled={busy}
                onClick={roll}
                className="group relative flex items-center gap-2 overflow-hidden rounded-full bg-gradient-to-r from-amber to-amber-2 px-5 py-2.5 text-sm font-semibold text-black glow-amber disabled:opacity-60"
              >
                <span className="h-2 w-2 rounded-full bg-rec rec-dot" />
                {busy ? "Rolling…" : "Roll camera"}
              </motion.button>
            </div>
            <AnimatePresence>
              {(msg || (sessionError && !me)) && (
                <motion.p initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }} className="mt-3 text-xs text-rec">
                  {msg || sessionError}
                </motion.p>
              )}
              {paid && (
                <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mt-3 text-xs text-green">
                  Payment received — credits are on their way.
                </motion.p>
              )}
            </AnimatePresence>
          </motion.div>
        </div>
      </section>

      {/* pipeline strip */}
      <section className="relative border-y border-line bg-panel/60">
        <div className="sprockets h-3 opacity-60" />
        <div className="no-scrollbar mx-auto flex max-w-7xl gap-0 overflow-x-auto px-4 py-6 sm:px-6">
          {PIPELINE.map(([name, sub], i) => (
            <motion.div
              key={name}
              initial={{ opacity: 0, y: 12 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.05 }}
              className="relative min-w-[150px] flex-1 border-l border-line px-4 first:border-l-0"
            >
              <div className="font-mono text-[10px] text-amber">{String(i + 1).padStart(2, "0")}</div>
              <div className="mt-1 font-display text-xl">{name}</div>
              <div className="mt-1 text-[11px] leading-snug text-muted">{sub}</div>
            </motion.div>
          ))}
        </div>
        <div className="sprockets h-3 opacity-60" />
      </section>

      {/* claude code + agents */}
      <section className="mx-auto grid max-w-7xl gap-6 px-4 py-20 sm:px-6 lg:grid-cols-2">
        <div>
          <h2 className="font-display text-4xl sm:text-5xl">
            Built for <span className="italic text-amber">Claude Code</span>.
            <br />
            Open to every agent.
          </h2>
          <p className="mt-4 max-w-lg text-muted">
            Install the plugin and direct films from your terminal — skills for script planning, emotive voice, motion graphics,
            captions and self-critique. Or connect any MCP agent to the hosted studio and pay per film with Stripe.
          </p>
        </div>
        <ClaudeCodePanel apiKey={me?.api_key} />
      </section>

      {/* gallery */}
      <section className="mx-auto max-w-7xl px-4 pb-24 sm:px-6">
        <div className="mb-6 flex items-end justify-between">
          <h2 className="font-display text-4xl">Dailies</h2>
          <span className="font-mono text-xs text-muted">{gallery.length} reels</span>
        </div>
        {gallery.length === 0 ? (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {[0, 1, 2].map((i) => (
              <div key={i} className="aspect-video rounded-xl border border-line shimmer" />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {gallery.map((g, i) => (
              <GalleryCard key={g.id} g={g} i={i} />
            ))}
          </div>
        )}
      </section>

      <footer className="border-t border-line py-8 text-center font-mono text-[11px] text-muted">
        Supabase · Claude · Gemini · OpenRouter · ElevenLabs · Jev · Stripe · Vercel — every Creative Commons source credited.
      </footer>
    </main>
  );
}

function GalleryCard({ g, i }: { g: GalleryItem; i: number }) {
  const [hover, setHover] = useState(false);
  const live = g.status !== "done" && g.status !== "failed";
  return (
    <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: (i % 3) * 0.08 }}>
      <Link
        href={`/p/${g.id}`}
        onMouseEnter={() => setHover(true)}
        onMouseLeave={() => setHover(false)}
        className="group relative block aspect-video overflow-hidden rounded-xl border border-line bg-panel-2 transition hover:border-amber/50"
      >
        {g.video_url ? (
          hover ? (
            <video src={g.video_url} autoPlay muted loop playsInline className="h-full w-full object-cover" />
          ) : g.poster_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={g.poster_url} alt="" className="h-full w-full object-cover" />
          ) : (
            <video src={`${g.video_url}#t=2`} muted playsInline preload="metadata" className="h-full w-full object-cover" />
          )
        ) : (
          <div className="h-full w-full aurora" />
        )}
        <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-black/20 to-transparent" />
        <div className="absolute left-3 top-3 flex items-center gap-1.5 rounded-full bg-black/60 px-2 py-0.5 font-mono text-[10px]">
          {live ? (
            <>
              <span className="h-1.5 w-1.5 rounded-full bg-rec rec-dot" /> {g.stage || g.status} · {g.progress}%
            </>
          ) : g.status === "failed" ? (
            <span className="text-rec">failed</span>
          ) : (
            <>
              {g.aspect_ratio} · {g.video_4k_url ? "4K" : "HD"}
            </>
          )}
        </div>
        <div className="absolute inset-x-3 bottom-3">
          <div className="font-display text-xl leading-tight">{g.title || g.topic || "Untitled"}</div>
          <div className="mt-0.5 line-clamp-1 text-xs text-muted">{g.logline || g.brief}</div>
        </div>
      </Link>
    </motion.div>
  );
}

function ClaudeCodePanel({ apiKey }: { apiKey?: string }) {
  const origin = useSyncExternalStore(
    () => () => {},
    () => window.location.origin,
    () => "https://cutroom.vercel.app",
  );
  const repo = process.env.NEXT_PUBLIC_PLUGIN_REPO || "cutroom/cutroom";
  const key = apiKey || "cr_…";
  const blocks = [
    { label: "Install the plugin (local studio)", code: `claude plugin marketplace add ${repo}\nclaude plugin install cutroom@cutroom` },
    { label: "Or connect the hosted studio over MCP", code: `claude mcp add --transport http cutroom ${origin}/api/mcp \\\n  --header "x-api-key: ${key}"` },
    { label: "Then just ask", code: `> Make a 2-minute 16:9 explainer on how neoclouds work,\n  narrated like a university professor, warm archival style.` },
  ];
  return (
    <div className="overflow-hidden rounded-2xl border border-line bg-panel">
      <div className="flex items-center gap-1.5 border-b border-line px-4 py-2.5">
        <span className="h-2.5 w-2.5 rounded-full bg-[#ff5f57]" />
        <span className="h-2.5 w-2.5 rounded-full bg-[#febc2e]" />
        <span className="h-2.5 w-2.5 rounded-full bg-[#28c840]" />
        <span className="ml-3 font-mono text-[11px] text-muted">~/films — claude</span>
      </div>
      <div className="space-y-4 p-4">
        {blocks.map((b) => (
          <CodeBlock key={b.label} {...b} />
        ))}
      </div>
    </div>
  );
}

function CodeBlock({ label, code }: { label: string; code: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div>
      <div className="mb-1.5 flex items-center justify-between font-mono text-[10px] uppercase tracking-widest text-muted">
        <span>{label}</span>
        <button
          onClick={() => {
            navigator.clipboard.writeText(code).then(() => {
              setCopied(true);
              setTimeout(() => setCopied(false), 1200);
            });
          }}
          className="rounded border border-line px-2 py-0.5 normal-case tracking-normal text-ink transition hover:border-amber hover:text-amber"
        >
          {copied ? "copied" : "copy"}
        </button>
      </div>
      <pre className="overflow-x-auto rounded-lg bg-black/50 p-3 font-mono text-[12px] leading-relaxed text-ink/90">
        <code>{code}</code>
      </pre>
    </div>
  );
}
