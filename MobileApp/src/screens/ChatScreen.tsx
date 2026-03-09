import React, { useState, useRef, useEffect, useCallback } from "react";
import {
  View, Text, TextInput, TouchableOpacity, FlatList, StyleSheet,
  KeyboardAvoidingView, Platform, ActivityIndicator, Image,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { colors, spacing, radius } from "../theme/colors";
import { streamChat, loadMessages, setDefaultAI, setThinking, setMoodSetting } from "../lib/api";
import type { Message, StreamChunk, Agent } from "../lib/types";
import { IconSend, IconStop, IconMenu, IconBrain, IconCopy, IconCheck, IconSliders, IconAttach, IconX, IconChevronDown } from "../components/Icons";
import { ProviderBadge, ProviderDot, getProviderColor } from "../components/ProviderIcon";
import { ThinkingWordAnimation, ThinkingDots } from "../components/ThinkingIndicator";
import * as Clipboard from "expo-clipboard";
import * as ImagePicker from "expo-image-picker";
import { PixelSprites } from "../components/PixelSprites";
import MarkdownContent from "../components/MarkdownContent";

const PROVIDERS = [
  { key: "claude", label: "Claude" },
  { key: "gemini", label: "Gemini" },
  { key: "openrouter", label: "OpenRouter" },
  { key: "ollama", label: "Local" },
];

const THINKING_LEVELS = ["off", "minimal", "low", "medium", "high", "xhigh"];
const MOODS = ["normal", "friendly", "serious"];

interface Props {
  conversationId?: string;
  onConversationCreated?: (id: string) => void;
  provider?: string;
  thinkingLevel?: string;
  mood?: string;
  agents?: Agent[];
  onOpenDrawer?: () => void;
  onProviderChange?: (p: string) => void;
  onThinkingChange?: (t: string) => void;
  onMoodChange?: (m: string) => void;
}

export default function ChatScreen({
  conversationId, onConversationCreated, provider = "claude",
  thinkingLevel = "off", mood = "normal", agents = [],
  onOpenDrawer, onProviderChange, onThinkingChange, onMoodChange,
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
  const [showToolbar, setShowToolbar] = useState(false);
  const [dropdown, setDropdown] = useState<"provider" | "thinking" | "mood" | "agent" | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [selectedAgent, setSelectedAgent] = useState<string | undefined>();
  const [inputFocused, setInputFocused] = useState(false);
  const [pendingImage, setPendingImage] = useState<{ uri: string; base64: string; mime: string } | null>(null);
  const flatListRef = useRef<FlatList>(null);
  const stopRef = useRef<(() => void) | null>(null);
  const convIdRef = useRef(conversationId);

  useEffect(() => {
    convIdRef.current = conversationId;
    if (conversationId) {
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
        .catch(() => {});
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
    setShowToolbar(false);

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

    let thinkAcc = "";
    let textAcc = "";
    let toolsDone: string[] = [];
    let finalConvId = convIdRef.current;

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
      () => {
        setStreaming(false);
        setStreamContent("");
        setStreamThinking("");
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

  const showThinking = thinkingLevel !== "off";

  function renderMessage({ item }: { item: Message }) {
    const isUser = item.role === "user";
    return (
      <View style={[styles.msgRow, isUser && styles.msgRowUser]}>
        {!isUser && (
          <View style={styles.avatarAssistant}>
            <Text style={styles.avatarText}>A</Text>
          </View>
        )}
        <View style={{ maxWidth: "82%", gap: 4 }}>
          <View style={[styles.bubble, isUser ? styles.bubbleUser : styles.bubbleAssistant]}>
            {/* Image attachment */}
            {item.imageUri && (
              <Image
                source={{ uri: item.imageUri }}
                style={styles.msgImage}
                resizeMode="cover"
              />
            )}
            {/* Thinking block */}
            {item.thinking && showThinking && (
              <View style={styles.thinkingBlock}>
                <View style={styles.thinkingHeader}>
                  <IconBrain size={11} color={colors.violet} />
                  <Text style={styles.thinkingLabel}>Thought</Text>
                </View>
                <Text style={styles.thinkingText} numberOfLines={6}>
                  {item.thinking}
                </Text>
              </View>
            )}
            {/* Completed tool pills */}
            {item.completedTools.length > 0 && (
              <View style={styles.toolRow}>
                {item.completedTools.map((t, i) => (
                  <View key={`${t}-${i}`} style={styles.toolPillDone}>
                    <View style={styles.toolDot} />
                    <Text style={styles.toolPillDoneText}>{t}</Text>
                  </View>
                ))}
              </View>
            )}
            {isUser ? (
              <Text style={[styles.msgText, styles.msgTextUser]} selectable>
                {item.content}
              </Text>
            ) : (
              <MarkdownContent>{item.content}</MarkdownContent>
            )}
          </View>
          {/* Message footer */}
          {!isUser && (
            <View style={styles.msgFooter}>
              {item.provider && <ProviderBadge provider={item.provider} size="sm" />}
              <TouchableOpacity
                style={styles.copyBtn}
                onPress={() => copyText(item.id, item.content)}
              >
                {copiedId === item.id
                  ? <IconCheck size={12} color={colors.success} />
                  : <IconCopy size={12} color={colors.labelTertiary} />
                }
              </TouchableOpacity>
            </View>
          )}
        </View>
      </View>
    );
  }

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
      keyboardVerticalOffset={0}
    >
      {/* Header */}
      <View style={[styles.header, { paddingTop: insets.top + 4 }]}>
        <TouchableOpacity style={styles.menuBtn} onPress={onOpenDrawer} activeOpacity={0.7}>
          <IconMenu size={22} color={colors.label} />
        </TouchableOpacity>

        {/* Compact header selectors */}
        <View style={styles.headerSelectors}>
          {/* Provider dropdown trigger */}
          <TouchableOpacity
            style={[styles.headerPill, dropdown === "provider" && styles.headerPillActive]}
            onPress={() => setDropdown(dropdown === "provider" ? null : "provider")}
            activeOpacity={0.7}
          >
            <ProviderDot provider={provider} size={7} />
            <Text style={styles.headerPillText}>
              {PROVIDERS.find(p => p.key === provider)?.label || provider}
            </Text>
            <IconChevronDown size={12} color={colors.labelTertiary} />
          </TouchableOpacity>

          {/* Thinking badge */}
          <TouchableOpacity
            style={[
              styles.headerPill,
              thinkingLevel !== "off" ? styles.headerPillThink : {},
              dropdown === "thinking" && styles.headerPillActive,
            ]}
            onPress={() => setDropdown(dropdown === "thinking" ? null : "thinking")}
            activeOpacity={0.7}
          >
            <IconBrain size={11} color={thinkingLevel !== "off" ? colors.violet : colors.labelTertiary} />
            {thinkingLevel !== "off" && (
              <Text style={[styles.headerPillText, { color: colors.violet, fontSize: 11 }]}>
                {thinkingLevel === "xhigh" ? "max" : thinkingLevel}
              </Text>
            )}
          </TouchableOpacity>

          {/* Agent badge */}
          {selectedAgent && (
            <TouchableOpacity
              style={[styles.headerPill, dropdown === "agent" && styles.headerPillActive]}
              onPress={() => setDropdown(dropdown === "agent" ? null : "agent")}
              activeOpacity={0.7}
            >
              <Text style={{ fontSize: 12 }}>
                {agents.find(a => a.id === selectedAgent)?.icon || "\uD83E\uDD16"}
              </Text>
              <Text style={[styles.headerPillText, { fontSize: 11 }]} numberOfLines={1}>
                {agents.find(a => a.id === selectedAgent)?.name || "Agent"}
              </Text>
            </TouchableOpacity>
          )}
        </View>

        <TouchableOpacity style={styles.toolbarToggle} onPress={() => { setShowToolbar(!showToolbar); setDropdown(null); }} activeOpacity={0.7}>
          <IconSliders size={18} color={showToolbar ? colors.accent : colors.labelSecondary} />
        </TouchableOpacity>
      </View>

      {/* Dropdown menus */}
      {dropdown && (
        <View style={styles.dropdownOverlay}>
          <TouchableOpacity style={{ flex: 1 }} onPress={() => setDropdown(null)} activeOpacity={1} />
          <View style={styles.dropdownMenu}>
            {dropdown === "provider" && (
              <>
                <Text style={styles.dropdownTitle}>AI Provider</Text>
                {PROVIDERS.map((p) => (
                  <TouchableOpacity
                    key={p.key}
                    style={[styles.dropdownItem, provider === p.key && styles.dropdownItemActive]}
                    onPress={() => { onProviderChange?.(p.key); setDefaultAI(p.key).catch(() => {}); setDropdown(null); }}
                    activeOpacity={0.7}
                  >
                    <ProviderDot provider={p.key} size={8} />
                    <Text style={[styles.dropdownItemText, provider === p.key && styles.dropdownItemTextActive]}>{p.label}</Text>
                    {provider === p.key && <IconCheck size={14} color={colors.accent} />}
                  </TouchableOpacity>
                ))}
              </>
            )}
            {dropdown === "thinking" && (
              <>
                <Text style={styles.dropdownTitle}>Thinking Level</Text>
                {THINKING_LEVELS.map((t) => (
                  <TouchableOpacity
                    key={t}
                    style={[styles.dropdownItem, thinkingLevel === t && styles.dropdownItemThinkActive]}
                    onPress={() => { onThinkingChange?.(t); setThinking(t).catch(() => {}); setDropdown(null); }}
                    activeOpacity={0.7}
                  >
                    {t !== "off" && <IconBrain size={12} color={thinkingLevel === t ? colors.violet : colors.labelTertiary} />}
                    <Text style={[styles.dropdownItemText, thinkingLevel === t && { color: colors.violet, fontWeight: "700" }]}>
                      {t === "xhigh" ? "Maximum" : t.charAt(0).toUpperCase() + t.slice(1)}
                    </Text>
                    {thinkingLevel === t && <IconCheck size={14} color={colors.violet} />}
                  </TouchableOpacity>
                ))}
              </>
            )}
            {dropdown === "agent" && (
              <>
                <Text style={styles.dropdownTitle}>Agent</Text>
                <TouchableOpacity
                  style={[styles.dropdownItem, !selectedAgent && styles.dropdownItemActive]}
                  onPress={() => { setSelectedAgent(undefined); setDropdown(null); }}
                  activeOpacity={0.7}
                >
                  <Text style={[styles.dropdownItemText, !selectedAgent && styles.dropdownItemTextActive]}>None (default)</Text>
                  {!selectedAgent && <IconCheck size={14} color={colors.accent} />}
                </TouchableOpacity>
                {agents.map((a) => (
                  <TouchableOpacity
                    key={a.id}
                    style={[styles.dropdownItem, selectedAgent === a.id && styles.dropdownItemActive]}
                    onPress={() => { setSelectedAgent(a.id); setDropdown(null); }}
                    activeOpacity={0.7}
                  >
                    <Text style={{ fontSize: 16 }}>{a.icon || "\uD83E\uDD16"}</Text>
                    <Text style={[styles.dropdownItemText, selectedAgent === a.id && styles.dropdownItemTextActive]}>{a.name}</Text>
                    {selectedAgent === a.id && <IconCheck size={14} color={colors.accent} />}
                  </TouchableOpacity>
                ))}
              </>
            )}
          </View>
        </View>
      )}

      {/* Quick toolbar (expanded settings panel) */}
      {showToolbar && !dropdown && (
        <View style={styles.toolbar}>
          {/* Provider */}
          <View style={styles.toolbarSection}>
            <Text style={styles.toolbarLabel}>Provider</Text>
            <View style={styles.toolbarChips}>
              {PROVIDERS.map((p) => (
                <TouchableOpacity
                  key={p.key}
                  style={[styles.toolbarChip, provider === p.key && styles.toolbarChipActive]}
                  onPress={() => { onProviderChange?.(p.key); setDefaultAI(p.key).catch(() => {}); }}
                  activeOpacity={0.7}
                >
                  <ProviderDot provider={p.key} size={6} />
                  <Text style={[styles.toolbarChipText, provider === p.key && styles.toolbarChipTextActive]}>{p.label}</Text>
                </TouchableOpacity>
              ))}
            </View>
          </View>
          {/* Thinking */}
          <View style={styles.toolbarSection}>
            <Text style={styles.toolbarLabel}>Thinking</Text>
            <View style={styles.toolbarChips}>
              {THINKING_LEVELS.map((t) => (
                <TouchableOpacity
                  key={t}
                  style={[styles.toolbarChip, thinkingLevel === t && styles.toolbarChipThinkActive]}
                  onPress={() => { onThinkingChange?.(t); setThinking(t).catch(() => {}); }}
                  activeOpacity={0.7}
                >
                  <Text style={[styles.toolbarChipText, thinkingLevel === t && { color: colors.violet }]}>
                    {t === "xhigh" ? "max" : t}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>
          </View>
          {/* Mood */}
          <View style={styles.toolbarSection}>
            <Text style={styles.toolbarLabel}>Mood</Text>
            <View style={styles.toolbarChips}>
              {MOODS.map((m) => (
                <TouchableOpacity
                  key={m}
                  style={[styles.toolbarChip, mood === m && styles.toolbarChipActive]}
                  onPress={() => { onMoodChange?.(m); setMoodSetting(m).catch(() => {}); }}
                  activeOpacity={0.7}
                >
                  <Text style={[styles.toolbarChipText, mood === m && styles.toolbarChipTextActive]}>{m}</Text>
                </TouchableOpacity>
              ))}
            </View>
          </View>
          {/* Agents */}
          {agents.length > 0 && (
            <View style={styles.toolbarSection}>
              <Text style={styles.toolbarLabel}>Agent</Text>
              <View style={styles.toolbarChips}>
                <TouchableOpacity
                  style={[styles.toolbarChip, !selectedAgent && styles.toolbarChipActive]}
                  onPress={() => setSelectedAgent(undefined)}
                  activeOpacity={0.7}
                >
                  <Text style={[styles.toolbarChipText, !selectedAgent && styles.toolbarChipTextActive]}>None</Text>
                </TouchableOpacity>
                {agents.map((a) => (
                  <TouchableOpacity
                    key={a.id}
                    style={[styles.toolbarChip, selectedAgent === a.id && styles.toolbarChipActive]}
                    onPress={() => setSelectedAgent(a.id)}
                    activeOpacity={0.7}
                  >
                    <Text style={{ fontSize: 12 }}>{a.icon || "\uD83E\uDD16"}</Text>
                    <Text style={[styles.toolbarChipText, selectedAgent === a.id && styles.toolbarChipTextActive]}>{a.name}</Text>
                  </TouchableOpacity>
                ))}
              </View>
            </View>
          )}
        </View>
      )}

      {/* Messages */}
      <FlatList
        ref={flatListRef}
        data={messages}
        renderItem={renderMessage}
        keyExtractor={(m) => m.id}
        contentContainerStyle={styles.list}
        onContentSizeChange={scrollToEnd}
        ListEmptyComponent={
          <View style={styles.empty}>
            <PixelSprites />
            <View style={styles.emptyContent}>
              <View style={styles.emptyLogo}>
                <Image source={require("../../assets/appicon.png")} style={{ width: 56, height: 56, borderRadius: 14 }} />
              </View>
              <Text style={styles.emptyTitle}>What can I help with?</Text>
              <Text style={styles.emptySubtitle}>Ask anything, or try a suggestion</Text>
              {/* Suggestion chips */}
              <View style={styles.suggestions}>
                {agents.slice(0, 4).map((a) => (
                  <TouchableOpacity
                    key={a.id}
                    style={styles.suggestionChip}
                    onPress={() => { setSelectedAgent(a.id); }}
                    activeOpacity={0.7}
                  >
                    <Text style={styles.suggestionText}>{a.name}</Text>
                  </TouchableOpacity>
                ))}
                {agents.length === 0 && (
                  <>
                    <TouchableOpacity style={styles.suggestionChip} onPress={() => send("What's on my schedule today?")} activeOpacity={0.7}>
                      <Text style={styles.suggestionText}>My schedule today</Text>
                    </TouchableOpacity>
                    <TouchableOpacity style={styles.suggestionChip} onPress={() => send("Summarize my recent notes")} activeOpacity={0.7}>
                      <Text style={styles.suggestionText}>Summarize notes</Text>
                    </TouchableOpacity>
                  </>
                )}
              </View>
            </View>
          </View>
        }
        ListFooterComponent={
          streaming ? (
            <View style={styles.msgRow}>
              <View style={styles.avatarAssistant}>
                <Text style={styles.avatarText}>A</Text>
              </View>
              <View style={{ maxWidth: "82%", gap: 4 }}>
                <View style={[styles.bubble, styles.bubbleAssistant]}>
                  {/* Thinking stream */}
                  {streamThinking && showThinking ? (
                    <View style={styles.thinkingBlock}>
                      <View style={styles.thinkingHeader}>
                        <IconBrain size={11} color={colors.violet} />
                        <Text style={styles.thinkingLabel}>Thinking</Text>
                        <ThinkingDots color={colors.violet} />
                      </View>
                      <Text style={styles.thinkingText}>{streamThinking}</Text>
                    </View>
                  ) : null}
                  {/* Completed tools */}
                  {completedTools.length > 0 && (
                    <View style={styles.toolRow}>
                      {completedTools.map((t, i) => (
                        <View key={`${t}-${i}`} style={styles.toolPillDone}>
                          <View style={styles.toolDot} />
                          <Text style={styles.toolPillDoneText}>{t}</Text>
                        </View>
                      ))}
                    </View>
                  )}
                  {/* Active tools */}
                  {activeTools.length > 0 && (
                    <View style={styles.toolRow}>
                      {activeTools.map((t) => (
                        <View key={t} style={styles.toolPillActive}>
                          <ActivityIndicator size={8} color={colors.accent} />
                          <Text style={styles.toolPillActiveText}>{t}</Text>
                        </View>
                      ))}
                    </View>
                  )}
                  {/* Status text */}
                  {statusText && !streamContent ? (
                    <View style={styles.statusLine}>
                      <ActivityIndicator size={8} color={colors.labelTertiary} />
                      <Text style={styles.statusLineText}>{statusText}</Text>
                    </View>
                  ) : null}
                  {/* Content stream */}
                  {streamContent ? (
                    <MarkdownContent>{streamContent}</MarkdownContent>
                  ) : !streamThinking && activeTools.length === 0 && !statusText ? (
                    <ThinkingWordAnimation />
                  ) : null}
                </View>
              </View>
            </View>
          ) : null
        }
      />

      {/* Input bar */}
      <View style={[styles.inputBar, { paddingBottom: Math.max(insets.bottom, 8) }]}>
        {/* Pending image preview */}
        {pendingImage && (
          <View style={styles.pendingImageRow}>
            <View style={styles.pendingImageWrap}>
              <Image source={{ uri: pendingImage.uri }} style={styles.pendingImageThumb} />
              <TouchableOpacity
                style={styles.pendingImageRemove}
                onPress={() => setPendingImage(null)}
                activeOpacity={0.7}
              >
                <IconX size={10} color="#fff" />
              </TouchableOpacity>
            </View>
          </View>
        )}
        <View style={styles.inputRow}>
          <TouchableOpacity
            style={styles.attachBtn}
            onPress={pickImage}
            disabled={streaming}
            activeOpacity={0.7}
          >
            <IconAttach size={20} color={pendingImage ? colors.accent : colors.labelTertiary} />
          </TouchableOpacity>
          <TextInput
            style={[styles.textInput, inputFocused && styles.textInputFocused]}
            value={input}
            onChangeText={setInput}
            placeholder={selectedAgent ? `Message @${agents.find(a => a.id === selectedAgent)?.name || "agent"}...` : "Ask anything..."}
            placeholderTextColor={colors.labelTertiary}
            multiline
            maxLength={10000}
            editable={!streaming}
            onSubmitEditing={() => send()}
            blurOnSubmit={false}
            onFocus={() => setInputFocused(true)}
            onBlur={() => setInputFocused(false)}
          />
          <TouchableOpacity
            style={[styles.sendBtn, streaming ? styles.stopBtn : (!input.trim() && !pendingImage ? styles.sendBtnDisabled : {})]}
            onPress={streaming ? () => stopRef.current?.() : () => send()}
            disabled={!input.trim() && !pendingImage && !streaming}
            activeOpacity={0.7}
          >
            {streaming ? <IconStop size={18} color={colors.danger} /> : <IconSend size={18} color="#fff" />}
          </TouchableOpacity>
        </View>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface },

  // Header
  header: {
    flexDirection: "row", alignItems: "center",
    paddingBottom: 8, paddingHorizontal: spacing.md,
    backgroundColor: colors.surface,
  },
  menuBtn: { padding: 6, marginRight: 4 },
  headerSelectors: {
    flex: 1, flexDirection: "row", alignItems: "center",
    gap: 6, flexWrap: "nowrap",
  },
  headerPill: {
    flexDirection: "row", alignItems: "center", gap: 4,
    backgroundColor: colors.white05,
    borderRadius: radius.full,
    paddingHorizontal: 10, paddingVertical: 5,
    borderWidth: 1, borderColor: colors.separator,
  },
  headerPillActive: { borderColor: colors.accent + "60" },
  headerPillThink: {
    backgroundColor: colors.violetSubtle,
    borderColor: "rgba(139,92,246,0.15)",
  },
  headerPillText: { fontSize: 12, fontWeight: "600", color: colors.label },
  toolbarToggle: { padding: 6 },

  // Dropdown
  dropdownOverlay: {
    position: "absolute", top: 0, left: 0, right: 0, bottom: 0,
    zIndex: 100, backgroundColor: "rgba(0,0,0,0.25)",
  },
  dropdownMenu: {
    position: "absolute", top: 8, left: spacing.md, right: spacing.md,
    backgroundColor: colors.surfaceRaised,
    borderRadius: radius.md,
    borderWidth: 1, borderColor: colors.separator,
    padding: spacing.sm,
    shadowColor: "#000", shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.3, shadowRadius: 20, elevation: 30,
  },
  dropdownTitle: {
    fontSize: 11, fontWeight: "700", color: colors.labelTertiary,
    textTransform: "uppercase", letterSpacing: 1,
    paddingHorizontal: 8, paddingVertical: 6,
  },
  dropdownItem: {
    flexDirection: "row", alignItems: "center", gap: 10,
    paddingHorizontal: 12, paddingVertical: 11,
    borderRadius: radius.sm,
  },
  dropdownItemActive: { backgroundColor: colors.accentSubtle },
  dropdownItemThinkActive: { backgroundColor: colors.violetSubtle },
  dropdownItemText: { fontSize: 14, fontWeight: "500", color: colors.label, flex: 1 },
  dropdownItemTextActive: { color: colors.accent, fontWeight: "600" },

  // Toolbar
  toolbar: {
    backgroundColor: colors.surfaceRaised,
    borderBottomWidth: 1, borderBottomColor: colors.separator,
    paddingHorizontal: spacing.md, paddingVertical: spacing.sm,
    gap: spacing.sm,
  },
  toolbarSection: { gap: 4 },
  toolbarLabel: { fontSize: 10, fontWeight: "700", color: colors.labelTertiary, textTransform: "uppercase", letterSpacing: 0.8 },
  toolbarChips: { flexDirection: "row", flexWrap: "wrap", gap: 4 },
  toolbarChip: {
    flexDirection: "row", alignItems: "center", gap: 4,
    backgroundColor: colors.white05,
    borderRadius: radius.full,
    paddingHorizontal: 10, paddingVertical: 5,
    borderWidth: 1, borderColor: colors.separator,
  },
  toolbarChipActive: { backgroundColor: colors.accentSubtle, borderColor: colors.accent },
  toolbarChipThinkActive: { backgroundColor: colors.violetSubtle, borderColor: colors.violet },
  toolbarChipText: { fontSize: 11, fontWeight: "600", color: colors.labelSecondary, textTransform: "capitalize" },
  toolbarChipTextActive: { color: colors.accent },

  // Messages
  list: { padding: spacing.md, paddingBottom: spacing.xxl, flexGrow: 1 },
  empty: { flex: 1, minHeight: 400, justifyContent: "center", alignItems: "center" },
  emptyContent: { alignItems: "center", zIndex: 1 },
  emptyLogo: {
    marginBottom: spacing.lg,
    shadowColor: colors.accent,
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.15,
    shadowRadius: 32,
    elevation: 10,
  },
  emptyTitle: { fontSize: 24, fontWeight: "700", color: colors.label, marginBottom: spacing.xs },
  emptySubtitle: { fontSize: 15, color: colors.labelTertiary, marginBottom: spacing.xl },
  suggestions: { flexDirection: "row", flexWrap: "wrap", justifyContent: "center", gap: spacing.sm },
  suggestionChip: {
    backgroundColor: colors.white08,
    borderRadius: radius.full,
    paddingHorizontal: 16, paddingVertical: 10,
    borderWidth: 1, borderColor: colors.separator,
  },
  suggestionText: { fontSize: 13, fontWeight: "500", color: colors.labelSecondary },

  msgRow: { flexDirection: "row", alignItems: "flex-start", marginBottom: spacing.md, gap: 8 },
  msgRowUser: { justifyContent: "flex-end" },
  avatarAssistant: {
    width: 28, height: 28, borderRadius: 14,
    backgroundColor: colors.accentSubtle,
    alignItems: "center", justifyContent: "center",
    marginTop: 2,
  },
  avatarText: { fontSize: 12, fontWeight: "700", color: colors.accent },
  bubble: { borderRadius: radius.lg, padding: spacing.md },
  bubbleUser: { backgroundColor: colors.userBubble, borderBottomRightRadius: 4 },
  bubbleAssistant: {
    backgroundColor: colors.surfaceRaised,
    borderBottomLeftRadius: 4,
    borderWidth: 1, borderColor: colors.separator,
  },
  msgImage: {
    width: "100%", height: 180,
    borderRadius: radius.md,
    marginBottom: spacing.sm,
  },
  msgText: { fontSize: 15, lineHeight: 22, color: colors.label },
  msgTextUser: { color: colors.userBubbleText },

  // Message footer
  msgFooter: { flexDirection: "row", alignItems: "center", gap: 8, paddingLeft: 4 },
  copyBtn: { padding: 4 },

  // Thinking
  thinkingBlock: {
    backgroundColor: colors.violetSubtle,
    borderRadius: radius.sm,
    padding: spacing.sm,
    marginBottom: spacing.sm,
    borderWidth: 1, borderColor: "rgba(139,92,246,0.15)",
  },
  thinkingHeader: { flexDirection: "row", alignItems: "center", gap: 4, marginBottom: 4 },
  thinkingLabel: { fontSize: 10, fontWeight: "700", color: colors.violet, textTransform: "uppercase", letterSpacing: 0.5 },
  thinkingText: { fontSize: 12, lineHeight: 18, color: colors.violetText },

  // Tools
  toolRow: { flexDirection: "row", flexWrap: "wrap", gap: 4, marginBottom: spacing.sm },
  toolPillDone: {
    flexDirection: "row", alignItems: "center", gap: 4,
    backgroundColor: colors.white04,
    borderWidth: 1, borderColor: colors.separator,
    borderRadius: radius.full, paddingHorizontal: 10, paddingVertical: 3,
  },
  toolDot: { width: 5, height: 5, borderRadius: 2.5, backgroundColor: colors.success },
  toolPillDoneText: { fontSize: 10, color: colors.labelSecondary, fontWeight: "500" },
  toolPillActive: {
    flexDirection: "row", alignItems: "center", gap: 4,
    backgroundColor: colors.accentGlow,
    borderWidth: 1, borderColor: "rgba(255,107,44,0.2)",
    borderRadius: radius.full, paddingHorizontal: 10, paddingVertical: 3,
  },
  toolPillActiveText: { fontSize: 10, color: colors.accent, fontWeight: "600" },

  // Status
  statusLine: { flexDirection: "row", alignItems: "center", gap: 6, paddingVertical: 2 },
  statusLineText: { fontSize: 11, color: colors.labelTertiary, fontStyle: "italic" },

  // Input bar
  inputBar: {
    paddingHorizontal: spacing.md,
    paddingTop: spacing.sm,
  },
  thinkingBadge: {
    flexDirection: "row", alignItems: "center", gap: 4,
    alignSelf: "flex-start",
    backgroundColor: colors.violetSubtle,
    borderRadius: radius.full,
    paddingHorizontal: 8, paddingVertical: 2,
    marginBottom: 4,
    borderWidth: 1, borderColor: "rgba(139,92,246,0.15)",
  },
  thinkingBadgeText: { fontSize: 10, color: colors.violet, fontWeight: "600", textTransform: "capitalize" },
  pendingImageRow: {
    flexDirection: "row",
    paddingBottom: spacing.sm,
  },
  pendingImageWrap: {
    position: "relative",
  },
  pendingImageThumb: {
    width: 64, height: 64,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.separator,
  },
  pendingImageRemove: {
    position: "absolute", top: -6, right: -6,
    width: 20, height: 20, borderRadius: 10,
    backgroundColor: colors.danger,
    alignItems: "center", justifyContent: "center",
  },
  attachBtn: {
    padding: 6,
  },
  inputRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  textInput: {
    flex: 1,
    backgroundColor: colors.white05,
    borderRadius: radius.xl,
    paddingHorizontal: spacing.lg,
    paddingVertical: 10,
    fontSize: 15,
    color: colors.label,
    maxHeight: 120,
    borderWidth: 1, borderColor: colors.separator,
  },
  textInputFocused: {
    borderColor: "rgba(255,107,44,0.5)",
  },
  sendBtn: {
    width: 40, height: 40, borderRadius: 10,
    backgroundColor: colors.accent,
    alignItems: "center", justifyContent: "center",
  },
  stopBtn: { backgroundColor: colors.dangerSubtle },
  sendBtnDisabled: { opacity: 0.3 },
});
