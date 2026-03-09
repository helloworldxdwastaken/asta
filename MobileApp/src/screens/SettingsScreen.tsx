import React, { useState, useEffect } from "react";
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet, Alert,
} from "react-native";
import { colors, spacing, radius } from "../theme/colors";
import {
  getDefaultAI, setDefaultAI, getThinking, setThinking,
  getMoodSetting, setMoodSetting, getServerStatus, checkHealth,
} from "../lib/api";
import { clearAuth, getUser } from "../lib/auth";
import type { User } from "../lib/types";

const PROVIDERS = ["claude", "gemini", "openrouter", "ollama"];
const THINKING_LEVELS = ["off", "minimal", "low", "medium", "high", "xhigh"];
const MOODS = ["normal", "friendly", "serious"];

interface Props {
  onLogout: () => void;
}

export default function SettingsScreen({ onLogout }: Props) {
  const [provider, setProvider] = useState("claude");
  const [thinkingLevel, setThinkingLevelState] = useState("off");
  const [mood, setMood] = useState("normal");
  const [user, setUserState] = useState<User | null>(null);
  const [version, setVersion] = useState("");
  const [serverOk, setServerOk] = useState<boolean | null>(null);

  useEffect(() => {
    getDefaultAI().then((r) => setProvider(r.provider || "claude")).catch(() => {});
    getThinking().then((r) => setThinkingLevelState(r.thinking_level || "off")).catch(() => {});
    getMoodSetting().then((r) => setMood(r.mood || "normal")).catch(() => {});
    getUser().then(setUserState);
    checkHealth().then((r) => { setVersion(r.version || ""); setServerOk(true); }).catch(() => setServerOk(false));
  }, []);

  async function handleLogout() {
    Alert.alert("Logout", "Are you sure?", [
      { text: "Cancel", style: "cancel" },
      { text: "Logout", style: "destructive", onPress: async () => { await clearAuth(); onLogout(); } },
    ]);
  }

  function Section({ title, children }: { title: string; children: React.ReactNode }) {
    return (
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>{title}</Text>
        {children}
      </View>
    );
  }

  function ChipRow({ items, selected, onSelect }: { items: string[]; selected: string; onSelect: (v: string) => void }) {
    return (
      <View style={styles.chipRow}>
        {items.map((item) => (
          <TouchableOpacity
            key={item}
            style={[styles.chip, selected === item && styles.chipActive]}
            onPress={() => onSelect(item)}
          >
            <Text style={[styles.chipText, selected === item && styles.chipTextActive]}>
              {item}
            </Text>
          </TouchableOpacity>
        ))}
      </View>
    );
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.pageTitle}>Settings</Text>

      <Section title="AI Provider">
        <ChipRow
          items={PROVIDERS}
          selected={provider}
          onSelect={(v) => { setProvider(v); setDefaultAI(v).catch(() => {}); }}
        />
      </Section>

      <Section title="Thinking Level">
        <ChipRow
          items={THINKING_LEVELS}
          selected={thinkingLevel}
          onSelect={(v) => { setThinkingLevelState(v); setThinking(v).catch(() => {}); }}
        />
      </Section>

      <Section title="Mood">
        <ChipRow
          items={MOODS}
          selected={mood}
          onSelect={(v) => { setMood(v); setMoodSetting(v).catch(() => {}); }}
        />
      </Section>

      <Section title="Server">
        <View style={styles.infoRow}>
          <Text style={styles.infoLabel}>Status</Text>
          <View style={styles.statusRow}>
            <View style={[styles.dot, serverOk ? styles.dotOnline : styles.dotOffline]} />
            <Text style={styles.infoValue}>{serverOk === null ? "Checking..." : serverOk ? "Online" : "Offline"}</Text>
          </View>
        </View>
        {version ? (
          <View style={styles.infoRow}>
            <Text style={styles.infoLabel}>Version</Text>
            <Text style={styles.infoValue}>{version}</Text>
          </View>
        ) : null}
      </Section>

      <Section title="Account">
        {user && (
          <View style={styles.infoRow}>
            <Text style={styles.infoLabel}>User</Text>
            <Text style={styles.infoValue}>{user.username} ({user.role})</Text>
          </View>
        )}
        <TouchableOpacity style={styles.logoutBtn} onPress={handleLogout}>
          <Text style={styles.logoutText}>Logout</Text>
        </TouchableOpacity>
      </Section>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface },
  content: { padding: spacing.lg, paddingBottom: 60 },
  pageTitle: { fontSize: 22, fontWeight: "700", color: colors.label, marginBottom: spacing.xl },
  section: { marginBottom: spacing.xl },
  sectionTitle: {
    fontSize: 11, fontWeight: "700", color: colors.labelTertiary,
    textTransform: "uppercase", letterSpacing: 1, marginBottom: spacing.sm,
  },
  chipRow: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  chip: {
    backgroundColor: colors.white05,
    borderRadius: radius.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: 8,
    borderWidth: 1,
    borderColor: colors.separator,
  },
  chipActive: { backgroundColor: colors.accentSubtle, borderColor: colors.accent },
  chipText: { fontSize: 13, color: colors.labelSecondary, textTransform: "capitalize" },
  chipTextActive: { color: colors.accent, fontWeight: "600" },
  infoRow: {
    flexDirection: "row", justifyContent: "space-between", alignItems: "center",
    paddingVertical: spacing.sm,
  },
  infoLabel: { fontSize: 14, color: colors.labelSecondary },
  infoValue: { fontSize: 14, color: colors.label },
  statusRow: { flexDirection: "row", alignItems: "center", gap: 6 },
  dot: { width: 8, height: 8, borderRadius: 4 },
  dotOnline: { backgroundColor: colors.success },
  dotOffline: { backgroundColor: colors.danger },
  logoutBtn: {
    backgroundColor: "rgba(255,59,48,0.1)",
    borderRadius: radius.md,
    paddingVertical: 12,
    alignItems: "center",
    marginTop: spacing.md,
  },
  logoutText: { color: colors.danger, fontSize: 15, fontWeight: "600" },
});
