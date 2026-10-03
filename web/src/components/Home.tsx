"use client";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
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

type Ratio = "16:9" | "9:16" | "1:1";

const STYLES = ["Documentary", "Explainer", "Noir", "Archival", "Nature", "Retro-futurist", "Cinematic trailer", "Kinetic type"];

/* The real pipeline, grouped the way a film crew would group it. Order matters here. */
const PHASES = [
  {
    name: "Pre-production",
    line: "Nothing is spent on video until the plan and animatic hold up.",
    stages: [
      ["Brief", "What, ratio, length, style"],
      ["Plan", "Script and shot list, a voice direction per line"],
      ["References", "One image per recurring subject, for consistency"],
      ["Animatic", "Keyframes and scratch voice on the plan's timing"],
    ],
  },
  {
    name: "Production",
    line: "Every department works in parallel.",
    stages: [
      ["Shots", "Veo 3.1 and Seedance 2.5"],
      ["Footage", "Creative Commons sections, original sound kept"],
      ["Motion", "Hyperframes, Manim, Motion Canvas, Blender"],
      ["Voice", "Gemini TTS, with emotion per line"],
      ["Score", "ElevenLabs music, ducked under the voice"],
    ],
  },
  {
    name: "Post",
    line: "The director watches its own cut and fixes it.",
    stages: [
      ["Cut", "OpenTimelineIO, rendered with ffmpeg at −16 LUFS"],
      ["Captions", "Word-level timing, current word highlighted"],
      ["Critique", "Contact sheets, transcript diff, up to three recuts"],
      ["4K", "Real-ESRGAN upscale, when you ask for it"],
    ],
  },
] as const;

const PACK_CENTS = 900;
const PACK_CREDITS = 10;
const perFilm = `$${(PACK_CENTS / PACK_CREDITS / 100).toFixed(2)}`;

export default function Home() {
  const router = useRouter();
  const { token, me, error: sessionError, refresh } = useSession();
  const [brief, setBrief] = useState("");
  const [ratio, setRatio] = useState<Ratio>("16:9");
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
        setMsg("Out of credits. Opening checkout…");
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

  const buy = () => startCheckout(token).catch((e) => setMsg(e.message));

  return (
    <main className="relative flex-1">
      <Nav credits={me?.credits} offline={!!sessionError && !me} onBuy={buy} />

      {/* hero */}
      <section className="cyc relative overflow-hidden pt-28 sm:pt-36">
        <div className="mx-auto max-w-6xl px-4 text-center sm:px-6">
          <motion.h1
            initial={{ opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, ease: [0.2, 0.7, 0.2, 1] }}
            className="display text-[13vw] sm:text-7xl lg:text-[6.5rem]"
          >
            A film studio
            <br />
            <span className="accent text-[1.08em]">your agents can hire.</span>
          </motion.h1>
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.35, duration: 0.6 }}
            className="mx-auto mt-7 max-w-xl text-lg leading-relaxed text-graphite sm:text-xl"
          >
            Brief it like a director.
            <br />
            Claude Code writes, shoots, scores, cuts and captions it.
            <br />
            Then it watches its own cut and fixes it.
          </motion.p>
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.5 }} className="mt-9 flex flex-wrap items-center justify-center gap-3">
            <a href="#brief" className="rounded-full bg-ink px-6 py-3 text-[15px] font-medium text-paper transition hover:bg-ink/85">
              Start a film
            </a>
            <a href="#interfaces" className="rounded-full border border-hairline bg-card px-6 py-3 text-[15px] font-medium text-ink transition hover:border-ink/30">
              Use it from Claude Code
            </a>
          </motion.div>
        </div>

        {/* the studio itself: brief on the left, monitor on the right, the edit underneath */}
        <motion.div
          id="brief"
          initial={{ opacity: 0, y: 40 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.25, duration: 0.9, ease: [0.2, 0.7, 0.2, 1] }}
          className="mx-auto mt-16 max-w-6xl scroll-mt-24 px-4 pb-24 sm:px-6"
        >
          <div className="window-shadow overflow-hidden rounded-[22px] border border-black/60 bg-screen text-screen-ink">
            <WindowBar title="New film" right={<span className="font-mono text-[11px] text-screen-muted">{cost} credit{cost > 1 ? "s" : ""}</span>} />
            <div className="grid lg:grid-cols-[420px_1fr]">
              {/* composer */}
              <div className="border-b border-screen-line p-5 lg:border-b-0 lg:border-r">
                <FieldLabel letter="a" text="What you want" />
                <textarea
                  value={brief}
                  onChange={(e) => setBrief(e.target.value)}
                  rows={4}
                  placeholder="A 90 second explainer on how neoclouds rent GPUs to AI labs, and why it matters."
                  className="w-full resize-none rounded-xl border border-screen-line bg-screen-2 p-3.5 text-[15px] leading-relaxed outline-none transition placeholder:text-screen-muted/70 focus:border-screen-muted"
                />
                <div className="mt-4 grid grid-cols-2 gap-4">
                  <div>
                    <FieldLabel letter="b" text="Aspect" />
                    <div className="flex gap-1 rounded-xl bg-screen-2 p-1">
                      {(["16:9", "9:16", "1:1"] as const).map((r) => (
                        <button
                          key={r}
                          onClick={() => setRatio(r)}
                          aria-pressed={ratio === r}
                          className={`flex flex-1 items-center justify-center gap-1.5 rounded-lg px-1.5 py-2 font-mono text-[11px] transition ${ratio === r ? "bg-screen-ink text-screen" : "text-screen-muted hover:text-screen-ink"}`}
                        >
                          <span
                            className="inline-block rounded-[2px] border border-current"
                            style={{ width: r === "9:16" ? 7 : r === "1:1" ? 10 : 14, height: r === "9:16" ? 12 : r === "1:1" ? 10 : 8 }}
                          />
                          {r}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div>
                    <FieldLabel letter="c" text="Length" value={fmtLen(length)} />
                    <input
                      type="range"
                      min={30}
                      max={240}
                      step={15}
                      value={length}
                      onChange={(e) => setLength(+e.target.value)}
                      aria-label="Length"
                      className="mt-3 w-full"
                    />
                  </div>
                </div>
                <div className="mt-4">
                  <FieldLabel letter="d" text="Style" />
                  <div className="flex flex-wrap gap-1.5">
                    {STYLES.map((s) => {
                      const on = styles.includes(s);
                      return (
                        <button
                          key={s}
                          onClick={() => setStyles((cur) => (on ? cur.filter((x) => x !== s) : [...cur, s]))}
                          aria-pressed={on}
                          className={`rounded-full border px-2.5 py-1 text-[12px] transition ${on ? "border-screen-ink bg-screen-ink text-screen" : "border-screen-line text-screen-muted hover:text-screen-ink"}`}
                        >
                          {s}
                        </button>
                      );
                    })}
                  </div>
                  <input
                    value={styleText}
                    onChange={(e) => setStyleText(e.target.value)}
                    placeholder="Narrated like a university professor, warm archival grade"
                    className="mt-2.5 w-full rounded-lg border border-screen-line bg-screen-2 px-3 py-2 text-[13px] outline-none placeholder:text-screen-muted/70 focus:border-screen-muted"
                  />
                </div>
                <div className="mt-5 flex items-center justify-between gap-3">
                  <button onClick={() => setWant4k((v) => !v)} aria-pressed={want4k} className="flex items-center gap-2 text-[13px] text-screen-muted">
                    <span className={`relative h-5 w-9 rounded-full transition ${want4k ? "bg-screen-ink" : "bg-screen-line"}`}>
                      <motion.span layout className={`absolute top-0.5 h-4 w-4 rounded-full ${want4k ? "bg-screen" : "bg-screen-muted"}`} style={{ left: want4k ? 18 : 2 }} />
                    </span>
                    <span className={want4k ? "text-screen-ink" : ""}>4K upscale</span>
                  </button>
                  <motion.button
                    whileTap={{ scale: 0.97 }}
                    disabled={busy}
                    onClick={roll}
                    className="flex items-center gap-2 rounded-full bg-screen-ink px-5 py-2.5 text-sm font-semibold text-screen transition hover:bg-white disabled:opacity-60"
                  >
                    <span className="h-2 w-2 rounded-full bg-rec rec-dot" />
                    {busy ? "Rolling…" : "Roll camera"}
                  </motion.button>
                </div>
                <AnimatePresence>
                  {(msg || (sessionError && !me)) && (
                    <motion.p initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }} className="mt-3 text-[13px] text-[#ff7b75]">
                      {msg || sessionError}
                    </motion.p>
                  )}
                  {paid && (
                    <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mt-3 text-[13px] text-[#6fd39e]">
                      Payment received. Your credits are on their way.
                    </motion.p>
                  )}
                </AnimatePresence>
              </div>

              {/* monitor */}
              <Monitor ratio={ratio} length={length} brief={brief} reelUrl={reel?.video_url || null} />
            </div>
            <Timeline length={length} />
          </div>
        </motion.div>
      </section>

      {/* how a film gets made */}
      <section id="how" className="scroll-mt-20 border-t border-hairline bg-paper">
        <div className="mx-auto max-w-6xl px-4 py-24 sm:px-6">
          <SectionHead title="How a film" accent="gets made" sub="Thirteen stages, in the order a real crew would run them. Every one streams live to the film's page." />
          <div className="mt-14 grid gap-4 lg:grid-cols-3">
            {PHASES.map((ph, pi) => {
              const start = PHASES.slice(0, pi).reduce((n, p) => n + p.stages.length, 0);
              return (
                <motion.div
                  key={ph.name}
                  initial={{ opacity: 0, y: 16 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true, margin: "-80px" }}
                  transition={{ delay: pi * 0.08 }}
                  className="card-shadow rounded-[20px] border border-hairline bg-card p-6"
                >
                  <div className="flex items-baseline justify-between">
                    <h3 className="display text-2xl">{ph.name}</h3>
                    <span className="font-mono text-[11px] text-graphite">
                      {String(start + 1).padStart(2, "0")}–{String(start + ph.stages.length).padStart(2, "0")}
                    </span>
                  </div>
                  <p className="mt-1.5 text-[14px] text-graphite">{ph.line}</p>
                  <ol className="mt-5 divide-y divide-hairline border-t border-hairline">
                    {ph.stages.map(([name, sub], i) => (
                      <li key={name} className="flex gap-3 py-3">
                        <span className="w-6 shrink-0 pt-0.5 font-mono text-[11px] text-graphite">{String(start + i + 1).padStart(2, "0")}</span>
                        <div>
                          <div className="text-[15px] font-medium">{name}</div>
                          <div className="text-[13px] leading-snug text-graphite">{sub}</div>
                        </div>
                      </li>
                    ))}
                  </ol>
                </motion.div>
              );
            })}
          </div>
        </div>
      </section>

      {/* every interface */}
      <section id="interfaces" className="scroll-mt-20 bg-paper-2/60">
        <div className="mx-auto max-w-6xl px-4 py-24 sm:px-6">
          <SectionHead title="One studio," accent="every interface" sub="Brief a film right here, direct it from your terminal, or let any agent order one over MCP." />
          <div className="mt-14 grid gap-5 lg:grid-cols-3">
            <InterfaceCard title="In Cutroom" sub="This page. No AI subscription needed." chrome={<WindowBar title="cutroom / new film" compact />}>
              <WebMock />
            </InterfaceCard>
            <InterfaceCard title="Terminal" sub="Claude Code with the Cutroom plugin" chrome={<WindowBar title="~/films" compact />}>
              <TerminalMock />
            </InterfaceCard>
            <InterfaceCard title="Any agent" sub="Claude Desktop, Cursor, any MCP client" chrome={<WindowBar title="Agent session" compact />}>
              <AgentMock />
            </InterfaceCard>
          </div>
          <SetupPanel apiKey={me?.api_key} />
        </div>
      </section>

      {/* dailies */}
      <section id="dailies" className="scroll-mt-20 border-t border-hairline">
        <div className="mx-auto max-w-6xl px-4 py-24 sm:px-6">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <SectionHead title="Dailies" accent="" sub="Films made by the studio. Hover to play." left />
            <span className="font-mono text-[12px] text-graphite">{gallery.length} reels</span>
          </div>
          <div className="mt-10 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {gallery.length === 0
              ? [0, 1, 2].map((i) => <div key={i} className="aspect-video rounded-[18px] border border-hairline shimmer" />)
              : gallery.map((g, i) => <GalleryCard key={g.id} g={g} i={i} />)}
          </div>
        </div>
      </section>

      {/* cost */}
      <section id="cost" className="scroll-mt-20 px-4 pb-24 sm:px-6">
        <div className="mx-auto grid max-w-6xl items-center gap-8 overflow-hidden rounded-[24px] bg-screen p-8 text-screen-ink sm:p-12 lg:grid-cols-[1fr_auto]">
          <div>
            <div className="flex items-baseline gap-3">
              <span className="display text-6xl sm:text-7xl">{perFilm}</span>
              <span className="accent text-2xl text-screen-muted sm:text-3xl">for a one minute film</span>
            </div>
            <p className="mt-5 max-w-xl text-[15px] leading-relaxed text-screen-muted">
              One credit directs one film, start to finish: plan, shots, footage, voice, score, cut, captions and critique. Credits come in packs of{" "}
              {PACK_CREDITS} for ${(PACK_CENTS / 100).toFixed(0)}. A 4K upscale uses two.
            </p>
          </div>
          <div className="flex flex-col items-start gap-3 lg:items-end">
            <button onClick={buy} className="rounded-full bg-screen-ink px-6 py-3 text-[15px] font-medium text-screen transition hover:bg-white">
              Buy {PACK_CREDITS} credits
            </button>
            <span className="font-mono text-[12px] text-screen-muted">
              {me ? `You have ${me.credits} credit${me.credits === 1 ? "" : "s"}` : "Checkout through Stripe"}
            </span>
          </div>
        </div>
      </section>

      <footer className="border-t border-hairline">
        <div className="mx-auto flex max-w-6xl flex-col gap-3 px-4 py-8 text-[13px] text-graphite sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <Logo />
          <span>Every Creative Commons clip and track is credited on the film it appears in.</span>
        </div>
      </footer>
    </main>
  );
}

/* ---------------------------------------------------------------- chrome */

function Logo() {
  return (
    <Link href="/" className="flex items-center gap-2 text-ink">
      <span className="grid h-6 w-6 place-items-center rounded-full border-[1.5px] border-ink">
        <span className="h-2 w-2 rounded-full bg-rec rec-dot" />
      </span>
      <span className="display text-[22px] tracking-[-0.04em]">Cutroom</span>
    </Link>
  );
}

function Nav({ credits, offline, onBuy }: { credits?: number; offline: boolean; onBuy: () => void }) {
  return (
    <header className="fixed inset-x-0 top-0 z-50 border-b border-hairline/70 bg-paper/80 backdrop-blur-md">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
        <Logo />
        <nav className="hidden items-center rounded-full border border-hairline bg-card/70 px-1.5 py-1 text-[14px] md:flex">
          {[
            ["How it works", "#how"],
            ["Interfaces", "#interfaces"],
            ["Dailies", "#dailies"],
            ["Cost", "#cost"],
          ].map(([l, h]) => (
            <a key={h} href={h} className="rounded-full px-4 py-1.5 text-graphite transition hover:bg-paper-2 hover:text-ink">
              {l}
            </a>
          ))}
        </nav>
        <div className="flex items-center gap-2">
          <span className="hidden font-mono text-[12px] text-graphite sm:inline">
            {credits != null ? `${credits} credits` : offline ? "offline" : "…"}
          </span>
          <button onClick={onBuy} className="rounded-full bg-ink px-4 py-2 text-[14px] font-medium text-paper transition hover:bg-ink/85">
            Buy credits
          </button>
        </div>
      </div>
    </header>
  );
}

function WindowBar({ title, right, compact }: { title: string; right?: React.ReactNode; compact?: boolean }) {
  return (
    <div className={`flex items-center gap-3 border-b border-screen-line ${compact ? "px-4 py-3" : "px-5 py-3.5"}`}>
      <div className="flex gap-1.5">
        <span className="h-3 w-3 rounded-full bg-[#ff5f57]" />
        <span className="h-3 w-3 rounded-full bg-[#febc2e]" />
        <span className="h-3 w-3 rounded-full bg-[#28c840]" />
      </div>
      <span className="flex-1 truncate text-center font-mono text-[11px] text-screen-muted">{title}</span>
      <span className="min-w-12 text-right">{right}</span>
    </div>
  );
}

function FieldLabel({ letter, text, value }: { letter: string; text: string; value?: string }) {
  return (
    <div className="mb-2 flex items-baseline justify-between text-[12px] text-screen-muted">
      <span>
        <span className="font-mono">{letter})</span> {text}
      </span>
      {value && <span className="font-mono text-screen-ink">{value}</span>}
    </div>
  );
}

function SectionHead({ title, accent, sub, left }: { title: string; accent: string; sub: string; left?: boolean }) {
  return (
    <div className={left ? "" : "mx-auto max-w-2xl text-center"}>
      <h2 className="display text-5xl sm:text-6xl">
        {title} {accent && <span className="accent">{accent}</span>}
      </h2>
      <p className="mt-4 text-[17px] leading-relaxed text-graphite">{sub}</p>
    </div>
  );
}

const fmtClock = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
const fmtLen = (s: number) => (s >= 60 ? `${Math.floor(s / 60)}m${s % 60 ? ` ${s % 60}s` : ""}` : `${s}s`);

/* ---------------------------------------------------------------- monitor + timeline */

function Monitor({ ratio, length, brief, reelUrl }: { ratio: Ratio; length: number; brief: string; reelUrl: string | null }) {
  const frame = ratio === "9:16" ? "aspect-[9/16] h-[300px] sm:h-[360px]" : ratio === "1:1" ? "aspect-square h-[260px] sm:h-[340px]" : "aspect-video w-full max-w-[560px]";
  return (
    <div className="flex flex-col p-5">
      <div className="mb-3 flex items-center justify-between font-mono text-[11px] text-screen-muted">
        <span>Preview</span>
        <span>
          0:00 / {fmtClock(length)} · {ratio}
        </span>
      </div>
      <div className="grid flex-1 place-items-center rounded-xl bg-black/40 p-4 sm:p-6">
        <motion.div layout transition={{ type: "spring", stiffness: 140, damping: 22 }} className={`relative overflow-hidden rounded-md ${frame}`}>
          {reelUrl ? (
            <video src={reelUrl} autoPlay muted loop playsInline className="absolute inset-0 h-full w-full object-cover" />
          ) : (
            <div className="standby absolute inset-0" />
          )}
          <div className="absolute inset-0 bg-gradient-to-t from-black/75 via-black/10 to-transparent" />
          <div className="absolute left-3 top-3 flex items-center gap-1.5 font-mono text-[10px] text-white/80">
            <span className="h-1.5 w-1.5 rounded-full bg-rec rec-dot" /> {reelUrl ? "Latest reel" : "Scene 1 · Take 1"}
          </div>
          <div className="absolute inset-x-4 bottom-4">
            <p className="accent line-clamp-3 text-lg leading-snug text-white sm:text-xl">
              {brief.trim() || "Your brief becomes the first line of the script."}
            </p>
          </div>
        </motion.div>
      </div>
    </div>
  );
}

const TRACKS: { id: string; label: string; color: string; clips: [number, number, string][] }[] = [
  { id: "V2", label: "Motion", color: "var(--trk-g)", clips: [[0, 9, "Title"], [41, 14, "Map"], [80, 12, "Lower third"]] },
  { id: "V1", label: "Picture", color: "var(--trk-v)", clips: [[0, 18, "Veo"], [18, 22, "Archival"], [40, 17, "Seedance"], [57, 25, "Archival"], [82, 18, "Veo"]] },
  { id: "A1", label: "Voice", color: "var(--trk-a)", clips: [[3, 30, "Narration"], [36, 28, "Narration"], [68, 29, "Narration"]] },
  { id: "A2", label: "Score", color: "var(--trk-m)", clips: [[0, 100, "Score, ducked under voice"]] },
];

function Timeline({ length }: { length: number }) {
  const reduce = !!useReducedMotion();
  const ticks = 5;
  return (
    <div className="border-t border-screen-line bg-screen-2/60 px-5 pb-5 pt-3">
      <div className="mb-2 flex items-center justify-between font-mono text-[10px] text-screen-muted">
        <span>Timeline</span>
        <span className="hidden sm:inline">OpenTimelineIO</span>
      </div>
      <div className="flex gap-3">
        <div className="w-[52px] shrink-0 pt-[18px] sm:w-[84px]">
          {TRACKS.map((t) => (
            <div key={t.id} className="mb-1.5 flex h-7 items-center gap-2 font-mono text-[10px] text-screen-muted last:mb-0">
              <span className="text-screen-ink">{t.id}</span>
              <span className="hidden sm:inline">{t.label}</span>
            </div>
          ))}
        </div>
        <div className="relative min-w-0 flex-1">
          <div className="mb-1.5 flex h-3 justify-between font-mono text-[9px] text-screen-muted">
            {Array.from({ length: ticks }, (_, i) => (
              <span key={i}>{timecode((length * i) / (ticks - 1)).slice(0, 5)}</span>
            ))}
          </div>
          <div className="relative space-y-1.5">
            {TRACKS.map((t, ti) => (
              <TrackRow key={t.id} t={t} ti={ti} reduce={reduce} />
            ))}
            <Playhead reduce={reduce} />
          </div>
        </div>
      </div>
    </div>
  );
}

function TrackRow({ t, ti, reduce }: { t: (typeof TRACKS)[number]; ti: number; reduce: boolean }) {
  return (
    <div className="ruler relative h-7 overflow-hidden rounded-md bg-screen">
      {t.clips.map(([start, w, label], ci) => (
        <motion.div
          key={ci}
          initial={reduce ? false : { scaleX: 0, opacity: 0 }}
          whileInView={{ scaleX: 1, opacity: 1 }}
          viewport={{ once: true }}
          transition={{ delay: 0.6 + ti * 0.18 + ci * 0.12, duration: 0.5, ease: [0.2, 0.7, 0.2, 1] }}
          style={{ left: `${start}%`, width: `calc(${w}% - 2px)`, background: `color-mix(in srgb, ${t.color} 32%, transparent)`, borderColor: t.color, transformOrigin: "left" }}
          className="absolute inset-y-0.5 overflow-hidden rounded-[5px] border-l-2 px-1.5"
        >
          <span className="block truncate pt-[5px] text-[10px] text-screen-ink/90">{label}</span>
        </motion.div>
      ))}
    </div>
  );
}

function Playhead({ reduce }: { reduce: boolean }) {
  return (
    <motion.div
      aria-hidden
      className="pointer-events-none absolute -top-1 bottom-0 z-10 w-px bg-rec"
      initial={{ left: "0%" }}
      animate={reduce ? { left: "38%" } : { left: ["0%", "100%"] }}
      transition={reduce ? { duration: 0 } : { duration: 14, ease: "linear", repeat: Infinity, delay: 1.6 }}
    >
      <span className="absolute -left-[4px] -top-px h-2 w-[9px] rounded-b-sm bg-rec" />
    </motion.div>
  );
}

/* ---------------------------------------------------------------- interface cards */

function InterfaceCard({ title, sub, chrome, children }: { title: string; sub: string; chrome: React.ReactNode; children: React.ReactNode }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      className="card-shadow flex flex-col overflow-hidden rounded-[20px] border border-hairline bg-card"
    >
      <div className="m-2 mb-0 overflow-hidden rounded-[14px] bg-screen text-screen-ink">
        {chrome}
        <div className="h-[300px] p-4">{children}</div>
      </div>
      <div className="px-6 py-5">
        <h3 className="display text-xl">{title}</h3>
        <p className="mt-0.5 text-[14px] text-graphite">{sub}</p>
      </div>
    </motion.div>
  );
}

function WebMock() {
  return (
    <div className="flex h-full flex-col text-[13px]">
      <div className="ml-auto max-w-[88%] rounded-2xl rounded-br-md bg-screen-2 px-3.5 py-2.5 leading-snug">
        A 60 second explainer on why data centres are built beside rivers. 16:9, calm documentary.
      </div>
      <div className="mt-3 space-y-2 leading-snug text-screen-muted">
        <p>
          <span className="text-screen-ink">Plan saved.</span> 14 shots, 3 archival clips, 2 maps.
        </p>
        <p>Animatic passed review. Rendering shots now.</p>
      </div>
      <div className="mt-auto">
        <div className="mb-2 h-1 overflow-hidden rounded-full bg-screen-2">
          <div className="h-full w-[62%] rounded-full bg-screen-ink" />
        </div>
        <div className="flex justify-between font-mono text-[10px] text-screen-muted">
          <span>Shots · 62%</span>
          <span className="flex items-center gap-1">
            <span className="h-1.5 w-1.5 rounded-full bg-rec rec-dot" /> Live
          </span>
        </div>
      </div>
    </div>
  );
}

function TerminalMock() {
  return (
    <div className="font-mono text-[12px] leading-[1.75]">
      <p>
        <span className="text-[#6fd39e]">~</span> <span className="text-screen-muted">$</span> claude
      </p>
      <p className="text-screen-muted">╭ Claude Code · cutroom plugin</p>
      <p>
        <span className="text-screen-muted">&gt;</span> make a 2 minute explainer on how neoclouds work
      </p>
      <p className="text-[#8fa6ec]">Planning 19 shots…</p>
      <p>
        <span className="text-[#6fd39e]">✓</span> Animatic reviewed
      </p>
      <p>
        <span className="text-[#6fd39e]">✓</span> Critique round 2: no notes above minor
      </p>
      <p>
        <span className="text-[#6fd39e]">✓</span> Published: neoclouds.mp4
      </p>
      <p>
        <span className="text-[#6fd39e]">~</span> <span className="text-screen-muted">$</span> <span className="inline-block h-3.5 w-2 translate-y-0.5 bg-screen-ink rec-dot" />
      </p>
    </div>
  );
}

function AgentMock() {
  return (
    <div className="flex h-full flex-col text-[13px]">
      <div className="ml-auto max-w-[85%] rounded-2xl rounded-br-md bg-screen-2 px-3.5 py-2.5 leading-snug">
        Make a 30 second vertical trailer for our launch
      </div>
      <p className="mt-3 text-[11px] text-screen-muted">Used 2 tools</p>
      <div className="mt-1.5 space-y-1.5">
        {[
          ["make_video", "queued"],
          ["get_status", "assemble · 84%"],
        ].map(([t, r]) => (
          <div key={t} className="flex items-center justify-between rounded-lg border border-screen-line px-3 py-2 font-mono text-[11px]">
            <span>↗ {t}</span>
            <span className="text-screen-muted">{r}</span>
          </div>
        ))}
      </div>
      <p className="mt-3 leading-snug text-screen-muted">
        <span className="text-screen-ink">Done.</span> Your trailer is cut and captioned. It used 1 credit.
      </p>
    </div>
  );
}

function SetupPanel({ apiKey }: { apiKey?: string }) {
  const origin = useSyncExternalStore(
    () => () => {},
    () => window.location.origin,
    () => "https://cutroom.vercel.app",
  );
  const repo = process.env.NEXT_PUBLIC_PLUGIN_REPO || "cutroom/cutroom";
  const key = apiKey || "cr_…";
  const tabs = [
    { label: "Claude Code plugin", code: `claude plugin marketplace add ${repo}\nclaude plugin install cutroom@cutroom` },
    { label: "Hosted studio over MCP", code: `claude mcp add --transport http cutroom ${origin}/api/mcp \\\n  --header "x-api-key: ${key}"` },
    { label: "Then just ask", code: `> Make a 2 minute 16:9 explainer on how neoclouds work,\n  narrated like a university professor, warm archival style.` },
  ];
  const [tab, setTab] = useState(0);
  const [copied, setCopied] = useState(false);
  const cur = tabs[tab];
  return (
    <div className="card-shadow mt-8 overflow-hidden rounded-[20px] border border-hairline bg-card">
      <div className="flex flex-wrap items-center gap-1 border-b border-hairline p-2">
        {tabs.map((t, i) => (
          <button
            key={t.label}
            onClick={() => setTab(i)}
            aria-pressed={tab === i}
            className={`rounded-full px-4 py-1.5 text-[14px] transition ${tab === i ? "bg-ink text-paper" : "text-graphite hover:text-ink"}`}
          >
            {t.label}
          </button>
        ))}
        <button
          onClick={() =>
            navigator.clipboard.writeText(cur.code).then(() => {
              setCopied(true);
              setTimeout(() => setCopied(false), 1200);
            })
          }
          className="ml-auto rounded-full border border-hairline px-3.5 py-1.5 text-[13px] text-ink transition hover:border-ink/30"
        >
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre className="overflow-x-auto p-5 font-mono text-[13px] leading-relaxed text-ink">
        <code>{cur.code}</code>
      </pre>
    </div>
  );
}

/* ---------------------------------------------------------------- dailies */

function GalleryCard({ g, i }: { g: GalleryItem; i: number }) {
  const [hover, setHover] = useState(false);
  const live = g.status !== "done" && g.status !== "failed";
  return (
    <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: (i % 3) * 0.08 }}>
      <Link href={`/p/${g.id}`} onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)} className="group block">
        <div className="card-shadow relative aspect-video overflow-hidden rounded-[18px] bg-screen">
          {g.video_url ? (
            hover ? (
              <video src={g.video_url} autoPlay muted loop playsInline className="h-full w-full object-cover" />
            ) : g.poster_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={g.poster_url} alt="" className="h-full w-full object-cover transition duration-500 group-hover:scale-[1.02]" />
            ) : (
              <video src={`${g.video_url}#t=2`} muted playsInline preload="metadata" className="h-full w-full object-cover" />
            )
          ) : (
            <div className="standby h-full w-full" />
          )}
          <div className="absolute left-3 top-3 flex items-center gap-1.5 rounded-full bg-black/60 px-2.5 py-1 font-mono text-[10px] text-white backdrop-blur">
            {live ? (
              <>
                <span className="h-1.5 w-1.5 rounded-full bg-rec rec-dot" /> {g.stage || g.status} · {g.progress}%
              </>
            ) : g.status === "failed" ? (
              <span className="text-[#ff7b75]">Failed</span>
            ) : (
              <>
                {g.aspect_ratio} · {g.video_4k_url ? "4K" : "HD"}
              </>
            )}
          </div>
        </div>
        <div className="mt-3 px-1">
          <div className="display text-lg leading-tight">{g.title || g.topic || "Untitled"}</div>
          <div className="mt-0.5 line-clamp-1 text-[14px] text-graphite">{g.logline || g.brief}</div>
        </div>
      </Link>
    </motion.div>
  );
}
