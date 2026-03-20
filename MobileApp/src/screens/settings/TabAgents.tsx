import React, { useState, useEffect } from "react";
import { View, Text, TextInput, TouchableOpacity, ScrollView, Alert, Platform } from "react-native";
import { colors, radius } from "../../theme/colors";
import { listAgents, createAgent, updateAgent, deleteAgent, toggleAgent } from "../../lib/api";
import type { Agent } from "../../lib/types";
import { IconPlus, IconTrash, IconEdit, resolveAgentIcon } from "../../components/Icons";
import Toggle from "../../components/Toggle";
import { Chip, st, THINKING_LEVELS, TabProps } from "./shared";

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

interface AgentFormState {
  editing: Agent | null;
  visible: boolean;
  name: string;
  description: string;
  system_prompt: string;
  icon: string;
  model_override: string;
  thinking_level: string;
  category: string;
}

export default function TabAgents(_props: TabProps) {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [agentForm, setAgentForm] = useState<AgentFormState | null>(null);
  const [agentSaving, setAgentSaving] = useState(false);
  const [agentFilter, setAgentFilter] = useState<"all" | "added" | "not_added">("all");

  useEffect(() => {
    listAgents().then((r) => setAgents(r.agents || [])).catch(() => {});
  }, []);

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
            <View style={st.agentCardTop}>
              {/* Avatar */}
              <TouchableOpacity onPress={() => openAgentForm(a)} activeOpacity={0.7}>
                <View style={[st.agentAvatar, { backgroundColor: ai.bg }]}>
                  <ai.Icon size={20} color={ai.color} />
                </View>
              </TouchableOpacity>
              {/* Info */}
              <TouchableOpacity style={{ flex: 1, minWidth: 0 }}
                onPress={() => openAgentForm(a)} activeOpacity={0.7}>
                <Text style={st.toggleName} numberOfLines={1}>{a.name}</Text>
                {a.description ? <Text style={st.toggleDesc} numberOfLines={2}>{a.description}</Text> : null}
              </TouchableOpacity>
              {/* Toggle */}
              <Toggle value={!!a.enabled}
                onValueChange={(v) => { setAgents(prev => prev.map(x => x.id === a.id ? { ...x, enabled: v } : x)); toggleAgent(a.id, v).catch(() => {}); }}
              />
            </View>
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
