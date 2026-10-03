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
      <div className="grid min-h-screen place-items-center px-4">
        <div className="text-center">
          <div className="display text-5xl">Reel not found</div>
          <p className="mt-3 text-graphite">This film doesn&apos;t exist, or it was never made public.</p>
          <Link href="/" className="mt-6 inline-block rounded-full bg-ink px-5 py-2.5 text-[15px] font-medium text-paper">
            Back to the studio
          </Link>
        </div>
      </div>
    );

  const p = project;
  const done = p?.status === "done";
  const failed = p?.status === "failed";
  const title = p?.title || p?.script?.title || p?.topic || "Untitled";

  return (
    <main className="relative min-h-screen pb-24">
      <header className="sticky top-0 z-40 border-b border-hairline/70 bg-paper/85 backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
          <Link href="/" className="flex items-center gap-2">
            <span className="grid h-6 w-6 place-items-center rounded-full border-[1.5px] border-ink">
              <span className={`h-2 w-2 rounded-full bg-rec ${done || failed ? "" : "rec-dot"}`} />
            </span>
            <span className="display text-[22px] tracking-[-0.04em]">Cutroom</span>
          </Link>
          <div className="flex items-center gap-3 text-[13px]">
            {!done && !failed && (
              <span className="flex items-center gap-1.5 rounded-full bg-rec/10 px-2.5 py-1 font-medium text-rec">
                <span className="h-1.5 w-1.5 rounded-full bg-rec rec-dot" /> Live
              </span>
            )}
            {done && <span className="rounded-full bg-trk-a/12 px-2.5 py-1 font-medium text-trk-a">Wrapped</span>}
            {failed && <span className="rounded-full bg-rec/10 px-2.5 py-1 font-medium text-rec">Failed</span>}
            <span className="hidden font-mono text-[12px] text-graphite sm:inline">{p ? `${p.aspect_ratio} · ${timecode(p.length_s || 0)}` : "…"}</span>
          </div>
        </div>
        <ProgressBar progress={p?.progress || 0} failed={failed} />
      </header>

      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <section className="pt-12">
          <div className="font-mono text-[12px] text-graphite">Production {id.slice(0, 8)}</div>
          <motion.h1 key={title} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="display mt-3 max-w-4xl text-4xl sm:text-6xl">
            {title}
          </motion.h1>
          {(p?.logline || p?.script?.logline) && <p className="accent mt-4 max-w-3xl text-xl text-graphite sm:text-2xl">{p?.logline || p?.script?.logline}</p>}
          {!p?.logline && !p?.script?.logline && p?.brief && <p className="accent mt-4 max-w-3xl text-xl text-graphite sm:text-2xl">“{p.brief}”</p>}
          {p?.style && <p className="mt-3 text-[13px] text-graphite">Style: {p.style}</p>}
        </section>

        <StageRail stage={p?.stage || "brief"} progress={p?.progress || 0} done={done} />

        {failed && p?.error && <div className="mt-6 rounded-2xl border border-rec/30 bg-rec/5 p-4 font-mono text-[13px] text-rec">{p.error}</div>}

        <div className="mt-8 grid gap-6 lg:grid-cols-[1fr_380px]">
          <div className="min-w-0 space-y-10">
            <Screen project={p} view={view} />
            <Storyboard view={view} />
            {view.clips.length > 0 && <FootageBin clips={view.clips} />}
          </div>
          <div className="min-w-0 space-y-5">
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
const panel = "card-shadow rounded-[20px] border border-hairline bg-card p-5";
const panelTitle = "mb-3 text-[13px] font-medium text-graphite";

function ProgressBar({ progress, failed }: { progress: number; failed: boolean }) {
  return (
    <div className="h-[2px] w-full bg-hairline">
      <motion.div
        className={`h-full ${failed ? "bg-rec" : "bg-ink"}`}
        animate={{ width: `${Math.max(2, Math.min(100, progress))}%` }}
        transition={{ type: "spring", stiffness: 60, damping: 20 }}
      />
    </div>
  );
}

function StageRail({ stage, progress, done }: { stage: string; progress: number; done: boolean }) {
  const idx = Math.max(0, STAGES.findIndex(([k]) => k === stage));
  return (
    <div className="mt-10">
      <div className="no-scrollbar overflow-x-auto">
        <div className="relative flex min-w-[880px] items-center justify-between px-1">
          <div className="absolute left-3 right-3 top-[11px] h-px bg-hairline" />
          <motion.div
            className="absolute left-3 top-[11px] h-px bg-ink"
            animate={{ width: `calc(${(done ? 1 : idx / (STAGES.length - 1)) * 100}% - 24px)` }}
            transition={{ type: "spring", stiffness: 50, damping: 18 }}
          />
          {STAGES.map(([k, label], i) => {
            const state = done || i < idx ? "past" : i === idx ? "now" : "future";
            return (
              <div key={k} className="relative z-10 flex flex-col items-center gap-2">
                <motion.div
                  animate={state === "now" ? { scale: [1, 1.18, 1] } : { scale: 1 }}
                  transition={state === "now" ? { repeat: Infinity, duration: 1.6 } : {}}
                  className={`grid h-[22px] w-[22px] place-items-center rounded-full border font-mono text-[9px] ${
                    state === "past" ? "border-ink bg-ink text-paper" : state === "now" ? "border-rec bg-card text-rec" : "border-hairline bg-paper text-graphite"
                  }`}
                >
                  {state === "past" ? "✓" : i + 1}
                </motion.div>
                <span className={`text-[11px] ${state === "future" ? "text-graphite/60" : state === "now" ? "font-medium text-rec" : "text-ink"}`}>{label}</span>
              </div>
            );
          })}
        </div>
      </div>
      <div className="mt-2 text-right font-mono text-[11px] text-graphite">{progress}%</div>
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
    <div className="window-shadow overflow-hidden rounded-[22px] border border-black/60 bg-screen text-screen-ink">
      <div className={`relative ${aspectClass(project?.aspect_ratio)} w-full overflow-hidden`}>
        <AnimatePresence mode="wait">
          {src ? (
            <motion.video key={src} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} src={src} controls autoPlay muted={chosen?.[0] !== "final"} loop={chosen?.[0] !== "final"} playsInline className="absolute inset-0 h-full w-full bg-black object-contain" />
          ) : (
            <motion.div key="wait" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="standby absolute inset-0">
              <div className="absolute inset-0 grid place-items-center px-6">
                <div className="text-center">
                  <div className="font-mono text-[11px] uppercase tracking-[0.2em] text-screen-muted">{project?.stage || "standing by"}</div>
                  <div className="accent mt-3 text-3xl sm:text-5xl">{project?.status === "queued" ? "Waiting for the director…" : "Rolling…"}</div>
                  <div className="mx-auto mt-6 h-[3px] w-48 overflow-hidden rounded-full bg-white/10">
                    <motion.div className="h-full rounded-full bg-screen-ink" animate={{ x: ["-100%", "250%"] }} transition={{ repeat: Infinity, duration: 1.4, ease: "easeInOut" }} style={{ width: "40%" }} />
                  </div>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
        <div className="pointer-events-none absolute left-3 top-3 flex items-center gap-1.5 rounded-full bg-black/60 px-2.5 py-1 font-mono text-[10px] text-white backdrop-blur">
          {!src && <span className="h-1.5 w-1.5 rounded-full bg-rec rec-dot" />}
          {chosen?.[0] ? chosen[0].replace(/^./, (c) => c.toUpperCase()) : "Standby"}
        </div>
      </div>
      {(available.length > 0 || project?.want_4k) && (
      <div className="flex flex-wrap items-center gap-1.5 border-t border-screen-line p-3">
        {available.map(([k]) => (
          <button key={k} onClick={() => setTab(k)} aria-pressed={chosen?.[0] === k} className={`rounded-full px-3 py-1 text-[12px] capitalize transition ${chosen?.[0] === k ? "bg-screen-ink text-screen" : "text-screen-muted hover:text-screen-ink"}`}>
            {k}
          </button>
        ))}
        <div className="ml-auto flex items-center gap-2">
          {project?.video_4k_url && (
            <button onClick={() => setUse4k((v) => !v)} className="rounded-full border border-screen-line px-3 py-1 font-mono text-[11px] text-screen-ink">
              {use4k ? "4K" : "1080p"}
            </button>
          )}
          {project?.want_4k && !project?.video_4k_url && project?.status === "done" && <span className="text-[12px] text-screen-muted">Upscaling to 4K…</span>}
          {final && (
            <a href={final} download className="rounded-full bg-screen-ink px-3.5 py-1 text-[12px] font-medium text-screen hover:bg-white">
              Download
            </a>
          )}
        </div>
      </div>
      )}
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

function SectionTitle({ title, meta }: { title: string; meta?: string }) {
  return (
    <div className="mb-4 flex items-end justify-between gap-4">
      <h2 className="display text-3xl">{title}</h2>
      {meta && <span className="font-mono text-[12px] text-graphite">{meta}</span>}
    </div>
  );
}

const KIND_TRACK: Record<string, string> = { generated: "bg-trk-v", footage: "bg-trk-v", keyframe: "bg-graphite", planned: "bg-hairline" };

function Storyboard({ view }: { view: View }) {
  return (
    <section>
      <SectionTitle title="Storyboard" meta={`${view.shots.length} shots`} />
      {view.refs.length > 0 && (
        <div className="no-scrollbar mb-5 flex gap-3 overflow-x-auto">
          {view.refs.map((r, i) => (
            <motion.div key={r.name + i} initial={{ opacity: 0, scale: 0.94 }} animate={{ opacity: 1, scale: 1 }} className="w-28 shrink-0">
              <div className="aspect-square overflow-hidden rounded-xl border border-hairline bg-paper-2">
                <Media url={r.url} className="h-full w-full object-cover" />
              </div>
              <div className="mt-1.5 truncate text-[12px] text-graphite">
                <span className="text-ink">Ref</span> · {r.name}
              </div>
            </motion.div>
          ))}
        </div>
      )}
      {view.shots.length === 0 ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {[0, 1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="aspect-video rounded-xl border border-hairline shimmer" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          <AnimatePresence>
            {view.shots.map((s, i) => {
              const yt = s.clip?.youtube_id ? ytThumb(str(s.clip.youtube_id)) : undefined;
              const media = s.shot || s.graphic || s.keyframe || yt;
              const kind = s.shot ? s.model || "generated" : s.graphic ? s.engine || "graphic" : s.clip ? "footage" : s.keyframe ? "keyframe" : s.plan?.kind || "planned";
              const bar = s.graphic ? "bg-trk-g" : KIND_TRACK[s.shot ? "generated" : s.clip ? "footage" : s.keyframe ? "keyframe" : "planned"];
              return (
                <motion.div key={s.id} layout initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: Math.min(i, 8) * 0.04 }} className="overflow-hidden rounded-xl border border-hairline bg-card">
                  <div className="relative aspect-video bg-screen">
                    {media ? <Media url={media} className="h-full w-full object-cover" /> : <div className="h-full w-full shimmer-dark" />}
                    <div className="absolute left-1.5 top-1.5 rounded-full bg-black/65 px-2 py-0.5 font-mono text-[9px] text-white">{s.id}</div>
                    <div className="absolute right-1.5 top-1.5 rounded-full bg-black/65 px-2 py-0.5 font-mono text-[9px] text-white/80">{kind}</div>
                    {s.voice && <div className="absolute bottom-1.5 right-1.5 rounded-full bg-trk-a px-2 py-0.5 font-mono text-[9px] text-white">VO</div>}
                  </div>
                  <div className={`h-[3px] ${bar}`} />
                  <div className="p-2.5">
                    <p className="line-clamp-2 text-[12px] leading-snug text-ink">{s.plan?.narration || s.plan?.visual || str(s.clip?.title) || "…"}</p>
                    {s.plan?.direction && <p className="accent mt-1 line-clamp-1 text-[12px] text-graphite">Voice: {s.plan.direction}</p>}
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
      <SectionTitle title="Footage bin" meta="Creative Commons" />
      <div className="no-scrollbar flex gap-3 overflow-x-auto pb-2">
        {clips.map((c, i) => (
          <a key={i} href={`https://www.youtube.com/watch?v=${str(c.youtube_id)}&t=${Math.floor(Number(c.start) || 0)}`} target="_blank" rel="noreferrer" className="w-56 shrink-0 overflow-hidden rounded-xl border border-hairline bg-card transition hover:border-ink/25">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={str(c.thumb) || ytThumb(str(c.youtube_id))} alt="" className="aspect-video w-full object-cover" />
            <div className="p-2.5">
              <div className="line-clamp-1 text-[13px]">{str(c.title)}</div>
              <div className="mt-0.5 flex justify-between gap-2 font-mono text-[10px] text-graphite">
                <span className="truncate">{str(c.channel)}</span>
                {c.start != null && (
                  <span className="shrink-0">
                    {timecode(Number(c.start))}–{timecode(Number(c.end))}
                  </span>
                )}
              </div>
              <div className="mt-1 line-clamp-1 font-mono text-[10px] text-trk-a">{str(c.license) || "CC BY"}</div>
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
      {n < text.length && <span className="ml-0.5 inline-block h-3 w-1.5 animate-pulse bg-screen-ink align-middle" />}
    </span>
  );
}

const KIND_COLOR: Record<string, string> = {
  thought: "text-screen-ink",
  tool: "text-[#8fa6ec]",
  stage: "text-[#e9b85c]",
  error: "text-[#ff7b75]",
  critique: "text-[#b597ee]",
  done: "text-[#6fd39e]",
};

function DirectorFeed({ events }: { events: Ev[] }) {
  const ref = useRef<HTMLDivElement>(null);
  const shown = events.slice(-80);
  const last = shown[shown.length - 1];
  useEffect(() => {
    ref.current?.scrollTo({ top: ref.current.scrollHeight, behavior: "smooth" });
  }, [shown.length]);
  return (
    <section className="window-shadow overflow-hidden rounded-[20px] border border-black/60 bg-screen text-screen-ink">
      <div className="flex items-center gap-3 border-b border-screen-line px-4 py-3">
        <div className="flex gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full bg-[#ff5f57]" />
          <span className="h-2.5 w-2.5 rounded-full bg-[#febc2e]" />
          <span className="h-2.5 w-2.5 rounded-full bg-[#28c840]" />
        </div>
        <span className="flex-1 truncate text-center font-mono text-[11px] text-screen-muted">Director · Claude Code</span>
        <span className="font-mono text-[10px] text-screen-muted">{events.length}</span>
      </div>
      <div ref={ref} className="h-[420px] space-y-2 overflow-y-auto p-4 font-mono text-[12px] leading-relaxed">
        {shown.length === 0 && <div className="text-screen-muted">Waiting for the first take…</div>}
        {shown.map((e) => (
          <motion.div key={e.id} initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }} className="flex gap-2">
            <span className="shrink-0 text-screen-muted/60">{new Date(e.created_at).toLocaleTimeString([], { hour12: false })}</span>
            <span className={`shrink-0 uppercase ${KIND_COLOR[e.kind] || "text-screen-muted"}`}>{e.kind.slice(0, 5).padEnd(5, " ")}</span>
            <span className={e.kind === "thought" ? "text-screen-ink" : "text-screen-ink/75"}>{e.id === last?.id && e.kind === "thought" ? <Typewriter text={e.message} /> : e.message}</span>
          </motion.div>
        ))}
      </div>
    </section>
  );
}

function CritiquePanel({ critiques }: { critiques: View["critiques"] }) {
  return (
    <section className={panel}>
      <h3 className={panelTitle}>Critic · screenshots and transcript</h3>
      <div className="space-y-5">
        {critiques.map((c) => (
          <div key={c.round}>
            <div className="mb-2 flex items-baseline justify-between">
              <span className="display text-xl">Round {c.round}</span>
              <span className="font-mono text-[11px] text-graphite">{c.issues.length} notes</span>
            </div>
            {c.contact_sheet_url && (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={c.contact_sheet_url} alt="Contact sheet" className="mb-2 w-full rounded-lg border border-hairline" />
            )}
            <ul className="space-y-1.5">
              {c.issues.slice(0, 8).map((iss, i) => (
                <li key={i} className="flex gap-2 text-[13px] leading-snug text-ink">
                  <span className="text-graphite">›</span>
                  <span>{typeof iss === "string" ? iss : str((iss as Record<string, unknown>).note || (iss as Record<string, unknown>).issue || JSON.stringify(iss))}</span>
                </li>
              ))}
              {c.issues.length === 0 && <li className="text-[13px] text-trk-a">{c.message || "Clean cut."}</li>}
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
    <section className={panel}>
      <h3 className={panelTitle}>Sound</h3>
      {view.music && (
        <div className="mb-3">
          <div className="mb-1.5 text-[13px] text-ink">♫ {view.music.message}</div>
          <audio src={view.music.url} controls className="h-8 w-full" />
        </div>
      )}
      {view.voices.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {view.voices.map((v, i) => (
            <button key={i} onClick={() => new Audio(v.url).play()} className="rounded-full border border-trk-a/40 px-2.5 py-0.5 font-mono text-[11px] text-trk-a transition hover:bg-trk-a/10">
              ▶ {v.shot_id || `vo${i + 1}`} {v.duration ? `${v.duration.toFixed(1)}s` : ""}
            </button>
          ))}
        </div>
      )}
      {view.captions && (
        <a href={view.captions} target="_blank" rel="noreferrer" className="mt-3 inline-block text-[13px] text-ink underline underline-offset-4">
          Word-level captions ↗
        </a>
      )}
    </section>
  );
}

function CreditsPanel({ credits }: { credits: Project["credits"] | View["ledger"] }) {
  const list = (credits || []) as { kind?: string; title?: string; channel?: string; url?: string; license?: string }[];
  return (
    <section className={panel}>
      <h3 className={panelTitle}>Credits · license ledger</h3>
      {list.length === 0 ? (
        <p className="text-[13px] leading-relaxed text-graphite">Every Creative Commons clip and track used lands here, with its license.</p>
      ) : (
        <ul className="divide-y divide-hairline">
          {list.map((c, i) => (
            <li key={i} className="py-2 text-[13px] first:pt-0 last:pb-0">
              <a href={c.url} target="_blank" rel="noreferrer" className="text-ink hover:underline">
                {c.title || c.url}
              </a>
              <div className="mt-0.5 font-mono text-[11px] text-graphite">
                {c.kind ? `${c.kind} · ` : ""}
                {c.channel} · <span className="text-trk-a">{c.license}</span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
