import React, { useState, useEffect, useCallback } from "react";
import {
  View, Text, TouchableOpacity, TextInput, ScrollView,
  StyleSheet, Alert, Platform, ActivityIndicator,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { colors, spacing, radius } from "../theme/colors";
import {
  cronDashboard, cronJobRuns, updateCron, createCron, deleteCron, runCronNow, listAgents,
} from "../lib/api";
import {
  IconClock, IconCheck, IconWarning, IconPlus, IconX,
  IconChevronLeft, IconEdit, IconTrash,
} from "../components/Icons";

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
  enabled?: boolean; model_override?: string; category?: string;
}

interface Props { onBack: () => void; }

const DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const DAY_CRON   = [1,     2,     3,     4,     5,     6,     0];

const COMMON_TZ = [
  "", "America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles",
  "Europe/London", "Europe/Paris", "Europe/Lisbon", "Europe/Berlin",
  "Asia/Tokyo", "Asia/Jerusalem", "Asia/Shanghai", "Australia/Sydney",
];

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
  if (!ts) return "";
  const d = new Date(ts);
  if (isNaN(d.getTime())) return "";
  const sec = (d.getTime() - Date.now()) / 1000;
  if (sec <= 0) return "now";
  if (sec < 3600) return `in ${Math.round(sec / 60)}m`;
  if (sec < 86400) return `in ${Math.round(sec / 3600)}h`;
  return `in ${Math.round(sec / 86400)}d`;
}

function parseCronDow(dow: string): number[] {
  if (dow === "*") return [0, 1, 2, 3, 4, 5, 6];
  return dow.split(",").map(Number).filter(n => !isNaN(n));
}

export default function AutomationsScreen({ onBack }: Props) {
  const insets = useSafeAreaInsets();
  const [jobs, setJobs] = useState<CronJob[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [runningId, setRunningId] = useState<string | null>(null);
  const [editingJob, setEditingJob] = useState<CronJob | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [expandedRunId, setExpandedRunId] = useState<number | null>(null);
  const [runs, setRuns] = useState<Record<string, CronRun[]>>({});

  const refresh = useCallback(async () => {
    try {
      const [cron, ag] = await Promise.all([cronDashboard(), listAgents()]);
      setJobs(cron.cron_jobs ?? []);
      setAgents(ag.agents ?? []);
    } catch (e) { console.error(e); }
    setLoading(false);
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  function getAgent(agentId?: string | null): Agent | undefined {
    if (!agentId) return undefined;
    return agents.find(a => a.id === agentId || a.id === agentId.toLowerCase());
  }

  async function handleToggle(id: string, enabled: boolean) {
    try {
      await updateCron(id, { enabled });
      setJobs(prev => prev.map(j => j.id === id ? { ...j, enabled } : j));
    } catch {}
  }

  async function handleRunNow(id: string) {
    setRunningId(id);
    try { await runCronNow(id); setTimeout(refresh, 1500); }
    catch (e: any) { console.error(e); }
    setRunningId(null);
  }

  function confirmDelete(id: string, name: string) {
    if (Platform.OS === "web") {
      if (confirm(`Delete "${name}"?`)) doDelete(id);
      return;
    }
    Alert.alert("Delete Automation", `Delete "${name}"?`, [
      { text: "Cancel", style: "cancel" },
      { text: "Delete", style: "destructive", onPress: () => doDelete(id) },
    ]);
  }

  async function doDelete(id: string) {
    try {
      await deleteCron(id);
      setJobs(prev => prev.filter(j => j.id !== id));
    } catch {}
  }

  async function toggleExpand(id: string) {
    if (expandedId === id) { setExpandedId(null); return; }
    setExpandedId(id);
    if (!runs[id]) {
      try {
        const res = await cronJobRuns(id, 10);
        setRuns(prev => ({ ...prev, [id]: res.runs ?? [] }));
      } catch {}
    }
  }

  const activeCount = jobs.filter(j => j.enabled).length;

  if (editingJob) {
    return (
      <EditJobView
        job={editingJob}
        insets={insets}
        onBack={() => setEditingJob(null)}
        onSave={async (updates) => {
          try {
            await updateCron(editingJob.id, updates);
            setJobs(prev => prev.map(j => j.id === editingJob.id ? { ...j, ...updates } : j));
            setEditingJob(null);
          } catch (e: any) { console.error(e); }
        }}
      />
    );
  }

  return (
    <View style={[s.container, { paddingTop: insets.top }]}>
      {/* Header */}
      <View style={s.header}>
        <TouchableOpacity onPress={onBack} style={s.backBtn} activeOpacity={0.7}>
          <IconChevronLeft size={20} color={colors.accent} />
          <Text style={s.backText}>Back</Text>
        </TouchableOpacity>
        <Text style={s.headerTitle}>Automations</Text>
        <View style={{ width: 60 }} />
      </View>

      {/* Stats */}
      <View style={s.statsRow}>
        <View style={s.statCard}>
          <Text style={s.statLabel}>RUNNING</Text>
          <Text style={[s.statValue, { color: colors.success }]}>{activeCount}</Text>
        </View>
        <View style={s.statCard}>
          <Text style={s.statLabel}>PAUSED</Text>
          <Text style={[s.statValue, { color: colors.warning }]}>{jobs.length - activeCount}</Text>
        </View>
        <View style={s.statCard}>
          <Text style={s.statLabel}>TOTAL</Text>
          <Text style={[s.statValue, { color: colors.accent }]}>{jobs.length}</Text>
        </View>
      </View>

      {/* Job list */}
      {loading ? (
        <View style={s.loadingWrap}>
          <ActivityIndicator color={colors.accent} />
        </View>
      ) : jobs.length === 0 ? (
        <View style={s.emptyWrap}>
          <IconClock size={32} color={colors.labelTertiary} />
          <Text style={s.emptyTitle}>No automations</Text>
          <Text style={s.emptySubtitle}>Create automations from the desktop app</Text>
        </View>
      ) : (
        <ScrollView style={s.list} showsVerticalScrollIndicator={false}>
          {jobs.map(job => {
            const agent = getAgent(job.agent_id);
            const active = !!job.enabled;
            const isExpanded = expandedId === job.id;
            const jobRuns = runs[job.id] ?? [];

            return (
              <View key={job.id} style={[s.jobCard, !active && s.jobCardInactive]}>
                <TouchableOpacity style={s.jobMain} onPress={() => toggleExpand(job.id)} activeOpacity={0.7}>
                  {/* Status dot */}
                  <View style={[s.statusDot, { backgroundColor: active ? colors.success : colors.labelTertiary }]} />

                  {/* Agent icon */}
                  {agent && <Text style={s.agentIcon}>{agent.icon || "\u{1F916}"}</Text>}

                  {/* Info */}
                  <View style={s.jobInfo}>
                    <Text style={s.jobName} numberOfLines={1}>{job.name}</Text>
                    <View style={s.jobMetaRow}>
                      <IconClock size={10} color={colors.labelTertiary} />
                      <Text style={s.jobMeta}>{describeCron(job.cron_expr)}</Text>
                    </View>
                    {active && job.next_run ? (
                      <Text style={s.jobNext}>Next: {timeUntil(job.next_run)}</Text>
                    ) : job.last_run ? (
                      <Text style={s.jobNext}>Last: {timeAgo(job.last_run.created_at)}</Text>
                    ) : null}
                  </View>

                  {/* Last status badge */}
                  {job.last_run?.status && (
                    <View style={[s.statusBadge, {
                      backgroundColor: (job.last_run.status === "ok" || job.last_run.status === "success")
                        ? "rgba(52,199,89,0.15)" : "rgba(255,59,48,0.15)"
                    }]}>
                      {(job.last_run.status === "ok" || job.last_run.status === "success")
                        ? <IconCheck size={10} color={colors.success} />
                        : <IconWarning size={10} color={colors.danger} />}
                    </View>
                  )}
                </TouchableOpacity>

                {/* Actions row */}
                <View style={s.actionsRow}>
                  {/* Run now */}
                  <TouchableOpacity
                    style={s.actionBtn}
                    onPress={() => handleRunNow(job.id)}
                    disabled={runningId === job.id}
                    activeOpacity={0.7}
                  >
                    {runningId === job.id
                      ? <ActivityIndicator size="small" color={colors.accent} />
                      : <Text style={s.actionBtnText}>Run</Text>}
                  </TouchableOpacity>

                  {/* Edit */}
                  <TouchableOpacity style={s.actionBtn} onPress={() => setEditingJob(job)} activeOpacity={0.7}>
                    <IconEdit size={14} color={colors.labelSecondary} />
                  </TouchableOpacity>

                  {/* Toggle */}
                  <TouchableOpacity
                    style={[s.toggleTrack, active && s.toggleTrackActive]}
                    onPress={() => handleToggle(job.id, !active)}
                    activeOpacity={0.7}
                  >
                    <View style={[s.toggleThumb, active && s.toggleThumbActive]} />
                  </TouchableOpacity>

                  {/* Delete */}
                  <TouchableOpacity
                    style={s.actionBtn}
                    onPress={() => confirmDelete(job.id, job.name)}
                    activeOpacity={0.7}
                  >
                    <IconTrash size={14} color={colors.danger} />
                  </TouchableOpacity>
                </View>

                {/* Message preview */}
                {job.message && (
                  <Text style={s.msgPreview} numberOfLines={2}>{job.message}</Text>
                )}

                {/* Expanded: run history */}
                {isExpanded && (
                  <View style={s.runsSection}>
                    <Text style={s.runsTitle}>Recent Runs</Text>
                    {jobRuns.length === 0 && <Text style={s.runsEmpty}>No runs yet</Text>}
                    {jobRuns.map(run => {
                      const fullText = run.error || run.output || "";
                      const isRunOpen = expandedRunId === run.id;
                      return (
                        <View key={run.id}>
                          <TouchableOpacity
                            style={s.runRow}
                            onPress={() => setExpandedRunId(isRunOpen ? null : run.id)}
                            activeOpacity={0.7}
                          >
                            <View style={[s.runDot, {
                              backgroundColor: (run.status === "ok" || run.status === "success")
                                ? colors.success : run.status === "running" ? colors.accent : colors.danger
                            }]} />
                            <Text style={[s.runStatus, {
                              color: (run.status === "ok" || run.status === "success")
                                ? colors.success : run.status === "running" ? colors.accent : colors.danger
                            }]}>{run.status}</Text>
                            <Text style={s.runOutput} numberOfLines={isRunOpen ? undefined : 1}>
                              {fullText ? fullText.slice(0, 120) : "—"}
                            </Text>
                            <Text style={s.runTime}>{timeAgo(run.created_at)}</Text>
                          </TouchableOpacity>
                          {isRunOpen && fullText.length > 0 && (
                            <View style={s.runFullOutput}>
                              <ScrollView style={s.runFullScroll} nestedScrollEnabled>
                                <Text style={s.runFullText}>{fullText}</Text>
                              </ScrollView>
                            </View>
                          )}
                        </View>
                      );
                    })}
                  </View>
                )}
              </View>
            );
          })}
          <View style={{ height: 40 }} />
        </ScrollView>
      )}
    </View>
  );
}

// ── Edit Job View ────────────────────────────────────────────────────────────

function EditJobView({ job, insets, onBack, onSave }: {
  job: CronJob;
  insets: { top: number; bottom: number };
  onBack: () => void;
  onSave: (updates: Record<string, any>) => void;
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
  const [notifyTelegram, setNotifyTelegram] = useState(job.channel === "telegram");
  const [notifyCall, setNotifyCall] = useState(!!job.tlg_call);
  const [saving, setSaving] = useState(false);

  function toggleDay(d: number) {
    setEditDays(prev => prev.includes(d) ? prev.filter(x => x !== d) : [...prev, d]);
  }

  const cronExpr = (() => {
    const sorted = [...editDays].sort((a, b) => a - b);
    const dowPart = sorted.length === 7 ? "*" : sorted.join(",");
    return `${editMinute} ${editHour} * * ${dowPart}`;
  })();

  async function handleSave() {
    setSaving(true);
    const updates: Record<string, any> = {};
    if (name.trim() !== job.name) updates.name = name.trim();
    if (cronExpr !== job.cron_expr) updates.cron_expr = cronExpr;
    if (message !== (job.message || "")) updates.message = message;
    if (tz !== (job.tz || "")) updates.tz = tz;
    const newChannel = notifyTelegram ? "telegram" : "web";
    if (newChannel !== (job.channel || "web")) updates.channel = newChannel;
    if (notifyCall !== !!job.tlg_call) updates.tlg_call = notifyCall;
    if (Object.keys(updates).length === 0) { onBack(); return; }
    await onSave(updates);
    setSaving(false);
  }

  const fmtHour = (h: number) => h === 0 ? "12 AM" : h < 12 ? `${h} AM` : h === 12 ? "12 PM" : `${h - 12} PM`;

  return (
    <View style={[s.container, { paddingTop: insets.top }]}>
      <View style={s.header}>
        <TouchableOpacity onPress={onBack} style={s.backBtn} activeOpacity={0.7}>
          <IconChevronLeft size={20} color={colors.accent} />
          <Text style={s.backText}>Back</Text>
        </TouchableOpacity>
        <Text style={s.headerTitle}>Edit</Text>
        <View style={{ width: 60 }} />
      </View>

      <ScrollView style={s.editScroll} showsVerticalScrollIndicator={false}>
        {/* Name */}
        <Text style={s.editLabel}>Name</Text>
        <TextInput style={s.editInput} value={name} onChangeText={setName} placeholderTextColor={colors.labelTertiary} />

        {/* Days */}
        <Text style={s.editLabel}>Days</Text>
        <View style={s.daysRow}>
          {DAY_LABELS.map((label, i) => {
            const cronDay = DAY_CRON[i];
            const active = editDays.includes(cronDay);
            return (
              <TouchableOpacity
                key={label}
                style={[s.dayBtn, active && s.dayBtnActive]}
                onPress={() => toggleDay(cronDay)}
                activeOpacity={0.7}
              >
                <Text style={[s.dayBtnText, active && s.dayBtnTextActive]}>{label}</Text>
              </TouchableOpacity>
            );
          })}
        </View>
        <View style={s.quickDaysRow}>
          {([["Weekdays", [1,2,3,4,5]], ["Weekends", [0,6]], ["Every day", [0,1,2,3,4,5,6]]] as [string, number[]][]).map(([label, days]) => (
            <TouchableOpacity key={label} onPress={() => setEditDays(days)} activeOpacity={0.7}>
              <Text style={s.quickDayText}>{label}</Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Time */}
        <Text style={s.editLabel}>Time</Text>
        <View style={s.timeRow}>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={s.timePicker}>
            {Array.from({ length: 24 }, (_, h) => (
              <TouchableOpacity
                key={h}
                style={[s.timeChip, editHour === h && s.timeChipActive]}
                onPress={() => setEditHour(h)}
                activeOpacity={0.7}
              >
                <Text style={[s.timeChipText, editHour === h && s.timeChipTextActive]}>{fmtHour(h)}</Text>
              </TouchableOpacity>
            ))}
          </ScrollView>
        </View>
        <View style={s.timeRow}>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={s.timePicker}>
            {[0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55].map(m => (
              <TouchableOpacity
                key={m}
                style={[s.timeChip, editMinute === m && s.timeChipActive]}
                onPress={() => setEditMinute(m)}
                activeOpacity={0.7}
              >
                <Text style={[s.timeChipText, editMinute === m && s.timeChipTextActive]}>:{m.toString().padStart(2, "0")}</Text>
              </TouchableOpacity>
            ))}
          </ScrollView>
        </View>
        <Text style={s.cronPreview}>{describeCron(cronExpr)}</Text>

        {/* Message */}
        <Text style={s.editLabel}>Message / Prompt</Text>
        <TextInput
          style={[s.editInput, { height: 80, textAlignVertical: "top" }]}
          value={message} onChangeText={setMessage}
          multiline placeholderTextColor={colors.labelTertiary}
          placeholder="What should the AI do?"
        />

        {/* Notifications */}
        <Text style={s.editLabel}>Notifications</Text>
        <View style={s.notifRow}>
          <TouchableOpacity
            style={[s.toggleTrack, notifyTelegram && s.toggleTrackActive]}
            onPress={() => setNotifyTelegram(!notifyTelegram)}
            activeOpacity={0.7}
          >
            <View style={[s.toggleThumb, notifyTelegram && s.toggleThumbActive]} />
          </TouchableOpacity>
          <Text style={s.notifLabel}>Telegram</Text>
        </View>
        <View style={s.notifRow}>
          <TouchableOpacity
            style={[s.toggleTrack, notifyCall && s.toggleTrackActive]}
            onPress={() => setNotifyCall(!notifyCall)}
            activeOpacity={0.7}
          >
            <View style={[s.toggleThumb, notifyCall && s.toggleThumbActive]} />
          </TouchableOpacity>
          <Text style={s.notifLabel}>Phone call</Text>
        </View>

        {/* Save */}
        <TouchableOpacity
          style={[s.saveBtn, saving && { opacity: 0.5 }]}
          onPress={handleSave}
          disabled={saving || !name.trim() || editDays.length === 0}
          activeOpacity={0.7}
        >
          {saving
            ? <ActivityIndicator color="#fff" size="small" />
            : <Text style={s.saveBtnText}>Save Changes</Text>}
        </TouchableOpacity>

        <View style={{ height: insets.bottom + 40 }} />
      </ScrollView>
    </View>
  );
}

// ── Styles ───────────────────────────────────────────────────────────────────

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface },

  // Header
  header: {
    flexDirection: "row", alignItems: "center", justifyContent: "space-between",
    paddingHorizontal: spacing.md, paddingVertical: spacing.md,
    borderBottomWidth: 1, borderBottomColor: colors.separator,
  },
  backBtn: { flexDirection: "row", alignItems: "center", gap: 4, width: 60 },
  backText: { fontSize: 15, color: colors.accent, fontWeight: "500" },
  headerTitle: { fontSize: 17, fontWeight: "700", color: colors.label },

  // Stats
  statsRow: {
    flexDirection: "row", gap: spacing.sm,
    paddingHorizontal: spacing.md, paddingVertical: spacing.md,
  },
  statCard: {
    flex: 1, backgroundColor: colors.white04,
    borderWidth: 1, borderColor: colors.separator,
    borderRadius: radius.md, paddingHorizontal: spacing.sm, paddingVertical: spacing.sm,
  },
  statLabel: { fontSize: 9, fontWeight: "700", color: colors.labelTertiary, letterSpacing: 1 },
  statValue: { fontSize: 20, fontWeight: "800", fontVariant: ["tabular-nums"] },

  // Loading / empty
  loadingWrap: { flex: 1, justifyContent: "center", alignItems: "center" },
  emptyWrap: { flex: 1, justifyContent: "center", alignItems: "center", gap: 8 },
  emptyTitle: { fontSize: 16, fontWeight: "600", color: colors.labelSecondary },
  emptySubtitle: { fontSize: 13, color: colors.labelTertiary },

  // List
  list: { flex: 1, paddingHorizontal: spacing.md },

  // Job card
  jobCard: {
    borderWidth: 1, borderColor: colors.separator,
    borderRadius: radius.md, marginBottom: spacing.sm,
    backgroundColor: colors.white04, overflow: "hidden",
  },
  jobCardInactive: { opacity: 0.5 },
  jobMain: {
    flexDirection: "row", alignItems: "center", gap: spacing.sm,
    paddingHorizontal: spacing.md, paddingVertical: spacing.md,
  },
  statusDot: { width: 8, height: 8, borderRadius: 4 },
  agentIcon: { fontSize: 18 },
  jobInfo: { flex: 1, gap: 2 },
  jobName: { fontSize: 14, fontWeight: "600", color: colors.label },
  jobMetaRow: { flexDirection: "row", alignItems: "center", gap: 4 },
  jobMeta: { fontSize: 11, color: colors.labelTertiary },
  jobNext: { fontSize: 10, color: colors.labelSecondary },
  statusBadge: {
    width: 24, height: 24, borderRadius: 12,
    alignItems: "center", justifyContent: "center",
  },

  // Actions
  actionsRow: {
    flexDirection: "row", alignItems: "center", gap: spacing.sm,
    paddingHorizontal: spacing.md, paddingBottom: spacing.sm,
  },
  actionBtn: {
    paddingHorizontal: spacing.sm, paddingVertical: 6,
    borderRadius: radius.sm, backgroundColor: colors.white05,
  },
  actionBtnText: { fontSize: 12, fontWeight: "600", color: colors.accent },

  // Toggle
  toggleTrack: {
    width: 40, height: 22, borderRadius: 11,
    backgroundColor: colors.white08, justifyContent: "center",
    paddingHorizontal: 2,
  },
  toggleTrackActive: { backgroundColor: colors.success },
  toggleThumb: {
    width: 18, height: 18, borderRadius: 9,
    backgroundColor: "#fff",
  },
  toggleThumbActive: { alignSelf: "flex-end" },

  // Message preview
  msgPreview: {
    fontSize: 11, color: colors.labelTertiary,
    paddingHorizontal: spacing.md, paddingBottom: spacing.sm,
  },

  // Runs
  runsSection: {
    borderTopWidth: 1, borderTopColor: colors.separator,
    paddingHorizontal: spacing.md, paddingVertical: spacing.sm,
  },
  runsTitle: { fontSize: 10, fontWeight: "700", color: colors.labelTertiary, letterSpacing: 1, marginBottom: 6 },
  runsEmpty: { fontSize: 12, color: colors.labelTertiary, paddingVertical: 4 },
  runRow: {
    flexDirection: "row", alignItems: "center", gap: 8,
    paddingVertical: 4,
  },
  runDot: { width: 6, height: 6, borderRadius: 3 },
  runStatus: { fontSize: 11, fontWeight: "600", width: 50 },
  runOutput: { flex: 1, fontSize: 10, color: colors.labelTertiary },
  runTime: { fontSize: 10, color: colors.labelTertiary, fontVariant: ["tabular-nums"] },
  runFullOutput: {
    marginLeft: 14, marginTop: 4, marginBottom: 6,
    backgroundColor: "rgba(0,0,0,0.2)", borderRadius: radius.sm,
    borderWidth: 1, borderColor: colors.separator,
    padding: spacing.sm,
  },
  runFullScroll: { maxHeight: 200 },
  runFullText: {
    fontSize: 11, color: colors.labelSecondary,
    fontFamily: Platform.OS === "ios" ? "Menlo" : "monospace",
    lineHeight: 16,
  },

  // ── Edit view ──
  editScroll: { flex: 1, paddingHorizontal: spacing.md, paddingTop: spacing.md },
  editLabel: {
    fontSize: 10, fontWeight: "700", color: colors.labelTertiary,
    letterSpacing: 1, textTransform: "uppercase", marginBottom: 6, marginTop: spacing.md,
  },
  editInput: {
    backgroundColor: colors.white05, borderWidth: 1, borderColor: colors.separator,
    borderRadius: radius.sm, paddingHorizontal: spacing.md, paddingVertical: 10,
    fontSize: 14, color: colors.label,
  },

  // Days
  daysRow: { flexDirection: "row", gap: 6 },
  dayBtn: {
    flex: 1, paddingVertical: 10, borderRadius: radius.sm,
    backgroundColor: colors.white05, alignItems: "center",
  },
  dayBtnActive: { backgroundColor: colors.accent },
  dayBtnText: { fontSize: 12, fontWeight: "600", color: colors.labelTertiary },
  dayBtnTextActive: { color: "#fff" },
  quickDaysRow: { flexDirection: "row", gap: spacing.md, marginTop: 6 },
  quickDayText: { fontSize: 10, color: colors.labelTertiary },

  // Time
  timeRow: { marginBottom: 4 },
  timePicker: { flexDirection: "row" },
  timeChip: {
    paddingHorizontal: 10, paddingVertical: 8,
    borderRadius: radius.sm, backgroundColor: colors.white05,
    marginRight: 6,
  },
  timeChipActive: { backgroundColor: colors.accent },
  timeChipText: { fontSize: 12, fontWeight: "600", color: colors.labelTertiary },
  timeChipTextActive: { color: "#fff" },
  cronPreview: { fontSize: 11, color: colors.labelSecondary, marginTop: 4 },

  // Notifications
  notifRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm, marginBottom: spacing.sm },
  notifLabel: { fontSize: 13, color: colors.labelSecondary },

  // Save button
  saveBtn: {
    backgroundColor: colors.accent, borderRadius: radius.md,
    paddingVertical: 14, alignItems: "center", marginTop: spacing.xl,
  },
  saveBtnText: { fontSize: 15, fontWeight: "700", color: "#fff" },
});
