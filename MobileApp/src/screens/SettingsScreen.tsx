import React, { useState, useEffect } from "react";
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet, Alert, Platform,
  Switch, TextInput, Image,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { colors, spacing, radius } from "../theme/colors";
import {
  getDefaultAI, setDefaultAI, getThinking, setThinking,
  getMoodSetting, setMoodSetting, getServerStatus, checkHealth,
  getKeyStatus, setKeys, getUsage, getSkills, toggleSkill,
  listAgents, createAgent, updateAgent, deleteAgent, toggleAgent, getPersona, setPersona,
  getTelegramUsername, setTelegramUsername, getPingram, setPingram, testPingramCall,
  getSecurityAudit,
  getBackendUrl, setBackendUrl,
  listCron, createCron, updateCron, deleteCron,
  listUsers, createUser, deleteUser, resetUserPassword,
  ragStatus, ragLearned, getMemoryHealth, ragDeleteTopic,
  getModels, getAvailableModels, setModel,
  getReasoning, setReasoning as setReasoningApi,
  getFinalMode, setFinalMode as setFinalModeApi,
  getVision, setVision as setVisionApi,
} from "../lib/api";
import { clearAuth, getUser, isAdmin } from "../lib/auth";
import type { User, Agent } from "../lib/types";
import {
  IconChevronLeft, IconChevronRight, IconBrain, IconUser, IconServer,
  IconKey, IconWifi, IconWifiOff, IconPuzzle, IconAgents, IconSend,
  IconInfo, IconSettings, IconPerson, IconClock, IconPlus, IconTrash,
  IconWarning, IconCheck, IconEdit, IconLink,
  resolveAgentIcon,
} from "../components/Icons";

/* ── Tab definitions ──────────────────────────────── */

type TabId = "general" | "keys" | "models" | "skills" | "agents" | "persona" | "channels" | "cron" | "users" | "knowledge" | "permissions" | "connection" | "about";

interface TabDef {
  id: TabId;
  label: string;
  Icon: (props: { size?: number; color?: string }) => React.ReactElement;
  adminOnly: boolean;
}

const TABS: TabDef[] = [
  { id: "general",    label: "General",    Icon: IconSettings,  adminOnly: false },
  { id: "keys",       label: "API Keys",   Icon: IconKey,       adminOnly: true },
  { id: "models",     label: "Models",     Icon: IconServer,    adminOnly: true },
  { id: "agents",     label: "Agents",     Icon: IconAgents,    adminOnly: true },
  { id: "skills",     label: "Skills",     Icon: IconPuzzle,    adminOnly: true },
  { id: "persona",    label: "Persona",    Icon: IconPerson,    adminOnly: false },
  { id: "channels",   label: "Channels",   Icon: IconSend,      adminOnly: true },
  { id: "cron",       label: "Schedule",   Icon: IconClock,     adminOnly: true },
  { id: "users",      label: "Users",      Icon: IconUser,      adminOnly: true },
  { id: "knowledge",  label: "Knowledge",  Icon: IconBrain,     adminOnly: true },
  { id: "permissions", label: "Permissions", Icon: IconWarning, adminOnly: true },
  { id: "connection", label: "Connection", Icon: IconServer,    adminOnly: true },
  { id: "about",      label: "About",      Icon: IconInfo,      adminOnly: false },
];

/* ── Constants ────────────────────────────────────── */

const PROVIDERS = [
  { key: "claude", label: "Claude", color: "#D97757" },
  { key: "gemini", label: "Gemini", color: "#4285F4" },
  { key: "openrouter", label: "OpenRouter", color: "#6366F1" },
  { key: "ollama", label: "Local", color: "#34C759" },
];
const THINKING_LEVELS = ["off", "minimal", "low", "medium", "high", "xhigh"];
const MOODS = ["normal", "friendly", "serious"];

const KEY_FIELDS = [
  { key: "anthropic_api_key",   label: "Anthropic (Claude)", ph: "sk-ant-..." },
  { key: "openai_api_key",      label: "OpenAI",             ph: "sk-..." },
  { key: "openrouter_api_key",  label: "OpenRouter",         ph: "sk-or-..." },
  { key: "gemini_api_key",      label: "Google / Gemini",    ph: "AIza..." },
  { key: "groq_api_key",        label: "Groq",               ph: "gsk_..." },
  { key: "huggingface_api_key", label: "HuggingFace",        ph: "hf_..." },
  { key: "giphy_api_key",       label: "Giphy",              ph: "" },
  { key: "notion_api_key",      label: "Notion",             ph: "ntn_..." },
];

/* ── Props ────────────────────────────────────────── */

interface Props {
  onBack: () => void;
  onLogout: () => void;
  provider: string;
  thinkingLevel: string;
  mood: string;
  onProviderChange: (p: string) => void;
  onThinkingChange: (t: string) => void;
  onMoodChange: (m: string) => void;
}

export default function SettingsScreen({
  onBack, onLogout, provider, thinkingLevel, mood,
  onProviderChange, onThinkingChange, onMoodChange,
}: Props) {
  const insets = useSafeAreaInsets();
  const [activeTab, setActiveTab] = useState<TabId | null>(null);
  const [admin, setAdmin] = useState(false);
  const [user, setUserState] = useState<User | null>(null);

  const [serverVersion, setServerVersion] = useState("");
  const [serverOk, setServerOk] = useState<boolean | null>(null);
  const [serverStatus, setServerStatus] = useState<any>(null);
  const [usage, setUsage] = useState<any>(null);
  const [keyStatus, setKeyStatusState] = useState<Record<string, boolean>>({});
  const [keyInputs, setKeyInputs] = useState<Record<string, string>>({});
  const [keyVis, setKeyVis] = useState<Record<string, boolean>>({});
  const [keySaving, setKeySaving] = useState(false);
  const [keySaved, setKeySaved] = useState(false);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [skills, setSkills] = useState<any[]>([]);
  const [persona, setPersonaState] = useState({ soul: "", user_soul: "", user: "" });
  const [personaTab, setPersonaTab] = useState<"soul" | "user_soul" | "user">("user");
  const [personaSaving, setPersonaSaving] = useState(false);
  const [backendUrl, setBackendUrlState] = useState("");
  const [connSaving, setConnSaving] = useState(false);

  // Cron state
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

  // Users state
  const [usersList, setUsersList] = useState<any[]>([]);
  const [showAddUser, setShowAddUser] = useState(false);
  const [newUsername, setNewUsername] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newRole, setNewRole] = useState<"user" | "admin">("user");
  const [userSaving, setUserSaving] = useState(false);
  const [userError, setUserError] = useState("");
  const [resetPwId, setResetPwId] = useState<string | null>(null);
  const [resetPwVal, setResetPwVal] = useState("");

  // Models state
  const [models, setModels] = useState<Record<string, string>>({});
  const [availableModels, setAvailableModels] = useState<Record<string, string[]>>({});
  const [modelSaving, setModelSaving] = useState<string | null>(null);

  // Advanced settings (admin)
  const [reasoningMode, setReasoningMode] = useState("off");
  const [finalMode, setFinalMode] = useState("off");
  const [visionEnabled, setVisionEnabled] = useState(true);

  // Knowledge state
  const [ragInfo, setRagInfo] = useState<any>(null);
  const [ragTopics, setRagTopics] = useState<any[]>([]);
  const [memHealth, setMemHealth] = useState<any>(null);

  useEffect(() => {
    getUser().then(setUserState);
    isAdmin().then(setAdmin);
    checkHealth().then((r) => { setServerVersion(r.version || ""); setServerOk(true); }).catch(() => setServerOk(false));
    getServerStatus().then(setServerStatus).catch(() => {});
    getUsage().then(setUsage).catch(() => {});
    getKeyStatus().then(setKeyStatusState).catch(() => {});
    listAgents().then((r) => setAgents(r.agents || [])).catch(() => {});
    getSkills().then((r) => setSkills(r.skills || r || [])).catch(() => {});
    getPersona().then((r) => setPersonaState({ soul: r.soul || "", user_soul: r.user_soul || "", user: r.user || "" })).catch(() => {});
    getBackendUrl().then(setBackendUrlState);
    listCron().then((r) => setCronJobs(r.cron_jobs || [])).catch(() => {});
    listUsers().then((r) => setUsersList(r.users || [])).catch(() => {});
    getModels().then((r) => setModels(r.models || r || {})).catch(() => {});
    getAvailableModels().then((r) => setAvailableModels(r.models || r || {})).catch(() => {});
    ragStatus().then(setRagInfo).catch(() => {});
    ragLearned().then((r) => setRagTopics(r.topics || r.learned || [])).catch(() => {});
    getMemoryHealth().then(setMemHealth).catch(() => {});
    getReasoning().then((r) => setReasoningMode(r.reasoning_mode || "off")).catch(() => {});
    getFinalMode().then((r) => setFinalMode(r.final_mode || "off")).catch(() => {});
    getVision().then((r) => setVisionEnabled(r.preprocess !== false)).catch(() => {});
  }, []);

  const visibleTabs = TABS.filter((t) => !t.adminOnly || admin);

  function doLogout() {
    if (Platform.OS === "web") { if (confirm("Sign out?")) clearAuth().then(onLogout); return; }
    Alert.alert("Sign Out", "Are you sure?", [
      { text: "Cancel", style: "cancel" },
      { text: "Sign Out", style: "destructive", onPress: () => clearAuth().then(onLogout) },
    ]);
  }

  async function saveKeys() {
    setKeySaving(true);
    const toSave: Record<string, string> = {};
    for (const f of KEY_FIELDS) { if (keyInputs[f.key]) toSave[f.key] = keyInputs[f.key]; }
    await setKeys(toSave).catch(() => {});
    setKeySaving(false); setKeySaved(true);
    getKeyStatus().then(setKeyStatusState).catch(() => {});
    setTimeout(() => setKeySaved(false), 2000);
  }

  async function savePersona() {
    setPersonaSaving(true);
    await setPersona(persona).catch(() => {});
    setPersonaSaving(false);
  }

  async function saveConnection() {
    setConnSaving(true);
    await setBackendUrl(backendUrl);
    checkHealth().then(() => setServerOk(true)).catch(() => setServerOk(false));
    setConnSaving(false);
  }

  /* ─────── Tab list view (no tab selected) ─────── */

  if (activeTab === null) {
    return (
      <View style={[st.container, { paddingTop: insets.top }]}>
        <View style={st.header}>
          <TouchableOpacity onPress={onBack} activeOpacity={0.7} style={st.headerBack}>
            <IconChevronLeft size={22} color={colors.accent} />
          </TouchableOpacity>
          <Text style={st.headerTitle}>Settings</Text>
          <View style={{ width: 32 }} />
        </View>

        <ScrollView style={st.menuScroll} contentContainerStyle={{ paddingBottom: insets.bottom + 40 }}>
          {/* User card */}
          {user && (
            <View style={st.userCard}>
              <View style={st.userAvatar}>
                <Text style={st.userAvatarLetter}>{user.username?.[0]?.toUpperCase() || "?"}</Text>
              </View>
              <View style={{ flex: 1 }}>
                <Text style={st.userName}>{user.username}</Text>
                <View style={st.userRoleBadge}>
                  <Text style={st.userRoleText}>{user.role}</Text>
                </View>
              </View>
              <View style={st.statusDotWrap}>
                {serverOk ? <IconWifi size={14} /> : <IconWifiOff size={14} />}
              </View>
            </View>
          )}

          {/* Tab list */}
          <Text style={st.menuSectionLabel}>Settings</Text>
          {visibleTabs.map((tab) => (
            <TouchableOpacity
              key={tab.id}
              style={st.menuRow}
              onPress={() => setActiveTab(tab.id)}
              activeOpacity={0.7}
            >
              <View style={st.menuIconWrap}>
                <tab.Icon size={18} color={colors.labelSecondary} />
              </View>
              <Text style={st.menuLabel}>{tab.label}</Text>
              <IconChevronRight size={16} color={colors.labelTertiary} />
            </TouchableOpacity>
          ))}

          {/* Logout */}
          <TouchableOpacity style={st.logoutRow} onPress={doLogout} activeOpacity={0.7}>
            <Text style={st.logoutText}>Sign Out</Text>
          </TouchableOpacity>

          {/* Version */}
          {serverVersion ? (
            <Text style={st.versionText}>Server {serverVersion}</Text>
          ) : null}
        </ScrollView>
      </View>
    );
  }

  /* ─────── Tab content view (tab selected) ─────── */

  const currentTab = TABS.find((t) => t.id === activeTab)!;

  return (
    <View style={[st.container, { paddingTop: insets.top }]}>
      {/* Header with back to tab list */}
      <View style={st.header}>
        <TouchableOpacity onPress={() => setActiveTab(null)} activeOpacity={0.7} style={st.headerBack}>
          <IconChevronLeft size={22} color={colors.accent} />
        </TouchableOpacity>
        <Text style={st.headerTitle}>{currentTab.label}</Text>
        <View style={{ width: 32 }} />
      </View>

      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={[st.tabContent, { paddingBottom: insets.bottom + 40 }]}
        key={activeTab}
      >
        {activeTab === "general" && <TabGeneral />}
        {activeTab === "keys" && <TabKeys />}
        {activeTab === "models" && <TabModels />}
        {activeTab === "agents" && <TabAgents />}
        {activeTab === "skills" && <TabSkills />}
        {activeTab === "persona" && <TabPersona />}
        {activeTab === "channels" && <TabChannels />}
        {activeTab === "cron" && <TabCron />}
        {activeTab === "users" && <TabUsers />}
        {activeTab === "knowledge" && <TabKnowledge />}
        {activeTab === "permissions" && <TabPermissions />}
        {activeTab === "connection" && <TabConnection />}
        {activeTab === "about" && <TabAbout />}
      </ScrollView>
    </View>
  );

  /* ─────── Tab: General ─────── */
  function TabGeneral() {
    return (
      <>
        <Label text="AI Provider" />
        {PROVIDERS.map((p) => (
          <TouchableOpacity
            key={p.key}
            style={[st.radioRow, provider === p.key && st.radioRowActive]}
            onPress={() => { onProviderChange(p.key); setDefaultAI(p.key).catch(() => {}); }}
            activeOpacity={0.7}
          >
            <View style={{ flexDirection: "row", alignItems: "center", gap: 10 }}>
              <View style={[st.provDot, { backgroundColor: p.color }]} />
              <Text style={[st.radioText, provider === p.key && st.radioTextActive]}>{p.label}</Text>
            </View>
            <View style={[st.radio, provider === p.key && st.radioActive]}>
              {provider === p.key && <View style={st.radioFill} />}
            </View>
          </TouchableOpacity>
        ))}

        <Label text="Thinking Level" />
        <View style={st.chipRow}>
          {THINKING_LEVELS.map((t) => (
            <Chip key={t} label={t === "xhigh" ? "max" : t}
              active={thinkingLevel === t} color={colors.violet}
              onPress={() => { onThinkingChange(t); setThinking(t).catch(() => {}); }}
            />
          ))}
        </View>

        <Label text="Mood" />
        <View style={st.chipRow}>
          {MOODS.map((m) => (
            <Chip key={m} label={m} active={mood === m} color={colors.accent}
              onPress={() => { onMoodChange(m); setMoodSetting(m).catch(() => {}); }}
            />
          ))}
        </View>

        {admin && (
          <>
            <Label text="Reasoning Mode" />
            <View style={st.chipRow}>
              {["off", "on"].map((v) => (
                <Chip key={v} label={v} active={reasoningMode === v} color={colors.accent}
                  onPress={() => { setReasoningMode(v); setReasoningApi(v).catch(() => {}); }}
                />
              ))}
            </View>

            <Label text="Final Mode" />
            <View style={st.chipRow}>
              {["off", "strict"].map((v) => (
                <Chip key={v} label={v} active={finalMode === v} color={colors.accent}
                  onPress={() => { setFinalMode(v); setFinalModeApi(v).catch(() => {}); }}
                />
              ))}
            </View>

            <Label text="Vision / Image Understanding" />
            <View style={st.switchRow}>
              <Text style={st.switchLabel}>{visionEnabled ? "Enabled" : "Disabled"}</Text>
              <Switch
                value={visionEnabled}
                onValueChange={(v) => { setVisionEnabled(v); setVisionApi({ preprocess: v }).catch(() => {}); }}
                trackColor={{ false: colors.white10, true: colors.accent }}
                thumbColor="#fff"
              />
            </View>
          </>
        )}
      </>
    );
  }

  /* ─────── Tab: API Keys ─────── */
  function TabKeys() {
    return (
      <>
        <Text style={st.desc}>Manage API keys for AI providers and services.</Text>
        {KEY_FIELDS.map((f) => {
          const isSet = keyStatus[f.key];
          return (
            <View key={f.key} style={st.keyBlock}>
              <View style={st.keyHead}>
                <Text style={st.keyName}>{f.label}</Text>
                <View style={[st.keyDot, { backgroundColor: isSet ? colors.success : "rgba(255,255,255,0.12)" }]} />
                <Text style={{ fontSize: 11, fontWeight: "600", color: isSet ? colors.success : colors.labelTertiary }}>
                  {isSet ? "Active" : "Not set"}
                </Text>
              </View>
              <View style={st.keyRow}>
                <TextInput
                  style={st.keyInput}
                  value={keyInputs[f.key] || ""}
                  onChangeText={(v) => setKeyInputs({ ...keyInputs, [f.key]: v })}
                  placeholder={isSet ? "Leave blank to keep" : f.ph || "Enter key..."}
                  placeholderTextColor={colors.labelTertiary}
                  secureTextEntry={!keyVis[f.key]}
                  autoCapitalize="none" autoCorrect={false}
                />
                <TouchableOpacity style={st.keyShowBtn}
                  onPress={() => setKeyVis({ ...keyVis, [f.key]: !keyVis[f.key] })}>
                  <Text style={st.keyShowText}>{keyVis[f.key] ? "Hide" : "Show"}</Text>
                </TouchableOpacity>
              </View>
            </View>
          );
        })}
        <TouchableOpacity style={st.accentBtn} onPress={saveKeys} disabled={keySaving} activeOpacity={0.7}>
          <Text style={st.accentBtnText}>{keySaved ? "Saved!" : keySaving ? "Saving..." : "Save Keys"}</Text>
        </TouchableOpacity>
      </>
    );
  }

  /* ─────── Tab: Models ─────── */

  const MODEL_PROVIDERS = ["claude", "gemini", "openrouter", "ollama"];

  async function handleSetModel(prov: string, model: string) {
    setModelSaving(prov);
    setModels((prev) => ({ ...prev, [prov]: model }));
    await setModel(prov, model).catch(() => {});
    setModelSaving(null);
  }

  function TabModels() {
    return (
      <>
        <Text style={st.desc}>Select which model each provider uses.</Text>
        {MODEL_PROVIDERS.map((prov) => {
          const current = models[prov] || "";
          const available = availableModels[prov] || [];
          const provLabel = prov === "claude" ? "Claude" : prov === "gemini" ? "Gemini" : prov === "openrouter" ? "OpenRouter" : "Ollama";
          const provColor = PROVIDERS.find((p) => p.key === prov)?.color || colors.labelSecondary;

          return (
            <View key={prov} style={{ marginBottom: 16 }}>
              <View style={{ flexDirection: "row", alignItems: "center", gap: 8, marginBottom: 6 }}>
                <View style={[st.provDot, { backgroundColor: provColor }]} />
                <Text style={{ fontSize: 14, fontWeight: "600", color: colors.label }}>{provLabel}</Text>
                {modelSaving === prov && <Text style={{ fontSize: 11, color: colors.accent }}>Saving...</Text>}
              </View>
              {available.length > 0 ? (
                <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                  <View style={{ flexDirection: "row", gap: 4 }}>
                    {available.map((m) => (
                      <TouchableOpacity
                        key={m}
                        style={[st.chip, current === m && { backgroundColor: provColor + "18", borderColor: provColor + "60" }]}
                        onPress={() => handleSetModel(prov, m)}
                        activeOpacity={0.7}
                      >
                        <Text style={[st.chipText, current === m && { color: provColor, fontWeight: "700" }]} numberOfLines={1}>
                          {m.replace(/^(claude-|gemini-|models\/)/, "")}
                        </Text>
                      </TouchableOpacity>
                    ))}
                  </View>
                </ScrollView>
              ) : (
                <TextInput
                  style={st.keyInput}
                  value={current}
                  onChangeText={(v) => setModels((prev) => ({ ...prev, [prov]: v }))}
                  onBlur={() => { if (current) handleSetModel(prov, current); }}
                  placeholder="Model name..."
                  placeholderTextColor={colors.labelTertiary}
                  autoCapitalize="none"
                  autoCorrect={false}
                />
              )}
              {current ? (
                <Text style={{ fontSize: 11, color: colors.labelTertiary, marginTop: 4 }}>
                  Current: {current}
                </Text>
              ) : null}
            </View>
          );
        })}
      </>
    );
  }

  /* ─────── Tab: Agents ─────── */

  const AGENT_CATEGORIES = [
    "Marketing", "Research", "Engineering", "Data", "Knowledge",
    "Operations", "Sales", "Support", "Design", "General",
  ];

  const AGENT_ICONS = [
    "\uD83E\uDD16", "\uD83E\uDDD1\u200D\uD83D\uDCBB", "\uD83D\uDD0D", "\uD83D\uDCCA", "\u270D\uFE0F", "\uD83C\uDFAF", "\uD83D\uDE80", "\uD83E\uDDE0",
    "\uD83D\uDCA1", "\uD83D\uDCDD", "\uD83D\uDCC8", "\uD83D\uDD27", "\uD83C\uDF10", "\uD83D\uDCE7", "\uD83C\uDFA8", "\uD83D\uDEE1\uFE0F",
    "\u2699\uFE0F", "\uD83D\uDCDA", "\uD83D\uDCBC", "\uD83C\uDF1F", "\uD83E\uDD1D", "\uD83D\uDCAC", "\uD83D\uDCC1", "\uD83E\uDDEA",
  ];

  const AGENT_TEMPLATES = [
    { name: "Competitor Analyst", category: "Research", icon: "\uD83D\uDD0D", description: "Researches and analyzes competitors", prompt: "You are a competitor research analyst. Research competitors, analyze strengths and weaknesses, track product updates and pricing changes. Provide structured, data-driven reports with actionable insights." },
    { name: "Code Reviewer", category: "Engineering", icon: "\uD83D\uDD27", description: "Reviews code for quality and best practices", prompt: "You are an expert code reviewer. Review code for bugs, security vulnerabilities, performance issues, and adherence to best practices. Provide specific, actionable feedback with code examples." },
    { name: "Research Assistant", category: "Research", icon: "\uD83D\uDCDA", description: "Helps research and summarize information", prompt: "You are a thorough research assistant. Help gather, analyze, and synthesize information on any topic. Provide well-organized summaries with key findings and supporting evidence." },
    { name: "Writing Editor", category: "Marketing", icon: "\u270D\uFE0F", description: "Edits and improves written content", prompt: "You are a skilled writing editor. Improve clarity, tone, grammar, and structure of written content. Preserve the author's voice while enhancing readability." },
  ];

  const [agentForm, setAgentForm] = useState<{
    editing: Agent | null; visible: boolean;
    name: string; description: string; system_prompt: string; icon: string;
    model_override: string; thinking_level: string; category: string;
  } | null>(null);
  const [agentSaving, setAgentSaving] = useState(false);
  const [agentFilter, setAgentFilter] = useState<"all" | "added" | "not_added">("all");

  function openAgentForm(agent?: Agent) {
    setAgentForm({
      editing: agent || null, visible: true,
      name: agent?.name ?? "", description: agent?.description ?? "",
      system_prompt: agent?.system_prompt ?? "", icon: agent?.icon ?? "\uD83E\uDD16",
      model_override: agent?.model_override ?? "", thinking_level: agent?.thinking_level ?? "",
      category: agent?.category ?? "",
    });
  }

  function applyAgentTemplate(t: typeof AGENT_TEMPLATES[number]) {
    if (!agentForm) return;
    setAgentForm({ ...agentForm, name: t.name, description: t.description, system_prompt: t.prompt, icon: t.icon, category: t.category });
  }

  async function saveAgent() {
    if (!agentForm || !agentForm.name.trim()) return;
    setAgentSaving(true);
    try {
      const payload = {
        name: agentForm.name.trim(),
        description: agentForm.description.trim(),
        system_prompt: agentForm.system_prompt.trim(),
        icon: agentForm.icon || "\uD83E\uDD16",
        model_override: agentForm.model_override.trim() || undefined,
        thinking_level: agentForm.thinking_level || undefined,
        category: agentForm.category || undefined,
      };
      if (agentForm.editing) {
        await updateAgent(agentForm.editing.id, payload);
      } else {
        await createAgent(payload);
      }
      const r = await listAgents();
      setAgents(r.agents || []);
      setAgentForm(null);
    } catch (e: any) {
      Alert.alert("Error", e.message || "Failed to save agent");
    } finally {
      setAgentSaving(false);
    }
  }

  function confirmDeleteAgent(a: Agent) {
    if (Platform.OS === "web") {
      if (confirm(`Delete agent "${a.name}"?`)) doDeleteAgent(a.id);
      return;
    }
    Alert.alert("Delete Agent", `Delete "${a.name}"?`, [
      { text: "Cancel", style: "cancel" },
      { text: "Delete", style: "destructive", onPress: () => doDeleteAgent(a.id) },
    ]);
  }

  async function doDeleteAgent(id: string) {
    try {
      await deleteAgent(id);
      setAgents(prev => prev.filter(a => a.id !== id));
    } catch {}
  }

  function TabAgents() {
    // Agent form view
    if (agentForm) {
      return (
        <>
          <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
            <Text style={st.sectionTitle}>{agentForm.editing ? "Edit Agent" : "New Agent"}</Text>
            <TouchableOpacity onPress={() => setAgentForm(null)} activeOpacity={0.7}>
              <Text style={{ color: colors.labelSecondary, fontSize: 14 }}>Cancel</Text>
            </TouchableOpacity>
          </View>

          {/* Templates (only for new) */}
          {!agentForm.editing && (
            <>
              <Text style={[st.desc, { marginBottom: 8 }]}>Start from a template:</Text>
              <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 16 }}>
                {AGENT_TEMPLATES.map((t) => (
                  <TouchableOpacity key={t.name} onPress={() => applyAgentTemplate(t)}
                    style={{ backgroundColor: colors.white05, borderRadius: radius.md, padding: 10, marginRight: 8, width: 140, borderWidth: 1, borderColor: colors.separator }}
                    activeOpacity={0.7}>
                    <Text style={{ fontSize: 20, marginBottom: 4 }}>{t.icon}</Text>
                    <Text style={{ color: colors.label, fontSize: 12, fontWeight: "600" }} numberOfLines={1}>{t.name}</Text>
                    <Text style={{ color: colors.labelTertiary, fontSize: 10, marginTop: 2 }} numberOfLines={2}>{t.description}</Text>
                  </TouchableOpacity>
                ))}
              </ScrollView>
            </>
          )}

          {/* Icon picker */}
          <Text style={st.fieldLabel}>Icon</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 12 }}>
            {AGENT_ICONS.map((ic) => (
              <TouchableOpacity key={ic} onPress={() => setAgentForm({ ...agentForm, icon: ic })}
                style={{ width: 40, height: 40, borderRadius: 20, backgroundColor: agentForm.icon === ic ? colors.accent + "33" : colors.white05, alignItems: "center", justifyContent: "center", marginRight: 6, borderWidth: agentForm.icon === ic ? 2 : 0, borderColor: colors.accent }}
                activeOpacity={0.7}>
                <Text style={{ fontSize: 20 }}>{ic}</Text>
              </TouchableOpacity>
            ))}
          </ScrollView>

          {/* Name */}
          <Text style={st.fieldLabel}>Name *</Text>
          <TextInput style={st.input} value={agentForm.name}
            onChangeText={(v) => setAgentForm({ ...agentForm, name: v })}
            placeholder="Agent name" placeholderTextColor={colors.labelTertiary} />

          {/* Description */}
          <Text style={st.fieldLabel}>Description</Text>
          <TextInput style={st.input} value={agentForm.description}
            onChangeText={(v) => setAgentForm({ ...agentForm, description: v })}
            placeholder="Short description" placeholderTextColor={colors.labelTertiary} />

          {/* Category */}
          <Text style={st.fieldLabel}>Category</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 12 }}>
            {AGENT_CATEGORIES.map((cat) => (
              <Chip key={cat} label={cat} active={agentForm.category === cat}
                color={colors.accent} onPress={() => setAgentForm({ ...agentForm, category: agentForm.category === cat ? "" : cat })} />
            ))}
          </ScrollView>

          {/* System Prompt */}
          <Text style={st.fieldLabel}>System Prompt</Text>
          <TextInput style={[st.textArea, { minHeight: 120 }]} value={agentForm.system_prompt}
            onChangeText={(v) => setAgentForm({ ...agentForm, system_prompt: v })}
            placeholder="Instructions for the agent..." placeholderTextColor={colors.labelTertiary}
            multiline textAlignVertical="top" />

          {/* Model Override */}
          <Text style={st.fieldLabel}>Model Override</Text>
          <TextInput style={st.input} value={agentForm.model_override}
            onChangeText={(v) => setAgentForm({ ...agentForm, model_override: v })}
            placeholder="Leave blank for default" placeholderTextColor={colors.labelTertiary} />

          {/* Thinking Level */}
          <Text style={st.fieldLabel}>Thinking Level</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 16 }}>
            {[{ value: "", label: "Default" }, ...THINKING_LEVELS.map(l => ({ value: l, label: l.charAt(0).toUpperCase() + l.slice(1) }))].map((t) => (
              <Chip key={t.value} label={t.label} active={agentForm.thinking_level === t.value}
                color={colors.accent} onPress={() => setAgentForm({ ...agentForm, thinking_level: t.value })} />
            ))}
          </ScrollView>

          {/* Save */}
          <TouchableOpacity style={st.accentBtn} onPress={saveAgent}
            disabled={agentSaving || !agentForm.name.trim()} activeOpacity={0.7}>
            <Text style={st.accentBtnText}>{agentSaving ? "Saving..." : agentForm.editing ? "Update Agent" : "Create Agent"}</Text>
          </TouchableOpacity>
        </>
      );
    }

    // Agent list view
    const filteredAgents = agentFilter === "all" ? agents
      : agentFilter === "added" ? agents.filter(a => a.enabled)
      : agents.filter(a => !a.enabled);

    return (
      <>
        <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          <Text style={st.desc}>Manage your AI agents.</Text>
          <TouchableOpacity style={[st.accentBtn, { paddingHorizontal: 12, paddingVertical: 6 }]}
            onPress={() => openAgentForm()} activeOpacity={0.7}>
            <IconPlus size={14} color="#fff" />
            <Text style={[st.accentBtnText, { marginLeft: 4 }]}>New</Text>
          </TouchableOpacity>
        </View>

        {/* Filter chips */}
        <View style={[st.chipRow, { marginBottom: 12 }]}>
          {(["all", "added", "not_added"] as const).map((f) => (
            <Chip key={f} label={f === "not_added" ? "Not Added" : f.charAt(0).toUpperCase() + f.slice(1)}
              active={agentFilter === f} color={colors.accent}
              onPress={() => setAgentFilter(f)} />
          ))}
        </View>

        {filteredAgents.length === 0 && <Text style={st.emptyText}>No agents found</Text>}
        {filteredAgents.map((a) => {
          const ai = resolveAgentIcon(a);
          return (
            <View key={a.id} style={st.agentCardOuter}>
              <TouchableOpacity style={st.agentCardTop}
                onPress={() => openAgentForm(a)} activeOpacity={0.7}>
                {/* Avatar */}
                <View style={[st.agentAvatar, { backgroundColor: ai.bg }]}>
                  <ai.Icon size={20} color={ai.color} />
                </View>
                {/* Info */}
                <View style={{ flex: 1, minWidth: 0 }}>
                  <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
                    <Text style={st.toggleName} numberOfLines={1}>{a.name}</Text>
                    <Switch value={a.enabled}
                      onValueChange={(v) => { setAgents(prev => prev.map(x => x.id === a.id ? { ...x, enabled: v } : x)); toggleAgent(a.id, v).catch(() => {}); }}
                      trackColor={{ false: colors.white08, true: colors.accent }} thumbColor="#fff"
                      style={{ transform: [{ scaleX: 0.8 }, { scaleY: 0.8 }] }} />
                  </View>
                  {a.description ? <Text style={st.toggleDesc} numberOfLines={2}>{a.description}</Text> : null}
                </View>
              </TouchableOpacity>
              {/* Footer badges + actions */}
              <View style={st.agentCardFooter}>
                <View style={{ flexDirection: "row", gap: 4, flex: 1, flexWrap: "wrap" }}>
                  {a.category ? (
                    <View style={[st.agentBadge, { backgroundColor: ai.color + "15" }]}>
                      <Text style={[st.agentBadgeText, { color: ai.color }]}>{a.category}</Text>
                    </View>
                  ) : null}
                  {a.model_override ? (
                    <View style={[st.agentBadge, { backgroundColor: colors.white05 }]}>
                      <Text style={[st.agentBadgeText, { color: colors.labelTertiary, fontFamily: Platform.OS === "ios" ? "Menlo" : "monospace" }]}>{a.model_override}</Text>
                    </View>
                  ) : null}
                  {a.skills && a.skills.length > 0 ? (
                    <View style={[st.agentBadge, { backgroundColor: colors.white05 }]}>
                      <Text style={[st.agentBadgeText, { color: colors.labelTertiary }]}>{a.skills.length} skill{a.skills.length !== 1 ? "s" : ""}</Text>
                    </View>
                  ) : null}
                </View>
                <View style={{ flexDirection: "row", gap: 4 }}>
                  <TouchableOpacity onPress={() => openAgentForm(a)} activeOpacity={0.7}
                    style={{ padding: 6, borderRadius: 8 }}>
                    <IconEdit size={12} color={colors.labelTertiary} />
                  </TouchableOpacity>
                  <TouchableOpacity onPress={() => confirmDeleteAgent(a)} activeOpacity={0.7}
                    style={{ padding: 6, borderRadius: 8 }}>
                    <IconTrash size={12} color={colors.danger} />
                  </TouchableOpacity>
                </View>
              </View>
            </View>
          );
        })}
      </>
    );
  }

  /* ─────── Tab: Skills ─────── */
  function TabSkills() {
    return (
      <>
        <Text style={st.desc}>Enable or disable workspace skills.</Text>
        {skills.length === 0 && <Text style={st.emptyText}>No skills found</Text>}
        {skills.map((sk: any) => (
          <View key={sk.id || sk.name} style={st.toggleRow}>
            <View style={{ flex: 1, marginRight: 12 }}>
              <Text style={st.toggleName}>{sk.name || sk.id}</Text>
              {sk.description ? <Text style={st.toggleDesc} numberOfLines={2}>{sk.description}</Text> : null}
            </View>
            <Switch value={sk.enabled}
              onValueChange={(v) => { setSkills(prev => prev.map((x: any) => (x.id || x.name) === (sk.id || sk.name) ? { ...x, enabled: v } : x)); toggleSkill(sk.id || sk.name, v).catch(() => {}); }}
              trackColor={{ false: colors.white08, true: colors.accent }} thumbColor="#fff" />
          </View>
        ))}
      </>
    );
  }

  /* ─────── Tab: Persona ─────── */
  function TabPersona() {
    const tabs = admin
      ? [{ id: "soul" as const, l: "Soul" }, { id: "user_soul" as const, l: "User Soul" }, { id: "user" as const, l: "Memories" }]
      : [{ id: "user" as const, l: "Memories" }];
    return (
      <>
        <Text style={st.desc}>
          {personaTab === "soul" ? "Asta's personality, voice, and character."
            : personaTab === "user_soul" ? "Personality shown to regular users."
            : "Info about you — Asta uses this to personalize."}
        </Text>
        {tabs.length > 1 && (
          <View style={st.chipRow}>
            {tabs.map((t) => (
              <Chip key={t.id} label={t.l} active={personaTab === t.id} color={colors.accent}
                onPress={() => setPersonaTab(t.id)} />
            ))}
          </View>
        )}
        <TextInput
          style={st.textArea}
          value={persona[personaTab]}
          onChangeText={(v) => setPersonaState({ ...persona, [personaTab]: v })}
          placeholder="Enter content..."
          placeholderTextColor={colors.labelTertiary}
          multiline textAlignVertical="top"
        />
        <TouchableOpacity style={st.accentBtn} onPress={savePersona} disabled={personaSaving} activeOpacity={0.7}>
          <Text style={st.accentBtnText}>{personaSaving ? "Saving..." : "Save"}</Text>
        </TouchableOpacity>
      </>
    );
  }

  /* ─────── Tab: Channels ─────── */

  const TG_COMMANDS = [
    { cmd: "/start", desc: "Start chatting with Asta" },
    { cmd: "/status", desc: "Show backend status" },
    { cmd: "/exec_mode", desc: "Toggle exec mode on/off" },
    { cmd: "/thinking", desc: "Set thinking level" },
    { cmd: "/reasoning", desc: "Set reasoning mode" },
  ];

  const [tgUser, setTgUser] = useState("");
  const [tgToken, setTgToken] = useState("");
  const [tgTokenSet, setTgTokenSet] = useState(false);
  const [pgPhone, setPgPhone] = useState("");
  const [pgToken, setPgToken] = useState("");
  const [pgClientId, setPgClientId] = useState("");
  const [pgClientSecret, setPgClientSecret] = useState("");
  const [pgNotifId, setPgNotifId] = useState("");
  const [channelSaving, setChannelSaving] = useState<string | null>(null);
  const [testCallResult, setTestCallResult] = useState<"ok" | "fail" | null>(null);

  useEffect(() => {
    if (activeTab !== "channels") return;
    getTelegramUsername().then(r => setTgUser(r.username ?? "")).catch(() => {});
    getKeyStatus().then(r => setTgTokenSet(!!r.telegram_bot_token)).catch(() => {});
    getPingram().then(r => {
      setPgToken(r.api_key ?? "");
      setPgPhone(r.phone_number ?? "");
      setPgClientId(r.client_id ?? "");
      setPgClientSecret(r.client_secret ?? "");
      setPgNotifId(r.notification_id ?? "");
    }).catch(() => {});
  }, [activeTab]);

  async function saveTgToken() {
    if (!tgToken.trim()) return;
    setChannelSaving("tg-token");
    try {
      await setKeys({ telegram_bot_token: tgToken.trim() });
      setTgTokenSet(true);
    } catch {}
    setChannelSaving(null);
  }

  async function saveTgUsername() {
    setChannelSaving("tg-user");
    try { await setTelegramUsername(tgUser); } catch {}
    setChannelSaving(null);
  }

  async function savePingram() {
    setChannelSaving("pg");
    try {
      await setPingram({ api_key: pgToken, phone_number: pgPhone, client_id: pgClientId, client_secret: pgClientSecret, notification_id: pgNotifId });
    } catch {}
    setChannelSaving(null);
  }

  async function doTestCall() {
    if (!pgPhone.trim()) { setTestCallResult("fail"); setTimeout(() => setTestCallResult(null), 3000); return; }
    try {
      const r: any = await testPingramCall(pgPhone.trim());
      setTestCallResult(r.ok ? "ok" : "fail");
    } catch { setTestCallResult("fail"); }
    setTimeout(() => setTestCallResult(null), 3000);
  }

  function TabChannels() {
    return (
      <>
        {/* Telegram section */}
        <Text style={st.sectionTitle}>Telegram</Text>
        <Text style={[st.desc, { marginBottom: 12 }]}>Connect a Telegram bot to chat with Asta.</Text>

        <Text style={st.fieldLabel}>Bot Token</Text>
        <View style={{ flexDirection: "row", alignItems: "center", gap: 6, marginBottom: 4 }}>
          {tgTokenSet && <View style={{ width: 6, height: 6, borderRadius: 3, backgroundColor: colors.success }} />}
          {tgTokenSet && <Text style={{ fontSize: 11, color: colors.success }}>Set</Text>}
        </View>
        <View style={{ flexDirection: "row", gap: 8, marginBottom: 12 }}>
          <TextInput style={[st.input, { flex: 1, marginBottom: 0 }]} value={tgToken}
            onChangeText={setTgToken} placeholder={tgTokenSet ? "Leave blank to keep existing" : "123456:ABC-DEF..."}
            placeholderTextColor={colors.labelTertiary} secureTextEntry />
          <TouchableOpacity style={[st.accentBtn, { marginTop: 0, paddingHorizontal: 16, paddingVertical: 11 }]}
            onPress={saveTgToken} disabled={channelSaving === "tg-token"} activeOpacity={0.7}>
            <Text style={st.accentBtnText}>{channelSaving === "tg-token" ? "..." : "Save"}</Text>
          </TouchableOpacity>
        </View>

        <Text style={st.fieldLabel}>Bot Username</Text>
        <View style={{ flexDirection: "row", gap: 8, marginBottom: 12 }}>
          <TextInput style={[st.input, { flex: 1, marginBottom: 0 }]} value={tgUser}
            onChangeText={setTgUser} placeholder="@YourBotUsername"
            placeholderTextColor={colors.labelTertiary} autoCapitalize="none" />
          <TouchableOpacity style={[st.accentBtn, { marginTop: 0, paddingHorizontal: 16, paddingVertical: 11 }]}
            onPress={saveTgUsername} disabled={channelSaving === "tg-user"} activeOpacity={0.7}>
            <Text style={st.accentBtnText}>{channelSaving === "tg-user" ? "..." : "Save"}</Text>
          </TouchableOpacity>
        </View>

        {/* Commands reference */}
        <View style={{ backgroundColor: colors.white05, borderRadius: radius.md, padding: 12, marginBottom: 20 }}>
          <Text style={{ fontSize: 11, fontWeight: "700", color: colors.labelTertiary, marginBottom: 8 }}>AVAILABLE COMMANDS</Text>
          {TG_COMMANDS.map((c) => (
            <View key={c.cmd} style={{ flexDirection: "row", gap: 12, marginBottom: 4 }}>
              <Text style={{ fontSize: 12, color: colors.accent, fontFamily: Platform.OS === "ios" ? "Menlo" : "monospace", width: 100 }}>{c.cmd}</Text>
              <Text style={{ fontSize: 12, color: colors.labelTertiary, flex: 1 }}>{c.desc}</Text>
            </View>
          ))}
        </View>

        {/* Pingram section */}
        <Text style={st.sectionTitle}>Pingram (Voice Calls)</Text>
        <Text style={[st.desc, { marginBottom: 12 }]}>Configure voice call integration.</Text>

        <Text style={st.fieldLabel}>Phone Number</Text>
        <TextInput style={st.input} value={pgPhone} onChangeText={setPgPhone}
          placeholder="+1234567890" placeholderTextColor={colors.labelTertiary} keyboardType="phone-pad" />

        <Text style={st.fieldLabel}>API Token</Text>
        <TextInput style={st.input} value={pgToken} onChangeText={setPgToken}
          placeholder="API token" placeholderTextColor={colors.labelTertiary} secureTextEntry />

        <Text style={st.fieldLabel}>Client ID</Text>
        <TextInput style={st.input} value={pgClientId} onChangeText={setPgClientId}
          placeholder="Client ID" placeholderTextColor={colors.labelTertiary} />

        <Text style={st.fieldLabel}>Client Secret</Text>
        <TextInput style={st.input} value={pgClientSecret} onChangeText={setPgClientSecret}
          placeholder="Client secret" placeholderTextColor={colors.labelTertiary} secureTextEntry />

        <Text style={st.fieldLabel}>Notification ID (optional)</Text>
        <TextInput style={st.input} value={pgNotifId} onChangeText={setPgNotifId}
          placeholder="Notification ID" placeholderTextColor={colors.labelTertiary} />

        <View style={{ flexDirection: "row", gap: 8, marginTop: 8 }}>
          <TouchableOpacity style={[st.accentBtn, { flex: 1, marginTop: 0 }]}
            onPress={savePingram} disabled={channelSaving === "pg"} activeOpacity={0.7}>
            <Text style={st.accentBtnText}>{channelSaving === "pg" ? "Saving..." : "Save"}</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[st.accentBtn, { marginTop: 0, paddingHorizontal: 16,
              backgroundColor: testCallResult === "ok" ? colors.success : testCallResult === "fail" ? colors.danger : colors.white08 }]}
            onPress={doTestCall} activeOpacity={0.7}>
            <Text style={[st.accentBtnText, { color: testCallResult ? "#fff" : colors.label }]}>
              {testCallResult === "ok" ? "Sent!" : testCallResult === "fail" ? "Failed" : "Test Call"}
            </Text>
          </TouchableOpacity>
        </View>
      </>
    );
  }

  /* ─────── Tab: Cron / Schedule ─────── */

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

  function TabCron() {
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
              <Switch
                value={!!job.enabled}
                onValueChange={(v) => toggleCronJob(String(job.id), v)}
                trackColor={{ false: colors.white08, true: colors.accent }}
                thumbColor="#fff"
              />
            </View>
          );
        })}
      </>
    );
  }

  /* ─────── Tab: Users ─────── */

  async function handleAddUser() {
    if (!newUsername.trim() || !newPassword.trim()) return;
    setUserSaving(true);
    setUserError("");
    try {
      await createUser(newUsername.trim(), newPassword, newRole);
      const r = await listUsers();
      setUsersList(r.users || []);
      setShowAddUser(false);
      setNewUsername("");
      setNewPassword("");
      setNewRole("user");
    } catch (e: any) {
      const msg = e.message || "";
      if (msg.includes("409")) setUserError("Username already taken");
      else setUserError("Failed to create user");
    }
    setUserSaving(false);
  }

  async function handleDeleteUser(uid: string) {
    const doDelete = async () => {
      await deleteUser(uid).catch(() => {});
      const r = await listUsers().catch(() => ({ users: [] }));
      setUsersList(r.users || []);
    };
    if (Platform.OS === "web") {
      if (confirm("Delete this user?")) await doDelete();
      return;
    }
    Alert.alert("Delete User", "This will prevent them from logging in. Continue?", [
      { text: "Cancel", style: "cancel" },
      { text: "Delete", style: "destructive", onPress: doDelete },
    ]);
  }

  async function handleResetPw() {
    if (!resetPwId || resetPwVal.length < 4) return;
    await resetUserPassword(resetPwId, resetPwVal).catch(() => {});
    setResetPwId(null);
    setResetPwVal("");
  }

  function TabUsers() {
    return (
      <>
        <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: spacing.lg }}>
          <Text style={st.desc}>Manage user accounts.</Text>
          <TouchableOpacity
            style={{ flexDirection: "row", alignItems: "center", gap: 4, backgroundColor: colors.accent, borderRadius: radius.md, paddingHorizontal: 12, paddingVertical: 8 }}
            onPress={() => setShowAddUser(!showAddUser)}
            activeOpacity={0.7}
          >
            <IconPlus size={14} color="#fff" />
            <Text style={{ fontSize: 13, fontWeight: "600", color: "#fff" }}>Add</Text>
          </TouchableOpacity>
        </View>

        {/* Add user form */}
        {showAddUser && (
          <View style={[st.card, { padding: 16, marginBottom: spacing.lg, gap: 10 }]}>
            <TextInput
              style={st.keyInput}
              value={newUsername}
              onChangeText={setNewUsername}
              placeholder="Username"
              placeholderTextColor={colors.labelTertiary}
              autoCapitalize="none"
              autoCorrect={false}
            />
            <TextInput
              style={st.keyInput}
              value={newPassword}
              onChangeText={setNewPassword}
              placeholder="Password (min 4 chars)"
              placeholderTextColor={colors.labelTertiary}
              secureTextEntry
            />
            <View style={st.chipRow}>
              <Chip label="User" active={newRole === "user"} color={colors.accent}
                onPress={() => setNewRole("user")} />
              <Chip label="Admin" active={newRole === "admin"} color={colors.accent}
                onPress={() => setNewRole("admin")} />
            </View>
            {userError ? <Text style={{ fontSize: 12, color: colors.danger }}>{userError}</Text> : null}
            <TouchableOpacity
              style={[st.accentBtn, { marginTop: 4, opacity: newUsername.trim() && newPassword.length >= 4 ? 1 : 0.4 }]}
              onPress={handleAddUser}
              disabled={!newUsername.trim() || newPassword.length < 4 || userSaving}
              activeOpacity={0.7}
            >
              <Text style={st.accentBtnText}>{userSaving ? "Creating..." : "Create User"}</Text>
            </TouchableOpacity>
          </View>
        )}

        {usersList.length === 0 && (
          <Text style={st.emptyText}>No users created yet. Running in single-user mode.</Text>
        )}

        {usersList.map((u) => (
          <View key={u.id} style={st.toggleRow}>
            <View style={{ flex: 1 }}>
              <View style={{ flexDirection: "row", alignItems: "center", gap: 8, marginBottom: 2 }}>
                <Text style={st.toggleName}>{u.username}</Text>
                <View style={{
                  backgroundColor: u.role === "admin" ? "rgba(99,102,241,0.12)" : colors.white08,
                  paddingHorizontal: 6, paddingVertical: 1, borderRadius: radius.full,
                }}>
                  <Text style={{
                    fontSize: 10, fontWeight: "700", textTransform: "uppercase",
                    color: u.role === "admin" ? "#818CF8" : colors.labelTertiary,
                  }}>{u.role}</Text>
                </View>
              </View>

              {/* Reset password inline */}
              {resetPwId === String(u.id) ? (
                <View style={{ flexDirection: "row", gap: 6, marginTop: 6 }}>
                  <TextInput
                    style={[st.keyInput, { flex: 1, paddingVertical: 8 }]}
                    value={resetPwVal}
                    onChangeText={setResetPwVal}
                    placeholder="New password"
                    placeholderTextColor={colors.labelTertiary}
                    secureTextEntry
                    autoFocus
                  />
                  <TouchableOpacity
                    style={{ backgroundColor: colors.accent, borderRadius: radius.sm, paddingHorizontal: 12, justifyContent: "center" }}
                    onPress={handleResetPw}
                    disabled={resetPwVal.length < 4}
                    activeOpacity={0.7}
                  >
                    <Text style={{ fontSize: 12, fontWeight: "600", color: "#fff" }}>Save</Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={{ justifyContent: "center", paddingHorizontal: 8 }}
                    onPress={() => { setResetPwId(null); setResetPwVal(""); }}
                    activeOpacity={0.7}
                  >
                    <Text style={{ fontSize: 12, fontWeight: "600", color: colors.labelTertiary }}>Cancel</Text>
                  </TouchableOpacity>
                </View>
              ) : (
                <View style={{ flexDirection: "row", gap: 12, marginTop: 6 }}>
                  <TouchableOpacity onPress={() => { setResetPwId(String(u.id)); setResetPwVal(""); }} activeOpacity={0.7}>
                    <Text style={{ fontSize: 12, fontWeight: "600", color: colors.accent }}>Reset password</Text>
                  </TouchableOpacity>
                  <TouchableOpacity onPress={() => handleDeleteUser(String(u.id))} activeOpacity={0.7}>
                    <Text style={{ fontSize: 12, fontWeight: "600", color: colors.danger }}>Delete</Text>
                  </TouchableOpacity>
                </View>
              )}
            </View>
          </View>
        ))}
      </>
    );
  }

  /* ─────── Tab: Knowledge ─────── */

  async function handleDeleteTopic(topic: string) {
    const doDelete = async () => {
      await ragDeleteTopic(topic).catch(() => {});
      const r = await ragLearned().catch(() => ({ topics: [], learned: [] }));
      setRagTopics(r.topics || r.learned || []);
      getMemoryHealth().then(setMemHealth).catch(() => {});
    };
    if (Platform.OS === "web") {
      if (confirm(`Delete topic "${topic}"?`)) await doDelete();
      return;
    }
    Alert.alert("Delete Topic", `Remove "${topic}" from knowledge base?`, [
      { text: "Cancel", style: "cancel" },
      { text: "Delete", style: "destructive", onPress: doDelete },
    ]);
  }

  function TabKnowledge() {
    const ragOk = ragInfo?.ok;
    return (
      <>
        <Text style={st.desc}>Knowledge base for context-aware responses.</Text>

        {/* RAG status */}
        <View style={st.card}>
          <CardRow label="Status" value={ragOk ? "Active" : "Inactive"}
            valueColor={ragOk ? colors.success : colors.labelTertiary} />
          {ragInfo?.provider && <CardRow label="Provider" value={ragInfo.provider} />}
          {ragInfo?.store_error && <CardRow label="Error" value={ragInfo.store_error} valueColor={colors.danger} />}
        </View>

        {/* Memory health */}
        {memHealth && (
          <>
            <Label text="Memory Health" />
            <View style={st.card}>
              {memHealth.vector_count != null && <CardRow label="Vectors" value={String(memHealth.vector_count)} />}
              {memHealth.chunk_count != null && <CardRow label="Chunks" value={String(memHealth.chunk_count)} />}
              {memHealth.store_size_mb != null && <CardRow label="Store Size" value={`${memHealth.store_size_mb} MB`} />}
            </View>
          </>
        )}

        {/* Learned topics */}
        <Label text="Learned Topics" />
        {ragTopics.length === 0 ? (
          <Text style={st.emptyText}>
            No topics learned yet. Use learning mode in chat to teach Asta.
          </Text>
        ) : (
          ragTopics.map((t: any) => {
            const name = typeof t === "string" ? t : t.topic || t.name || "";
            const chunks = typeof t === "object" ? t.chunks || t.chunk_count : undefined;
            return (
              <View key={name} style={st.toggleRow}>
                <View style={{ flex: 1 }}>
                  <Text style={st.toggleName}>{name}</Text>
                  {chunks != null && (
                    <Text style={st.toggleDesc}>{chunks} chunk{chunks !== 1 ? "s" : ""}</Text>
                  )}
                </View>
                <TouchableOpacity onPress={() => handleDeleteTopic(name)} activeOpacity={0.7}>
                  <IconTrash size={16} color={colors.danger} />
                </TouchableOpacity>
              </View>
            );
          })
        )}
      </>
    );
  }

  /* ─────── Tab: Permissions ─────── */

  const [auditFindings, setAuditFindings] = useState<any[] | null>(null);

  useEffect(() => {
    if (activeTab !== "permissions") return;
    getSecurityAudit().then(r => setAuditFindings(r.findings ?? [])).catch(() => setAuditFindings([]));
  }, [activeTab]);

  function TabPermissions() {
    return (
      <>
        <Text style={st.desc}>Security audit of your Asta configuration.</Text>
        {auditFindings === null && <Text style={st.emptyText}>Loading...</Text>}
        {auditFindings && auditFindings.length === 0 && (
          <View style={{ backgroundColor: "rgba(52,199,89,0.1)", borderWidth: 1, borderColor: "rgba(52,199,89,0.2)", borderRadius: radius.md, padding: 14, flexDirection: "row", alignItems: "center", gap: 8 }}>
            <IconCheck size={14} color={colors.success} />
            <Text style={{ fontSize: 13, color: colors.success, fontWeight: "600" }}>All checks passed — no warnings</Text>
          </View>
        )}
        {auditFindings && auditFindings.length > 0 && auditFindings.map((w: any, i: number) => (
          <View key={i} style={{ backgroundColor: "rgba(255,159,10,0.1)", borderWidth: 1, borderColor: "rgba(255,159,10,0.2)", borderRadius: radius.md, padding: 14, flexDirection: "row", alignItems: "flex-start", gap: 8, marginBottom: 8 }}>
            <IconWarning size={14} color={colors.warning} />
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: 13, color: colors.warning, fontWeight: "600" }}>{w.title ?? (typeof w === "string" ? w : JSON.stringify(w))}</Text>
              {w.detail && <Text style={{ fontSize: 12, color: colors.labelTertiary, marginTop: 4 }}>{w.detail}</Text>}
            </View>
          </View>
        ))}
      </>
    );
  }

  /* ─────── Tab: Connection ─────── */
  function TabConnection() {
    return (
      <>
        <Text style={st.desc}>Configure backend server connection.</Text>
        <View style={st.card}>
          <View style={st.cardRow}>
            <Text style={st.cardLabel}>Status</Text>
            <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
              {serverOk ? <IconWifi size={13} /> : <IconWifiOff size={13} />}
              <Text style={{ fontSize: 13, fontWeight: "600", color: serverOk ? colors.success : colors.danger }}>
                {serverOk === null ? "..." : serverOk ? "Connected" : "Unreachable"}
              </Text>
            </View>
          </View>
          {serverVersion ? (
            <View style={[st.cardRow, { borderTopWidth: 1, borderTopColor: colors.separator }]}>
              <Text style={st.cardLabel}>Version</Text>
              <Text style={st.cardVal}>{serverVersion}</Text>
            </View>
          ) : null}
        </View>
        <Label text="Backend URL" />
        <TextInput style={st.keyInput} value={backendUrl} onChangeText={setBackendUrlState}
          placeholder="https://asta.example.com" placeholderTextColor={colors.labelTertiary}
          autoCapitalize="none" autoCorrect={false} />
        <TouchableOpacity style={[st.accentBtn, { marginTop: 12 }]} onPress={saveConnection} disabled={connSaving} activeOpacity={0.7}>
          <Text style={st.accentBtnText}>{connSaving ? "Connecting..." : "Save & Test"}</Text>
        </TouchableOpacity>
      </>
    );
  }

  /* ─────── Tab: About ─────── */
  function TabAbout() {
    return (
      <>
        <View style={{ alignItems: "center", marginBottom: 20 }}>
          <View style={st.aboutLogo}>
            <Image source={require("../../assets/appicon.png")} style={{ width: 64, height: 64, borderRadius: 14 }} />
          </View>
          <Text style={{ fontSize: 24, fontWeight: "800", color: colors.label }}>Asta</Text>
          <Text style={{ fontSize: 13, color: colors.labelTertiary, marginTop: 2 }}>Mobile v1.0</Text>
        </View>
        <Label text="Server" />
        <View style={st.card}>
          <CardRow label="Status" value={serverOk ? "Online" : serverOk === false ? "Offline" : "..."} valueColor={serverOk ? colors.success : colors.danger} />
          {serverVersion ? <CardRow label="Version" value={serverVersion} /> : null}
          {serverStatus?.cpu_percent != null && <CardRow label="CPU" value={`${serverStatus.cpu_percent}%`} />}
          {serverStatus?.ram?.percent != null && <CardRow label="RAM" value={`${serverStatus.ram.percent}%`} />}
          {serverStatus?.uptime && <CardRow label="Uptime" value={serverStatus.uptime} />}
        </View>
        {usage && (
          <>
            <Label text="Usage (7 days)" />
            <View style={st.card}>
              {usage.total_messages != null && <CardRow label="Messages" value={usage.total_messages.toLocaleString()} />}
              {usage.total_tokens != null && <CardRow label="Tokens" value={
                usage.total_tokens >= 1_000_000 ? `${(usage.total_tokens / 1_000_000).toFixed(1)}M` : `${(usage.total_tokens / 1000).toFixed(0)}k`
              } />}
            </View>
          </>
        )}
      </>
    );
  }
}

/* ── Tiny shared components ───────────────────────── */

function Label({ text }: { text: string }) {
  return <Text style={st.label}>{text}</Text>;
}

function Chip({ label, active, color, onPress }: { label: string; active: boolean; color: string; onPress: () => void }) {
  return (
    <TouchableOpacity
      style={[st.chip, active && { backgroundColor: color + "18", borderColor: color + "60" }]}
      onPress={onPress} activeOpacity={0.7}
    >
      <Text style={[st.chipText, active && { color, fontWeight: "700" }]}>{label}</Text>
    </TouchableOpacity>
  );
}

function CardRow({ label, value, valueColor }: { label: string; value: string; valueColor?: string }) {
  return (
    <View style={st.cardRow}>
      <Text style={st.cardLabel}>{label}</Text>
      <Text style={[st.cardVal, valueColor ? { color: valueColor } : null]}>{value}</Text>
    </View>
  );
}

/* ── Styles ───────────────────────────────────────── */

const st = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface },

  /* Header */
  header: {
    flexDirection: "row", alignItems: "center", justifyContent: "space-between",
    paddingHorizontal: spacing.md, paddingVertical: 12,
    backgroundColor: colors.surfaceRaised,
    borderBottomWidth: 1, borderBottomColor: colors.separator,
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

  /* Agent cards (matches desktop) */
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
