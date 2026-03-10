import React, { useState, useRef, useEffect, useCallback } from "react";
import {
  View, Text, TextInput, TouchableOpacity, FlatList, StyleSheet,
  KeyboardAvoidingView, Platform, ActivityIndicator, Image,
  ScrollView,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { colors, spacing, radius } from "../theme/colors";
import { streamChat, loadMessages, setDefaultAI, setThinking, setMoodSetting, truncateConversation } from "../lib/api";
import type { Message, StreamChunk, Agent } from "../lib/types";
import {
  IconSend, IconStop, IconMenu, IconBrain, IconCopy, IconCheck,
  IconSliders, IconAttach, IconX, IconChevronDown, IconAgents, IconEdit,
  resolveAgentIcon,
} from "../components/Icons";
import { ProviderBadge, ProviderDot } from "../components/ProviderIcon";
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
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [selectedAgent, setSelectedAgent] = useState<string | undefined>();
  const [inputFocused, setInputFocused] = useState(false);
  const [pendingImage, setPendingImage] = useState<{ uri: string; base64: string; mime: string } | null>(null);
  const [showScrollBtn, setShowScrollBtn] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editText, setEditText] = useState("");
  const [errorMsg, setErrorMsg] = useState("");
  const [loadingMsgs, setLoadingMsgs] = useState(false);
  // Dropdown state: which menu is open (anchored to input bar)
  const [dropdown, setDropdown] = useState<"provider" | "thinking" | "mood" | "agent" | null>(null);
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

  const showThinking = thinkingLevel !== "off";
  const activeAgent = agents.find(a => a.id === selectedAgent);

  function renderMessage({ item }: { item: Message }) {
    const isUser = item.role === "user";
    const isEditing = editingId === item.id;
    return (
      <View style={[styles.msgRow, isUser && styles.msgRowUser]}>
        {!isUser && (
          <View style={styles.avatarAssistant}>
            <Text style={styles.avatarText}>A</Text>
          </View>
        )}
        <View style={{ maxWidth: "82%", gap: 4 }}>
          <View style={[styles.bubble, isUser ? styles.bubbleUser : styles.bubbleAssistant]}>
            {item.imageUri && (
              <Image source={{ uri: item.imageUri }} style={styles.msgImage} resizeMode="cover" />
            )}
            {item.thinking && showThinking && (
              <View style={styles.thinkingBlock}>
                <View style={styles.thinkingHeader}>
                  <IconBrain size={11} color={colors.violet} />
                  <Text style={styles.thinkingLabel}>Thought</Text>
                </View>
                <Text style={styles.thinkingText} numberOfLines={8}>{item.thinking}</Text>
              </View>
            )}
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
            {isUser && isEditing ? (
              <View style={styles.editBlock}>
                <TextInput
                  style={styles.editInput}
                  value={editText}
                  onChangeText={setEditText}
                  multiline
                  autoFocus
                />
                <View style={styles.editActions}>
                  <TouchableOpacity onPress={cancelEdit} activeOpacity={0.7}>
                    <Text style={styles.editCancelText}>Cancel</Text>
                  </TouchableOpacity>
                  <TouchableOpacity style={styles.editSaveBtn} onPress={submitEdit} activeOpacity={0.7}>
                    <Text style={styles.editSaveText}>Save & Send</Text>
                  </TouchableOpacity>
                </View>
              </View>
            ) : isUser ? (
              <Text style={[styles.msgText, styles.msgTextUser]} selectable>{item.content}</Text>
            ) : (
              <MarkdownContent>{item.content}</MarkdownContent>
            )}
          </View>
          {isUser && !isEditing && !streaming && (
            <View style={styles.msgFooter}>
              <TouchableOpacity style={styles.copyBtn} onPress={() => startEdit(item)}>
                <IconEdit size={12} color={colors.labelTertiary} />
              </TouchableOpacity>
            </View>
          )}
          {!isUser && (
            <View style={styles.msgFooter}>
              {item.provider && <ProviderBadge provider={item.provider} size="sm" />}
              <TouchableOpacity style={styles.copyBtn} onPress={() => copyText(item.id, item.content)}>
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

  // Track if user is near bottom for scroll-to-bottom FAB
  function handleScroll(e: any) {
    const { contentOffset, contentSize, layoutMeasurement } = e.nativeEvent;
    const distanceFromBottom = contentSize.height - layoutMeasurement.height - contentOffset.y;
    setShowScrollBtn(distanceFromBottom > 200);
  }

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
      keyboardVerticalOffset={0}
    >
      {/* ── Header ── */}
      <View style={[styles.header, { paddingTop: insets.top + 4 }]}>
        <TouchableOpacity style={styles.menuBtn} onPress={onOpenDrawer} activeOpacity={0.7}>
          <IconMenu size={22} color={colors.label} />
        </TouchableOpacity>

        <Text style={styles.headerTitle}>Asta</Text>

        {/* Thinking badge in header (like desktop brain indicator) */}
        {thinkingLevel !== "off" && (
          <View style={styles.thinkingIndicator}>
            <IconBrain size={12} color={colors.violet} />
            <Text style={styles.thinkingIndicatorText}>
              {thinkingLevel === "xhigh" ? "max" : thinkingLevel}
            </Text>
          </View>
        )}

        {/* Settings menu (thinking + mood) */}
        <TouchableOpacity
          style={[styles.headerBtn, dropdown === "thinking" && { backgroundColor: colors.white08 }]}
          onPress={() => setDropdown(dropdown === "thinking" ? null : "thinking")}
          activeOpacity={0.7}
        >
          <IconSliders size={16} color={dropdown === "thinking" ? colors.accent : colors.labelSecondary} />
          <IconChevronDown size={10} color={colors.labelTertiary} />
        </TouchableOpacity>
      </View>

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
        onContentSizeChange={scrollToEnd}
        onScroll={handleScroll}
        scrollEventThrottle={100}
        ListEmptyComponent={
          loadingMsgs ? (
            <View style={styles.loadingCenter}>
              <ActivityIndicator size="small" color={colors.accent} />
              <Text style={styles.loadingText}>Loading messages...</Text>
            </View>
          ) : (
          <View style={styles.empty}>
            <PixelSprites />
            <View style={styles.emptyContent}>
              <View style={styles.emptyLogo}>
                <Image source={require("../../assets/appicon.png")} style={{ width: 56, height: 56, borderRadius: 14 }} />
              </View>
              <Text style={styles.emptyTitle}>What can I help with?</Text>
              <Text style={styles.emptySubtitle}>Ask anything, or try a suggestion</Text>
              <View style={styles.suggestions}>
                {agents.slice(0, 4).map((a) => {
                  const ai = resolveAgentIcon(a);
                  return (
                    <TouchableOpacity key={a.id} style={styles.agentCard}
                      onPress={() => { setSelectedAgent(a.id); }}
                      activeOpacity={0.7}>
                      <View style={[styles.agentCardIcon, { backgroundColor: ai.bg }]}>
                        <ai.Icon size={15} color={ai.color} />
                      </View>
                      <Text style={styles.agentCardName} numberOfLines={1}>{a.name}</Text>
                    </TouchableOpacity>
                  );
                })}
                {agents.length === 0 && (
                  <>
                    <TouchableOpacity style={styles.suggestionChip} onPress={() => send("What's on my schedule today?")} activeOpacity={0.7}>
                      <Text style={styles.suggestionText}>My schedule today</Text>
                    </TouchableOpacity>
                    <TouchableOpacity style={styles.suggestionChip} onPress={() => send("Summarize my recent notes")} activeOpacity={0.7}>
                      <Text style={styles.suggestionText}>Summarize notes</Text>
                    </TouchableOpacity>
                    <TouchableOpacity style={styles.suggestionChip} onPress={() => send("What's the weather like?")} activeOpacity={0.7}>
                      <Text style={styles.suggestionText}>Check the weather</Text>
                    </TouchableOpacity>
                    <TouchableOpacity style={styles.suggestionChip} onPress={() => send("Write a quick email draft")} activeOpacity={0.7}>
                      <Text style={styles.suggestionText}>Draft an email</Text>
                    </TouchableOpacity>
                  </>
                )}
              </View>
            </View>
          </View>
          )
        }
        ListFooterComponent={
          streaming ? (
            <View style={styles.msgRow}>
              <View style={styles.avatarAssistant}>
                <Text style={styles.avatarText}>A</Text>
              </View>
              <View style={{ maxWidth: "82%", gap: 4 }}>
                <View style={[styles.bubble, styles.bubbleAssistant]}>
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
                  {activeTools.length > 0 && (
                    <View style={styles.toolRow}>
                      {activeTools.map((t) => (
                        <View key={t} style={styles.toolPillActive}>
                          <View style={{ transform: [{ scale: 0.5 }], width: 10, height: 10 }}>
                            <ActivityIndicator size="small" color={colors.accent} />
                          </View>
                          <Text style={styles.toolPillActiveText}>{t}</Text>
                        </View>
                      ))}
                    </View>
                  )}
                  {statusText && !streamContent ? (
                    <View style={styles.statusLine}>
                      <View style={{ transform: [{ scale: 0.5 }], width: 10, height: 10 }}>
                        <ActivityIndicator size="small" color={colors.labelTertiary} />
                      </View>
                      <Text style={styles.statusLineText}>{statusText}</Text>
                    </View>
                  ) : null}
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

      {/* ── Scroll-to-bottom FAB ── */}
      {showScrollBtn && !streaming && (
        <TouchableOpacity style={styles.scrollFab} onPress={scrollToEnd} activeOpacity={0.7}>
          <IconChevronDown size={16} color={colors.labelSecondary} />
        </TouchableOpacity>
      )}

      {/* ── Dropdown menus (anchored above input bar) ── */}
      {dropdown && (
        <View style={styles.dropdownOverlay}>
          <TouchableOpacity style={{ flex: 1 }} onPress={() => setDropdown(null)} activeOpacity={1} />
          <View style={styles.dropdownSheet}>
            <View style={styles.dropdownHandle} />
            <ScrollView style={{ maxHeight: 360 }} bounces={false}>
              {dropdown === "provider" && (
                <>
                  <Text style={styles.dropdownTitle}>AI Provider</Text>
                  {PROVIDERS.map((p) => (
                    <TouchableOpacity key={p.key}
                      style={[styles.dropdownItem, provider === p.key && styles.dropdownItemActive]}
                      onPress={() => { onProviderChange?.(p.key); setDefaultAI(p.key).catch(() => {}); setDropdown(null); }}
                      activeOpacity={0.7}>
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
                    <TouchableOpacity key={t}
                      style={[styles.dropdownItem, thinkingLevel === t && styles.dropdownItemThinkActive]}
                      onPress={() => { onThinkingChange?.(t); setThinking(t).catch(() => {}); setDropdown(null); }}
                      activeOpacity={0.7}>
                      {t !== "off" && <IconBrain size={12} color={thinkingLevel === t ? colors.violet : colors.labelTertiary} />}
                      <Text style={[styles.dropdownItemText, thinkingLevel === t && { color: colors.violet, fontWeight: "700" }]}>
                        {t === "xhigh" ? "Maximum" : t.charAt(0).toUpperCase() + t.slice(1)}
                      </Text>
                      {thinkingLevel === t && <IconCheck size={14} color={colors.violet} />}
                    </TouchableOpacity>
                  ))}
                  <View style={styles.dropdownDivider} />
                  <Text style={styles.dropdownTitle}>Mood</Text>
                  {MOODS.map((m) => (
                    <TouchableOpacity key={m}
                      style={[styles.dropdownItem, mood === m && styles.dropdownItemActive]}
                      onPress={() => { onMoodChange?.(m); setMoodSetting(m).catch(() => {}); setDropdown(null); }}
                      activeOpacity={0.7}>
                      <Text style={[styles.dropdownItemText, mood === m && styles.dropdownItemTextActive]}>
                        {m.charAt(0).toUpperCase() + m.slice(1)}
                      </Text>
                      {mood === m && <IconCheck size={14} color={colors.accent} />}
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
                </>
              )}
            </ScrollView>
          </View>
        </View>
      )}

      {/* ── Input bar ── */}
      <View style={[styles.inputBar, { paddingBottom: Math.max(insets.bottom, 8) }]}>
        {/* Pending image preview */}
        {pendingImage && (
          <View style={styles.pendingImageRow}>
            <View style={styles.pendingImageWrap}>
              <Image source={{ uri: pendingImage.uri }} style={styles.pendingImageThumb} />
              <TouchableOpacity style={styles.pendingImageRemove} onPress={() => setPendingImage(null)} activeOpacity={0.7}>
                <IconX size={10} color="#fff" />
              </TouchableOpacity>
            </View>
          </View>
        )}
        {/* Main input container (matches desktop rounded-2xl wrapper) */}
        <View style={[styles.inputContainer, inputFocused && styles.inputContainerFocused]}>
          <TextInput
            style={styles.textInput}
            value={input}
            onChangeText={setInput}
            placeholder={activeAgent ? `Message @${activeAgent.name}...` : "Ask anything..."}
            placeholderTextColor={colors.labelTertiary}
            multiline
            maxLength={10000}
            editable={!streaming}
            onSubmitEditing={() => send()}
            blurOnSubmit={false}
            onFocus={() => setInputFocused(true)}
            onBlur={() => setInputFocused(false)}
          />
          {/* Bottom toolbar row inside input container */}
          <View style={styles.inputToolbar}>
            {/* Left: attach + agent */}
            <View style={styles.inputToolbarLeft}>
              <TouchableOpacity style={styles.inputToolBtn} onPress={pickImage} disabled={streaming} activeOpacity={0.7}>
                <IconAttach size={18} color={pendingImage ? colors.accent : colors.labelTertiary} />
              </TouchableOpacity>
              {agents.length > 0 && (
                <TouchableOpacity
                  style={[styles.inputToolBtn, selectedAgent ? { backgroundColor: colors.accentSubtle } : {}]}
                  onPress={() => setDropdown(dropdown === "agent" ? null : "agent")}
                  activeOpacity={0.7}>
                  <IconAgents size={16} color={selectedAgent ? colors.accent : colors.labelTertiary} />
                </TouchableOpacity>
              )}
            </View>
            {/* Right: provider selector + send */}
            <View style={styles.inputToolbarRight}>
              <TouchableOpacity
                style={styles.providerSelector}
                onPress={() => setDropdown(dropdown === "provider" ? null : "provider")}
                activeOpacity={0.7}>
                <ProviderDot provider={provider} size={6} />
                <Text style={styles.providerSelectorText}>
                  {PROVIDERS.find(p => p.key === provider)?.label || provider}
                </Text>
                <IconChevronDown size={8} color={colors.labelTertiary} />
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.sendBtn, streaming ? styles.stopBtn : (!input.trim() && !pendingImage ? styles.sendBtnDisabled : {})]}
                onPress={streaming ? () => stopRef.current?.() : () => send()}
                disabled={!input.trim() && !pendingImage && !streaming}
                activeOpacity={0.7}>
                {streaming ? <IconStop size={16} color={colors.danger} /> : <IconSend size={16} color="#fff" />}
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </View>
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

  // ── Header ──
  header: {
    flexDirection: "row", alignItems: "center",
    paddingBottom: 8, paddingHorizontal: spacing.md,
    borderBottomWidth: 1, borderBottomColor: colors.separator,
  },
  menuBtn: { padding: 6, marginRight: 6 },
  headerTitle: { fontSize: 18, fontWeight: "700", color: colors.label, flex: 1 },
  thinkingIndicator: {
    flexDirection: "row", alignItems: "center", gap: 4,
    backgroundColor: colors.violetSubtle,
    borderRadius: radius.full,
    paddingHorizontal: 8, paddingVertical: 3,
    marginRight: 6,
    borderWidth: 1, borderColor: "rgba(139,92,246,0.15)",
  },
  thinkingIndicatorText: { fontSize: 10, fontWeight: "700", color: colors.violet, textTransform: "capitalize" },
  headerBtn: {
    flexDirection: "row", alignItems: "center", gap: 2,
    backgroundColor: colors.white05,
    borderRadius: radius.sm,
    paddingHorizontal: 8, paddingVertical: 6,
    borderWidth: 1, borderColor: colors.separator,
  },

  // ── Scroll-to-bottom FAB ──
  scrollFab: {
    position: "absolute", right: spacing.lg, bottom: 100,
    width: 36, height: 36, borderRadius: 18,
    backgroundColor: colors.surfaceRaised,
    borderWidth: 1, borderColor: colors.separatorBold,
    alignItems: "center", justifyContent: "center",
    shadowColor: "#000", shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.25, shadowRadius: 8, elevation: 10,
    zIndex: 20,
  },

  // ── Dropdown (bottom-sheet style) ──
  dropdownOverlay: {
    position: "absolute", top: 0, left: 0, right: 0, bottom: 0,
    zIndex: 100, backgroundColor: "rgba(0,0,0,0.3)",
    justifyContent: "flex-end",
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

  // ── Messages ──
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
  suggestions: { flexDirection: "row", flexWrap: "wrap", justifyContent: "center", gap: spacing.sm, maxWidth: 320 },
  suggestionChip: {
    flexDirection: "row", alignItems: "center", gap: 6,
    backgroundColor: colors.white05,
    borderRadius: radius.md,
    paddingHorizontal: 14, paddingVertical: 10,
    borderWidth: 1, borderColor: colors.separator,
  },
  suggestionText: { fontSize: 13, fontWeight: "500", color: colors.labelSecondary },

  msgRow: { flexDirection: "row", alignItems: "flex-start", marginBottom: spacing.md, gap: 8 },
  msgRowUser: { justifyContent: "flex-end" },
  avatarAssistant: {
    width: 28, height: 28, borderRadius: 8,
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

  msgFooter: { flexDirection: "row", alignItems: "center", gap: 8, paddingLeft: 4, marginTop: 2 },
  copyBtn: { padding: 4 },

  // ── Thinking ──
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

  // ── Tools ──
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

  statusLine: { flexDirection: "row", alignItems: "center", gap: 6, paddingVertical: 2 },
  statusLineText: { fontSize: 11, color: colors.labelTertiary, fontStyle: "italic" },

  // ── Input bar ──
  inputBar: {
    paddingHorizontal: spacing.md,
    paddingTop: spacing.sm,
  },
  pendingImageRow: { flexDirection: "row", paddingBottom: spacing.sm },
  pendingImageWrap: { position: "relative" },
  pendingImageThumb: {
    width: 64, height: 64, borderRadius: radius.md,
    borderWidth: 1, borderColor: colors.separator,
  },
  pendingImageRemove: {
    position: "absolute", top: -6, right: -6,
    width: 20, height: 20, borderRadius: 10,
    backgroundColor: colors.danger,
    alignItems: "center", justifyContent: "center",
  },
  inputContainer: {
    backgroundColor: colors.white05,
    borderRadius: 20,
    borderWidth: 1, borderColor: colors.separator,
    overflow: "hidden",
  },
  inputContainerFocused: { borderColor: "rgba(255,107,44,0.3)" },
  textInput: {
    paddingHorizontal: spacing.lg,
    paddingTop: 10, paddingBottom: 6,
    fontSize: 15, color: colors.label,
    maxHeight: 120, minHeight: 40,
  },
  inputToolbar: {
    flexDirection: "row", alignItems: "center", justifyContent: "space-between",
    paddingHorizontal: 8, paddingBottom: 6, paddingTop: 0,
  },
  inputToolbarLeft: { flexDirection: "row", alignItems: "center", gap: 2 },
  inputToolbarRight: { flexDirection: "row", alignItems: "center", gap: 6 },
  inputToolBtn: {
    width: 32, height: 32, borderRadius: 8,
    alignItems: "center", justifyContent: "center",
  },
  providerSelector: {
    flexDirection: "row", alignItems: "center", gap: 4,
    paddingHorizontal: 8, height: 30, borderRadius: 8,
  },
  providerSelectorText: { fontSize: 11, fontWeight: "600", color: colors.labelTertiary },
  sendBtn: {
    width: 34, height: 34, borderRadius: 10,
    backgroundColor: colors.accent,
    alignItems: "center", justifyContent: "center",
  },
  stopBtn: { backgroundColor: colors.dangerSubtle },
  sendBtnDisabled: { opacity: 0.3 },

  // ── Edit message ──
  editBlock: { gap: 8 },
  editInput: {
    fontSize: 15, lineHeight: 22, color: colors.label,
    backgroundColor: colors.white05,
    borderRadius: radius.sm,
    padding: spacing.sm,
    minHeight: 60, maxHeight: 160,
    borderWidth: 1, borderColor: "rgba(255,107,44,0.3)",
  },
  editActions: { flexDirection: "row", justifyContent: "flex-end", gap: 10, alignItems: "center" },
  editCancelText: { fontSize: 13, fontWeight: "500", color: colors.labelTertiary },
  editSaveBtn: {
    backgroundColor: colors.accent,
    borderRadius: radius.sm,
    paddingHorizontal: 12, paddingVertical: 6,
  },
  editSaveText: { fontSize: 13, fontWeight: "600", color: "#fff" },

  // ── Loading state ──
  loadingCenter: {
    flex: 1, minHeight: 300,
    justifyContent: "center", alignItems: "center", gap: 12,
  },
  loadingText: { fontSize: 13, color: colors.labelTertiary },

  // ── Agent cards (empty state, matches desktop grid) ──
  agentCard: {
    flexDirection: "row", alignItems: "center", gap: 10,
    backgroundColor: colors.white04,
    borderRadius: radius.lg,
    paddingHorizontal: 14, paddingVertical: 12,
    borderWidth: 1, borderColor: colors.separator,
    width: "48%",
  },
  agentCardIcon: {
    width: 28, height: 28, borderRadius: 8,
    alignItems: "center", justifyContent: "center",
  },
  agentCardName: { fontSize: 13, fontWeight: "600", color: colors.labelSecondary, flex: 1 },

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
