"use client";
import { AnimatePresence, motion } from "framer-motion";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { sb, timecode, ytThumb } from "@/lib/client";

type Ev = { id: number; project_id: string; kind: string; message: string; data: Record<string, unknown> | null; created_at: string };
type Shot = {
  id: string;
  kind?: string;
  duration_s?: number;
  narration?: string;
  direction?: string;
  visual?: string;
  motion?: boolean;
  engine?: string;
  youtube_query?: string;
};
type Project = {
  id: string;
  topic: string | null;
  brief: string | null;
  aspect_ratio: string | null;
  length_s: number | null;
  style: string | null;
  want_4k: boolean;
  status: string;
  stage: string | null;
  progress: number;
  title: string | null;
  logline: string | null;
  script: { title?: string; logline?: string; shots?: Shot[]; references?: { name: string; prompt: string }[] } | null;
  credits: { kind?: string; title?: string; channel?: string; url?: string; license?: string; used?: number[][] }[] | null;
  video_url: string | null;
  video_4k_url: string | null;
  poster_url: string | null;
  error: string | null;
  created_at: string;
};

const STAGES = [
  ["brief", "Brief"],
  ["plan", "Plan"],
  ["references", "Refs"],
  ["animatic", "Animatic"],
  ["shots", "Shots"],
  ["footage", "Footage"],
  ["graphics", "Motion"],
  ["voice", "Voice"],
  ["music", "Score"],
  ["assemble", "Cut"],
  ["captions", "Captions"],
  ["critique", "Critique"],
  ["recut", "Recut"],
  ["upscale", "4K"],
  ["done", "Wrap"],
] as const;

const isVideo = (u?: unknown) => typeof u === "string" && /\.(mp4|webm|mov|m4v)(\?|$)/i.test(u);
const str = (v: unknown) => (typeof v === "string" ? v : v == null ? "" : String(v));

export default function Studio({ id }: { id: string }) {
  const [project, setProject] = useState<Project | null>(null);
  const [events, setEvents] = useState<Ev[]>([]);
  const [missing, setMissing] = useState(false);
  const seen = useRef(new Set<number>());

  useEffect(() => {
    let alive = true;
    const load = async () => {
      const r = await fetch(`/api/projects/${id}`, { cache: "no-store" });
      if (r.status === 404) {
        if (alive) setMissing(true);
        return;
      }
      const j = await r.json().catch(() => null);
      if (!alive || !j?.project) return;
      setProject(j.project);
      const fresh = (j.events as Ev[]).filter((e) => !seen.current.has(e.id));
      fresh.forEach((e) => seen.current.add(e.id));
      if (fresh.length) setEvents((cur) => [...cur, ...fresh].sort((a, b) => a.id - b.id));
    };
    load();
    // polling fallback (Realtime below makes it instant when configured)
    const t = setInterval(load, 4000);
    const client = sb();
    const ch = client
      ?.channel(`studio-${id}`)
      .on("postgres_changes", { event: "INSERT", schema: "public", table: "events", filter: `project_id=eq.${id}` }, (p) => {
        const e = p.new as Ev;
        if (seen.current.has(e.id)) return;
        seen.current.add(e.id);
        setEvents((cur) => [...cur, e].sort((a, b) => a.id - b.id));
      })
      .on("postgres_changes", { event: "UPDATE", schema: "public", table: "projects", filter: `id=eq.${id}` }, (p) => setProject(p.new as Project))
      .subscribe();
    return () => {
      alive = false;
      clearInterval(t);
      if (ch) client?.removeChannel(ch);
    };
  }, [id]);

  const view = useMemo(() => derive(project, events), [project, events]);

  if (missing)
    return (
      <div className="grid min-h-screen place-items-center">
        <div className="text-center">
          <div className="font-display text-5xl">Reel not found</div>
          <Link href="/" className="mt-4 inline-block text-amber underline">Back to the studio</Link>
        </div>
      </div>
    );

  const p = project;
  const done = p?.status === "done";
  const failed = p?.status === "failed";
  const title = p?.title || p?.script?.title || p?.topic || "Untitled";

  return (
    <main className="relative min-h-screen pb-24">
      <header className="sticky top-0 z-40 border-b border-white/5 bg-bg/80 backdrop-blur-md">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
          <Link href="/" className="font-display text-2xl">Cutroom</Link>
          <div className="flex items-center gap-3 font-mono text-[11px]">
            {!done && !failed && (
              <span className="flex items-center gap-1.5 text-rec">
                <span className="h-2 w-2 rounded-full bg-rec rec-dot" /> LIVE
              </span>
            )}
            {done && <span className="text-green">● WRAPPED</span>}
            {failed && <span className="text-rec">● FAILED</span>}
            <span className="text-muted">{p ? `${p.aspect_ratio} · ${timecode(p.length_s || 0)}` : "…"}</span>
          </div>
        </div>
        <ProgressBar progress={p?.progress || 0} failed={failed} />
      </header>

      <div className="mx-auto max-w-7xl px-4 sm:px-6">
        {/* title block */}
        <section className="pt-10">
          <div className="font-mono text-[11px] uppercase tracking-[0.25em] text-muted">Production · {id.slice(0, 8)}</div>
          <motion.h1 key={title} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="mt-2 font-display text-4xl leading-tight sm:text-6xl">
            {title}
          </motion.h1>
          {(p?.logline || p?.script?.logline) && <p className="mt-2 max-w-3xl text-muted">{p?.logline || p?.script?.logline}</p>}
          {!p?.logline && !p?.script?.logline && p?.brief && <p className="mt-2 max-w-3xl text-muted">“{p.brief}”</p>}
          {p?.style && <p className="mt-1 font-mono text-xs text-muted/80">style: {p.style}</p>}
        </section>

        <StageRail stage={p?.stage || "brief"} progress={p?.progress || 0} done={done} />

        {failed && p?.error && (
          <div className="mt-6 rounded-xl border border-rec/40 bg-rec/10 p-4 font-mono text-sm text-rec">{p.error}</div>
        )}

        <div className="mt-8 grid gap-6 lg:grid-cols-[1fr_380px]">
          {/* left: screen */}
          <div className="space-y-6">
            <Screen project={p} view={view} />
            <Storyboard view={view} />
            {view.clips.length > 0 && <FootageBin clips={view.clips} />}
          </div>
          {/* right: director + panels */}
          <div className="space-y-6">
            <DirectorFeed events={events} />
            {view.critiques.length > 0 && <CritiquePanel critiques={view.critiques} />}
            <AudioPanel view={view} />
            <CreditsPanel credits={p?.credits || view.ledger} />
          </div>
        </div>
      </div>
    </main>
  );
}

/* ---------------------------------------------------------------- derive view */
function derive(p: Project | null, events: Ev[]) {
  const shots = new Map<string, { plan?: Shot; keyframe?: string; shot?: string; model?: string; graphic?: string; engine?: string; clip?: Record<string, unknown>; voice?: string }>();
  for (const s of p?.script?.shots || []) shots.set(s.id, { plan: s });
  const refs: { name: string; url: string }[] = [];
  const clips: Record<string, unknown>[] = [];
  const cuts: { round: number; url: string; duration?: number }[] = [];
  const critiques: { round: number; issues: unknown[]; contact_sheet_url?: string; message: string }[] = [];
  const voices: { shot_id: string; url: string; duration?: number }[] = [];
  let music: { url: string; message: string } | null = null;
  let animatic: string | null = null;
  let captions: string | null = null;
  let upscale: string | null = null;
  for (const e of events) {
    const d = e.data || {};
    const sid = str(d.shot_id);
    const slot = () => {
      if (!shots.has(sid)) shots.set(sid, {});
      return shots.get(sid)!;
    };
    switch (e.kind) {
      case "reference":
        refs.push({ name: str(d.name), url: str(d.url) });
        break;
      case "keyframe":
        if (sid) slot().keyframe = str(d.url);
        break;
      case "shot":
        if (sid) Object.assign(slot(), { shot: str(d.url), model: str(d.model) });
        break;
      case "graphic":
        if (sid) Object.assign(slot(), { graphic: str(d.url), engine: str(d.engine) });
        break;
      case "clip":
        clips.push(d);
        if (sid) slot().clip = d;
        break;
      case "voice":
        voices.push({ shot_id: sid, url: str(d.url), duration: Number(d.duration) || undefined });
        if (sid) slot().voice = str(d.url);
        break;
      case "music":
        music = { url: str(d.url), message: e.message };
        break;
      case "animatic":
        animatic = str(d.url);
        break;
      case "cut":
        cuts.push({ round: Number(d.round) || cuts.length + 1, url: str(d.url), duration: Number(d.duration) || undefined });
        break;
      case "captions":
        captions = str(d.url);
        break;
      case "critique":
        critiques.push({ round: Number(d.round) || critiques.length + 1, issues: (d.issues as unknown[]) || [], contact_sheet_url: str(d.contact_sheet_url) || undefined, message: e.message });
        break;
      case "upscale":
        upscale = str(d.url);
        break;
    }
  }
  const ledger = clips
    .filter((c) => c.youtube_id)
    .map((c) => ({ kind: "footage", title: str(c.title), channel: str(c.channel), url: `https://www.youtube.com/watch?v=${str(c.youtube_id)}`, license: str(c.license) }));
  return {
    shots: [...shots.entries()].filter(([k]) => k).map(([id, v]) => ({ id, ...v })),
    refs,
    clips,
    cuts,
    critiques,
    voices,
    music: music as { url: string; message: string } | null,
    animatic: animatic as string | null,
    captions: captions as string | null,
    upscale: upscale as string | null,
    ledger,
  };
}
type View = ReturnType<typeof derive>;

/* ---------------------------------------------------------------- pieces */
function ProgressBar({ progress, failed }: { progress: number; failed: boolean }) {
  return (
    <div className="h-[2px] w-full bg-line">
      <motion.div
        className={`h-full ${failed ? "bg-rec" : "bg-gradient-to-r from-amber-2 via-amber to-cyan"}`}
        animate={{ width: `${Math.max(2, Math.min(100, progress))}%` }}
        transition={{ type: "spring", stiffness: 60, damping: 20 }}
        style={{ boxShadow: "0 0 12px rgba(255,181,71,.7)" }}
      />
    </div>
  );
}

function StageRail({ stage, progress, done }: { stage: string; progress: number; done: boolean }) {
  const idx = Math.max(0, STAGES.findIndex(([k]) => k === stage));
  return (
    <div className="no-scrollbar mt-8 overflow-x-auto">
      <div className="relative flex min-w-[880px] items-center justify-between px-1">
        <div className="absolute left-3 right-3 top-[11px] h-px bg-line" />
        <motion.div
          className="absolute left-3 top-[11px] h-px bg-amber"
          style={{ boxShadow: "0 0 10px rgba(255,181,71,.9)" }}
          animate={{ width: `calc(${(done ? 1 : idx / (STAGES.length - 1)) * 100}% - 24px)` }}
          transition={{ type: "spring", stiffness: 50, damping: 18 }}
        />
        {STAGES.map(([k, label], i) => {
          const state = done || i < idx ? "past" : i === idx ? "now" : "future";
          return (
            <div key={k} className="relative z-10 flex flex-col items-center gap-2">
              <motion.div
                animate={state === "now" ? { scale: [1, 1.25, 1] } : { scale: 1 }}
                transition={state === "now" ? { repeat: Infinity, duration: 1.6 } : {}}
                className={`grid h-[22px] w-[22px] place-items-center rounded-full border text-[9px] font-mono ${
                  state === "past" ? "border-amber bg-amber text-black" : state === "now" ? "border-amber bg-bg text-amber glow-amber" : "border-line bg-bg text-muted"
                }`}
              >
                {state === "past" ? "✓" : i + 1}
              </motion.div>
              <span className={`font-mono text-[10px] uppercase tracking-wider ${state === "future" ? "text-muted/60" : state === "now" ? "text-amber" : "text-ink"}`}>{label}</span>
            </div>
          );
        })}
      </div>
      <div className="mt-2 text-right font-mono text-[10px] text-muted">{progress}%</div>
    </div>
  );
}

function aspectClass(r?: string | null) {
  return r === "9:16" ? "aspect-[9/16] max-h-[78vh] mx-auto" : r === "1:1" ? "aspect-square max-h-[78vh] mx-auto" : "aspect-video";
}

function Screen({ project, view }: { project: Project | null; view: View }) {
  const [use4k, setUse4k] = useState(false);
  const [tab, setTab] = useState<string>("auto");
  const final = project?.status === "done" ? (use4k && project.video_4k_url ? project.video_4k_url : project.video_url) : null;
  const options: [string, string | null][] = [
    ["final", final],
    ...view.cuts.map((c) => [`cut ${c.round}`, c.url] as [string, string]),
    ["animatic", view.animatic],
  ];
  const available = options.filter(([, u]) => u);
  const chosen = tab === "auto" ? available[0] : available.find(([k]) => k === tab) || available[0];
  const src = chosen?.[1] || null;
  return (
    <div className="overflow-hidden rounded-2xl border border-line bg-black">
      <div className={`relative ${aspectClass(project?.aspect_ratio)} w-full overflow-hidden scanline`}>
        <AnimatePresence mode="wait">
          {src ? (
            <motion.video key={src} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} src={src} controls autoPlay muted={chosen?.[0] !== "final"} loop={chosen?.[0] !== "final"} playsInline className="absolute inset-0 h-full w-full bg-black object-contain" />
          ) : (
            <motion.div key="wait" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="absolute inset-0 aurora">
              <div className="absolute inset-0 grid place-items-center">
                <div className="text-center">
                  <div className="font-mono text-[11px] uppercase tracking-[0.3em] text-muted">{project?.stage || "standing by"}</div>
                  <div className="mt-3 font-display text-3xl sm:text-5xl">{project?.status === "queued" ? "Waiting for the director…" : "Rolling…"}</div>
                  <div className="mx-auto mt-5 h-1 w-48 overflow-hidden rounded bg-white/10">
                    <motion.div className="h-full bg-amber" animate={{ x: ["-100%", "200%"] }} transition={{ repeat: Infinity, duration: 1.4, ease: "easeInOut" }} style={{ width: "40%" }} />
                  </div>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
        <div className="pointer-events-none absolute left-3 top-3 rounded bg-black/60 px-2 py-0.5 font-mono text-[10px] text-ink">{chosen?.[0]?.toUpperCase() || "STANDBY"}</div>
      </div>
      <div className="flex flex-wrap items-center gap-2 border-t border-line p-3">
        {available.map(([k]) => (
          <button key={k} onClick={() => setTab(k)} className={`rounded-full border px-3 py-1 font-mono text-[11px] uppercase ${chosen?.[0] === k ? "border-amber text-amber" : "border-line text-muted hover:text-ink"}`}>
            {k}
          </button>
        ))}
        <div className="ml-auto flex items-center gap-2">
          {project?.video_4k_url && (
            <button onClick={() => setUse4k((v) => !v)} className={`rounded-full border px-3 py-1 font-mono text-[11px] ${use4k ? "border-cyan text-cyan" : "border-line text-muted"}`}>
              {use4k ? "4K" : "1080p"}
            </button>
          )}
          {project?.want_4k && !project?.video_4k_url && project?.status === "done" && <span className="font-mono text-[11px] text-muted">4K upscaling…</span>}
          {final && (
            <a href={final} download className="rounded-full bg-ink px-3 py-1 font-mono text-[11px] text-bg hover:bg-amber">
              Download
            </a>
          )}
        </div>
      </div>
    </div>
  );
}

function Media({ url, className }: { url?: string; className?: string }) {
  if (!url) return null;
  return isVideo(url) ? (
    <video src={url} autoPlay muted loop playsInline className={className} />
  ) : (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={url} alt="" className={className} />
  );
}

function Storyboard({ view }: { view: View }) {
  return (
    <section>
      <div className="mb-3 flex items-end justify-between">
        <h2 className="font-display text-3xl">Storyboard</h2>
        <span className="font-mono text-[11px] text-muted">{view.shots.length} shots</span>
      </div>
      {view.refs.length > 0 && (
        <div className="no-scrollbar mb-4 flex gap-3 overflow-x-auto">
          {view.refs.map((r, i) => (
            <motion.div key={r.name + i} initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} className="w-32 shrink-0">
              <div className="aspect-square overflow-hidden rounded-lg border border-cyan/40 bg-panel-2">
                <Media url={r.url} className="h-full w-full object-cover" />
              </div>
              <div className="mt-1 truncate font-mono text-[10px] text-cyan">ref · {r.name}</div>
            </motion.div>
          ))}
        </div>
      )}
      {view.shots.length === 0 ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {[0, 1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="aspect-video rounded-lg border border-line shimmer" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          <AnimatePresence>
            {view.shots.map((s, i) => {
              const yt = s.clip?.youtube_id ? ytThumb(str(s.clip.youtube_id)) : undefined;
              const media = s.shot || s.graphic || s.keyframe || yt;
              const kind = s.shot ? s.model || "generated" : s.graphic ? s.engine || "graphic" : s.clip ? "footage" : s.keyframe ? "keyframe" : s.plan?.kind || "planned";
              return (
                <motion.div key={s.id} layout initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: Math.min(i, 8) * 0.04 }} className="group overflow-hidden rounded-lg border border-line bg-panel">
                  <div className="relative aspect-video bg-panel-2">
                    {media ? <Media url={media} className="h-full w-full object-cover" /> : <div className="h-full w-full shimmer" />}
                    <div className="absolute left-1.5 top-1.5 rounded bg-black/70 px-1.5 py-0.5 font-mono text-[9px] text-amber">{s.id}</div>
                    <div className="absolute right-1.5 top-1.5 rounded bg-black/70 px-1.5 py-0.5 font-mono text-[9px] text-ink/80">{kind}</div>
                    {s.voice && <div className="absolute bottom-1.5 right-1.5 rounded bg-black/70 px-1.5 py-0.5 font-mono text-[9px] text-green">♪ vo</div>}
                  </div>
                  <div className="p-2">
                    <p className="line-clamp-2 text-[11px] text-ink/90">{s.plan?.narration || s.plan?.visual || str(s.clip?.title) || "…"}</p>
                    {s.plan?.direction && <p className="mt-1 line-clamp-1 font-mono text-[9px] italic text-muted">voice: {s.plan.direction}</p>}
                  </div>
                </motion.div>
              );
            })}
          </AnimatePresence>
        </div>
      )}
    </section>
  );
}

function FootageBin({ clips }: { clips: Record<string, unknown>[] }) {
  return (
    <section>
      <h2 className="mb-3 font-display text-3xl">Footage bin <span className="font-mono text-xs text-muted">Creative Commons</span></h2>
      <div className="no-scrollbar flex gap-3 overflow-x-auto pb-2">
        {clips.map((c, i) => (
          <a key={i} href={`https://www.youtube.com/watch?v=${str(c.youtube_id)}&t=${Math.floor(Number(c.start) || 0)}`} target="_blank" rel="noreferrer" className="w-56 shrink-0 overflow-hidden rounded-lg border border-line bg-panel transition hover:border-amber/50">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={str(c.thumb) || ytThumb(str(c.youtube_id))} alt="" className="aspect-video w-full object-cover" />
            <div className="p-2">
              <div className="line-clamp-1 text-xs">{str(c.title)}</div>
              <div className="mt-0.5 flex justify-between font-mono text-[9px] text-muted">
                <span className="truncate">{str(c.channel)}</span>
                {c.start != null && <span>{timecode(Number(c.start))}–{timecode(Number(c.end))}</span>}
              </div>
              <div className="mt-1 line-clamp-1 font-mono text-[9px] text-green">{str(c.license) || "CC BY"}</div>
            </div>
          </a>
        ))}
      </div>
    </section>
  );
}

function Typewriter({ text }: { text: string }) {
  const [n, setN] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setN((v) => (v >= text.length ? v : v + 2)), 18);
    return () => clearInterval(t);
  }, [text]);
  return (
    <span>
      {text.slice(0, n)}
      {n < text.length && <span className="ml-0.5 inline-block h-3 w-1.5 animate-pulse bg-amber align-middle" />}
    </span>
  );
}

const KIND_COLOR: Record<string, string> = {
  thought: "text-ink",
  tool: "text-cyan",
  stage: "text-amber",
  error: "text-rec",
  critique: "text-amber-2",
  done: "text-green",
};

function DirectorFeed({ events }: { events: Ev[] }) {
  const ref = useRef<HTMLDivElement>(null);
  const shown = events.slice(-80);
  const last = shown[shown.length - 1];
  useEffect(() => {
    ref.current?.scrollTo({ top: ref.current.scrollHeight, behavior: "smooth" });
  }, [shown.length]);
  return (
    <section className="overflow-hidden rounded-2xl border border-line bg-panel">
      <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
        <span className="font-mono text-[11px] uppercase tracking-widest text-muted">Director · Claude Code</span>
        <span className="font-mono text-[10px] text-muted">{events.length} events</span>
      </div>
      <div ref={ref} className="h-[420px] space-y-2 overflow-y-auto p-4 font-mono text-[12px] leading-relaxed">
        {shown.length === 0 && <div className="text-muted">Waiting for the first take…</div>}
        {shown.map((e) => (
          <motion.div key={e.id} initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }} className="flex gap-2">
            <span className="shrink-0 text-muted/60">{new Date(e.created_at).toLocaleTimeString([], { hour12: false })}</span>
            <span className={`shrink-0 uppercase ${KIND_COLOR[e.kind] || "text-muted"}`}>{e.kind.slice(0, 5).padEnd(5, " ")}</span>
            <span className={e.kind === "thought" ? "text-ink" : "text-ink/75"}>{e.id === last?.id && e.kind === "thought" ? <Typewriter text={e.message} /> : e.message}</span>
          </motion.div>
        ))}
      </div>
    </section>
  );
}

function CritiquePanel({ critiques }: { critiques: View["critiques"] }) {
  return (
    <section className="rounded-2xl border border-line bg-panel p-4">
      <h3 className="mb-3 font-mono text-[11px] uppercase tracking-widest text-muted">Critic · screenshots + transcript</h3>
      <div className="space-y-4">
        {critiques.map((c) => (
          <div key={c.round}>
            <div className="mb-1.5 flex items-center justify-between">
              <span className="font-display text-xl">Round {c.round}</span>
              <span className="font-mono text-[10px] text-muted">{c.issues.length} notes</span>
            </div>
            {c.contact_sheet_url && (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={c.contact_sheet_url} alt="contact sheet" className="mb-2 w-full rounded-lg border border-line" />
            )}
            <ul className="space-y-1">
              {c.issues.slice(0, 8).map((iss, i) => (
                <li key={i} className="flex gap-2 text-[12px] text-ink/85">
                  <span className="text-amber-2">›</span>
                  <span>{typeof iss === "string" ? iss : str((iss as Record<string, unknown>).note || (iss as Record<string, unknown>).issue || JSON.stringify(iss))}</span>
                </li>
              ))}
              {c.issues.length === 0 && <li className="text-[12px] text-green">{c.message || "Clean cut."}</li>}
            </ul>
          </div>
        ))}
      </div>
    </section>
  );
}

function AudioPanel({ view }: { view: View }) {
  if (!view.music && view.voices.length === 0 && !view.captions) return null;
  return (
    <section className="rounded-2xl border border-line bg-panel p-4">
      <h3 className="mb-3 font-mono text-[11px] uppercase tracking-widest text-muted">Sound</h3>
      {view.music && (
        <div className="mb-3">
          <div className="mb-1 text-xs text-ink/80">♫ {view.music.message}</div>
          <audio src={view.music.url} controls className="h-8 w-full" />
        </div>
      )}
      {view.voices.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {view.voices.map((v, i) => (
            <button key={i} onClick={() => new Audio(v.url).play()} className="rounded-full border border-green/40 px-2 py-0.5 font-mono text-[10px] text-green hover:bg-green/10">
              ▶ {v.shot_id || `vo${i + 1}`} {v.duration ? `${v.duration.toFixed(1)}s` : ""}
            </button>
          ))}
        </div>
      )}
      {view.captions && (
        <a href={view.captions} target="_blank" rel="noreferrer" className="mt-3 inline-block font-mono text-[11px] text-cyan underline">
          word-level captions ↗
        </a>
      )}
    </section>
  );
}

function CreditsPanel({ credits }: { credits: Project["credits"] | View["ledger"] }) {
  const list = (credits || []) as { kind?: string; title?: string; channel?: string; url?: string; license?: string }[];
  return (
    <section className="rounded-2xl border border-line bg-panel p-4">
      <h3 className="mb-3 font-mono text-[11px] uppercase tracking-widest text-muted">Credits · license ledger</h3>
      {list.length === 0 ? (
        <p className="text-[12px] text-muted">Every Creative Commons clip and track used lands here, with its license.</p>
      ) : (
        <ul className="space-y-2">
          {list.map((c, i) => (
            <li key={i} className="text-[12px]">
              <a href={c.url} target="_blank" rel="noreferrer" className="text-ink hover:text-amber">
                {c.title || c.url}
              </a>
              <div className="font-mono text-[10px] text-muted">
                {c.kind ? `${c.kind} · ` : ""}
                {c.channel} · <span className="text-green">{c.license}</span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
