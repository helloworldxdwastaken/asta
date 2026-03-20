import { useState, useEffect, useCallback, useRef } from "react";
import { cronDashboard, cronJobRuns, updateCron, createCron, deleteCron, runCronNow, listAgents } from "../../lib/api";
import { IconClock, IconCheck, IconWarning, IconPlus, IconTrash, IconEdit, IconClose } from "../../lib/icons";

// ── Types ────────────────────────────────────────────────────────────────────

interface CronRun {
  id: number; status: string; output?: string; error?: string; created_at: string;
}

interface CronJob {
  id: string; name: string; cron_expr: string; message?: string;
  enabled?: boolean; tz?: string; next_run?: string;
  last_run?: CronRun | null; agent_id?: string | null;
  channel?: string; payload_kind?: string; tlg_call?: boolean;
}

interface Agent {
  id: string; name: string; description?: string; icon?: string;
  enabled: boolean; model_override?: string; category?: string;
}

interface Props { onClose: () => void; }

type ViewMode = "list" | "calendar" | "pipeline";
type ScheduleType = "youtube" | "custom";
type VideoFormat = "short" | "standard" | "long";

// ── Constants ────────────────────────────────────────────────────────────────

const DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const DAY_CRON   = [1,     2,     3,     4,     5,     6,     0];

const COMMON_TZ = [
  "", "America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles",
  "Europe/London", "Europe/Paris", "Europe/Lisbon", "Europe/Berlin",
  "Asia/Tokyo", "Asia/Jerusalem", "Asia/Shanghai", "Australia/Sydney",
];

const inputCls = "w-full bg-white/[.06] border border-separator rounded-lg px-3 py-2 text-13 text-label outline-none focus:border-accent/50";
const labelCls = "text-11 text-label-tertiary block mb-1";

// ── Helpers ──────────────────────────────────────────────────────────────────

interface YouTubeScheduleEntry {
  day: number; dayLabel: string; hour: number; minute: number;
  format: VideoFormat; prompt: string;
}

function buildYouTubePreset(niche: string): YouTubeScheduleEntry[] {
  const topic = niche.trim() || "general";
  return [
    { day: 1, dayLabel: "Mon", hour: 10, minute: 0, format: "short", prompt: `Create a YouTube Short about ${topic}. Make it punchy, under 60 seconds, with a strong hook in the first 3 seconds.` },
    { day: 2, dayLabel: "Tue", hour: 10, minute: 0, format: "standard", prompt: `Create a standard YouTube video (8-12 min) about ${topic}. Include a compelling intro, well-structured sections, and a clear call-to-action.` },
    { day: 3, dayLabel: "Wed", hour: 10, minute: 0, format: "short", prompt: `Create a YouTube Short about ${topic}. Focus on a surprising fact or hot take. Keep it under 60 seconds.` },
    { day: 4, dayLabel: "Thu", hour: 10, minute: 0, format: "standard", prompt: `Create a standard YouTube video (8-12 min) about ${topic}. Deep-dive into a specific subtopic with research and examples.` },
    { day: 5, dayLabel: "Fri", hour: 10, minute: 0, format: "short", prompt: `Create a YouTube Short about ${topic}. Use a listicle or "did you know" format. Maximum engagement, under 60 seconds.` },
    { day: 6, dayLabel: "Sat", hour: 10, minute: 0, format: "short", prompt: `Create a YouTube Short about ${topic}. Weekend content — lighter tone, entertaining angle. Under 60 seconds.` },
  ];
}

function describeCron(expr: string): string {
  const parts = expr.trim().split(/\s+/);
  if (parts.length !== 5) return expr;
  const [min, hour, , , dow] = parts;
  const h = parseInt(hour, 10);
  const m = parseInt(min, 10);
  if (isNaN(h) || isNaN(m)) return expr;
  const time = `${h % 12 || 12}:${m.toString().padStart(2, "0")} ${h >= 12 ? "PM" : "AM"}`;
  if (dow === "*") return `Daily at ${time}`;
  const dayMap: Record<string, string> = { "0": "Sun", "1": "Mon", "2": "Tue", "3": "Wed", "4": "Thu", "5": "Fri", "6": "Sat" };
  const days = dow.split(",").map(d => dayMap[d] || d).join(", ");
  return `${days} at ${time}`;
}

function timeAgo(ts?: string): string {
  if (!ts) return "never";
  const d = new Date(ts);
  if (isNaN(d.getTime())) return "?";
  const sec = (Date.now() - d.getTime()) / 1000;
  if (sec < 60) return "just now";
  if (sec < 3600) return `${Math.round(sec / 60)}m ago`;
  if (sec < 86400) return `${Math.round(sec / 3600)}h ago`;
  return `${Math.round(sec / 86400)}d ago`;
}

function timeUntil(ts?: string): string {
  if (!ts) return "—";
  const d = new Date(ts);
  if (isNaN(d.getTime())) return "—";
  const sec = (d.getTime() - Date.now()) / 1000;
  if (sec <= 0) return "now";
  if (sec < 60) return `in ${Math.round(sec)}s`;
  if (sec < 3600) return `in ${Math.round(sec / 60)}m`;
  if (sec < 86400) return `in ${Math.round(sec / 3600)}h`;
  return `in ${Math.round(sec / 86400)}d`;
}

/** Parse a single cron field into a set of matching values within [min, max]. */
function parseCronField(field: string, min: number, max: number): number[] {
  const result = new Set<number>();
  for (const part of field.split(",")) {
    const trimmed = part.trim();
    // */N or N
    if (trimmed.includes("/")) {
      const [range, stepStr] = trimmed.split("/");
      const step = parseInt(stepStr, 10);
      if (isNaN(step) || step <= 0) continue;
      let start = min;
      if (range !== "*") {
        const s = parseInt(range, 10);
        if (!isNaN(s)) start = s;
      }
      for (let i = start; i <= max; i += step) result.add(i);
    } else if (trimmed.includes("-")) {
      const [a, b] = trimmed.split("-").map(Number);
      if (!isNaN(a) && !isNaN(b)) {
        for (let i = a; i <= b; i++) result.add(i);
      }
    } else if (trimmed === "*") {
      for (let i = min; i <= max; i++) result.add(i);
    } else {
      const v = parseInt(trimmed, 10);
      if (!isNaN(v)) result.add(v);
    }
  }
  return Array.from(result).sort((a, b) => a - b);
}

/** Get days-of-month in a given month/year that a cron expression fires on. */
function cronExprToDaysOfMonth(expr: string, year: number, month: number): number[] {
  const parts = expr.trim().split(/\s+/);
  if (parts.length !== 5) return [];
  const [, , domField, monField, dowField] = parts;

  // Check if this month matches
  const months = parseCronField(monField, 1, 12);
  if (monField !== "*" && !months.includes(month + 1)) return [];

  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const domAll = domField === "*";
  const dowAll = dowField === "*";

  if (domAll && dowAll) {
    // Every day
    return Array.from({ length: daysInMonth }, (_, i) => i + 1);
  }

  const result = new Set<number>();

  if (!domAll) {
    const doms = parseCronField(domField, 1, 31);
    for (const d of doms) {
      if (d <= daysInMonth) result.add(d);
    }
  }

  if (!dowAll) {
    const dows = parseCronField(dowField, 0, 7).map(d => d % 7); // normalize 7→0
    for (let d = 1; d <= daysInMonth; d++) {
      const dayOfWeek = new Date(year, month, d).getDay();
      if (dows.includes(dayOfWeek)) result.add(d);
    }
  }

  // Standard cron: if both dom and dow are restricted, union them
  return Array.from(result).sort((a, b) => a - b);
}

// ── Pipeline step types ──────────────────────────────────────────────────────

interface PipelineStep {
  id: string;
  label: string;
  status: "idle" | "running" | "done" | "error";
  detail?: string;
  startedAt?: string;
  finishedAt?: string;
}

function buildPipelineSteps(job: CronJob, lastRun?: CronRun | null): PipelineStep[] {
  const hasAgent = !!job.agent_id;
  const steps: PipelineStep[] = [
    { id: "trigger", label: "Trigger", status: "idle", detail: describeCron(job.cron_expr) },
    { id: "prepare", label: "Prepare", status: "idle", detail: hasAgent ? `Agent: ${job.agent_id}` : "Direct message" },
    { id: "execute", label: "Execute", status: "idle", detail: job.message?.slice(0, 60) || "—" },
    { id: "complete", label: "Complete", status: "idle" },
  ];

  if (!lastRun) return steps;

  const s = lastRun.status;
  if (s === "running") {
    steps[0].status = "done";
    steps[1].status = "done";
    steps[2].status = "running";
    steps[2].detail = "Running now...";
  } else if (s === "ok" || s === "success") {
    steps.forEach(st => st.status = "done");
    steps[3].detail = lastRun.output?.slice(0, 80) || "Completed";
  } else {
    steps[0].status = "done";
    steps[1].status = "done";
    steps[2].status = "error";
    steps[2].detail = lastRun.error?.slice(0, 80) || "Failed";
    steps[3].status = "idle";
  }

  return steps;
}

// ═════════════════════════════════════════════════════════════════════════════
// MAIN COMPONENT
// ═════════════════════════════════════════════════════════════════════════════

export default function AutomationDashboard(_props: Props) {
  const [jobs, setJobs] = useState<CronJob[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [viewMode, setViewMode] = useState<ViewMode>("list");
  const [expandedJob, setExpandedJob] = useState<string | null>(null);
  const [runs, setRuns] = useState<Record<string, CronRun[]>>({});
  const [togglingId, setTogglingId] = useState<string | null>(null);
  const [runningId, setRunningId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [savingEdit, setSavingEdit] = useState(false);

  // Creation form state
  const [showForm, setShowForm] = useState(false);
  const [scheduleType, setScheduleType] = useState<ScheduleType>("youtube");
  const [formName, setFormName] = useState("");
  const [formNiche, setFormNiche] = useState("");
  const [formTz, setFormTz] = useState("");
  const [formEnabled, setFormEnabled] = useState(true);
  const [creating, setCreating] = useState(false);

  // Custom schedule fields
  const [customDays, setCustomDays] = useState<number[]>([1, 2, 3, 4, 5]);
  const [customHour, setCustomHour] = useState(10);
  const [customMinute, setCustomMinute] = useState(0);
  const [customFormat, setCustomFormat] = useState<VideoFormat>("standard");
  const [customPrompt, setCustomPrompt] = useState("");

  // YouTube preset entries
  const [ytEntries, setYtEntries] = useState<YouTubeScheduleEntry[]>(() => buildYouTubePreset(""));

  // Calendar state
  const [calMonth, setCalMonth] = useState(() => new Date().getMonth());
  const [calYear, setCalYear] = useState(() => new Date().getFullYear());

  function resetForm() {
    setFormName(""); setFormNiche(""); setFormTz(""); setFormEnabled(true);
    setScheduleType("youtube"); setCreating(false);
    setCustomDays([1, 2, 3, 4, 5]); setCustomHour(10); setCustomMinute(0);
    setCustomFormat("standard"); setCustomPrompt("");
    setYtEntries(buildYouTubePreset(""));
  }

  function handleNicheChange(niche: string) {
    setFormNiche(niche);
    setYtEntries(buildYouTubePreset(niche));
  }

  function toggleCustomDay(d: number) {
    setCustomDays(prev => prev.includes(d) ? prev.filter(x => x !== d) : [...prev, d]);
  }

  async function handleCreate() {
    if (!formName.trim()) return;
    setCreating(true);
    try {
      if (scheduleType === "youtube") {
        const baseName = formName.trim();
        for (const entry of ytEntries) {
          const cronExpr = `${entry.minute} ${entry.hour} * * ${entry.day}`;
          const formatLabel = entry.format === "short" ? "Short" : entry.format === "long" ? "Long" : "Standard";
          await createCron({
            name: `${baseName} — ${entry.dayLabel} ${formatLabel}`,
            cron_expr: cronExpr, message: entry.prompt,
            tz: formTz || undefined, enabled: formEnabled,
            channel: "web", payload_kind: "agentturn", tlg_call: false,
          });
        }
      } else {
        if (!customPrompt.trim() || customDays.length === 0) return;
        const sorted = [...customDays].sort((a, b) => a - b);
        const dowPart = sorted.length === 7 ? "*" : sorted.join(",");
        const cronExpr = `${customMinute} ${customHour} * * ${dowPart}`;
        await createCron({
          name: formName.trim(), cron_expr: cronExpr, message: customPrompt,
          tz: formTz || undefined, enabled: formEnabled,
          channel: "web", payload_kind: "agentturn",
        });
      }
      resetForm(); setShowForm(false); refresh();
    } catch (e: any) { console.error("Create automation error:", e); }
    setCreating(false);
  }

  const refresh = useCallback(async () => {
    try {
      const [cron, ag] = await Promise.all([cronDashboard(), listAgents()]);
      setJobs(cron.cron_jobs ?? []);
      setAgents(ag.agents ?? []);
    } catch (e) { console.error("Dashboard fetch error:", e); }
    setLoading(false);
  }, []);

  useEffect(() => { refresh(); const iv = setInterval(refresh, 30_000); return () => clearInterval(iv); }, [refresh]);

  async function toggleJob(id: string, enabled: boolean) {
    setTogglingId(id);
    try {
      await updateCron(id, { enabled });
      setJobs(prev => prev.map(j => j.id === id ? { ...j, enabled } : j));
    } catch {}
    setTogglingId(null);
  }

  async function handleRunNow(id: string) {
    setRunningId(id);
    try {
      await runCronNow(id);
      // Refresh to get updated run status
      setTimeout(refresh, 1000);
    } catch (e: any) { console.error("Run now error:", e); }
    setRunningId(null);
  }

  async function handleDelete(id: string) {
    setDeletingId(id);
    try {
      await deleteCron(id);
      setJobs(prev => prev.filter(j => j.id !== id));
      if (expandedJob === id) setExpandedJob(null);
    } catch (e: any) { console.error("Delete error:", e); }
    setDeletingId(null);
  }

  async function handleSaveEdit(id: string, updates: { name?: string; cron_expr?: string; message?: string; tz?: string; channel?: string; tlg_call?: boolean }) {
    setSavingEdit(true);
    try {
      await updateCron(id, updates);
      setJobs(prev => prev.map(j => j.id === id ? { ...j, ...updates } : j));
      setEditingId(null);
    } catch (e: any) { console.error("Edit error:", e); }
    setSavingEdit(false);
  }

  async function loadRuns(jobId: string) {
    if (expandedJob === jobId) { setExpandedJob(null); return; }
    setExpandedJob(jobId);
    if (!runs[jobId]) {
      try {
        const res = await cronJobRuns(jobId, 5);
        setRuns(prev => ({ ...prev, [jobId]: res.runs ?? [] }));
      } catch {}
    }
  }

  function getAgent(agentId?: string | null): Agent | undefined {
    if (!agentId) return undefined;
    return agents.find(a => a.id === agentId || a.id === agentId.toLowerCase());
  }

  const activeCount = jobs.filter(j => j.enabled).length;
  const totalCount = jobs.length;

  // ── View mode icons ──────────────────────────────────────────────────────

  const viewModes: { mode: ViewMode; label: string; icon: React.ReactNode }[] = [
    { mode: "list", label: "List", icon: (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
        <line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/>
        <line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/>
      </svg>
    )},
    { mode: "calendar", label: "Calendar", icon: (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>
      </svg>
    )},
    { mode: "pipeline", label: "Pipeline", icon: (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="5" cy="6" r="3"/><circle cx="19" cy="6" r="3"/><circle cx="12" cy="18" r="3"/>
        <path d="M5 9v3a3 3 0 003 3h8a3 3 0 003-3V9"/>
        <line x1="12" y1="15" x2="12" y2="15"/>
      </svg>
    )},
  ];

  // ═══════════════════════════════════════════════════════════════════════════
  // RENDER
  // ═══════════════════════════════════════════════════════════════════════════

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Header */}
      <div className="px-6 pt-4 pb-3 border-b border-separator shrink-0">
        <div className="flex items-center justify-between">
          {/* View mode toggle */}
          <div className="flex bg-white/[.06] rounded-lg p-0.5">
            {viewModes.map(({ mode, label, icon }) => (
              <button
                key={mode}
                onClick={() => setViewMode(mode)}
                className={`flex items-center gap-1.5 px-3 py-1.5 text-12 font-medium rounded-md transition-all ${
                  viewMode === mode
                    ? "bg-white/[.10] text-label shadow-sm"
                    : "text-label-tertiary hover:text-label"
                }`}
              >
                {icon}
                {label}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-3">
            <p className="text-12 text-label-tertiary tabular-nums">
              {activeCount} active &middot; {totalCount} total
            </p>
            <button
              onClick={() => { setShowForm(!showForm); if (!showForm) resetForm(); }}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-accent/15 hover:bg-accent/25 text-accent text-12 font-medium transition-colors"
            >
              <IconPlus size={12} />
              New
            </button>
          </div>
        </div>

        {/* Stats bar */}
        <div className="mt-3 flex gap-3">
          <div className="flex-1 bg-white/[.04] border border-separator rounded-xl px-4 py-2">
            <p className="text-[10px] text-label-tertiary uppercase tracking-wider font-semibold">Running</p>
            <p className="text-18 font-bold text-success tabular-nums">{activeCount}</p>
          </div>
          <div className="flex-1 bg-white/[.04] border border-separator rounded-xl px-4 py-2">
            <p className="text-[10px] text-label-tertiary uppercase tracking-wider font-semibold">Paused</p>
            <p className="text-18 font-bold text-warning tabular-nums">{totalCount - activeCount}</p>
          </div>
          <div className="flex-1 bg-white/[.04] border border-separator rounded-xl px-4 py-2">
            <p className="text-[10px] text-label-tertiary uppercase tracking-wider font-semibold">Agents</p>
            <p className="text-18 font-bold text-accent tabular-nums">{new Set(jobs.map(j => j.agent_id).filter(Boolean)).size}</p>
          </div>
        </div>
      </div>

      {/* Creation form */}
      {showForm && <CreateJobForm
        scheduleType={scheduleType} setScheduleType={setScheduleType}
        formName={formName} setFormName={setFormName}
        formNiche={formNiche} handleNicheChange={handleNicheChange}
        formTz={formTz} setFormTz={setFormTz}
        formEnabled={formEnabled} setFormEnabled={setFormEnabled}
        creating={creating} handleCreate={handleCreate}
        customDays={customDays} toggleCustomDay={toggleCustomDay} setCustomDays={setCustomDays}
        customHour={customHour} setCustomHour={setCustomHour}
        customMinute={customMinute} setCustomMinute={setCustomMinute}
        customFormat={customFormat} setCustomFormat={setCustomFormat}
        customPrompt={customPrompt} setCustomPrompt={setCustomPrompt}
        ytEntries={ytEntries} setYtEntries={setYtEntries}
        onCancel={() => { setShowForm(false); resetForm(); }}
      />}

      {/* Content area */}
      {loading ? (
        <div className="flex-1 flex items-center justify-center">
          <div className="w-6 h-6 border-2 border-accent/40 border-t-accent rounded-full animate-spin" />
        </div>
      ) : viewMode === "list" ? (
        <ListView
          jobs={jobs} agents={agents} expandedJob={expandedJob} runs={runs}
          togglingId={togglingId} runningId={runningId} deletingId={deletingId}
          editingId={editingId} savingEdit={savingEdit}
          getAgent={getAgent} toggleJob={toggleJob} handleRunNow={handleRunNow}
          handleDelete={handleDelete} loadRuns={loadRuns}
          setEditingId={setEditingId} handleSaveEdit={handleSaveEdit}
        />
      ) : viewMode === "calendar" ? (
        <CalendarView
          jobs={jobs} agents={agents} getAgent={getAgent}
          calMonth={calMonth} calYear={calYear}
          setCalMonth={setCalMonth} setCalYear={setCalYear}
          onSelectJob={(id) => { setViewMode("list"); setExpandedJob(id); }}
        />
      ) : (
        <PipelineView jobs={jobs} agents={agents} getAgent={getAgent} runningId={runningId} />
      )}

      {/* Footer */}
      <div className="px-6 py-2.5 border-t border-separator shrink-0 flex items-center justify-between">
        <p className="text-11 text-label-tertiary">Auto-refreshes every 30s</p>
        <button onClick={refresh} className="text-12 text-accent hover:text-accent/80 font-medium transition-colors">
          Refresh now
        </button>
      </div>
    </div>
  );
}

// ═════════════════════════════════════════════════════════════════════════════
// LIST VIEW
// ═════════════════════════════════════════════════════════════════════════════

function ListView({ jobs, agents: _agents, expandedJob, runs, togglingId, runningId, deletingId, editingId, savingEdit, getAgent, toggleJob, handleRunNow, handleDelete, loadRuns, setEditingId, handleSaveEdit }: {
  jobs: CronJob[]; agents: Agent[]; expandedJob: string | null; runs: Record<string, CronRun[]>;
  togglingId: string | null; runningId: string | null; deletingId: string | null;
  editingId: string | null; savingEdit: boolean;
  getAgent: (id?: string | null) => Agent | undefined;
  toggleJob: (id: string, enabled: boolean) => void;
  handleRunNow: (id: string) => void;
  handleDelete: (id: string) => void;
  loadRuns: (id: string) => void;
  setEditingId: (id: string | null) => void;
  handleSaveEdit: (id: string, updates: { name?: string; cron_expr?: string; message?: string; tz?: string; channel?: string; tlg_call?: boolean }) => void;
}) {
  const [expandedRunId, setExpandedRunId] = useState<number | null>(null);

  if (jobs.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-center px-4">
        <div className="w-12 h-12 rounded-2xl bg-white/[.04] flex items-center justify-center mb-3">
          <IconClock size={24} className="text-label-tertiary" />
        </div>
        <p className="text-14 font-medium text-label-secondary">No automations yet</p>
        <p className="text-12 text-label-tertiary mt-1">
          Hit the <span className="text-accent font-medium">+</span> button above to create your first automation
        </p>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto px-4 py-3 space-y-2 scrollbar-thin">
      {jobs.map(job => {
        const agent = getAgent(job.agent_id);
        const isActive = !!job.enabled;
        const isExpanded = expandedJob === job.id;
        const lastStatus = job.last_run?.status;
        const jobRuns = runs[job.id] ?? [];

        return (
          <div key={job.id} className={`border rounded-xl transition-all duration-200 ${
            isActive
              ? "border-separator bg-white/[.03] hover:bg-white/[.05]"
              : "border-separator/50 bg-white/[.01] opacity-60 hover:opacity-80"
          }`}>
            {/* Main row */}
            <div className="px-4 py-3 flex items-center gap-3">
              {/* Status indicator */}
              <div className="relative shrink-0">
                <div className={`w-3 h-3 rounded-full ${isActive ? "bg-success" : "bg-label-tertiary/40"}`} />
                {isActive && <div className="absolute inset-0 w-3 h-3 rounded-full bg-success animate-ping opacity-30" />}
              </div>

              {/* Agent icon */}
              {agent && (
                <div className="w-8 h-8 rounded-lg bg-white/[.06] flex items-center justify-center text-16 shrink-0">
                  {agent.icon || "\u{1F916}"}
                </div>
              )}

              {/* Info */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-13 font-semibold text-label truncate">{job.name}</span>
                  {agent && (
                    <span className="text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded-full bg-accent/10 text-accent shrink-0">
                      {agent.name}
                    </span>
                  )}
                  {lastStatus && (
                    <span className={`flex items-center gap-0.5 text-[10px] font-medium shrink-0 ${
                      lastStatus === "ok" || lastStatus === "success" ? "text-success" : "text-danger"
                    }`}>
                      {lastStatus === "ok" || lastStatus === "success"
                        ? <IconCheck size={10} /> : <IconWarning size={10} />}
                      {lastStatus}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-3 mt-0.5">
                  <span className="text-12 text-label-tertiary">
                    <IconClock size={10} className="inline -mt-px mr-1" />
                    {describeCron(job.cron_expr)}
                  </span>
                  {job.tz && <span className="text-11 text-label-tertiary">{job.tz}</span>}
                </div>
              </div>

              {/* Right side actions */}
              <div className="flex items-center gap-2 shrink-0">
                <div className="text-right mr-1">
                  {isActive && job.next_run && (
                    <p className="text-11 text-label-secondary font-medium">Next: {timeUntil(job.next_run)}</p>
                  )}
                  {job.last_run && (
                    <p className="text-11 text-label-tertiary">Last: {timeAgo(job.last_run.created_at)}</p>
                  )}
                </div>

                {/* Run Now */}
                <button
                  onClick={() => handleRunNow(job.id)}
                  disabled={runningId === job.id}
                  className="px-2 py-1 rounded-lg text-11 font-medium bg-accent/10 hover:bg-accent/20 text-accent transition-colors disabled:opacity-40"
                  title="Run now"
                >
                  {runningId === job.id ? (
                    <div className="w-3 h-3 border-2 border-accent/40 border-t-accent rounded-full animate-spin" />
                  ) : (
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg>
                  )}
                </button>

                {/* Toggle */}
                <button
                  onClick={() => toggleJob(job.id, !isActive)}
                  disabled={togglingId === job.id}
                  className={`relative w-10 h-[22px] rounded-full transition-all duration-300 ${
                    isActive ? "bg-success" : "bg-white/[.12]"
                  } ${togglingId === job.id ? "opacity-50" : ""}`}
                >
                  <div className={`absolute top-[2px] w-[18px] h-[18px] rounded-full bg-white shadow-sm transition-transform duration-300 ${
                    isActive ? "translate-x-[20px]" : "translate-x-[2px]"
                  }`} />
                </button>

                {/* Edit */}
                <button
                  onClick={() => setEditingId(editingId === job.id ? null : job.id)}
                  className={`w-7 h-7 flex items-center justify-center rounded-lg transition-all ${
                    editingId === job.id ? "bg-accent/15 text-accent" : "hover:bg-white/[.08] text-label-tertiary"
                  }`}
                  title="Edit"
                >
                  <IconEdit size={12} />
                </button>

                {/* Delete */}
                <button
                  onClick={() => handleDelete(job.id)}
                  disabled={deletingId === job.id}
                  className="w-7 h-7 flex items-center justify-center rounded-lg hover:bg-danger/10 text-label-tertiary hover:text-danger transition-all disabled:opacity-40"
                  title="Delete"
                >
                  {deletingId === job.id ? (
                    <div className="w-3 h-3 border-2 border-danger/40 border-t-danger rounded-full animate-spin" />
                  ) : (
                    <IconTrash size={12} />
                  )}
                </button>

                {/* Expand */}
                <button
                  onClick={() => loadRuns(job.id)}
                  className="w-7 h-7 flex items-center justify-center rounded-lg hover:bg-white/[.08] text-label-tertiary transition-all"
                >
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"
                    className={`transition-transform duration-200 ${isExpanded ? "rotate-180" : ""}`}>
                    <polyline points="6 9 12 15 18 9"/>
                  </svg>
                </button>
              </div>
            </div>

            {/* Message preview */}
            {job.message && (
              <div className="px-4 pb-2 -mt-1">
                <p className="text-11 text-label-tertiary truncate pl-6">
                  {job.message.length > 100 ? job.message.slice(0, 100) + "..." : job.message}
                </p>
              </div>
            )}

            {/* Inline edit form */}
            {editingId === job.id && (
              <EditJobForm job={job} saving={savingEdit}
                onSave={(updates) => handleSaveEdit(job.id, updates)}
                onCancel={() => setEditingId(null)}
              />
            )}

            {/* Expanded: run history */}
            {isExpanded && (
              <div className="border-t border-separator/50 px-4 py-3">
                <p className="text-11 font-semibold text-label-tertiary uppercase tracking-wider mb-2">Recent Runs</p>
                {jobRuns.length === 0 && (
                  <p className="text-12 text-label-tertiary py-2">No runs yet</p>
                )}
                <div className="space-y-1.5">
                  {jobRuns.map(run => {
                    const fullText = run.error || run.output || "";
                    const isRunExpanded = expandedRunId === run.id;
                    return (
                      <div key={run.id}>
                        <div
                          className="flex items-center gap-3 px-3 py-2 rounded-lg bg-white/[.02] border border-separator/30 cursor-pointer hover:bg-white/[.04] transition-colors"
                          onClick={() => setExpandedRunId(isRunExpanded ? null : run.id)}
                        >
                          <div className={`w-2 h-2 rounded-full shrink-0 ${
                            run.status === "ok" || run.status === "success" ? "bg-success" : run.status === "running" ? "bg-accent" : "bg-danger"
                          }`} />
                          <span className={`text-12 font-medium shrink-0 w-16 ${
                            run.status === "ok" || run.status === "success" ? "text-success" : run.status === "running" ? "text-accent" : "text-danger"
                          }`}>
                            {run.status}
                          </span>
                          <span className="text-11 text-label-tertiary flex-1 truncate">
                            {fullText ? fullText.slice(0, 120) : "—"}
                          </span>
                          <span className="text-11 text-label-tertiary tabular-nums shrink-0">
                            {timeAgo(run.created_at)}
                          </span>
                          {fullText.length > 120 && (
                            <svg className={`w-3 h-3 text-label-tertiary shrink-0 transition-transform ${isRunExpanded ? "rotate-180" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                              <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                            </svg>
                          )}
                        </div>
                        {isRunExpanded && fullText && (
                          <div className="mt-1 ml-5 px-3 py-2.5 rounded-lg bg-black/20 border border-separator/20">
                            <pre className="text-11 text-label-secondary whitespace-pre-wrap break-words font-mono leading-relaxed max-h-64 overflow-y-auto">
                              {fullText}
                            </pre>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ═════════════════════════════════════════════════════════════════════════════
// EDIT JOB FORM
// ═════════════════════════════════════════════════════════════════════════════

/** Parse cron dow field into array of day numbers. */
function parseCronDow(dow: string): number[] {
  if (dow === "*") return [0, 1, 2, 3, 4, 5, 6];
  return dow.split(",").map(Number).filter(n => !isNaN(n));
}

/** Build cron expression from visual picker state. */
function buildCronFromVisual(minute: number, hour: number, days: number[]): string {
  const sorted = [...days].sort((a, b) => a - b);
  const dowPart = sorted.length === 7 ? "*" : sorted.join(",");
  return `${minute} ${hour} * * ${dowPart}`;
}

function EditJobForm({ job, saving, onSave, onCancel }: {
  job: CronJob; saving: boolean;
  onSave: (updates: { name?: string; cron_expr?: string; message?: string; tz?: string; channel?: string; tlg_call?: boolean }) => void;
  onCancel: () => void;
}) {
  const parts = job.cron_expr.trim().split(/\s+/);
  const initMin = parts.length >= 1 ? parseInt(parts[0], 10) : 0;
  const initHour = parts.length >= 2 ? parseInt(parts[1], 10) : 10;
  const initDow = parts.length >= 5 ? parseCronDow(parts[4]) : [1, 2, 3, 4, 5];

  const [name, setName] = useState(job.name);
  const [message, setMessage] = useState(job.message || "");
  const [tz, setTz] = useState(job.tz || "");
  const [editDays, setEditDays] = useState<number[]>(initDow);
  const [editHour, setEditHour] = useState(isNaN(initHour) ? 10 : initHour);
  const [editMinute, setEditMinute] = useState(isNaN(initMin) ? 0 : initMin);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [rawCron, setRawCron] = useState(job.cron_expr);
  const [notifyTelegram, setNotifyTelegram] = useState(job.channel === "telegram");
  const [notifyCall, setNotifyCall] = useState(!!job.tlg_call);

  function toggleDay(d: number) {
    setEditDays(prev => prev.includes(d) ? prev.filter(x => x !== d) : [...prev, d]);
  }

  const cronExpr = showAdvanced ? rawCron : buildCronFromVisual(editMinute, editHour, editDays);

  function handleSubmit() {
    const updates: Record<string, any> = {};
    if (name.trim() && name !== job.name) updates.name = name.trim();
    if (cronExpr.trim() && cronExpr !== job.cron_expr) updates.cron_expr = cronExpr.trim();
    if (message !== (job.message || "")) updates.message = message;
    if (tz !== (job.tz || "")) updates.tz = tz;
    const newChannel = notifyTelegram ? "telegram" : "web";
    if (newChannel !== (job.channel || "web")) updates.channel = newChannel;
    if (notifyCall !== !!job.tlg_call) updates.tlg_call = notifyCall;
    if (Object.keys(updates).length === 0) { onCancel(); return; }
    onSave(updates);
  }

  return (
    <div className="border-t border-separator/50 px-4 py-3">
      <div className="flex items-center justify-between mb-2">
        <p className="text-11 font-semibold text-label-tertiary uppercase tracking-wider">Edit Automation</p>
        <button onClick={onCancel} className="w-6 h-6 flex items-center justify-center rounded-md hover:bg-white/[.08] text-label-tertiary">
          <IconClose size={10} />
        </button>
      </div>
      <div className="space-y-2.5">
        {/* Name */}
        <div>
          <label className={labelCls}>Name</label>
          <input type="text" value={name} onChange={e => setName(e.target.value)}
            className={inputCls} placeholder="Job name" />
        </div>

        {/* Schedule — visual picker */}
        {!showAdvanced ? (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className={labelCls}>Schedule</label>
              <button onClick={() => { setShowAdvanced(true); setRawCron(cronExpr); }}
                className="text-[10px] text-accent hover:text-accent/80 transition-colors">Advanced (cron)</button>
            </div>

            {/* Day picker */}
            <div className="flex gap-1.5">
              {DAY_LABELS.map((label, i) => {
                const cronDay = DAY_CRON[i];
                const active = editDays.includes(cronDay);
                return (
                  <button key={label} onClick={() => toggleDay(cronDay)}
                    className={`flex-1 py-1.5 rounded-lg text-11 font-medium transition-colors ${
                      active ? "bg-accent text-white" : "bg-white/[.06] text-label-tertiary hover:text-label hover:bg-white/[.1]"
                    }`}>{label}</button>
                );
              })}
            </div>
            {/* Quick select */}
            <div className="flex gap-2">
              {([["Weekdays", [1,2,3,4,5]], ["Weekends", [0,6]], ["Every day", [0,1,2,3,4,5,6]]] as [string, number[]][]).map(([label, days]) => (
                <button key={label} onClick={() => setEditDays(days)}
                  className="text-[10px] text-label-tertiary hover:text-accent transition-colors">{label}</button>
              ))}
            </div>

            {/* Time picker */}
            <div className="flex items-center gap-3">
              <div className="flex-1">
                <label className={labelCls}>Hour</label>
                <select value={editHour} onChange={e => setEditHour(parseInt(e.target.value, 10))} className={inputCls}>
                  {Array.from({ length: 24 }, (_, h) => (
                    <option key={h} value={h}>{h === 0 ? "12 AM" : h < 12 ? `${h} AM` : h === 12 ? "12 PM" : `${h - 12} PM`}</option>
                  ))}
                </select>
              </div>
              <div className="flex-1">
                <label className={labelCls}>Minute</label>
                <select value={editMinute} onChange={e => setEditMinute(parseInt(e.target.value, 10))} className={inputCls}>
                  {[0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55].map(m => (
                    <option key={m} value={m}>{m.toString().padStart(2, "0")}</option>
                  ))}
                </select>
              </div>
            </div>
            <p className="text-[10px] text-label-tertiary pl-1">{describeCron(cronExpr)}</p>
          </div>
        ) : (
          <div>
            <div className="flex items-center justify-between">
              <label className={labelCls}>Schedule (cron)</label>
              <button onClick={() => setShowAdvanced(false)}
                className="text-[10px] text-accent hover:text-accent/80 transition-colors">Simple view</button>
            </div>
            <input type="text" value={rawCron} onChange={e => setRawCron(e.target.value)}
              className={inputCls} placeholder="e.g. 0 10 * * 1,3,5" />
            <p className="text-[10px] text-label-tertiary mt-0.5 pl-1">{describeCron(rawCron)}</p>
          </div>
        )}

        {/* Message */}
        <div>
          <label className={labelCls}>Message / Prompt</label>
          <textarea value={message} onChange={e => setMessage(e.target.value)}
            rows={3} className={`${inputCls} resize-none`} placeholder="What should the AI do?" />
        </div>

        {/* Timezone */}
        <div>
          <label className={labelCls}>Timezone</label>
          <select value={tz} onChange={e => setTz(e.target.value)} className={inputCls}>
            <option value="">Local (server default)</option>
            {COMMON_TZ.filter(Boolean).map(t => <option key={t} value={t}>{t.replace(/_/g, " ")}</option>)}
          </select>
        </div>

        {/* Notifications */}
        <div>
          <label className={labelCls}>Notifications</label>
          <div className="flex gap-4 mt-1">
            {/* Telegram toggle */}
            <div className="flex items-center gap-2">
              <button onClick={() => setNotifyTelegram(!notifyTelegram)}
                className={`relative w-9 h-[20px] rounded-full transition-all duration-300 ${notifyTelegram ? "bg-accent" : "bg-white/[.12]"}`}>
                <div className={`absolute top-[2px] w-[16px] h-[16px] rounded-full bg-white shadow-sm transition-transform duration-300 ${
                  notifyTelegram ? "translate-x-[18px]" : "translate-x-[2px]"}`} />
              </button>
              <span className="text-11 text-label-secondary">Telegram</span>
            </div>
            {/* Phone call toggle */}
            <div className="flex items-center gap-2">
              <button onClick={() => setNotifyCall(!notifyCall)}
                className={`relative w-9 h-[20px] rounded-full transition-all duration-300 ${notifyCall ? "bg-accent" : "bg-white/[.12]"}`}>
                <div className={`absolute top-[2px] w-[16px] h-[16px] rounded-full bg-white shadow-sm transition-transform duration-300 ${
                  notifyCall ? "translate-x-[18px]" : "translate-x-[2px]"}`} />
              </button>
              <span className="text-11 text-label-secondary">Phone call</span>
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-2 pt-1">
          <button
            onClick={handleSubmit}
            disabled={saving || !name.trim() || (!showAdvanced && editDays.length === 0)}
            className="text-12 bg-accent hover:bg-accent-hover disabled:opacity-40 text-white px-4 py-1.5 rounded-lg transition-colors flex items-center gap-2"
          >
            {saving ? (
              <><div className="w-3 h-3 border-2 border-white/40 border-t-white rounded-full animate-spin" />Saving...</>
            ) : "Save Changes"}
          </button>
          <button onClick={onCancel} className="text-12 text-label-tertiary hover:text-label px-4 py-1.5 transition-colors">
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

// ═════════════════════════════════════════════════════════════════════════════
// CALENDAR VIEW
// ═════════════════════════════════════════════════════════════════════════════

function CalendarView({ jobs, agents: _agents, getAgent, calMonth, calYear, setCalMonth, setCalYear, onSelectJob }: {
  jobs: CronJob[]; agents: Agent[];
  getAgent: (id?: string | null) => Agent | undefined;
  calMonth: number; calYear: number;
  setCalMonth: (m: number) => void; setCalYear: (y: number) => void;
  onSelectJob: (id: string) => void;
}) {
  const MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

  function prevMonth() {
    if (calMonth === 0) { setCalMonth(11); setCalYear(calYear - 1); }
    else setCalMonth(calMonth - 1);
  }
  function nextMonth() {
    if (calMonth === 11) { setCalMonth(0); setCalYear(calYear + 1); }
    else setCalMonth(calMonth + 1);
  }

  // Build job-to-days map
  const jobDaysMap: Map<string, Set<number>> = new Map();
  for (const job of jobs) {
    if (!job.enabled) continue;
    const days = cronExprToDaysOfMonth(job.cron_expr, calYear, calMonth);
    jobDaysMap.set(job.id, new Set(days));
  }

  // Build calendar grid
  const firstDayOfMonth = new Date(calYear, calMonth, 1).getDay(); // 0=Sun
  const daysInMonth = new Date(calYear, calMonth + 1, 0).getDate();
  const startOffset = firstDayOfMonth === 0 ? 6 : firstDayOfMonth - 1; // Mon=0
  const totalCells = Math.ceil((startOffset + daysInMonth) / 7) * 7;
  const today = new Date();
  const isCurrentMonth = today.getMonth() === calMonth && today.getFullYear() === calYear;

  return (
    <div className="flex-1 overflow-y-auto px-4 py-3 scrollbar-thin">
      {/* Month navigation */}
      <div className="flex items-center justify-between mb-4">
        <button onClick={prevMonth} className="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-white/[.08] text-label-tertiary transition-all">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><polyline points="15 18 9 12 15 6"/></svg>
        </button>
        <h3 className="text-14 font-semibold text-label">{MONTH_NAMES[calMonth]} {calYear}</h3>
        <button onClick={nextMonth} className="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-white/[.08] text-label-tertiary transition-all">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><polyline points="9 18 15 12 9 6"/></svg>
        </button>
      </div>

      {/* Day headers */}
      <div className="grid grid-cols-7 gap-px mb-1">
        {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map(d => (
          <div key={d} className="text-center text-[10px] font-semibold text-label-tertiary uppercase tracking-wider py-1">{d}</div>
        ))}
      </div>

      {/* Calendar grid */}
      <div className="grid grid-cols-7 gap-px bg-separator/20 rounded-xl overflow-hidden">
        {Array.from({ length: totalCells }, (_, i) => {
          const dayNum = i - startOffset + 1;
          const isValidDay = dayNum >= 1 && dayNum <= daysInMonth;
          const isToday = isCurrentMonth && dayNum === today.getDate();

          // Jobs firing on this day
          const dayJobs: CronJob[] = [];
          if (isValidDay) {
            for (const job of jobs) {
              if (!job.enabled) continue;
              const days = jobDaysMap.get(job.id);
              if (days?.has(dayNum)) dayJobs.push(job);
            }
          }

          return (
            <div
              key={i}
              className={`min-h-[72px] p-1.5 ${
                isValidDay ? "bg-surface" : "bg-white/[.01]"
              } ${isToday ? "ring-1 ring-inset ring-accent/40" : ""}`}
            >
              {isValidDay && (
                <>
                  <div className={`text-11 font-medium mb-1 ${isToday ? "text-accent font-bold" : "text-label-secondary"}`}>
                    {dayNum}
                  </div>
                  <div className="space-y-0.5">
                    {dayJobs.slice(0, 3).map(job => {
                      const agent = getAgent(job.agent_id);
                      return (
                        <button
                          key={job.id}
                          onClick={() => onSelectJob(job.id)}
                          className="w-full text-left px-1 py-0.5 rounded text-[9px] font-medium truncate bg-accent/10 text-accent hover:bg-accent/20 transition-colors"
                          title={job.name}
                        >
                          {agent?.icon ? `${agent.icon} ` : ""}{job.name.length > 12 ? job.name.slice(0, 12) + "…" : job.name}
                        </button>
                      );
                    })}
                    {dayJobs.length > 3 && (
                      <div className="text-[9px] text-label-tertiary pl-1">+{dayJobs.length - 3} more</div>
                    )}
                  </div>
                </>
              )}
            </div>
          );
        })}
      </div>

      {/* Legend */}
      <div className="mt-4 flex flex-wrap gap-3">
        {jobs.filter(j => j.enabled).map(job => {
          const agent = getAgent(job.agent_id);
          return (
            <div key={job.id} className="flex items-center gap-1.5 text-11 text-label-secondary">
              <div className="w-2 h-2 rounded-full bg-accent" />
              {agent?.icon && <span>{agent.icon}</span>}
              <span className="truncate max-w-[120px]">{job.name}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ═════════════════════════════════════════════════════════════════════════════
// PIPELINE VIEW
// ═════════════════════════════════════════════════════════════════════════════

function PipelineView({ jobs, agents: _agents, getAgent, runningId }: {
  jobs: CronJob[]; agents: Agent[];
  getAgent: (id?: string | null) => Agent | undefined;
  runningId: string | null;
}) {
  // Animate connector dashes
  const animRef = useRef<number>(0);
  const [, forceRender] = useState(0);

  useEffect(() => {
    let running = true;
    const tick = () => {
      if (!running) return;
      animRef.current = (animRef.current + 0.5) % 100;
      forceRender(n => n + 1);
      requestAnimationFrame(tick);
    };
    // Only animate when there's a running job
    const hasRunning = jobs.some(j => j.last_run?.status === "running") || !!runningId;
    if (hasRunning) requestAnimationFrame(tick);
    return () => { running = false; };
  }, [jobs, runningId]);

  if (jobs.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center text-center">
        <p className="text-13 text-label-tertiary">No automations to visualize</p>
      </div>
    );
  }

  const statusColor = (s: PipelineStep["status"]) => {
    switch (s) {
      case "done": return { fill: "#34C759", stroke: "#34C759", text: "text-success" };
      case "running": return { fill: "#007AFF", stroke: "#007AFF", text: "text-accent" };
      case "error": return { fill: "#FF3B30", stroke: "#FF3B30", text: "text-danger" };
      default: return { fill: "rgba(255,255,255,0.15)", stroke: "rgba(255,255,255,0.2)", text: "text-label-tertiary" };
    }
  };

  return (
    <div className="flex-1 overflow-y-auto px-4 py-4 scrollbar-thin space-y-4">
      {jobs.map(job => {
        const agent = getAgent(job.agent_id);
        const isActive = !!job.enabled;
        const steps = buildPipelineSteps(job, job.last_run);
        const isRunning = runningId === job.id || job.last_run?.status === "running";

        return (
          <div key={job.id} className={`border rounded-xl p-4 transition-all ${
            isActive ? "border-separator bg-white/[.03]" : "border-separator/50 bg-white/[.01] opacity-50"
          }`}>
            {/* Job header */}
            <div className="flex items-center gap-2 mb-4">
              {agent && (
                <span className="text-16">{agent.icon || "\u{1F916}"}</span>
              )}
              <span className="text-13 font-semibold text-label">{job.name}</span>
              {isRunning && (
                <span className="flex items-center gap-1 text-[10px] font-semibold text-accent bg-accent/10 px-2 py-0.5 rounded-full">
                  <div className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
                  RUNNING
                </span>
              )}
              <span className="text-11 text-label-tertiary ml-auto">{describeCron(job.cron_expr)}</span>
            </div>

            {/* Pipeline SVG */}
            <div className="relative">
              <svg width="100%" height="60" viewBox="0 0 600 60" preserveAspectRatio="xMidYMid meet" className="overflow-visible">
                {steps.map((step, i) => {
                  const x = (i / (steps.length - 1)) * 520 + 40;
                  const colors = statusColor(step.status);

                  return (
                    <g key={step.id}>
                      {/* Connector line to next step */}
                      {i < steps.length - 1 && (() => {
                        const nextX = ((i + 1) / (steps.length - 1)) * 520 + 40;
                        const nextColors = statusColor(steps[i + 1].status);
                        const isFlowing = step.status === "done" && steps[i + 1].status === "running";
                        return (
                          <line
                            x1={x + 14} y1={20} x2={nextX - 14} y2={20}
                            stroke={step.status === "done" ? colors.stroke : nextColors.stroke}
                            strokeWidth="2"
                            strokeDasharray={isFlowing ? "6 4" : "none"}
                            strokeDashoffset={isFlowing ? -animRef.current : 0}
                            opacity={step.status === "idle" ? 0.3 : 0.8}
                          />
                        );
                      })()}

                      {/* Step circle */}
                      <circle
                        cx={x} cy={20} r={12}
                        fill={step.status === "idle" ? "transparent" : colors.fill}
                        stroke={colors.stroke}
                        strokeWidth={step.status === "running" ? 2.5 : 1.5}
                        opacity={step.status === "idle" ? 0.4 : 1}
                      />

                      {/* Step icon */}
                      {step.status === "done" && (
                        <path d={`M${x - 4} ${20} L${x - 1} ${23} L${x + 5} ${16}`} fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                      )}
                      {step.status === "running" && (
                        <circle cx={x} cy={20} r={4} fill="white">
                          <animate attributeName="opacity" values="1;0.3;1" dur="1.2s" repeatCount="indefinite" />
                        </circle>
                      )}
                      {step.status === "error" && (
                        <text x={x} y={24} textAnchor="middle" fill="white" fontSize="14" fontWeight="bold">!</text>
                      )}
                      {step.status === "idle" && (
                        <text x={x} y={24} textAnchor="middle" fill="rgba(255,255,255,0.3)" fontSize="11">{i + 1}</text>
                      )}

                      {/* Label */}
                      <text x={x} y={48} textAnchor="middle" fill="currentColor" fontSize="10"
                        className={colors.text} fontWeight="500">
                        {step.label}
                      </text>
                    </g>
                  );
                })}
              </svg>
            </div>

            {/* Step details */}
            <div className="flex gap-2 mt-2">
              {steps.map(step => {
                const colors = statusColor(step.status);
                return (
                  <div key={step.id} className="flex-1 text-center">
                    {step.detail && (
                      <p className={`text-[9px] ${colors.text} truncate px-1`} title={step.detail}>
                        {step.detail}
                      </p>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ═════════════════════════════════════════════════════════════════════════════
// CREATE JOB FORM
// ═════════════════════════════════════════════════════════════════════════════

function CreateJobForm({ scheduleType, setScheduleType, formName, setFormName, formNiche, handleNicheChange, formTz, setFormTz, formEnabled, setFormEnabled, creating, handleCreate, customDays, toggleCustomDay, setCustomDays, customHour, setCustomHour, customMinute, setCustomMinute, customFormat, setCustomFormat, customPrompt, setCustomPrompt, ytEntries, setYtEntries, onCancel }: {
  scheduleType: ScheduleType; setScheduleType: (t: ScheduleType) => void;
  formName: string; setFormName: (n: string) => void;
  formNiche: string; handleNicheChange: (n: string) => void;
  formTz: string; setFormTz: (t: string) => void;
  formEnabled: boolean; setFormEnabled: (b: boolean) => void;
  creating: boolean; handleCreate: () => void;
  customDays: number[]; toggleCustomDay: (d: number) => void; setCustomDays: (d: number[]) => void;
  customHour: number; setCustomHour: (h: number) => void;
  customMinute: number; setCustomMinute: (m: number) => void;
  customFormat: VideoFormat; setCustomFormat: (f: VideoFormat) => void;
  customPrompt: string; setCustomPrompt: (p: string) => void;
  ytEntries: YouTubeScheduleEntry[]; setYtEntries: (e: YouTubeScheduleEntry[]) => void;
  onCancel: () => void;
}) {
  return (
    <div className="px-4 pt-3 pb-1 border-b border-separator shrink-0 max-h-[50vh] overflow-y-auto scrollbar-thin">
      <div className="bg-white/[.04] border border-separator rounded-xl p-4 space-y-3">
        <p className="text-11 font-semibold text-label-tertiary uppercase tracking-wider">New Automation</p>

        {/* Name */}
        <div>
          <label className={labelCls}>Name</label>
          <input type="text" value={formName} onChange={e => setFormName(e.target.value)}
            placeholder="e.g. Tech YouTube Growth" className={inputCls} />
        </div>

        {/* Schedule type */}
        <div>
          <label className={labelCls}>Schedule Type</label>
          <div className="flex gap-2">
            <button onClick={() => setScheduleType("youtube")}
              className={`flex-1 py-2 rounded-lg text-12 font-medium transition-colors border ${
                scheduleType === "youtube" ? "bg-accent/15 border-accent/40 text-accent" : "bg-white/[.04] border-separator text-label-tertiary hover:text-label hover:bg-white/[.08]"
              }`}>
              YouTube Growth<span className="block text-[10px] opacity-70 mt-0.5">4 Shorts + 2 Standard/week</span>
            </button>
            <button onClick={() => setScheduleType("custom")}
              className={`flex-1 py-2 rounded-lg text-12 font-medium transition-colors border ${
                scheduleType === "custom" ? "bg-accent/15 border-accent/40 text-accent" : "bg-white/[.04] border-separator text-label-tertiary hover:text-label hover:bg-white/[.08]"
              }`}>
              Custom<span className="block text-[10px] opacity-70 mt-0.5">Build your own schedule</span>
            </button>
          </div>
        </div>

        {/* Niche / topic */}
        <div>
          <label className={labelCls}>Niche / Topic</label>
          <input type="text" value={formNiche} onChange={e => handleNicheChange(e.target.value)}
            placeholder="e.g. tech, space, finance, cooking" className={inputCls} />
        </div>

        {scheduleType === "youtube" ? (
          <div>
            <label className={labelCls}>Schedule Preview (6 jobs)</label>
            <div className="space-y-1.5">
              {ytEntries.map((entry, i) => {
                const formatLabel = entry.format === "short" ? "Short" : entry.format === "long" ? "Long" : "Standard";
                return (
                  <div key={i} className="bg-white/[.03] border border-separator/50 rounded-lg px-3 py-2">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-12 font-semibold text-label">{entry.dayLabel}</span>
                      <span className={`text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded-full ${
                        entry.format === "short" ? "bg-accent/10 text-accent" : "bg-success/10 text-success"
                      }`}>{formatLabel}</span>
                      <span className="text-11 text-label-tertiary ml-auto">
                        {entry.hour === 0 ? "12" : entry.hour > 12 ? entry.hour - 12 : entry.hour}:{entry.minute.toString().padStart(2, "0")} {entry.hour >= 12 ? "PM" : "AM"}
                      </span>
                    </div>
                    <textarea value={entry.prompt} onChange={e => {
                      const updated = [...ytEntries]; updated[i] = { ...entry, prompt: e.target.value }; setYtEntries(updated);
                    }} rows={2} className={`${inputCls} resize-none text-11`} />
                    <div className="flex items-center gap-2 mt-1.5">
                      <select value={entry.hour} onChange={e => {
                        const updated = [...ytEntries]; updated[i] = { ...entry, hour: parseInt(e.target.value, 10) }; setYtEntries(updated);
                      }} className="bg-white/[.06] border border-separator rounded px-2 py-1 text-11 text-label outline-none">
                        {Array.from({ length: 24 }, (_, h) => (
                          <option key={h} value={h}>{h === 0 ? "12 AM" : h < 12 ? `${h} AM` : h === 12 ? "12 PM" : `${h - 12} PM`}</option>
                        ))}
                      </select>
                      <select value={entry.minute} onChange={e => {
                        const updated = [...ytEntries]; updated[i] = { ...entry, minute: parseInt(e.target.value, 10) }; setYtEntries(updated);
                      }} className="bg-white/[.06] border border-separator rounded px-2 py-1 text-11 text-label outline-none">
                        {[0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55].map(m => (
                          <option key={m} value={m}>{m.toString().padStart(2, "0")}</option>
                        ))}
                      </select>
                      <select value={entry.format} onChange={e => {
                        const updated = [...ytEntries]; updated[i] = { ...entry, format: e.target.value as VideoFormat }; setYtEntries(updated);
                      }} className="bg-white/[.06] border border-separator rounded px-2 py-1 text-11 text-label outline-none">
                        <option value="short">Short</option>
                        <option value="standard">Standard</option>
                        <option value="long">Long</option>
                      </select>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ) : (
          <>
            <div className="space-y-2">
              <label className={labelCls}>Days</label>
              <div className="flex gap-1.5">
                {DAY_LABELS.map((label, i) => {
                  const cronDay = DAY_CRON[i];
                  const active = customDays.includes(cronDay);
                  return (
                    <button key={label} onClick={() => toggleCustomDay(cronDay)}
                      className={`flex-1 py-1.5 rounded-lg text-11 font-medium transition-colors ${
                        active ? "bg-accent text-white" : "bg-white/[.06] text-label-tertiary hover:text-label hover:bg-white/[.1]"
                      }`}>{label}</button>
                  );
                })}
              </div>
              <div className="flex gap-2">
                {([["Weekdays", [1,2,3,4,5]], ["Weekends", [0,6]], ["Every day", [0,1,2,3,4,5,6]]] as [string, number[]][]).map(([label, days]) => (
                  <button key={label} onClick={() => setCustomDays(days)}
                    className="text-[10px] text-label-tertiary hover:text-accent transition-colors">{label}</button>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className={labelCls}>Hour</label>
                <select value={customHour} onChange={e => setCustomHour(parseInt(e.target.value, 10))} className={inputCls}>
                  {Array.from({ length: 24 }, (_, i) => (
                    <option key={i} value={i}>{i === 0 ? "12 AM" : i < 12 ? `${i} AM` : i === 12 ? "12 PM" : `${i - 12} PM`}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className={labelCls}>Minute</label>
                <select value={customMinute} onChange={e => setCustomMinute(parseInt(e.target.value, 10))} className={inputCls}>
                  {[0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55].map(m => (
                    <option key={m} value={m}>{m.toString().padStart(2, "0")}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className={labelCls}>Format</label>
                <select value={customFormat} onChange={e => setCustomFormat(e.target.value as VideoFormat)} className={inputCls}>
                  <option value="short">Short</option>
                  <option value="standard">Standard</option>
                  <option value="long">Long</option>
                </select>
              </div>
            </div>

            <div>
              <label className={labelCls}>Message / Prompt</label>
              <textarea value={customPrompt} onChange={e => setCustomPrompt(e.target.value)}
                placeholder="What should the AI do on each run?" rows={3} className={`${inputCls} resize-none`} />
            </div>
          </>
        )}

        {/* Timezone */}
        <div>
          <label className={labelCls}>Timezone</label>
          <select value={formTz} onChange={e => setFormTz(e.target.value)} className={inputCls}>
            <option value="">Local (server default)</option>
            {COMMON_TZ.filter(Boolean).map(t => <option key={t} value={t}>{t.replace(/_/g, " ")}</option>)}
          </select>
        </div>

        {/* Enable toggle */}
        <div className="flex items-center gap-3">
          <button onClick={() => setFormEnabled(!formEnabled)}
            className={`relative w-10 h-[22px] rounded-full transition-all duration-300 ${formEnabled ? "bg-success" : "bg-white/[.12]"}`}>
            <div className={`absolute top-[2px] w-[18px] h-[18px] rounded-full bg-white shadow-sm transition-transform duration-300 ${
              formEnabled ? "translate-x-[20px]" : "translate-x-[2px]"}`} />
          </button>
          <span className="text-12 text-label-secondary">Enable immediately</span>
        </div>

        {/* Actions */}
        <div className="flex gap-2 pt-1">
          <button onClick={handleCreate}
            disabled={creating || !formName.trim() || (scheduleType === "custom" && (!customPrompt.trim() || customDays.length === 0))}
            className="text-12 bg-accent hover:bg-accent-hover disabled:opacity-40 text-white px-4 py-1.5 rounded-lg transition-colors flex items-center gap-2">
            {creating ? (
              <><div className="w-3 h-3 border-2 border-white/40 border-t-white rounded-full animate-spin" />Creating{scheduleType === "youtube" ? " 6 jobs..." : "..."}</>
            ) : (
              <>Create {scheduleType === "youtube" ? "6 Jobs" : "Job"}</>
            )}
          </button>
          <button onClick={onCancel} className="text-12 text-label-tertiary hover:text-label px-4 py-1.5 transition-colors">Cancel</button>
        </div>
      </div>
    </div>
  );
}
