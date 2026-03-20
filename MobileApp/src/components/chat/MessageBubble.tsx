import React from "react";
import {
  View, Text, TextInput, TouchableOpacity, Image,
  ActivityIndicator, StyleSheet, Linking, Alert,
} from "react-native";
import { colors, spacing, radius } from "../../theme/colors";
import {
  IconBrain, IconCopy, IconCheck, IconEdit, IconTrash,
} from "../Icons";
import { ProviderBadge } from "../ProviderIcon";
import { ThinkingDots } from "../ThinkingIndicator";
import MarkdownContent from "../MarkdownContent";
import type { Message } from "../../lib/types";
import { downloadFile } from "../../lib/api";

// ── Download link helpers ──

const DOWNLOAD_RE = /Download:\s*(\/api\/files\/download-(?:pdf|office|video)\/([^\s\n]+))/gi;

function extractDownloadLinks(content: string): { path: string; name: string }[] {
  const links: { path: string; name: string }[] = [];
  let m: RegExpExecArray | null;
  const re = new RegExp(DOWNLOAD_RE.source, DOWNLOAD_RE.flags);
  while ((m = re.exec(content)) !== null) {
    const path = m[1];
    const name = decodeURIComponent(m[2].split("/").pop() || "file");
    links.push({ path, name });
  }
  return links;
}

async function handleDownload(path: string) {
  try {
    const url = await downloadFile(path);
    await Linking.openURL(url);
  } catch {
    Alert.alert("Download Error", "Could not open download link");
  }
}

// ── Props ──

interface MessageBubbleProps {
  message: Message;
  isUser: boolean;
  showThinking: boolean;
  copiedId: string | null;
  isEditing: boolean;
  editText: string;
  streaming: boolean;
  onEditTextChange: (text: string) => void;
  onStartEdit: (msg: Message) => void;
  onCancelEdit: () => void;
  onSubmitEdit: () => void;
  onCopy: (id: string, text: string) => void;
  onDelete: (id: string) => void;
}

export default function MessageBubble({
  message,
  isUser,
  showThinking,
  copiedId,
  isEditing,
  editText,
  streaming,
  onEditTextChange,
  onStartEdit,
  onCancelEdit,
  onSubmitEdit,
  onCopy,
  onDelete,
}: MessageBubbleProps) {
  return (
    <View style={[styles.msgRow, isUser && styles.msgRowUser]}>
      {!isUser && (
        <View style={styles.avatarAssistant}>
          <Text style={styles.avatarText}>A</Text>
        </View>
      )}
      <View style={{ maxWidth: "82%", gap: 4 }}>
        <View style={[styles.bubble, isUser ? styles.bubbleUser : styles.bubbleAssistant]}>
          {message.imageUri && (
            <Image source={{ uri: message.imageUri }} style={styles.msgImage} resizeMode="cover" />
          )}
          {message.thinking && showThinking && (
            <View style={styles.thinkingBlock}>
              <View style={styles.thinkingHeader}>
                <IconBrain size={11} color={colors.violet} />
                <Text style={styles.thinkingLabel}>Thought</Text>
              </View>
              <Text style={styles.thinkingText} numberOfLines={8}>{message.thinking}</Text>
            </View>
          )}
          {message.completedTools.length > 0 && (
            <View style={styles.toolRow}>
              {message.completedTools.map((t, i) => (
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
                onChangeText={onEditTextChange}
                multiline
                autoFocus
              />
              <View style={styles.editActions}>
                <TouchableOpacity onPress={onCancelEdit} activeOpacity={0.7}>
                  <Text style={styles.editCancelText}>Cancel</Text>
                </TouchableOpacity>
                <TouchableOpacity style={styles.editSaveBtn} onPress={onSubmitEdit} activeOpacity={0.7}>
                  <Text style={styles.editSaveText}>Save & Send</Text>
                </TouchableOpacity>
              </View>
            </View>
          ) : isUser ? (
            <>
              {!message.imageUri && /\[Image:\s*image\/\w+\]/.test(message.content) && (
                <View style={{ flexDirection: "row", alignItems: "center", gap: 6, marginBottom: 4 }}>
                  <Text style={{ fontSize: 14 }}>{"\u{1F5BC}"}</Text>
                  <Text style={{ fontSize: 12, color: colors.labelSecondary }}>image</Text>
                </View>
              )}
              <Text style={[styles.msgText, styles.msgTextUser]} selectable>
                {message.content.replace(/\s*\[Image:\s*image\/\w+\]\s*/g, " ").trim()}
              </Text>
            </>
          ) : (
            <>
              <MarkdownContent>{message.content}</MarkdownContent>
              {extractDownloadLinks(message.content).map((dl, i) => (
                <TouchableOpacity key={i} style={styles.downloadBtn}
                  onPress={() => handleDownload(dl.path)} activeOpacity={0.7}>
                  <Text style={styles.downloadIcon}>{dl.name.match(/\.(mp4|mov|webm)$/i) ? "\u{1F3AC}" : "\u{1F4C4}"}</Text>
                  <Text style={styles.downloadText} numberOfLines={1}>{dl.name}</Text>
                  <Text style={styles.downloadArrow}>{"\u2193"}</Text>
                </TouchableOpacity>
              ))}
            </>
          )}
        </View>
        {isUser && !isEditing && !streaming && (
          <View style={styles.msgFooter}>
            <TouchableOpacity style={styles.copyBtn} onPress={() => onStartEdit(message)}>
              <IconEdit size={12} color={colors.labelTertiary} />
            </TouchableOpacity>
            <TouchableOpacity style={styles.copyBtn} onPress={() => onCopy(message.id, message.content)}>
              {copiedId === message.id
                ? <IconCheck size={12} color={colors.success} />
                : <IconCopy size={12} color={colors.labelTertiary} />
              }
            </TouchableOpacity>
            <TouchableOpacity style={styles.copyBtn} onPress={() => onDelete(message.id)}>
              <IconTrash size={12} color={colors.labelTertiary} />
            </TouchableOpacity>
          </View>
        )}
        {!isUser && (
          <View style={styles.msgFooter}>
            {message.provider && <ProviderBadge provider={message.provider} size="sm" />}
            <TouchableOpacity style={styles.copyBtn} onPress={() => onCopy(message.id, message.content)}>
              {copiedId === message.id
                ? <IconCheck size={12} color={colors.success} />
                : <IconCopy size={12} color={colors.labelTertiary} />
              }
            </TouchableOpacity>
            <TouchableOpacity style={styles.copyBtn} onPress={() => onDelete(message.id)}>
              <IconTrash size={12} color={colors.labelTertiary} />
            </TouchableOpacity>
          </View>
        )}
      </View>
    </View>
  );
}

// ── Streaming message bubble (ListFooterComponent) ──

interface StreamingBubbleProps {
  streamContent: string;
  streamThinking: string;
  showThinking: boolean;
  activeTools: string[];
  completedTools: string[];
  statusText: string;
}

export function StreamingBubble({
  streamContent,
  streamThinking,
  showThinking,
  activeTools,
  completedTools,
  statusText,
}: StreamingBubbleProps) {
  const { ThinkingWordAnimation } = require("../ThinkingIndicator");

  return (
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
  );
}

const styles = StyleSheet.create({
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
  downloadBtn: {
    flexDirection: "row", alignItems: "center", gap: 8,
    backgroundColor: colors.accentSubtle,
    borderRadius: radius.sm,
    paddingHorizontal: 12, paddingVertical: 10,
    marginTop: spacing.sm,
    borderWidth: 1, borderColor: "rgba(255,107,44,0.2)",
  },
  downloadIcon: { fontSize: 16 },
  downloadText: { flex: 1, fontSize: 13, fontWeight: "600", color: colors.accent },
  downloadArrow: { fontSize: 16, fontWeight: "700", color: colors.accent },
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
});
