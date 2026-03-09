import React, { useState, useRef, useEffect, useCallback } from "react";
import {
  View, Text, TextInput, TouchableOpacity, FlatList, StyleSheet,
  KeyboardAvoidingView, Platform, ActivityIndicator,
} from "react-native";
import { colors, spacing, radius } from "../theme/colors";
import { streamChat, loadMessages } from "../lib/api";
import type { Message, StreamChunk } from "../lib/types";

interface Props {
  conversationId?: string;
  onConversationCreated?: (id: string) => void;
  provider?: string;
  thinkingLevel?: string;
}

export default function ChatScreen({ conversationId, onConversationCreated, provider, thinkingLevel }: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [streamContent, setStreamContent] = useState("");
  const [streamThinking, setStreamThinking] = useState("");
  const [activeTools, setActiveTools] = useState<string[]>([]);
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

  async function send() {
    const text = input.trim();
    if (!text || streaming) return;
    setInput("");

    const userMsg: Message = {
      id: `u-${Date.now()}`,
      role: "user",
      content: text,
      activeTools: [],
      completedTools: [],
    };
    setMessages((prev) => [...prev, userMsg]);
    scrollToEnd();

    setStreaming(true);
    setStreamContent("");
    setStreamThinking("");
    setActiveTools([]);

    let thinkAccumulated = "";
    let textAccumulated = "";
    let finalConvId = convIdRef.current;

    const stop = await streamChat(
      {
        text,
        conversation_id: convIdRef.current,
        provider: provider || undefined,
      },
      (chunk: StreamChunk) => {
        switch (chunk.type) {
          case "thinking": {
            let delta = chunk.delta || chunk.text || "";
            if (!thinkAccumulated && delta.startsWith("Reasoning:\n")) {
              delta = delta.slice("Reasoning:\n".length);
            }
            thinkAccumulated += delta;
            setStreamThinking(thinkAccumulated);
            break;
          }
          case "text": {
            textAccumulated += chunk.delta || chunk.text || "";
            setStreamContent(textAccumulated);
            scrollToEnd();
            break;
          }
          case "assistant_final": {
            textAccumulated = chunk.text || chunk.delta || textAccumulated;
            setStreamContent(textAccumulated);
            break;
          }
          case "tool_start": {
            setActiveTools((prev) => [...prev, chunk.label || chunk.name || "tool"]);
            setStreamContent("");
            textAccumulated = "";
            break;
          }
          case "tool_end": {
            const label = chunk.label || chunk.name || "tool";
            setActiveTools((prev) => prev.filter((t) => t !== label));
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
          content: textAccumulated || "",
          thinking: thinkAccumulated || undefined,
          activeTools: [],
          completedTools: [],
        };
        setMessages((prev) => [...prev, assistantMsg]);
        setStreamContent("");
        setStreamThinking("");
        setActiveTools([]);
        setStreaming(false);
        if (finalConvId && finalConvId !== convIdRef.current) {
          convIdRef.current = finalConvId;
          onConversationCreated?.(finalConvId);
        }
        scrollToEnd();
      },
      (err) => {
        setStreaming(false);
        setStreamContent("");
        setStreamThinking("");
      },
    );
    stopRef.current = stop;
  }

  function renderMessage({ item }: { item: Message }) {
    const isUser = item.role === "user";
    return (
      <View style={[styles.msgRow, isUser && styles.msgRowUser]}>
        <View style={[styles.bubble, isUser ? styles.bubbleUser : styles.bubbleAssistant]}>
          {/* Thinking block */}
          {item.thinking && thinkingLevel !== "off" && (
            <View style={styles.thinkingBlock}>
              <Text style={styles.thinkingText}>{item.thinking}</Text>
            </View>
          )}
          {/* Tool pills */}
          {item.completedTools.length > 0 && (
            <View style={styles.toolRow}>
              {item.completedTools.map((t) => (
                <View key={t} style={styles.toolPill}>
                  <Text style={styles.toolPillText}>{t}</Text>
                </View>
              ))}
            </View>
          )}
          <Text style={[styles.msgText, isUser && styles.msgTextUser]}>{item.content}</Text>
        </View>
      </View>
    );
  }

  const showThinking = thinkingLevel !== "off";

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
      keyboardVerticalOffset={Platform.OS === "ios" ? 90 : 0}
    >
      <FlatList
        ref={flatListRef}
        data={messages}
        renderItem={renderMessage}
        keyExtractor={(m) => m.id}
        contentContainerStyle={styles.list}
        onContentSizeChange={scrollToEnd}
        ListEmptyComponent={
          <View style={styles.empty}>
            <Text style={styles.emptyTitle}>Asta</Text>
            <Text style={styles.emptySubtitle}>What can I help with?</Text>
          </View>
        }
        ListFooterComponent={
          streaming ? (
            <View style={styles.msgRow}>
              <View style={[styles.bubble, styles.bubbleAssistant]}>
                {streamThinking && showThinking ? (
                  <View style={styles.thinkingBlock}>
                    <View style={styles.thinkingDot} />
                    <Text style={styles.thinkingText}>{streamThinking}</Text>
                  </View>
                ) : null}
                {activeTools.length > 0 ? (
                  <View style={styles.toolRow}>
                    {activeTools.map((t) => (
                      <View key={t} style={[styles.toolPill, styles.toolPillActive]}>
                        <ActivityIndicator size={8} color={colors.accent} />
                        <Text style={[styles.toolPillText, { color: colors.accent }]}>{t}</Text>
                      </View>
                    ))}
                  </View>
                ) : null}
                {streamContent ? (
                  <Text style={styles.msgText}>{streamContent}</Text>
                ) : !streamThinking && activeTools.length === 0 ? (
                  <ActivityIndicator size="small" color={colors.accent} />
                ) : null}
              </View>
            </View>
          ) : null
        }
      />

      {/* Input bar */}
      <View style={styles.inputBar}>
        <TextInput
          style={styles.textInput}
          value={input}
          onChangeText={setInput}
          placeholder="Ask anything..."
          placeholderTextColor={colors.labelTertiary}
          multiline
          maxLength={10000}
          editable={!streaming}
        />
        <TouchableOpacity
          style={[styles.sendBtn, (!input.trim() || streaming) && styles.sendBtnDisabled]}
          onPress={streaming ? () => stopRef.current?.() : send}
          disabled={!input.trim() && !streaming}
        >
          <Text style={styles.sendBtnText}>{streaming ? "Stop" : "Send"}</Text>
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface },
  list: { padding: spacing.lg, paddingBottom: spacing.xxl, flexGrow: 1 },
  empty: { flex: 1, justifyContent: "center", alignItems: "center", paddingTop: 120 },
  emptyTitle: { fontSize: 32, fontWeight: "700", color: colors.accent, marginBottom: spacing.sm },
  emptySubtitle: { fontSize: 16, color: colors.labelSecondary },

  msgRow: { marginBottom: spacing.md },
  msgRowUser: { alignItems: "flex-end" },
  bubble: { maxWidth: "85%", borderRadius: radius.lg, padding: spacing.md },
  bubbleUser: { backgroundColor: colors.accent, borderBottomRightRadius: 4 },
  bubbleAssistant: { backgroundColor: colors.surfaceRaised, borderBottomLeftRadius: 4 },
  msgText: { fontSize: 15, lineHeight: 22, color: colors.label },
  msgTextUser: { color: "#fff" },

  thinkingBlock: {
    backgroundColor: colors.violetSubtle,
    borderRadius: radius.sm,
    padding: spacing.sm,
    marginBottom: spacing.sm,
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 6,
  },
  thinkingDot: {
    width: 6, height: 6, borderRadius: 3,
    backgroundColor: colors.violet,
    marginTop: 6,
  },
  thinkingText: { fontSize: 12, color: colors.violetText, flex: 1 },

  toolRow: { flexDirection: "row", flexWrap: "wrap", gap: 6, marginBottom: spacing.sm },
  toolPill: {
    flexDirection: "row", alignItems: "center", gap: 4,
    backgroundColor: colors.white04,
    borderWidth: 1, borderColor: colors.separator,
    borderRadius: radius.full, paddingHorizontal: 10, paddingVertical: 4,
  },
  toolPillActive: { borderColor: "rgba(255,107,44,0.15)", backgroundColor: colors.accentGlow },
  toolPillText: { fontSize: 11, color: colors.labelSecondary },

  inputBar: {
    flexDirection: "row",
    alignItems: "flex-end",
    padding: spacing.md,
    paddingBottom: Platform.OS === "ios" ? spacing.xxl : spacing.md,
    backgroundColor: colors.surfaceRaised,
    borderTopWidth: 1,
    borderTopColor: colors.separator,
    gap: spacing.sm,
  },
  textInput: {
    flex: 1,
    backgroundColor: colors.white05,
    borderRadius: radius.lg,
    paddingHorizontal: spacing.lg,
    paddingVertical: 12,
    fontSize: 15,
    color: colors.label,
    maxHeight: 120,
    borderWidth: 1,
    borderColor: colors.separator,
  },
  sendBtn: {
    backgroundColor: colors.accent,
    borderRadius: radius.md,
    paddingHorizontal: spacing.lg,
    paddingVertical: 12,
    justifyContent: "center",
  },
  sendBtnDisabled: { opacity: 0.4 },
  sendBtnText: { color: "#fff", fontSize: 14, fontWeight: "600" },
});
