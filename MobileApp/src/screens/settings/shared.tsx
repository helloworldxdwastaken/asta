import React from "react";
import { View, Text, TouchableOpacity, StyleSheet, Platform } from "react-native";
import { colors, spacing, radius } from "../../theme/colors";

/* ── Shared prop types ───────────────────────────── */

export interface TabProps {
  admin: boolean;
}

export interface GeneralTabProps extends TabProps {
  provider: string;
  thinkingLevel: string;
  mood: string;
  onProviderChange: (p: string) => void;
  onThinkingChange: (t: string) => void;
  onMoodChange: (m: string) => void;
}

export interface ConnectionTabProps extends TabProps {
  serverOk: boolean | null;
  serverVersion: string;
  setServerOk: (v: boolean) => void;
}

export interface AboutTabProps extends TabProps {
  serverOk: boolean | null;
  serverVersion: string;
  serverStatus: any;
  usage: any;
}

export interface GoogleTabProps extends TabProps {
  keyStatus: Record<string, boolean>;
  setKeyStatus: (v: Record<string, boolean>) => void;
}

/* ── Constants ───────────────────────────────────── */

export const PROVIDERS = [
  { key: "claude", label: "Claude", color: "#D97757" },
  { key: "gemini", label: "Gemini", color: "#4285F4" },
  { key: "openrouter", label: "OpenRouter", color: "#6366F1" },
  { key: "ollama", label: "Local", color: "#34C759" },
];

export const THINKING_LEVELS = ["off", "minimal", "low", "medium", "high", "xhigh"];
export const MOODS = ["normal", "friendly", "serious"];

export const KEY_FIELDS = [
  { key: "anthropic_api_key",   label: "Anthropic (Claude)", ph: "sk-ant-..." },
  { key: "openai_api_key",      label: "OpenAI",             ph: "sk-..." },
  { key: "openrouter_api_key",  label: "OpenRouter",         ph: "sk-or-..." },
  { key: "gemini_api_key",      label: "Google / Gemini",    ph: "AIza..." },
  { key: "groq_api_key",        label: "Groq",               ph: "gsk_..." },
  { key: "huggingface_api_key", label: "HuggingFace",        ph: "hf_..." },
  { key: "giphy_api_key",       label: "Giphy",              ph: "" },
  { key: "notion_api_key",      label: "Notion",             ph: "ntn_..." },
  { key: "pexels_api_key",     label: "Pexels",             ph: "" },
  { key: "pixabay_api_key",    label: "Pixabay",            ph: "" },
  { key: "youtube_api_key",    label: "YouTube",            ph: "AIza..." },
  { key: "github_token",       label: "GitHub",             ph: "ghp_..." },
];

/* ── Tiny shared components ─────────────────────── */

export function Label({ text }: { text: string }) {
  return <Text style={st.label}>{text}</Text>;
}

export function Chip({ label, active, color, onPress }: { label: string; active: boolean; color: string; onPress: () => void }) {
  return (
    <TouchableOpacity
      style={[st.chip, active && { backgroundColor: color + "18", borderColor: color + "60" }]}
      onPress={onPress} activeOpacity={0.7}
    >
      <Text style={[st.chipText, active && { color, fontWeight: "700" }]}>{label}</Text>
    </TouchableOpacity>
  );
}

export function CardRow({ label, value, valueColor }: { label: string; value: string; valueColor?: string }) {
  return (
    <View style={st.cardRow}>
      <Text style={st.cardLabel}>{label}</Text>
      <Text style={[st.cardVal, valueColor ? { color: valueColor } : null]}>{value}</Text>
    </View>
  );
}

/* ── Styles (shared across tabs) ────────────────── */

export const st = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface },
  dragHandle: {
    width: 36, height: 4, borderRadius: 2,
    backgroundColor: colors.white10,
    alignSelf: "center", marginTop: 8, marginBottom: 4,
  },

  /* Header */
  header: {
    flexDirection: "row", alignItems: "center", justifyContent: "space-between",
    paddingHorizontal: spacing.md, paddingVertical: 12,
  },
  headerBack: { width: 32, alignItems: "flex-start" },
  headerTitle: { fontSize: 17, fontWeight: "700", color: colors.label },

  /* Menu list (tab list) */
  menuScroll: { flex: 1 },
  userCard: {
    flexDirection: "row", alignItems: "center", gap: 12,
    margin: spacing.lg, marginBottom: spacing.md,
    backgroundColor: colors.surfaceRaised,
    borderRadius: radius.lg, padding: spacing.lg,
    borderWidth: 1, borderColor: colors.separator,
  },
  userAvatar: {
    width: 44, height: 44, borderRadius: 22,
    backgroundColor: colors.accent,
    alignItems: "center", justifyContent: "center",
  },
  userAvatarLetter: { color: "#fff", fontSize: 18, fontWeight: "700" },
  userName: { fontSize: 16, fontWeight: "700", color: colors.label, marginBottom: 2 },
  userRoleBadge: {
    alignSelf: "flex-start",
    backgroundColor: colors.accentSubtle,
    paddingHorizontal: 8, paddingVertical: 1,
    borderRadius: radius.full,
  },
  userRoleText: { fontSize: 10, fontWeight: "700", color: colors.accent, textTransform: "uppercase" },
  statusDotWrap: { paddingRight: 2 },

  menuSectionLabel: {
    fontSize: 11, fontWeight: "700", color: colors.labelTertiary,
    textTransform: "uppercase", letterSpacing: 1.2,
    marginLeft: spacing.lg, marginBottom: spacing.sm, marginTop: spacing.sm,
  },
  menuRow: {
    flexDirection: "row", alignItems: "center",
    paddingVertical: 14, paddingHorizontal: spacing.lg,
    marginHorizontal: spacing.md, marginBottom: 2,
    borderRadius: radius.md,
    backgroundColor: colors.surfaceRaised,
    borderWidth: 1, borderColor: colors.separator,
  },
  menuIconWrap: {
    width: 32, height: 32, borderRadius: 8,
    backgroundColor: colors.white05,
    alignItems: "center", justifyContent: "center",
    marginRight: 12,
  },
  menuLabel: { flex: 1, fontSize: 15, fontWeight: "600", color: colors.label },
  logoutRow: {
    marginHorizontal: spacing.md, marginTop: spacing.xl,
    paddingVertical: 14, borderRadius: radius.md,
    backgroundColor: "rgba(255,59,48,0.06)",
    borderWidth: 1, borderColor: "rgba(255,59,48,0.12)",
    alignItems: "center",
  },
  logoutText: { fontSize: 15, fontWeight: "600", color: colors.danger },
  versionText: {
    fontSize: 11, color: colors.labelTertiary, textAlign: "center",
    marginTop: spacing.lg,
  },

  /* Tab content */
  tabContent: { padding: spacing.lg },

  /* Shared */
  label: {
    fontSize: 11, fontWeight: "700", color: colors.labelTertiary,
    textTransform: "uppercase", letterSpacing: 1.2,
    marginTop: spacing.xl, marginBottom: spacing.sm,
  },
  desc: { fontSize: 14, color: colors.labelSecondary, lineHeight: 20, marginBottom: spacing.lg },
  emptyText: { fontSize: 14, color: colors.labelTertiary, textAlign: "center", paddingVertical: 40 },

  /* Radio rows */
  radioRow: {
    flexDirection: "row", justifyContent: "space-between", alignItems: "center",
    backgroundColor: colors.surfaceRaised,
    borderRadius: radius.md, paddingHorizontal: 16, paddingVertical: 14,
    marginBottom: 4, borderWidth: 1, borderColor: colors.separator,
  },
  radioRowActive: { borderColor: colors.accent + "40" },
  provDot: { width: 10, height: 10, borderRadius: 5 },
  radioText: { fontSize: 15, fontWeight: "500", color: colors.labelSecondary },
  radioTextActive: { color: colors.label, fontWeight: "600" },
  radio: {
    width: 22, height: 22, borderRadius: 11,
    borderWidth: 2, borderColor: "rgba(255,255,255,0.12)",
    alignItems: "center", justifyContent: "center",
  },
  radioActive: { borderColor: colors.accent },
  radioFill: { width: 12, height: 12, borderRadius: 6, backgroundColor: colors.accent },

  /* Chips */
  chipRow: { flexDirection: "row", flexWrap: "wrap", gap: 6 },
  chip: {
    backgroundColor: colors.white05,
    borderRadius: radius.sm,
    paddingHorizontal: 14, paddingVertical: 8,
    borderWidth: 1, borderColor: colors.separator,
  },
  chipText: { fontSize: 13, fontWeight: "500", color: colors.labelSecondary, textTransform: "capitalize" },

  /* Card */
  card: {
    backgroundColor: colors.surfaceRaised,
    borderRadius: radius.md, borderWidth: 1, borderColor: colors.separator,
    overflow: "hidden",
  },
  cardRow: {
    flexDirection: "row", justifyContent: "space-between", alignItems: "center",
    paddingHorizontal: 16, paddingVertical: 13,
    borderBottomWidth: 1, borderBottomColor: colors.separator,
  },
  cardLabel: { fontSize: 14, color: colors.labelSecondary },
  cardVal: { fontSize: 14, fontWeight: "500", color: colors.label },

  /* Keys */
  keyBlock: { marginBottom: 16 },
  keyHead: { flexDirection: "row", alignItems: "center", gap: 6, marginBottom: 6 },
  keyName: { fontSize: 13, fontWeight: "600", color: colors.label },
  keyDot: { width: 6, height: 6, borderRadius: 3 },
  keyRow: { flexDirection: "row", gap: 8 },
  keyInput: {
    flex: 1,
    backgroundColor: colors.white05, borderWidth: 1, borderColor: colors.separator,
    borderRadius: radius.sm, paddingHorizontal: 12, paddingVertical: 11,
    fontSize: 13, color: colors.label,
    fontFamily: Platform.OS === "ios" ? "Menlo" : "monospace",
  },
  keyShowBtn: {
    backgroundColor: colors.white05, borderWidth: 1, borderColor: colors.separator,
    borderRadius: radius.sm, paddingHorizontal: 12, justifyContent: "center",
  },
  keyShowText: { fontSize: 11, fontWeight: "600", color: colors.labelTertiary },

  /* Toggle rows */
  toggleRow: {
    flexDirection: "row", justifyContent: "space-between", alignItems: "center",
    backgroundColor: colors.surfaceRaised, borderRadius: radius.md,
    padding: 16, marginBottom: 4,
    borderWidth: 1, borderColor: colors.separator,
  },
  toggleName: { fontSize: 14, fontWeight: "600", color: colors.label },
  toggleDesc: { fontSize: 12, color: colors.labelTertiary, marginTop: 2 },

  /* Text area */
  textArea: {
    backgroundColor: colors.surfaceRaised, borderWidth: 1, borderColor: colors.separator,
    borderRadius: radius.md, padding: 14,
    fontSize: 13, color: colors.label, lineHeight: 20,
    minHeight: 220, marginTop: 8,
    fontFamily: Platform.OS === "ios" ? "Menlo" : "monospace",
  },

  /* Accent button */
  accentBtn: {
    flexDirection: "row", justifyContent: "center",
    backgroundColor: colors.accent, borderRadius: radius.md,
    paddingVertical: 14, alignItems: "center", marginTop: 12, gap: 4,
  },
  accentBtnText: { color: "#fff", fontSize: 14, fontWeight: "700" },

  /* About */
  aboutLogo: {
    marginBottom: 12,
    shadowColor: colors.accent,
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.15,
    shadowRadius: 32,
    elevation: 10,
  },

  /* Cron */
  dayPill: {
    width: 38, height: 38,
    borderRadius: 19,
    backgroundColor: colors.white05,
    borderWidth: 1, borderColor: colors.separator,
    alignItems: "center", justifyContent: "center",
  },
  dayPillActive: {
    backgroundColor: colors.accentSubtle,
    borderColor: colors.accent,
  },
  dayPillText: {
    fontSize: 11, fontWeight: "600",
    color: colors.labelTertiary,
  },
  dayPillTextActive: {
    color: colors.accent,
  },
  timePill: {
    paddingHorizontal: 10, paddingVertical: 6,
    borderRadius: radius.sm,
    backgroundColor: colors.white05,
    borderWidth: 1, borderColor: colors.separator,
  },
  timePillActive: {
    backgroundColor: colors.accentSubtle,
    borderColor: colors.accent,
  },
  timePillText: {
    fontSize: 12, fontWeight: "600",
    color: colors.labelSecondary,
  },
  timePillTextActive: {
    color: colors.accent,
  },

  /* Agent form */
  fieldLabel: {
    fontSize: 12, fontWeight: "700", color: colors.labelSecondary,
    textTransform: "uppercase", letterSpacing: 0.8,
    marginTop: 8, marginBottom: 6,
  },
  sectionTitle: { fontSize: 17, fontWeight: "700", color: colors.label },
  input: {
    backgroundColor: colors.surfaceRaised, borderWidth: 1, borderColor: colors.separator,
    borderRadius: radius.sm, paddingHorizontal: 12, paddingVertical: 11,
    fontSize: 14, color: colors.label, marginBottom: 4,
  },
  switchRow: {
    flexDirection: "row", alignItems: "center", justifyContent: "space-between",
    backgroundColor: colors.surfaceRaised, borderRadius: radius.sm,
    paddingHorizontal: 16, paddingVertical: 12,
    borderWidth: 1, borderColor: colors.separator,
  },
  switchLabel: { fontSize: 14, fontWeight: "500", color: colors.label },

  /* Agent cards */
  agentCardOuter: {
    backgroundColor: colors.surfaceRaised, borderRadius: radius.lg,
    borderWidth: 1, borderColor: colors.separator,
    padding: 16, marginBottom: 6,
  },
  agentCardTop: {
    flexDirection: "row", alignItems: "center", gap: 12,
  },
  agentAvatar: {
    width: 40, height: 40, borderRadius: 12,
    alignItems: "center", justifyContent: "center",
  },
  agentCardFooter: {
    flexDirection: "row", alignItems: "center", justifyContent: "space-between",
    marginTop: 10, paddingTop: 10,
    borderTopWidth: 1, borderTopColor: "rgba(255,255,255,0.04)",
  },
  agentBadge: {
    borderRadius: 9999,
    paddingHorizontal: 8, paddingVertical: 2,
  },
  agentBadgeText: { fontSize: 10, fontWeight: "700" },
});
