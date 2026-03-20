import React, { useState, useRef, useEffect, useCallback } from "react";
import {
  View, Text, TouchableOpacity, FlatList, StyleSheet,
  KeyboardAvoidingView, Platform, ScrollView, Alert,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { colors, spacing, radius } from "../theme/colors";
import { streamChat, loadMessages, setDefaultAI, setThinking, truncateConversation } from "../lib/api";
import type { Message, StreamChunk, Agent } from "../lib/types";
import {
  IconBrain, IconCheck, IconChevronDown, resolveAgentIcon,
} from "../components/Icons";
import { ProviderLogo } from "../components/ProviderIcon";
import { IconX } from "../components/Icons";
import * as Clipboard from "expo-clipboard";
import * as ImagePicker from "expo-image-picker";
import ChatHeader from "../components/chat/ChatHeader";
import ChatEmptyState from "../components/chat/ChatEmptyState";
import MessageBubble, { StreamingBubble } from "../components/chat/MessageBubble";
import ChatInput from "../components/chat/ChatInput";

const PROVIDERS = [
  { key: "claude", label: "Claude" },
  { key: "gemini", label: "Gemini" },
  { key: "openrouter", label: "OpenRouter" },
  { key: "ollama", label: "Local" },
];

const THINKING_LEVELS = ["off", "minimal", "low", "medium", "high", "xhigh"];

interface Props {
  conversationId?: string;
  onConversationCreated?: (id: string) => void;
  provider?: string;
  thinkingLevel?: string;
  agents?: Agent[];
  onOpenDrawer?: () => void;
  onProviderChange?: (p: string) => void;
  onThinkingChange?: (t: string) => void;
}

export default function ChatScreen({
  conversationId, onConversationCreated, provider = "claude",
  thinkingLevel = "off", agents = [],
  onOpenDrawer, onProviderChange, onThinkingChange,
}: Props) {
  const insets = useSafeAreaInsets();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [streamContent, setStreamContent] = useState("");
  const [streamThinking, setStreamThinking] = useState("");
  const [activeTools, setActiveTools] = useState<string[]>([]);
  const [completedTools, setCompletedTools] = useState<string[]>([]);
  const [statusText, setStatusText] = useState("");
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [selectedAgent, setSelectedAgent] = useState<string | undefined>();
  const [inputFocused, setInputFocused] = useState(false);
  const [pendingImage, setPendingImage] = useState<{ uri: string; base64: string; mime: string } | null>(null);
  const [showScrollBtn, setShowScrollBtn] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editText, setEditText] = useState("");
  const [errorMsg, setErrorMsg] = useState("");
  const [loadingMsgs, setLoadingMsgs] = useState(false);
  const [dropdown, setDropdown] = useState<"provider" | "thinking" | "agent" | null>(null);
  const flatListRef = useRef<FlatList>(null);
  const stopRef = useRef<(() => void) | null>(null);
  const convIdRef = useRef(conversationId);

  useEffect(() => {
    convIdRef.current = conversationId;
    if (conversationId) {
      setLoadingMsgs(true);
      setErrorMsg("");
      loadMessages(conversationId)
        .then((r) => {
          const msgs = (r.messages || []).map((m: any) => ({
            id: m.id || String(Math.random()),
            role: m.role,
            content: m.content || "",
            thinking: m.thinking || m.thinkingContent,
            provider: m.provider,
            activeTools: [],
            completedTools: m.tool_names || [],
          }));
          setMessages(msgs);
        })
        .catch((e) => {
          setErrorMsg(e.message === "auth-expired" ? "Session expired — please sign in again" : "Failed to load messages");
          setTimeout(() => setErrorMsg(""), 8000);
        })
        .finally(() => setLoadingMsgs(false));
    } else {
      setMessages([]);
    }
  }, [conversationId]);

  const scrollToEnd = useCallback(() => {
    setTimeout(() => flatListRef.current?.scrollToEnd({ animated: true }), 100);
  }, []);

  async function pickImage() {
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ["images"],
      allowsEditing: false,
      quality: 0.8,
      base64: true,
    });
    if (!result.canceled && result.assets?.[0]) {
      const asset = result.assets[0];
      if (asset.base64) {
        const mime = asset.mimeType || (asset.uri.endsWith(".png") ? "image/png" : "image/jpeg");
        setPendingImage({ uri: asset.uri, base64: asset.base64, mime });
      }
    }
  }

  async function send(text?: string) {
    const msg = (text || input).trim();
    if (!msg && !pendingImage) return;
    if (streaming) return;
    setInput("");
    setDropdown(null);

    const imgForMsg = pendingImage;
    setPendingImage(null);

    const userMsg: Message = {
      id: `u-${Date.now()}`,
      role: "user",
      content: msg || (imgForMsg ? "[Image]" : ""),
      imageUri: imgForMsg?.uri,
      activeTools: [],
      completedTools: [],
    };
    setMessages((prev) => [...prev, userMsg]);
    scrollToEnd();

    setStreaming(true);
    setStreamContent("");
    setStreamThinking("");
    setActiveTools([]);
    setCompletedTools([]);
    setStatusText("");
    setErrorMsg("");

    let thinkAcc = "";
    let textAcc = "";
    let toolsDone: string[] = [];
    let finalConvId = convIdRef.current;
    let finished = false;

    const stop = await streamChat(
      {
        text: msg || "What's in this image?",
        conversation_id: convIdRef.current,
        provider: provider || undefined,
        agent_id: selectedAgent,
        image_base64: imgForMsg?.base64,
        image_mime: imgForMsg?.mime,
      },
      (chunk: StreamChunk) => {
        switch (chunk.type) {
          case "thinking": {
            let delta = chunk.delta || chunk.text || "";
            if (!thinkAcc && delta.startsWith("Reasoning:\n")) delta = delta.slice(11);
            thinkAcc += delta;
            setStreamThinking(thinkAcc);
            break;
          }
          case "text": {
            textAcc += chunk.delta || chunk.text || "";
            setStreamContent(textAcc);
            scrollToEnd();
            break;
          }
          case "assistant_final": {
            textAcc = chunk.text || chunk.delta || textAcc;
            setStreamContent(textAcc);
            break;
          }
          case "tool_start": {
            const label = chunk.label || chunk.name || "tool";
            setActiveTools((prev) => [...prev, label]);
            setStatusText(label);
            setStreamContent("");
            textAcc = "";
            break;
          }
          case "tool_end": {
            const label = chunk.label || chunk.name || "tool";
            setActiveTools((prev) => prev.filter((t) => t !== label));
            toolsDone = [...toolsDone, label];
            setCompletedTools([...toolsDone]);
            setStatusText("");
            break;
          }
          case "status": {
            setStatusText(chunk.text || chunk.delta || "");
            break;
          }
          case "done": {
            if (chunk.conversation_id) finalConvId = chunk.conversation_id;
            break;
          }
        }
      },
      (cid?: string) => {
        if (finished) return;
        finished = true;
        if (cid) finalConvId = cid;
        const assistantMsg: Message = {
          id: `a-${Date.now()}`,
          role: "assistant",
          content: textAcc || "",
          thinking: thinkAcc || undefined,
          provider: provider,
          activeTools: [],
          completedTools: toolsDone,
        };
        setMessages((prev) => [...prev, assistantMsg]);
        setStreamContent("");
        setStreamThinking("");
        setActiveTools([]);
        setCompletedTools([]);
        setStatusText("");
        setStreaming(false);
        if (finalConvId && finalConvId !== convIdRef.current) {
          convIdRef.current = finalConvId;
          onConversationCreated?.(finalConvId);
        }
        scrollToEnd();
      },
      (err: string) => {
        if (finished) return;
        finished = true;
        setStreaming(false);
        setStreamContent("");
        setStreamThinking("");
        setErrorMsg(err || "Connection failed");
        setTimeout(() => setErrorMsg(""), 6000);
      },
    );
    stopRef.current = stop;
  }

  async function copyText(id: string, text: string) {
    try {
      if (Platform.OS === "web" && navigator?.clipboard) {
        await navigator.clipboard.writeText(text);
      } else {
        await Clipboard.setStringAsync(text);
      }
    } catch {}
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  }

  function startEdit(msg: Message) {
    setEditingId(msg.id);
    setEditText(msg.content);
  }

  function cancelEdit() {
    setEditingId(null);
    setEditText("");
  }

  async function submitEdit() {
    if (!editingId || !conversationId) return;
    if (!editText.trim()) { cancelEdit(); return; }
    if (streaming) return;
    const msgIndex = messages.findIndex(m => m.id === editingId);
    if (msgIndex < 0) return;
    const captured = editText;
    setEditingId(null);
    setEditText("");
    await truncateConversation(conversationId, msgIndex).catch(() => {});
    setMessages(prev => prev.slice(0, msgIndex));
    send(captured);
  }

  function confirmDeleteMessage(id: string) {
    if (Platform.OS === "web") {
      if (confirm("Delete this message?")) setMessages(prev => prev.filter(m => m.id !== id));
      return;
    }
    Alert.alert("Delete Message", "Remove this message?", [
      { text: "Cancel", style: "cancel" },
      { text: "Delete", style: "destructive", onPress: () => setMessages(prev => prev.filter(m => m.id !== id)) },
    ]);
  }

  const showThinking = thinkingLevel !== "off";
  const activeAgent = agents.find(a => a.id === selectedAgent);

  function handleScroll(e: any) {
    const { contentOffset, contentSize, layoutMeasurement } = e.nativeEvent;
    const distanceFromBottom = contentSize.height - layoutMeasurement.height - contentOffset.y;
    setShowScrollBtn(distanceFromBottom > 200);
  }

  function renderMessage({ item }: { item: Message }) {
    return (
      <MessageBubble
        message={item}
        isUser={item.role === "user"}
        showThinking={showThinking}
        copiedId={copiedId}
        isEditing={editingId === item.id}
        editText={editText}
        streaming={streaming}
        onEditTextChange={setEditText}
        onStartEdit={startEdit}
        onCancelEdit={cancelEdit}
        onSubmitEdit={submitEdit}
        onCopy={copyText}
        onDelete={confirmDeleteMessage}
      />
    );
  }

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
      keyboardVerticalOffset={0}
    >
      {/* ── Header ── */}
      <ChatHeader
        topInset={insets.top}
        thinkingLevel={thinkingLevel}
        isThinkingDropdownOpen={dropdown === "thinking"}
        onOpenDrawer={onOpenDrawer}
        onToggleThinkingDropdown={() => setDropdown(dropdown === "thinking" ? null : "thinking")}
      />

      {/* ── Error banner ── */}
      {errorMsg ? (
        <TouchableOpacity style={styles.errorBanner} onPress={() => setErrorMsg("")} activeOpacity={0.8}>
          <Text style={styles.errorBannerText}>{errorMsg}</Text>
          <IconX size={12} color={colors.danger} />
        </TouchableOpacity>
      ) : null}

      {/* ── Messages ── */}
      <FlatList
        ref={flatListRef}
        data={messages}
        renderItem={renderMessage}
        keyExtractor={(m) => m.id}
        contentContainerStyle={styles.list}
        onContentSizeChange={() => { if (streaming || !showScrollBtn) scrollToEnd(); }}
        onScroll={handleScroll}
        scrollEventThrottle={100}
        ListEmptyComponent={
          <ChatEmptyState
            agents={agents}
            loadingMsgs={loadingMsgs}
            onAgentSelect={(id) => setSelectedAgent(id)}
            onSuggestionClick={(text) => send(text)}
          />
        }
        ListFooterComponent={
          streaming ? (
            <StreamingBubble
              streamContent={streamContent}
              streamThinking={streamThinking}
              showThinking={showThinking}
              activeTools={activeTools}
              completedTools={completedTools}
              statusText={statusText}
            />
          ) : null
        }
      />

      {/* ── Scroll-to-bottom FAB ── */}
      {showScrollBtn && !streaming && (
        <TouchableOpacity style={styles.scrollFab} onPress={scrollToEnd} activeOpacity={0.7}>
          <IconChevronDown size={16} color={colors.labelSecondary} />
        </TouchableOpacity>
      )}

      {/* ── Input bar ── */}
      <ChatInput
        input={input}
        onInputChange={setInput}
        onSend={() => send()}
        onStop={() => stopRef.current?.()}
        streaming={streaming}
        pendingImage={pendingImage}
        onAttach={pickImage}
        onRemoveImage={() => setPendingImage(null)}
        activeAgent={activeAgent}
        selectedAgent={selectedAgent}
        agents={agents}
        provider={provider}
        bottomInset={insets.bottom}
        isProviderDropdownOpen={dropdown === "provider"}
        isAgentDropdownOpen={dropdown === "agent"}
        onToggleProviderDropdown={() => setDropdown(dropdown === "provider" ? null : "provider")}
        onToggleAgentDropdown={() => setDropdown(dropdown === "agent" ? null : "agent")}
        inputFocused={inputFocused}
        onFocus={() => setInputFocused(true)}
        onBlur={() => setInputFocused(false)}
      />

      {/* ── All dropdowns rendered LAST so they float above header, chat & input ── */}

      {/* Thinking dropdown — drops DOWN from header */}
      {dropdown === "thinking" && (
        <View style={styles.dropdownOverlay}>
          <TouchableOpacity style={StyleSheet.absoluteFill} onPress={() => setDropdown(null)} activeOpacity={1} />
          <View style={[styles.topDropdown, { top: insets.top + 48 }]}>
            <Text style={styles.dropdownTitle}>Thinking Level</Text>
            {THINKING_LEVELS.map((t) => (
              <TouchableOpacity key={t}
                style={[styles.dropdownItem, thinkingLevel === t && styles.dropdownItemThinkActive]}
                onPress={() => { onThinkingChange?.(t); setThinking(t).catch(() => {}); setDropdown(null); }}
                activeOpacity={0.7}>
                {t !== "off" && <IconBrain size={14} color={thinkingLevel === t ? colors.violet : colors.labelTertiary} />}
                <Text style={[styles.dropdownItemText, thinkingLevel === t && { color: colors.violet, fontWeight: "700" }]}>
                  {t === "xhigh" ? "Maximum" : t.charAt(0).toUpperCase() + t.slice(1)}
                </Text>
                {thinkingLevel === t && <IconCheck size={14} color={colors.violet} />}
              </TouchableOpacity>
            ))}
          </View>
        </View>
      )}

      {/* Provider dropdown — bottom sheet */}
      {dropdown === "provider" && (
        <View style={styles.dropdownOverlay}>
          <TouchableOpacity style={{ flex: 1 }} onPress={() => setDropdown(null)} activeOpacity={1} />
          <View style={styles.dropdownSheet}>
            <View style={styles.dropdownHandle} />
            <Text style={styles.dropdownTitle}>Provider</Text>
            {PROVIDERS.map((p) => (
              <TouchableOpacity key={p.key}
                style={[styles.dropdownItem, provider === p.key && styles.dropdownItemActive]}
                onPress={() => { onProviderChange?.(p.key); setDefaultAI(p.key).catch(() => {}); setDropdown(null); }}
                activeOpacity={0.7}>
                <ProviderLogo provider={p.key} size={18} />
                <Text style={[styles.dropdownItemText, provider === p.key && styles.dropdownItemTextActive]}>{p.label}</Text>
                {provider === p.key && <IconCheck size={14} color={colors.accent} />}
              </TouchableOpacity>
            ))}
          </View>
        </View>
      )}

      {/* Agent dropdown — bottom sheet */}
      {dropdown === "agent" && (
        <View style={styles.dropdownOverlay}>
          <TouchableOpacity style={{ flex: 1 }} onPress={() => setDropdown(null)} activeOpacity={1} />
          <View style={styles.dropdownSheet}>
            <View style={styles.dropdownHandle} />
            <ScrollView style={{ maxHeight: 360 }} bounces={false}>
              <Text style={styles.dropdownTitle}>Agent</Text>
              <TouchableOpacity
                style={[styles.dropdownItem, !selectedAgent && styles.dropdownItemActive]}
                onPress={() => { setSelectedAgent(undefined); setDropdown(null); }}
                activeOpacity={0.7}>
                <Text style={[styles.dropdownItemText, !selectedAgent && styles.dropdownItemTextActive]}>None (default)</Text>
                {!selectedAgent && <IconCheck size={14} color={colors.accent} />}
              </TouchableOpacity>
              <View style={styles.dropdownDivider} />
              {agents.map((a) => {
                const ai = resolveAgentIcon(a);
                const isActive = selectedAgent === a.id;
                return (
                  <TouchableOpacity key={a.id}
                    style={[styles.dropdownItem, isActive && styles.dropdownItemActive]}
                    onPress={() => { setSelectedAgent(a.id); setDropdown(null); }}
                    activeOpacity={0.7}>
                    <View style={[styles.agentIconSmall, { backgroundColor: ai.bg }]}>
                      <ai.Icon size={12} color={ai.color} />
                    </View>
                    <View style={{ flex: 1 }}>
                      <Text style={[styles.dropdownItemText, isActive && styles.dropdownItemTextActive]}>{a.name}</Text>
                      {a.description ? <Text style={styles.dropdownItemDesc} numberOfLines={1}>{a.description}</Text> : null}
                      {a.category ? (
                        <View style={[styles.agentCategoryBadge, { backgroundColor: ai.color + "15" }]}>
                          <Text style={[styles.agentCategoryText, { color: ai.color }]}>{a.category}</Text>
                        </View>
                      ) : null}
                    </View>
                    {isActive && <IconCheck size={14} color={colors.accent} />}
                  </TouchableOpacity>
                );
              })}
            </ScrollView>
          </View>
        </View>
      )}
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface },

  // ── Error banner ──
  errorBanner: {
    flexDirection: "row", alignItems: "center", justifyContent: "space-between",
    backgroundColor: colors.dangerSubtle,
    paddingHorizontal: spacing.md, paddingVertical: 10,
    borderBottomWidth: 1, borderBottomColor: "rgba(255,59,48,0.2)",
  },
  errorBannerText: { fontSize: 13, fontWeight: "500", color: colors.danger, flex: 1 },

  // ── Scroll-to-bottom FAB ──
  scrollFab: {
    position: "absolute", right: spacing.lg, bottom: 100,
    width: 36, height: 36, borderRadius: 18,
    backgroundColor: colors.surfaceRaised,
    borderWidth: 1, borderColor: colors.separatorBold,
    alignItems: "center", justifyContent: "center",
    shadowColor: "#000", shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.25, shadowRadius: 8, elevation: 10,
    zIndex: 5,
  },

  // ── Messages ──
  list: { padding: spacing.md, paddingBottom: spacing.xxl, flexGrow: 1 },

  // ── Dropdown (bottom-sheet style) ──
  dropdownOverlay: {
    position: "absolute", top: 0, left: 0, right: 0, bottom: 0,
    zIndex: 200, backgroundColor: "rgba(0,0,0,0.3)",
    justifyContent: "flex-end",
  },
  topDropdown: {
    position: "absolute", left: spacing.md, right: spacing.md,
    backgroundColor: colors.surfaceRaised,
    borderRadius: radius.lg,
    paddingHorizontal: spacing.md, paddingVertical: spacing.sm,
    borderWidth: 1, borderColor: colors.separator,
    shadowColor: "#000", shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.3, shadowRadius: 20, elevation: 30,
    zIndex: 201,
  },
  dropdownSheet: {
    backgroundColor: colors.surfaceRaised,
    borderTopLeftRadius: radius.lg, borderTopRightRadius: radius.lg,
    paddingHorizontal: spacing.md, paddingBottom: spacing.xl,
    borderWidth: 1, borderColor: colors.separator,
    borderBottomWidth: 0,
    shadowColor: "#000", shadowOffset: { width: 0, height: -8 },
    shadowOpacity: 0.3, shadowRadius: 20, elevation: 30,
  },
  dropdownHandle: {
    width: 36, height: 4, borderRadius: 2,
    backgroundColor: colors.white10,
    alignSelf: "center", marginTop: 10, marginBottom: 12,
  },
  dropdownTitle: {
    fontSize: 11, fontWeight: "700", color: colors.labelTertiary,
    textTransform: "uppercase", letterSpacing: 1,
    paddingHorizontal: 8, paddingVertical: 6,
  },
  dropdownDivider: {
    height: 1, backgroundColor: colors.separator,
    marginHorizontal: 8, marginVertical: 6,
  },
  dropdownItem: {
    flexDirection: "row", alignItems: "center", gap: 10,
    paddingHorizontal: 12, paddingVertical: 12,
    borderRadius: radius.sm,
  },
  dropdownItemActive: { backgroundColor: colors.accentSubtle },
  dropdownItemThinkActive: { backgroundColor: colors.violetSubtle },
  dropdownItemText: { fontSize: 15, fontWeight: "500", color: colors.label, flex: 1 },
  dropdownItemTextActive: { color: colors.accent, fontWeight: "600" },
  dropdownItemDesc: { fontSize: 12, color: colors.labelTertiary, marginTop: 1 },

  // ── Agent icon in dropdown ──
  agentIconSmall: {
    width: 20, height: 20, borderRadius: 6,
    alignItems: "center", justifyContent: "center",
  },
  agentCategoryBadge: {
    alignSelf: "flex-start",
    borderRadius: radius.full,
    paddingHorizontal: 6, paddingVertical: 1,
    marginTop: 3,
  },
  agentCategoryText: { fontSize: 10, fontWeight: "700" },
});
