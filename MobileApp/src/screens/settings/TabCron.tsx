import React, { useState, useEffect } from "react";
import { View, Text, TextInput, TouchableOpacity, ScrollView, Alert, Platform } from "react-native";
import { colors, spacing, radius } from "../../theme/colors";
import { listCron, createCron, updateCron, deleteCron } from "../../lib/api";
import { IconPlus } from "../../components/Icons";
import Toggle from "../../components/Toggle";
import { Label, Chip, st, TabProps } from "./shared";

const DAY_LABELS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const COMMON_TZ = [
  "", "America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles",
  "Europe/London", "Europe/Paris", "Europe/Berlin",
  "Asia/Tokyo", "Asia/Shanghai", "Australia/Sydney",
];

function parseCronExpr(expr: string): { minute: number; hour: number; days: number[] } | null {
  const p = expr.split(" ");
  if (p.length !== 5 || p[2] !== "*" || p[3] !== "*") return null;
  const minute = parseInt(p[0], 10);
  const hour = parseInt(p[1], 10);
  if (isNaN(minute) || isNaN(hour)) return null;
  let days: number[];
  if (p[4] === "*") { days = [0, 1, 2, 3, 4, 5, 6]; }
  else if (p[4].includes("-")) {
    const [a, b] = p[4].split("-").map(Number);
    days = [];
    for (let i = a; i <= b; i++) days.push(i);
  } else { days = p[4].split(",").map(Number); }
  return { minute, hour, days };
}

function buildCronExpr(h: number, m: number, days: number[]): string {
  const sorted = [...days].sort((a, b) => a - b);
  const dow = sorted.length === 7 ? "*" : sorted.join(",");
  return `${m} ${h} * * ${dow}`;
}

function fmtTime12(h: number, m: number): string {
  const ampm = h >= 12 ? "PM" : "AM";
  const h12 = h === 0 ? 12 : h > 12 ? h - 12 : h;
  return `${h12}:${String(m).padStart(2, "0")} ${ampm}`;
}

function fmtDaysList(days: number[]): string {
  const s = [...days].sort((a, b) => a - b);
  if (s.length === 7) return "Every day";
  if (s.length === 5 && [1, 2, 3, 4, 5].every((d) => s.includes(d))) return "Weekdays";
  if (s.length === 2 && s.includes(0) && s.includes(6)) return "Weekends";
  return s.map((d) => DAY_LABELS[d]).join(", ");
}

export default function TabCron(_props: TabProps) {
  const [cronJobs, setCronJobs] = useState<any[]>([]);
  const [cronForm, setCronForm] = useState(false);
  const [cronEditId, setCronEditId] = useState<string | null>(null);
  const [cronName, setCronName] = useState("");
  const [cronMessage, setCronMessage] = useState("");
  const [cronAdvanced, setCronAdvanced] = useState(false);
  const [cronExpr, setCronExpr] = useState("");
  const [cronDays, setCronDays] = useState<number[]>([1, 2, 3, 4, 5]);
  const [cronHour, setCronHour] = useState(8);
  const [cronMinute, setCronMinute] = useState(0);
  const [cronTz, setCronTz] = useState("");
  const [cronSaving, setCronSaving] = useState(false);

  useEffect(() => {
    listCron().then((r) => setCronJobs(r.cron_jobs || [])).catch(() => {});
  }, []);

  function resetCronForm() {
    setCronForm(false);
    setCronEditId(null);
    setCronName("");
    setCronMessage("");
    setCronAdvanced(false);
    setCronExpr("");
    setCronDays([1, 2, 3, 4, 5]);
    setCronHour(8);
    setCronMinute(0);
    setCronTz("");
  }

  function editCronJob(job: any) {
    setCronEditId(String(job.id));
    setCronName(job.name || "");
    setCronMessage(job.message || "");
    setCronTz(job.tz || "");
    const parsed = parseCronExpr(job.cron_expr || "");
    if (parsed) {
      setCronAdvanced(false);
      setCronHour(parsed.hour);
      setCronMinute(parsed.minute);
      setCronDays(parsed.days);
      setCronExpr("");
    } else {
      setCronAdvanced(true);
      setCronExpr(job.cron_expr || "");
    }
    setCronForm(true);
  }

  async function saveCronJob() {
    setCronSaving(true);
    const expr = cronAdvanced ? cronExpr : buildCronExpr(cronHour, cronMinute, cronDays);
    const payload: any = {
      name: cronName,
      cron_expr: expr,
      message: cronMessage,
      channel: "web",
      payload_kind: "agentturn",
    };
    if (cronTz) payload.tz = cronTz;
    try {
      if (cronEditId) {
        await updateCron(cronEditId, payload);
      } else {
        await createCron(payload);
      }
      const r = await listCron();
      setCronJobs(r.cron_jobs || []);
      resetCronForm();
    } catch {}
    setCronSaving(false);
  }

  async function removeCronJob(id: string) {
    if (Platform.OS === "web") {
      if (!confirm("Delete this scheduled task?")) return;
    } else {
      return new Promise<void>((resolve) => {
        Alert.alert("Delete", "Delete this scheduled task?", [
          { text: "Cancel", style: "cancel", onPress: () => resolve() },
          {
            text: "Delete", style: "destructive",
            onPress: async () => {
              await deleteCron(id).catch(() => {});
              const r = await listCron().catch(() => ({ cron_jobs: [] }));
              setCronJobs(r.cron_jobs || []);
              resolve();
            },
          },
        ]);
      });
    }
    await deleteCron(id).catch(() => {});
    const r = await listCron().catch(() => ({ cron_jobs: [] }));
    setCronJobs(r.cron_jobs || []);
  }

  async function toggleCronJob(id: string, enabled: boolean) {
    setCronJobs((prev) => prev.map((j) => (String(j.id) === id ? { ...j, enabled } : j)));
    await updateCron(id, { enabled }).catch(() => {});
  }

  const canSave = cronName.trim() && cronMessage.trim()
    && (cronAdvanced ? cronExpr.trim() : cronDays.length > 0);

  if (cronForm) {
    return (
      <>
        <Text style={st.desc}>
          {cronEditId ? "Edit scheduled task." : "Create a new scheduled task."}
        </Text>

        {/* Name */}
        <Label text="Name" />
        <TextInput
          style={st.keyInput}
          value={cronName}
          onChangeText={setCronName}
          placeholder="e.g. Daily schedule summary"
          placeholderTextColor={colors.labelTertiary}
        />

        {/* Schedule */}
        <Label text="When" />
        <View style={st.chipRow}>
          <Chip label="Simple" active={!cronAdvanced} color={colors.accent}
            onPress={() => setCronAdvanced(false)} />
          <Chip label="Advanced" active={cronAdvanced} color={colors.accent}
            onPress={() => setCronAdvanced(true)} />
        </View>

        {cronAdvanced ? (
          <>
            <TextInput
              style={[st.keyInput, { marginTop: 8 }]}
              value={cronExpr}
              onChangeText={setCronExpr}
              placeholder="0 8 * * 1,2,3,4,5"
              placeholderTextColor={colors.labelTertiary}
              autoCapitalize="none"
              autoCorrect={false}
            />
            <Text style={{ fontSize: 11, color: colors.labelTertiary, marginTop: 4 }}>
              5-field cron: minute hour day-of-month month day-of-week
            </Text>
          </>
        ) : (
          <>
            {/* Day pills */}
            <View style={[st.chipRow, { marginTop: 8, gap: 4 }]}>
              {DAY_LABELS.map((label, i) => {
                const active = cronDays.includes(i);
                return (
                  <TouchableOpacity
                    key={i}
                    style={[st.dayPill, active && st.dayPillActive]}
                    onPress={() => {
                      setCronDays((prev) =>
                        prev.includes(i) ? prev.filter((d) => d !== i) : [...prev, i]
                      );
                    }}
                    activeOpacity={0.7}
                  >
                    <Text style={[st.dayPillText, active && st.dayPillTextActive]}>
                      {label}
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </View>
            {/* Quick select */}
            <View style={[st.chipRow, { marginTop: 6 }]}>
              <Chip label="Weekdays" active={false} color={colors.labelSecondary}
                onPress={() => setCronDays([1, 2, 3, 4, 5])} />
              <Chip label="Weekends" active={false} color={colors.labelSecondary}
                onPress={() => setCronDays([0, 6])} />
              <Chip label="Every day" active={false} color={colors.labelSecondary}
                onPress={() => setCronDays([0, 1, 2, 3, 4, 5, 6])} />
            </View>
            {/* Time picker */}
            <View style={{ flexDirection: "row", gap: 12, marginTop: 12 }}>
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 11, color: colors.labelTertiary, marginBottom: 4, fontWeight: "600" }}>Hour</Text>
                <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                  <View style={{ flexDirection: "row", gap: 4 }}>
                    {Array.from({ length: 24 }, (_, i) => i).map((h) => (
                      <TouchableOpacity
                        key={h}
                        style={[st.timePill, cronHour === h && st.timePillActive]}
                        onPress={() => setCronHour(h)}
                        activeOpacity={0.7}
                      >
                        <Text style={[st.timePillText, cronHour === h && st.timePillTextActive]}>
                          {h === 0 ? "12a" : h < 12 ? `${h}a` : h === 12 ? "12p" : `${h - 12}p`}
                        </Text>
                      </TouchableOpacity>
                    ))}
                  </View>
                </ScrollView>
              </View>
            </View>
            <View style={{ marginTop: 8 }}>
              <Text style={{ fontSize: 11, color: colors.labelTertiary, marginBottom: 4, fontWeight: "600" }}>Minute</Text>
              <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                <View style={{ flexDirection: "row", gap: 4 }}>
                  {[0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55].map((m) => (
                    <TouchableOpacity
                      key={m}
                      style={[st.timePill, cronMinute === m && st.timePillActive]}
                      onPress={() => setCronMinute(m)}
                      activeOpacity={0.7}
                    >
                      <Text style={[st.timePillText, cronMinute === m && st.timePillTextActive]}>
                        :{String(m).padStart(2, "0")}
                      </Text>
                    </TouchableOpacity>
                  ))}
                </View>
              </ScrollView>
            </View>
            {cronDays.length === 0 && (
              <Text style={{ fontSize: 12, color: colors.danger, marginTop: 6 }}>
                Select at least one day
              </Text>
            )}
          </>
        )}

        {/* Message */}
        <Label text="Message" />
        <TextInput
          style={[st.textArea, { minHeight: 80 }]}
          value={cronMessage}
          onChangeText={setCronMessage}
          placeholder="What should Asta do? e.g. Summarize my calendar events for today"
          placeholderTextColor={colors.labelTertiary}
          multiline
          textAlignVertical="top"
        />

        {/* Timezone */}
        <Label text="Timezone" />
        <ScrollView horizontal showsHorizontalScrollIndicator={false}>
          <View style={{ flexDirection: "row", gap: 4 }}>
            {COMMON_TZ.map((tz) => (
              <TouchableOpacity
                key={tz || "__local"}
                style={[st.chip, cronTz === tz && { backgroundColor: colors.accent + "18", borderColor: colors.accent + "60" }]}
                onPress={() => setCronTz(tz)}
                activeOpacity={0.7}
              >
                <Text style={[st.chipText, cronTz === tz && { color: colors.accent, fontWeight: "700" }]}>
                  {tz ? tz.split("/").pop()!.replace(/_/g, " ") : "Server default"}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        </ScrollView>

        {/* Actions */}
        <View style={{ flexDirection: "row", gap: 8, marginTop: spacing.xl }}>
          <TouchableOpacity
            style={[st.accentBtn, { flex: 1, opacity: canSave ? 1 : 0.4 }]}
            onPress={saveCronJob}
            disabled={!canSave || cronSaving}
            activeOpacity={0.7}
          >
            <Text style={st.accentBtnText}>
              {cronSaving ? "Saving..." : cronEditId ? "Save" : "Create"}
            </Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[st.accentBtn, { flex: 1, backgroundColor: colors.white08 }]}
            onPress={resetCronForm}
            activeOpacity={0.7}
          >
            <Text style={[st.accentBtnText, { color: colors.labelSecondary }]}>Cancel</Text>
          </TouchableOpacity>
        </View>
      </>
    );
  }

  // Job list view
  return (
    <>
      <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: spacing.lg }}>
        <Text style={st.desc}>Scheduled tasks run automatically.</Text>
        <TouchableOpacity
          style={{ flexDirection: "row", alignItems: "center", gap: 4, backgroundColor: colors.accent, borderRadius: radius.md, paddingHorizontal: 12, paddingVertical: 8 }}
          onPress={() => setCronForm(true)}
          activeOpacity={0.7}
        >
          <IconPlus size={14} color="#fff" />
          <Text style={{ fontSize: 13, fontWeight: "600", color: "#fff" }}>Add</Text>
        </TouchableOpacity>
      </View>

      {cronJobs.length === 0 && (
        <Text style={st.emptyText}>No scheduled tasks yet</Text>
      )}

      {cronJobs.map((job) => {
        const parsed = parseCronExpr(job.cron_expr || "");
        return (
          <View key={job.id} style={st.toggleRow}>
            <View style={{ flex: 1, marginRight: 12 }}>
              <View style={{ flexDirection: "row", alignItems: "center", gap: 6, marginBottom: 2 }}>
                <Text style={st.toggleName}>{job.name}</Text>
              </View>
              <Text style={{ fontSize: 12, color: colors.labelSecondary, marginBottom: 2 }}>
                {parsed
                  ? `${fmtDaysList(parsed.days)} at ${fmtTime12(parsed.hour, parsed.minute)}`
                  : job.cron_expr}
              </Text>
              {job.message && (
                <Text style={st.toggleDesc} numberOfLines={1}>{job.message}</Text>
              )}
              <View style={{ flexDirection: "row", gap: 8, marginTop: 6 }}>
                <TouchableOpacity onPress={() => editCronJob(job)} activeOpacity={0.7}>
                  <Text style={{ fontSize: 12, fontWeight: "600", color: colors.accent }}>Edit</Text>
                </TouchableOpacity>
                <TouchableOpacity onPress={() => removeCronJob(String(job.id))} activeOpacity={0.7}>
                  <Text style={{ fontSize: 12, fontWeight: "600", color: colors.danger }}>Delete</Text>
                </TouchableOpacity>
              </View>
            </View>
            <Toggle
              value={!!job.enabled}
              onValueChange={(v) => toggleCronJob(String(job.id), v)}
            />
          </View>
        );
      })}
    </>
  );
}
