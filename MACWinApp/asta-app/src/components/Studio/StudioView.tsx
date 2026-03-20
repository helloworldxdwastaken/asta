import { useState, useEffect, useRef, useCallback } from "react";
import {
  listStudioChannels, createStudioChannel, deleteStudioChannel,
  listStudioAssets, uploadStudioAsset, deleteStudioAsset,
  listStudioRenders,
} from "../../lib/api";

// ── Types ──────────────────────────────────────────────────────────────────

type View = "create" | "channels" | "editor" | "schedule";
type SettingsTab = "video" | "assets" | "renders";
type MsgRole = "user" | "assistant" | "progress" | "error";

interface ChatMsg { id: string; role: MsgRole; content: string; progress?: number; step?: string; }
interface Channel { id: string; channel_name: string; channel_youtube_id?: string; default_voice?: string; enabled?: number; }
interface Asset { id: string; name: string; asset_type: string; file_path?: string; duration_seconds?: number; }
interface Render { id: string; status: string; step?: string; progress?: number; error?: string; }
interface TimelineClip { id: number; type: string; label: string; left: number; width: number; }

// ── Scoped CSS (timeline only — Tailwind can't do % positioning) ───────────

const SCOPED = `
.st-lane{position:relative;min-width:600px}
.st-clip{position:absolute;top:3px;bottom:3px;border-radius:5px;display:flex;align-items:center;padding:0 6px;font-size:9px;font-family:'JetBrains Mono',monospace;cursor:grab;white-space:nowrap;overflow:hidden;font-weight:700;letter-spacing:.3px}
.st-clip-intro{background:rgba(255,45,45,.25);border:1px solid rgba(255,45,45,.45);color:#ff2d2d}
.st-clip-img{background:rgba(124,58,237,.18);border:1px solid rgba(124,58,237,.35);color:#8B5CF6}
.st-clip-voice{background:rgba(34,197,94,.12);border:1px solid rgba(34,197,94,.3);color:#22C55E}
.st-clip-sub{background:rgba(234,179,8,.12);border:1px solid rgba(234,179,8,.25);color:#EAB308}
.st-clip-outro{background:rgba(124,58,237,.18);border:1px solid rgba(124,58,237,.35);color:#8B5CF6}
.st-clip-music{background:rgba(167,139,250,.12);border:1px solid rgba(167,139,250,.25);color:#A78BFA}
.st-drop{border-color:rgba(124,58,237,.5)!important;background:rgba(124,58,237,.04)!important}
`;

// ── Icons (inline SVG) ─────────────────────────────────────────────────────

const Ico = {
  create:   <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8"><path d="M12 3c0 0-7 3-7 9s7 9 7 9 7-3 7-9-7-9-7-9z"/><circle cx="12" cy="12" r="3"/></svg>,
  channels: <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8"><rect x="3" y="6" width="18" height="13" rx="2"/><path d="M10 9l5 3-5 3V9z"/></svg>,
  editor:   <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8"><rect x="2" y="14" width="20" height="6" rx="1.5"/><rect x="2" y="9" width="20" height="4" rx="1"/><rect x="2" y="4" width="20" height="4" rx="1"/></svg>,
  schedule: <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M3 9h18M8 2v4M16 2v4M7 13h3v3H7z"/></svg>,
  settings: <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 01-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/></svg>,
  play:     <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5l13 7-13 7V5z"/></svg>,
  plus:     <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5"><path d="M12 5v14M5 12h14"/></svg>,
  spark:    <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>,
  upload:   <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>,
  grip:     <svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor" opacity="0.35"><circle cx="8" cy="6" r="1.5"/><circle cx="16" cy="6" r="1.5"/><circle cx="8" cy="12" r="1.5"/><circle cx="16" cy="12" r="1.5"/><circle cx="8" cy="18" r="1.5"/><circle cx="16" cy="18" r="1.5"/></svg>,
  send:     <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><path d="M22 2L11 13"/><path d="M22 2l-7 20-4-9-9-4 20-7z"/></svg>,
  stop:     <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>,
  yt:       <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M23 7s-.3-2-1.2-2.8c-1.1-1.2-2.4-1.2-3-1.3C16.2 2.7 12 2.7 12 2.7s-4.2 0-6.8.2c-.6.1-1.9.1-3 1.3C1.3 5 1 7 1 7S.7 9.3.7 11.5v2c0 2.2.3 4.5.3 4.5s.3 2 1.2 2.8c1.1 1.2 2.6 1.1 3.3 1.2C7.5 22 12 22 12 22s4.2 0 6.8-.2c.6-.1 1.9-.1 3-1.3.9-.8 1.2-2.8 1.2-2.8s.3-2.2.3-4.5v-2C23.3 9.3 23 7 23 7zM9.7 15.5V8.4l8.1 3.6-8.1 3.5z"/></svg>,
  error:    <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M15 9l-6 6M9 9l6 6"/></svg>,
  trash:    <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8"><path d="M3 6h18M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6"/></svg>,
};

// ── Shared class helpers ───────────────────────────────────────────────────

const card     = "bg-white/[.03] border border-separator rounded-xl transition-all";
const btnP     = "px-3.5 py-1.5 text-12 font-medium bg-studio text-white rounded-mac hover:bg-studio-hover transition-colors inline-flex items-center gap-1.5";
const btnS     = "px-3.5 py-1.5 text-12 font-medium bg-white/[.06] text-label-secondary border border-separator rounded-mac hover:bg-white/[.10] hover:text-label transition-colors inline-flex items-center gap-1.5";
const btnG     = "px-2.5 py-1.5 text-12 text-label-tertiary hover:text-label-secondary hover:bg-white/[.04] rounded-md transition-colors inline-flex items-center gap-1.5";
const inp      = "w-full bg-white/[.05] border border-separator rounded-lg px-3 py-2 text-13 text-label outline-none focus:border-studio/50 focus:bg-white/[.07] transition-colors";
const lbl      = "text-10 text-label-tertiary font-mono uppercase tracking-wider block mb-1";
const section  = "font-display font-bold text-13 text-label-secondary uppercase tracking-wider";

const badgeCls = (c: "studio" | "green" | "blue" | "red") => {
  const m: Record<string, string> = {
    studio: "bg-studio/15 text-studio border-studio/30",
    green:  "bg-success/10 text-success border-success/25",
    blue:   "bg-thinking/10 text-thinking border-thinking/25",
    red:    "bg-danger/15 text-danger border-danger/30",
  };
  return `px-2 py-0.5 rounded-full text-10 font-mono font-bold tracking-wide border ${m[c]}`;
};

const ASSET_COLORS: Record<string, string> = {
  intro: "bg-danger/20 text-danger", outro: "bg-studio/20 text-studio",
  subscribe: "bg-success/20 text-success", overlay: "bg-warning/20 text-warning",
  music: "bg-thinking/20 text-thinking", watermark: "bg-white/10 text-label-secondary",
};

// ── Demo timeline clips ────────────────────────────────────────────────────

const DEMO_TIMELINE: Record<string, TimelineClip[]> = {
  video:     [{ id: 1, type: "intro", label: "Intro", left: 0, width: 8 }, { id: 2, type: "img", label: "AI Tools Scene", left: 9, width: 15 }, { id: 3, type: "img", label: "B-Roll", left: 25, width: 20 }, { id: 4, type: "outro", label: "Outro", left: 88, width: 12 }],
  voice:     [{ id: 5, type: "voice", label: "Narration", left: 8, width: 80 }],
  subtitles: [{ id: 6, type: "sub", label: "Auto Subtitles", left: 8, width: 80 }],
  overlay:   [{ id: 7, type: "sub", label: "Subscribe CTA", left: 45, width: 8 }],
};

const DEMO_POSTS = [
  { day: 3, time: "10:00", title: "10 AI Tools Changing the World", channel: "TechVault", status: "scheduled" as const },
  { day: 7, time: "14:00", title: "Finance Tips Nobody Tells You", channel: "FinanceFlow", status: "scheduled" as const },
  { day: 12, time: "09:30", title: "Mind Reading Tech Explained", channel: "MindExpand", status: "scheduled" as const },
  { day: 20, time: "11:00", title: "Quantum Computing Basics", channel: "MindExpand", status: "today" as const },
  { day: 22, time: "15:30", title: "Crypto Market Analysis", channel: "FinanceFlow", status: "draft" as const },
];

const RULERS = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60];

// ═══════════════════════════════════════════════════════════════════════════
// Component
// ═══════════════════════════════════════════════════════════════════════════

export default function StudioView() {
  const [view, setView] = useState<View>("create");

  // ── API data ─────────────────────────────────────────────────────────────
  const [channels, setChannels] = useState<Channel[]>([]);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [renders, setRenders] = useState<Render[]>([]);

  const reload = useCallback(async () => {
    try { const r = await listStudioChannels(); setChannels(r.channels ?? []); } catch {}
    try { const r = await listStudioAssets(); setAssets(r.assets ?? []); } catch {}
    try { const r = await listStudioRenders(); setRenders(r.renders ?? []); } catch {}
  }, []);

  useEffect(() => { reload(); }, [reload]);

  // ── Local UI state ───────────────────────────────────────────────────────
  const [selChannel, setSelChannel] = useState("");
  const [assetTab, setAssetTab] = useState("all");
  const [dropTrack, setDropTrack] = useState<string | null>(null);
  const [dragAsset, setDragAsset] = useState<Asset | null>(null);
  const [timelineClips, setTimelineClips] = useState(DEMO_TIMELINE);
  const [showAddCh, setShowAddCh] = useState(false);
  const [newChName, setNewChName] = useState("");
  const [newChYtId, setNewChYtId] = useState("");
  const [videoFormat, setVideoFormat] = useState("landscape");
  const [showSettings, setShowSettings] = useState(false);
  const [settingsTab, setSettingsTab] = useState<SettingsTab>("video");

  // ── Chat state ───────────────────────────────────────────────────────────
  const [msgs, setMsgs] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs]);

  const send = () => {
    const text = input.trim();
    if (!text || streaming) return;
    setMsgs(p => [...p, { id: Date.now().toString(), role: "user", content: text }]);
    setInput("");
    setStreaming(true);

    // Simulated pipeline progress (Phase 2: replace with real stream)
    const steps = ["Analyzing topic...", "Writing script...", "Sourcing footage...", "Generating voiceover...", "Rendering video..."];
    let idx = 0;
    const pid = (Date.now() + 1).toString();
    setMsgs(p => [...p, { id: pid, role: "progress", content: steps[0], progress: 0, step: steps[0] }]);

    const iv = setInterval(() => {
      idx++;
      if (idx < steps.length) {
        const pct = Math.round((idx / steps.length) * 100);
        setMsgs(p => p.map(m => m.id === pid ? { ...m, content: steps[idx], progress: pct, step: steps[idx] } : m));
      } else {
        clearInterval(iv);
        setMsgs(p => [
          ...p.filter(m => m.id !== pid),
          { id: (Date.now() + 2).toString(), role: "assistant", content: `Your video about "${text}" is ready.\n\nI wrote a script, sourced **12 clips** from Pexels, generated narration, and added subtitles.\n\nThe result is **3:24** in **16:9** format.` },
        ]);
        setStreaming(false);
      }
    }, 1200);
  };

  const onKey = (e: React.KeyboardEvent) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } };

  // ── Channel CRUD ─────────────────────────────────────────────────────────
  const addChannel = async () => {
    if (!newChName.trim()) return;
    try {
      await createStudioChannel({ channel_name: newChName.trim(), channel_youtube_id: newChYtId.trim() || undefined });
      await reload();
    } catch {}
    setNewChName(""); setNewChYtId(""); setShowAddCh(false);
  };

  const rmChannel = async (id: string) => {
    try { await deleteStudioChannel(id); await reload(); } catch {}
  };

  // ── Asset upload + delete ────────────────────────────────────────────────
  const handleUpload = async (file: File, type: string) => {
    try {
      await uploadStudioAsset(file, file.name.replace(/\.[^.]+$/, ""), type, selChannel);
      await reload();
    } catch {}
  };

  const rmAsset = async (id: string) => {
    try { await deleteStudioAsset(id); await reload(); } catch {}
  };

  // ── Asset drag into timeline ─────────────────────────────────────────────
  const handleDrop = (track: string) => {
    if (!dragAsset) { setDropTrack(null); return; }
    const clips = timelineClips[track] ?? [];
    const maxRight = clips.reduce((m, c) => Math.max(m, c.left + c.width), 0);
    const newClip: TimelineClip = {
      id: Date.now(), type: dragAsset.asset_type === "voice" ? "voice" : dragAsset.asset_type,
      label: dragAsset.name, left: Math.min(maxRight + 1, 90), width: 10,
    };
    setTimelineClips(prev => ({ ...prev, [track]: [...(prev[track] ?? []), newClip] }));
    setDragAsset(null); setDropTrack(null);
  };

  // ── Filtered assets ──────────────────────────────────────────────────────
  const filteredAssets = assetTab === "all" ? assets : assets.filter(a => a.asset_type === assetTab);

  // ── Nav item class ───────────────────────────────────────────────────────
  const nav = (id: View) =>
    `w-full flex items-center gap-2.5 px-3 py-2 rounded-mac text-13 font-medium transition-all cursor-pointer ${
      view === id ? "bg-studio/15 text-studio" : "text-label-secondary hover:bg-white/[.04] hover:text-label"
    }`;

  // ── Inline helpers ───────────────────────────────────────────────────────
  const studioAvatar = (ch: Channel) => {
    const initials = ch.channel_name.slice(0, 2).toUpperCase();
    return <div className="w-10 h-10 rounded-full bg-studio/15 flex items-center justify-center font-display font-extrabold text-14 text-studio shrink-0">{initials}</div>;
  };

  const fmtDur = (s?: number) => s ? `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}` : "—";

  // ═════════════════════════════════════════════════════════════════════════
  return (
    <>
      <style>{SCOPED}</style>
      <div className="flex flex-1 overflow-hidden">

        {/* ─── Sidebar (w-60, glass-subtle — matches Asta) ─── */}
        <div className="w-60 shrink-0 border-r border-separator glass-subtle flex flex-col"
             style={{ WebkitAppRegion: "drag" } as React.CSSProperties}>
          <div className="flex-1 px-3 pt-4 pb-2 space-y-0.5" style={{ WebkitAppRegion: "no-drag" } as React.CSSProperties}>
            <button className={nav("create")}   onClick={() => setView("create")}>{Ico.create} Create</button>
            <button className={nav("channels")}  onClick={() => setView("channels")}>{Ico.channels} Channels</button>
            <button className={nav("editor")}    onClick={() => setView("editor")}>{Ico.editor} Video Editor</button>
            <button className={nav("schedule")}  onClick={() => setView("schedule")}>{Ico.schedule} Scheduler</button>
          </div>

          {/* Render queue in sidebar */}
          {renders.length > 0 && (
            <div className="px-3 pb-2 space-y-1" style={{ WebkitAppRegion: "no-drag" } as React.CSSProperties}>
              <div className="text-9 text-label-tertiary font-mono uppercase tracking-wider px-1">Queue</div>
              {renders.slice(0, 3).map(r => (
                <div key={r.id} className={`rounded-lg px-2.5 py-1.5 text-10 ${r.status === "error" ? "bg-danger/10 text-danger" : "bg-white/[.03] text-label-secondary"}`}>
                  <div className="truncate font-medium">{r.step || "Render"}</div>
                  {r.status === "error" ? (
                    <div className="text-9 mt-0.5 opacity-80 truncate">{r.error}</div>
                  ) : (
                    <div className="h-1 bg-separator rounded-full mt-1 overflow-hidden">
                      <div className="h-full rounded-full bg-studio transition-all" style={{ width: `${r.progress ?? 0}%` }} />
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          <div className="px-3 pb-4 border-t border-separator pt-2" style={{ WebkitAppRegion: "no-drag" } as React.CSSProperties}>
            <button className="w-full flex items-center gap-2.5 px-3 py-2 rounded-mac text-13 font-medium transition-all cursor-pointer text-label-secondary hover:bg-white/[.04] hover:text-label"
              onClick={() => setShowSettings(true)}>{Ico.settings} Settings</button>
          </div>
        </div>

        {/* ─── Main area ─── */}
        <div className="flex-1 flex flex-col overflow-hidden min-w-0">

          {/* Header (draggable) */}
          <div className="h-[52px] shrink-0 border-b border-separator flex items-center px-5"
               style={{ WebkitAppRegion: "drag" } as React.CSSProperties}>
            <div className="flex items-center gap-4 flex-1" style={{ WebkitAppRegion: "no-drag" } as React.CSSProperties}>
              {view === "create" && <>
                <span className="font-display font-bold text-14 text-label">Create</span>
                <span className="text-12 text-label-tertiary">— describe your video</span>
                <div className="flex-1" />
                {streaming && <span className={`${badgeCls("studio")} animate-pulse`}>Working...</span>}
                {channels.length > 0 && (
                  <select className="bg-white/[.06] border border-separator rounded-lg px-2.5 py-1 text-11 text-label-secondary outline-none"
                    value={selChannel} onChange={e => setSelChannel(e.target.value)}>
                    <option value="">All channels</option>
                    {channels.map(ch => <option key={ch.id} value={ch.id}>{ch.channel_name}</option>)}
                  </select>
                )}
              </>}
              {view === "channels" && <>
                <span className="font-display font-bold text-14 text-label">Channels</span>
                <span className="text-12 text-label-tertiary">— {channels.length} channel{channels.length !== 1 ? "s" : ""}</span>
                <div className="flex-1" />
                <button className={btnP} onClick={() => setShowAddCh(true)}>{Ico.plus} Add Channel</button>
              </>}
              {view === "editor" && <>
                <span className="font-display font-bold text-14 text-label">Video Editor</span>
                <span className="text-12 text-label-tertiary">— drag assets to timeline</span>
                <div className="flex-1" />
                <span className={badgeCls("blue")}>{Object.keys(timelineClips).length} Tracks</span>
                <button className={btnP}>{Ico.play} Export</button>
              </>}
              {view === "schedule" && <>
                <span className="font-display font-bold text-14 text-label">Scheduler</span>
                <div className="flex-1" />
                <span className={badgeCls("blue")}>{DEMO_POSTS.length} Scheduled</span>
              </>}
            </div>
          </div>

          {/* ─── Content ─── */}
          <div className="flex-1 overflow-hidden flex">

            {/* ══════════ CREATE ══════════ */}
            {view === "create" && (
              <div className="flex-1 flex flex-col overflow-hidden">
                <div className="flex-1 overflow-y-auto px-5 py-5 space-y-5 scrollbar-thin">
                  {/* Empty hero — matches ChatView style */}
                  {msgs.length === 0 && (
                    <div className="flex flex-col items-center justify-center h-full gap-4 relative overflow-hidden pt-8">
                      {/* Floating pixel sprites (video-themed colors) */}
                      <div className="absolute inset-0 pointer-events-none transition-opacity duration-500" style={{ opacity: input.trim() ? 0 : 1 }} aria-hidden>
                        <div className="pixel-block absolute left-[6%] top-[12%]" style={{ animationDelay: "0s", animationDuration: "7s" }}>
                          <svg width="20" height="20" viewBox="0 0 5 5" style={{ imageRendering: "pixelated" }}>
                            <rect x="2" y="0" width="1" height="1" fill="#7C3AED" /><rect x="0" y="2" width="1" height="1" fill="#7C3AED" />
                            <rect x="1" y="1" width="1" height="1" fill="#7C3AED" /><rect x="2" y="2" width="1" height="1" fill="#7C3AED" />
                            <rect x="3" y="1" width="1" height="1" fill="#7C3AED" /><rect x="4" y="2" width="1" height="1" fill="#7C3AED" />
                            <rect x="2" y="4" width="1" height="1" fill="#7C3AED" /><rect x="1" y="3" width="1" height="1" fill="#7C3AED" />
                            <rect x="3" y="3" width="1" height="1" fill="#7C3AED" />
                          </svg>
                        </div>
                        <div className="pixel-block absolute left-[14%] top-[38%]" style={{ animationDelay: "1.2s", animationDuration: "8s" }}>
                          <svg width="15" height="15" viewBox="0 0 5 5" style={{ imageRendering: "pixelated" }}>
                            <rect x="2" y="0" width="1" height="1" fill="#a78bfa" /><rect x="1" y="1" width="1" height="1" fill="#a78bfa" />
                            <rect x="3" y="1" width="1" height="1" fill="#a78bfa" /><rect x="0" y="2" width="1" height="1" fill="#a78bfa" />
                            <rect x="4" y="2" width="1" height="1" fill="#a78bfa" /><rect x="1" y="3" width="1" height="1" fill="#a78bfa" />
                            <rect x="3" y="3" width="1" height="1" fill="#a78bfa" /><rect x="2" y="4" width="1" height="1" fill="#a78bfa" />
                          </svg>
                        </div>
                        <div className="pixel-block absolute left-[4%] top-[60%]" style={{ animationDelay: "2.4s", animationDuration: "9s" }}>
                          <svg width="18" height="15" viewBox="0 0 6 5" style={{ imageRendering: "pixelated" }}>
                            <rect x="0" y="1" width="6" height="3" fill="#8B5CF6" />
                            <rect x="2" y="2" width="2" height="1" fill="white" opacity="0.4" />
                          </svg>
                        </div>
                        <div className="pixel-block absolute left-[10%] top-[78%]" style={{ animationDelay: "0.8s", animationDuration: "6.5s" }}>
                          <svg width="20" height="20" viewBox="0 0 5 5" style={{ imageRendering: "pixelated" }}>
                            <rect x="2" y="0" width="1" height="1" fill="#C084FC" /><rect x="0" y="2" width="5" height="1" fill="#C084FC" />
                            <rect x="2" y="1" width="1" height="1" fill="#C084FC" /><rect x="1" y="1" width="1" height="1" fill="#C084FC" opacity="0.5" />
                            <rect x="3" y="1" width="1" height="1" fill="#C084FC" opacity="0.5" /><rect x="2" y="3" width="1" height="1" fill="#C084FC" />
                            <rect x="1" y="4" width="1" height="1" fill="#C084FC" /><rect x="3" y="4" width="1" height="1" fill="#C084FC" />
                          </svg>
                        </div>
                        <div className="pixel-block absolute right-[8%] top-[15%]" style={{ animationDelay: "0.5s", animationDuration: "7.5s" }}>
                          <svg width="18" height="15" viewBox="0 0 6 5" style={{ imageRendering: "pixelated" }}>
                            <rect x="0" y="0" width="6" height="5" fill="#7C3AED" opacity="0.6" />
                            <rect x="2" y="1" width="1" height="1" fill="white" opacity="0.5" />
                            <rect x="2" y="3" width="2" height="1" fill="white" opacity="0.3" />
                          </svg>
                        </div>
                        <div className="pixel-block absolute right-[5%] top-[35%]" style={{ animationDelay: "1.8s", animationDuration: "6s" }}>
                          <svg width="15" height="15" viewBox="0 0 5 5" style={{ imageRendering: "pixelated" }}>
                            <rect x="2" y="0" width="1" height="1" fill="#A855F7" />
                            <rect x="1" y="1" width="3" height="1" fill="#A855F7" />
                            <rect x="0" y="2" width="5" height="1" fill="#A855F7" />
                            <rect x="2" y="3" width="1" height="1" fill="#A855F7" />
                            <rect x="2" y="4" width="1" height="1" fill="#A855F7" />
                          </svg>
                        </div>
                        <div className="pixel-block absolute right-[12%] top-[55%]" style={{ animationDelay: "3s", animationDuration: "7.2s" }}>
                          <svg width="16" height="16" viewBox="0 0 5 5" style={{ imageRendering: "pixelated" }}>
                            <rect x="2" y="0" width="1" height="1" fill="#C084FC" /><rect x="0" y="2" width="5" height="1" fill="#C084FC" />
                            <rect x="2" y="1" width="1" height="1" fill="#C084FC" /><rect x="1" y="1" width="1" height="1" fill="#C084FC" opacity="0.5" />
                            <rect x="3" y="1" width="1" height="1" fill="#C084FC" opacity="0.5" /><rect x="2" y="3" width="1" height="1" fill="#C084FC" />
                            <rect x="1" y="4" width="1" height="1" fill="#C084FC" /><rect x="3" y="4" width="1" height="1" fill="#C084FC" />
                          </svg>
                        </div>
                        <div className="pixel-block absolute right-[3%] top-[72%]" style={{ animationDelay: "2s", animationDuration: "8.2s" }}>
                          <svg width="12" height="12" viewBox="0 0 3 3" style={{ imageRendering: "pixelated" }}>
                            <rect width="3" height="3" fill="#7C3AED" /><rect x="0" y="0" width="1" height="1" fill="white" opacity="0.3" />
                          </svg>
                        </div>
                        {/* Ambient glow orbs */}
                        <div className="absolute w-48 h-48 rounded-full opacity-[0.03] pointer-events-none"
                          style={{ background: "radial-gradient(circle, #7C3AED, transparent 70%)", top: "8%", left: "-3%", animation: "orb-float 12s ease-in-out infinite" }} />
                        <div className="absolute w-36 h-36 rounded-full opacity-[0.025] pointer-events-none"
                          style={{ background: "radial-gradient(circle, #A855F7, transparent 70%)", bottom: "5%", right: "-2%", animation: "orb-float 15s ease-in-out infinite reverse" }} />
                      </div>

                      <div className="relative w-20 h-20 z-10 hero-enter" style={{ animationDelay: "0s" }}>
                        <div className="absolute inset-0 rounded-full bg-studio/20 blur-xl animate-[orb-float_8s_ease-in-out_infinite]" />
                        <img src="/appicon-512.png" alt="Asta" className="relative w-20 h-20 rounded-2xl"
                          style={{ boxShadow: "0 8px 32px rgba(124,58,237,0.15), 0 0 0 1px rgba(255,255,255,0.06)" }} />
                      </div>
                      <div className="text-center z-10 hero-enter" style={{ animationDelay: "0.12s" }}>
                        <p className="text-label text-[28px] font-bold tracking-tight leading-tight">What video should I make?</p>
                        <p className="text-label-tertiary text-13 mt-2 font-medium">Describe the topic — I'll handle script, footage, voice, and editing</p>
                      </div>
                      <div className="grid grid-cols-2 gap-2.5 max-w-sm w-full mt-2 z-10 hero-enter" style={{ animationDelay: "0.24s" }}>
                        {["Top 10 AI tools in 2026", "Bitcoin explained in 60 seconds", "5 morning habits of CEOs", "The future of remote work"].map(s => (
                          <button key={s} onClick={() => { setInput(s); inputRef.current?.focus(); }}
                            className="flex items-center gap-2.5 bg-white/[.04] hover:bg-white/[.08] border border-separator hover:border-separator-bold rounded-xl px-3.5 py-3 transition-all duration-200 active:scale-[0.97] text-left">
                            <span className="text-13 text-label-secondary font-medium truncate">{s}</span>
                          </button>
                        ))}
                      </div>
                      <p className="text-label-tertiary text-11 tracking-wide mt-4 opacity-40 z-10 hero-enter text-center" style={{ animationDelay: "0.36s" }}>
                        Enter to send · Shift+Enter for new line
                      </p>
                    </div>
                  )}

                  {/* Messages */}
                  {msgs.map(m => {
                    if (m.role === "user") return (
                      <div key={m.id} className="flex justify-end">
                        <div className="max-w-[75%] bubble-gradient rounded-bubble px-4 py-2.5 text-14" style={{ color: "var(--user-bubble-text)" }}>
                          <div className="whitespace-pre-wrap">{m.content}</div>
                        </div>
                      </div>
                    );
                    if (m.role === "progress") return (
                      <div key={m.id} className="flex gap-2.5">
                        <div className="w-7 h-7 rounded-lg bg-studio/20 flex items-center justify-center shrink-0 mt-0.5 text-studio">{Ico.spark}</div>
                        <div className={`${card} p-4 flex-1 max-w-[75%] border-studio/20`}>
                          <div className="flex items-center gap-2 mb-2">
                            <span className="w-2 h-2 rounded-full bg-studio animate-pulse" />
                            <span className="text-13 font-medium">{m.step}</span>
                          </div>
                          <div className="h-1.5 bg-separator rounded-full overflow-hidden">
                            <div className="h-full rounded-full bg-gradient-to-r from-studio to-accent transition-all duration-500" style={{ width: `${m.progress ?? 0}%` }} />
                          </div>
                          <div className="text-10 text-label-tertiary font-mono mt-1.5">{m.progress}%</div>
                        </div>
                      </div>
                    );
                    if (m.role === "error") return (
                      <div key={m.id} className="flex gap-2.5">
                        <div className="w-7 h-7 rounded-lg bg-danger/20 flex items-center justify-center shrink-0 mt-0.5 text-danger">{Ico.error}</div>
                        <div className={`${card} p-4 flex-1 max-w-[75%] border-danger/30`}>
                          <div className="flex items-center gap-2 mb-1.5">
                            <span className="w-2 h-2 rounded-full bg-danger" />
                            <span className="text-13 font-medium text-danger">Render Failed</span>
                          </div>
                          <p className="text-12 text-label-secondary">{m.content}</p>
                          <button className={btnP + " mt-3 !bg-danger hover:!bg-red-500"} onClick={() => { setInput("retry"); }}>Retry</button>
                        </div>
                      </div>
                    );
                    // assistant
                    return (
                      <div key={m.id} className="flex gap-2.5">
                        <div className="w-7 h-7 rounded-lg bg-studio/20 flex items-center justify-center shrink-0 mt-0.5 text-studio">{Ico.spark}</div>
                        <div className="flex-1 min-w-0 max-w-[75%]">
                          <div className="text-14 text-label leading-relaxed whitespace-pre-wrap">
                            {m.content.split(/(\*\*.*?\*\*)/).map((p, i) =>
                              p.startsWith("**") && p.endsWith("**")
                                ? <strong key={i} className="font-semibold">{p.slice(2, -2)}</strong>
                                : <span key={i}>{p}</span>
                            )}
                          </div>
                          {!streaming && m === msgs[msgs.length - 1] && (
                            <div className="flex gap-2 mt-3">
                              <button className={btnP} onClick={() => setView("editor")}>{Ico.play} Preview & Edit</button>
                              <button className={btnS} onClick={() => setView("schedule")}>{Ico.schedule} Schedule</button>
                              <button className={btnG}>Regenerate</button>
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })}

                  {streaming && msgs[msgs.length - 1]?.role !== "progress" && (
                    <div className="flex gap-2.5">
                      <div className="w-7 h-7 rounded-lg bg-studio/20 flex items-center justify-center shrink-0 mt-0.5 text-studio">{Ico.spark}</div>
                      <div className="px-2 py-3 flex gap-1.5">
                        {[0, 1, 2].map(i => <div key={i} className="w-1.5 h-1.5 rounded-full bg-studio animate-bounce" style={{ animationDelay: `${i * .15}s` }} />)}
                      </div>
                    </div>
                  )}
                  <div ref={endRef} />
                </div>

                {/* Input bar */}
                <div className="px-4 py-3">
                  <div className="bg-white/[.04] border border-separator hover:border-separator-bold focus-within:border-accent/30 rounded-2xl transition-all duration-200">
                    <textarea ref={inputRef} rows={1} value={input} onChange={e => setInput(e.target.value)} onKeyDown={onKey}
                      placeholder="Describe the video you want to create..."
                      className="w-full bg-transparent px-4 pt-3 pb-2 text-14 text-label placeholder-label-tertiary outline-none resize-none"
                      style={{ minHeight: 40, maxHeight: 200, lineHeight: "20px" }}
                      onInput={e => { const el = e.currentTarget; el.style.height = "auto"; el.style.height = Math.min(el.scrollHeight, 200) + "px"; }} />
                    <div className="flex items-center justify-between px-2 pb-2">
                      <select value={videoFormat} onChange={e => setVideoFormat(e.target.value)}
                        className="bg-transparent text-11 text-label-tertiary hover:text-label-secondary outline-none cursor-pointer px-2 py-1 rounded-lg hover:bg-white/[.04]">
                        <option value="landscape">16:9</option><option value="shorts">9:16 Short</option><option value="square">1:1</option>
                      </select>
                      <button onClick={streaming ? undefined : send} disabled={streaming || !input.trim()}
                        className={`w-8 h-8 flex items-center justify-center rounded-[10px] shrink-0 transition-all active:scale-[0.93] ${
                          input.trim() && !streaming ? "bg-studio text-white shadow-[0_0_10px_rgba(124,58,237,.25)]" : "bg-white/[.06] text-label-tertiary"}`}>
                        {streaming ? Ico.stop : Ico.send}
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* ══════════ CHANNELS ══════════ */}
            {view === "channels" && (
              <div className="flex-1 overflow-y-auto p-5">
                {channels.length === 0 ? (
                  <div className="flex flex-col items-center justify-center h-full gap-3 text-label-tertiary">
                    <div className="text-[40px] opacity-20">{Ico.channels}</div>
                    <p className="text-14">No channels yet</p>
                    <button className={btnP} onClick={() => setShowAddCh(true)}>{Ico.plus} Add your first channel</button>
                  </div>
                ) : (
                  <div className="grid grid-cols-[repeat(auto-fill,minmax(300px,1fr))] gap-3">
                    {channels.map(ch => (
                      <div key={ch.id} onClick={() => setSelChannel(ch.id)}
                        className={`${card} p-4 cursor-pointer hover:border-studio/30 hover:-translate-y-px hover:shadow-card relative overflow-hidden ${selChannel === ch.id ? "border-studio/50" : ""}`}>
                        {selChannel === ch.id && <div className="absolute top-0 left-0 right-0 h-0.5 bg-gradient-to-r from-studio to-accent" />}
                        <div className="flex items-center gap-3 mb-3">
                          {studioAvatar(ch)}
                          <div className="flex-1 min-w-0">
                            <div className="font-display font-bold text-14 truncate">{ch.channel_name}</div>
                            {ch.channel_youtube_id && <div className="text-11 text-label-tertiary font-mono mt-0.5">@{ch.channel_youtube_id}</div>}
                          </div>
                          <div className={`w-2 h-2 rounded-full shrink-0 ${ch.channel_youtube_id ? "bg-success shadow-[0_0_6px_theme(colors.success)]" : "bg-label-tertiary"}`} />
                        </div>
                        <div className="flex gap-1.5">
                          {ch.channel_youtube_id
                            ? <span className={badgeCls("green")}>Connected</span>
                            : <button className={btnP + " text-10 !px-2.5 !py-1"}>{Ico.yt} Connect</button>
                          }
                          <button className={btnS + " text-10 !px-2.5 !py-1"} onClick={e => { e.stopPropagation(); setShowSettings(true); }}>Settings</button>
                          <button className={btnG + " text-10 !px-2 !py-1 ml-auto text-danger hover:text-danger hover:bg-danger/10"} onClick={e => { e.stopPropagation(); rmChannel(ch.id); }}>{Ico.trash}</button>
                        </div>
                      </div>
                    ))}
                    <div onClick={() => setShowAddCh(true)} className={`${card} p-4 cursor-pointer border-dashed hover:border-studio/30 flex flex-col items-center justify-center gap-2 min-h-[140px] text-label-tertiary hover:text-studio`}>
                      <span className="text-22">+</span>
                      <span className="text-12">Add channel</span>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* ══════════ EDITOR ══════════ */}
            {view === "editor" && (
              <div className="flex-1 flex overflow-hidden">
                {/* Asset panel */}
                <div className="w-[220px] shrink-0 border-r border-separator flex flex-col overflow-hidden">
                  <div className="p-3.5 pb-2.5 border-b border-separator">
                    <div className={section + " text-11"}>Assets</div>
                    <div className="flex gap-1 mt-2 flex-wrap">
                      {["all", "intro", "outro", "subscribe", "music"].map(t => (
                        <button key={t} onClick={() => setAssetTab(t)}
                          className={`px-2 py-1 rounded text-10 font-mono tracking-wide transition-all ${assetTab === t ? "bg-studio text-white" : "bg-white/[.06] text-label-tertiary hover:text-label-secondary"}`}>{t}</button>
                      ))}
                    </div>
                  </div>
                  <div className="flex-1 overflow-y-auto p-2.5 space-y-1.5">
                    {filteredAssets.length === 0 && (
                      <p className="text-11 text-label-tertiary text-center py-4">No {assetTab === "all" ? "" : assetTab + " "}assets yet.<br />Upload below.</p>
                    )}
                    {filteredAssets.map(a => (
                      <div key={a.id} draggable
                        onDragStart={() => setDragAsset(a)}
                        onDragEnd={() => setDragAsset(null)}
                        className={`${card} p-2 px-2.5 cursor-grab flex items-center gap-2 hover:border-studio/30 active:cursor-grabbing active:opacity-70`}>
                        <div className={`w-8 h-5 rounded flex items-center justify-center text-10 ${ASSET_COLORS[a.asset_type] ?? "bg-white/10 text-label-secondary"}`}>{Ico.play}</div>
                        <div className="flex-1 min-w-0">
                          <div className="text-11 font-medium truncate">{a.name}</div>
                          <div className="text-9 text-label-tertiary font-mono">{fmtDur(a.duration_seconds)}</div>
                        </div>
                        <button className="opacity-0 group-hover:opacity-100 text-label-tertiary hover:text-danger transition-all p-0.5" onClick={() => rmAsset(a.id)}>{Ico.trash}</button>
                        {Ico.grip}
                      </div>
                    ))}
                  </div>
                  <label className="m-2.5 border border-dashed border-separator rounded-lg py-3 text-center cursor-pointer hover:border-studio/30 hover:bg-studio/[.04] transition-colors block">
                    {Ico.upload}
                    <p className="text-10 text-label-tertiary mt-1">Upload asset</p>
                    <input type="file" accept="video/*,audio/*,image/*" className="hidden" onChange={e => {
                      const f = e.target.files?.[0]; if (f) handleUpload(f, assetTab === "all" ? "intro" : assetTab);
                      e.target.value = "";
                    }} />
                  </label>
                </div>

                {/* Canvas + Timeline */}
                <div className="flex-1 flex flex-col overflow-hidden">
                  {/* Preview */}
                  <div className="h-[260px] shrink-0 bg-black relative flex items-center justify-center border-b border-separator">
                    <div className="w-[440px] h-[248px] bg-gradient-to-br from-[#0a0f1e] via-[#1a0a2e] to-[#0a1a1e] rounded relative overflow-hidden flex items-center justify-center">
                      <div className="text-center"><div className="text-[32px] opacity-20">&#9654;</div><p className="text-12 text-label-tertiary mt-1">Preview</p></div>
                      <div className="absolute top-2 right-2"><span className={badgeCls("studio")}>00:00 / 01:12</span></div>
                    </div>
                    <div className="absolute bottom-3 left-1/2 -translate-x-1/2 flex gap-2">
                      <button className={btnS + " !px-2 !py-1"}>&#9198;</button>
                      <button className={btnP + " !px-2 !py-1"}>{Ico.play}</button>
                      <button className={btnS + " !px-2 !py-1"}>&#9197;</button>
                    </div>
                  </div>

                  {/* Timeline */}
                  <div className="flex-1 overflow-auto p-3 space-y-1.5">
                    <div className="flex items-center gap-2 mb-1">
                      <div className="w-[70px]" />
                      <div className="st-lane h-5 flex items-end relative">
                        {RULERS.map(s => (
                          <div key={s} className="absolute bottom-0 flex flex-col items-center gap-px" style={{ left: `${(s / 60) * 100}%` }}>
                            <div className="w-px" style={{ height: s % 10 === 0 ? 8 : 4, background: "var(--separator-bold)" }} />
                            {s % 10 === 0 && <span className="text-[8px] text-label-tertiary font-mono">{s}s</span>}
                          </div>
                        ))}
                      </div>
                    </div>
                    {Object.entries(timelineClips).map(([track, clips]) => (
                      <div key={track} className="flex items-center gap-2">
                        <div className="w-[70px] text-right text-9 text-label-tertiary uppercase tracking-wide font-mono shrink-0">{track}</div>
                        <div className={`st-lane h-8 bg-white/[.03] rounded-md border border-separator ${dropTrack === track ? "st-drop" : ""}`}
                          onDragOver={e => { e.preventDefault(); setDropTrack(track); }}
                          onDragLeave={() => setDropTrack(null)}
                          onDrop={e => { e.preventDefault(); handleDrop(track); }}>
                          {clips.map(c => (
                            <div key={c.id} className={`st-clip st-clip-${c.type}`} style={{ left: `${c.left}%`, width: `${c.width}%` }}>{c.label}</div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* ══════════ SCHEDULE ══════════ */}
            {view === "schedule" && (
              <div className="flex-1 overflow-y-auto p-5">
                <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-6">
                  {/* Calendar */}
                  <div>
                    <div className="grid grid-cols-7 gap-1">
                      {["SUN","MON","TUE","WED","THU","FRI","SAT"].map(d => (
                        <div key={d} className="text-9 text-label-tertiary text-center py-1 font-mono uppercase">{d}</div>
                      ))}
                      {Array.from({ length: 31 }, (_, i) => {
                        const day = i + 1;
                        const dp = DEMO_POSTS.filter(post => post.day === day);
                        const today = day === 20;
                        return (
                          <div key={day} className={`aspect-square rounded-md bg-white/[.03] border border-separator flex flex-col items-center p-1 cursor-pointer hover:border-studio/30 min-h-[48px] ${dp.length ? "border-studio/40" : ""} ${today ? "bg-studio/[.06] border-studio/50" : ""}`}>
                            <span className="text-11 font-mono text-label-secondary">{day}</span>
                            {dp.map((_, j) => <div key={j} className="w-1.5 h-1.5 rounded-full mt-0.5 bg-studio" />)}
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  {/* Upcoming sidebar */}
                  <div>
                    <span className={section}>Upcoming</span>
                    <div className="space-y-1.5 mt-3">
                      {[...DEMO_POSTS].sort((a, b) => a.day - b.day).map((p, i) => (
                        <div key={i} className={`${card} p-2.5 px-3 flex gap-2.5 items-center cursor-pointer hover:border-studio/30`}>
                          <div className="font-mono text-10 text-label-tertiary shrink-0">Mar {String(p.day).padStart(2, "0")}<br/>{p.time}</div>
                          <div className="flex-1 min-w-0">
                            <div className="text-12 font-medium truncate">{p.title}</div>
                            <div className="text-10 text-label-tertiary">{p.channel}</div>
                          </div>
                          <span className={badgeCls(p.status === "today" ? "studio" : p.status === "draft" ? "blue" : "green") + " text-9"}>
                            {p.status === "today" ? "TODAY" : p.status === "draft" ? "DRAFT" : "SCHED"}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            )}

          </div>
        </div>

        {/* ─── Add Channel Modal ─── */}
        {showAddCh && (
          <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 backdrop-blur-sm" onClick={() => setShowAddCh(false)}>
            <div className="bg-surface-raised border border-separator rounded-2xl p-6 w-[420px] space-y-4 shadow-modal" onClick={e => e.stopPropagation()}>
              <h2 className="font-display font-extrabold text-18">Add Channel</h2>
              <p className="text-12 text-label-tertiary leading-relaxed">Connect a YouTube channel. OAuth coming soon — for now, enter the channel name.</p>
              <div><label className={lbl}>Channel Name</label><input className={inp} placeholder="My Channel" value={newChName} onChange={e => setNewChName(e.target.value)} /></div>
              <div><label className={lbl}>YouTube Channel ID (optional)</label><input className={inp} placeholder="UC..." value={newChYtId} onChange={e => setNewChYtId(e.target.value)} /></div>
              <div className="flex gap-2 justify-end pt-1">
                <button className={btnS} onClick={() => setShowAddCh(false)}>Cancel</button>
                <button className={btnP} onClick={addChannel}>Add Channel</button>
              </div>
            </div>
          </div>
        )}

        {/* ─── Studio Settings Sheet ─── */}
        {showSettings && (
          <div className="absolute inset-0 bg-black/60 flex items-center justify-center z-40 animate-fade-in" onClick={() => setShowSettings(false)}>
            <div className="bg-surface-raised rounded-mac shadow-modal flex overflow-hidden animate-scale-in border border-separator" style={{ width: 780, height: 580 }} onClick={e => e.stopPropagation()}>
              {/* Tab sidebar */}
              <div className="w-44 bg-surface border-r border-separator flex flex-col py-3">
                <div className="flex items-center justify-between px-4 mb-3">
                  <span className="text-14 font-semibold text-label">Studio Settings</span>
                  <button onClick={() => setShowSettings(false)} className="text-label-tertiary hover:text-label-secondary p-1 rounded-mac hover:bg-white/[.06] transition-colors">
                    <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
                  </button>
                </div>
                <div className="flex-1 overflow-y-auto space-y-0.5 px-2 scrollbar-thin">
                  {([
                    { id: "video" as const, label: "Video Defaults", icon: Ico.create },
                    { id: "assets" as const, label: "Default Assets", icon: Ico.upload },
                    { id: "renders" as const, label: "Render Queue", icon: Ico.spark },
                  ]).map(t => (
                    <button key={t.id} onClick={() => setSettingsTab(t.id)}
                      className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-mac text-left text-13 transition-all duration-150 ${
                        settingsTab === t.id ? "bg-studio/[.12] text-studio font-medium" : "text-label-secondary hover:bg-white/[.04]"
                      }`}>
                      <span className="shrink-0">{t.icon}</span>
                      <span className="truncate">{t.label}</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Content */}
              <div className="flex-1 overflow-y-auto p-6 scrollbar-thin">
                {settingsTab === "video" && (
                  <div className="space-y-5">
                    <div>
                      <h3 className="text-16 font-bold text-label mb-1">Video Defaults</h3>
                      <p className="text-12 text-label-tertiary mb-5">Configure defaults for new video projects</p>
                    </div>
                    {[
                      { l: "Default Voice", desc: "Narrator style for generated voiceover", opts: ["Deep Narrator","Friendly Host","News Anchor","Energetic"] },
                      { l: "Image Style", desc: "Visual tone for sourced footage", opts: ["Cinematic / Dark","Clean Minimal","Vibrant Colors","Photorealistic"] },
                      { l: "Caption Style", desc: "How subtitles appear on screen", opts: ["Bold Centered","Lower Third","Karaoke Pop","Minimal Bottom"] },
                      { l: "Footage Source", desc: "Where to pull stock clips and images", opts: ["Pexels + Pixabay","Pexels Only","AI Generated","All Free Sources"] },
                      { l: "Output Quality", desc: "Resolution of the final render", opts: ["1080p (recommended)","720p (fast)","4K (slow)"] },
                      { l: "After Render", desc: "What happens when the video is done", opts: ["Save as draft","Post immediately","Best time (AI pick)"] },
                    ].map(c => (
                      <div key={c.l} className="flex items-start justify-between gap-6 py-3 border-b border-separator last:border-0">
                        <div className="min-w-0">
                          <div className="text-13 font-medium text-label">{c.l}</div>
                          <div className="text-11 text-label-tertiary mt-0.5">{c.desc}</div>
                        </div>
                        <select className="shrink-0 bg-white/[.05] border border-separator rounded-lg px-3 py-1.5 text-13 text-label outline-none focus:border-studio/50 transition-colors w-[200px]">
                          {c.opts.map(o => <option key={o}>{o}</option>)}
                        </select>
                      </div>
                    ))}
                  </div>
                )}

                {settingsTab === "assets" && (
                  <div className="space-y-5">
                    <div>
                      <h3 className="text-16 font-bold text-label mb-1">Default Assets</h3>
                      <p className="text-12 text-label-tertiary mb-5">Auto-attach these clips to every new video</p>
                    </div>
                    {["intro", "outro", "subscribe", "watermark", "music"].map(type => {
                      const ta = assets.filter(a => a.asset_type === type);
                      return (
                        <div key={type} className="flex items-start justify-between gap-6 py-3 border-b border-separator last:border-0">
                          <div className="min-w-0">
                            <div className="text-13 font-medium text-label capitalize">{type}</div>
                            <div className="text-11 text-label-tertiary mt-0.5">
                              {ta.length === 0 ? `No ${type} assets uploaded yet` : `${ta.length} available`}
                            </div>
                          </div>
                          <select className="shrink-0 bg-white/[.05] border border-separator rounded-lg px-3 py-1.5 text-13 text-label outline-none focus:border-studio/50 transition-colors w-[200px]"
                            disabled={ta.length === 0}>
                            <option value="">None</option>
                            {ta.map(a => <option key={a.id} value={a.id}>{a.name} ({fmtDur(a.duration_seconds)})</option>)}
                          </select>
                        </div>
                      );
                    })}
                    <div className="pt-2">
                      <p className="text-11 text-label-tertiary">Upload assets in the <button className="text-studio hover:underline" onClick={() => { setShowSettings(false); setView("editor"); }}>Video Editor</button> panel</p>
                    </div>
                  </div>
                )}

                {settingsTab === "renders" && (
                  <div className="space-y-5">
                    <div>
                      <h3 className="text-16 font-bold text-label mb-1">Render Queue</h3>
                      <p className="text-12 text-label-tertiary mb-5">Active and recent render jobs</p>
                    </div>
                    {renders.length === 0 ? (
                      <div className="flex flex-col items-center justify-center py-16 text-label-tertiary">
                        <span className="text-studio opacity-30 mb-3">{Ico.spark}</span>
                        <p className="text-13">No renders yet</p>
                        <p className="text-11 mt-1">Create a video to start rendering</p>
                      </div>
                    ) : (
                      <div className="space-y-2">
                        {renders.map(r => (
                          <div key={r.id} className={`bg-white/[.03] border rounded-xl p-4 space-y-2 ${r.status === "error" ? "border-danger/30" : "border-separator"}`}>
                            <div className="flex items-center justify-between">
                              <span className="text-13 font-medium truncate max-w-[320px]">{r.step || "Render"}</span>
                              <span className={badgeCls(r.status === "done" ? "green" : r.status === "error" ? "red" : "studio")}>
                                {r.status === "done" ? "Done" : r.status === "error" ? "Error" : "Rendering"}
                              </span>
                            </div>
                            {r.status === "error" && r.error && (
                              <div className="text-12 text-danger/80 bg-danger/5 rounded-lg px-3 py-2">{r.error}</div>
                            )}
                            {r.status !== "error" && r.status !== "done" && (
                              <div className="h-1.5 bg-separator rounded-full overflow-hidden">
                                <div className="h-full rounded-full bg-gradient-to-r from-studio to-accent transition-all" style={{ width: `${r.progress ?? 0}%` }} />
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </>
  );
}
