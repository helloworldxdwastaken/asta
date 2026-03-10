import React, { useState, useCallback, Component, type ReactNode } from "react";
import { View, Text, TouchableOpacity, Platform, StyleSheet, Linking } from "react-native";
import Markdown from "react-native-markdown-display";
import * as Clipboard from "expo-clipboard";
import { colors, spacing, radius } from "../theme/colors";
import { IconCopy, IconCheck } from "./Icons";

const MONO = Platform.OS === "ios" ? "Menlo" : "monospace";

interface Props {
  children: string;
  isUser?: boolean;
}

/** Error boundary to prevent markdown crashes from taking down the chat */
class MarkdownErrorBoundary extends Component<{ children: ReactNode; fallback: string }, { hasError: boolean }> {
  state = { hasError: false };
  static getDerivedStateFromError() { return { hasError: true }; }
  render() {
    if (this.state.hasError) {
      return <Text style={{ fontSize: 15, lineHeight: 22, color: colors.label }}>{this.props.fallback}</Text>;
    }
    return this.props.children;
  }
}

/**
 * Markdown renderer for chat messages.
 * Matches the desktop app's styling: GFM tables, code blocks with copy,
 * inline code, blockquotes, links, lists.
 */
export default function MarkdownContent({ children, isUser }: Props) {
  // Guard against empty/null content
  if (!children || typeof children !== "string") return null;
  const [copiedBlock, setCopiedBlock] = useState<number | null>(null);

  const copyCode = useCallback(async (text: string, index: number) => {
    try {
      if (Platform.OS === "web" && navigator?.clipboard) {
        await navigator.clipboard.writeText(text);
      } else {
        await Clipboard.setStringAsync(text);
      }
    } catch {}
    setCopiedBlock(index);
    setTimeout(() => setCopiedBlock(null), 2000);
  }, []);

  // Track code block index for copy buttons
  let codeBlockIndex = 0;

  const rules = {
    // ── Code blocks (fenced ```code```) ──
    fence: (node: any, _children: any, _parent: any, styles: any) => {
      const content = node.content || "";
      const lang = node.sourceInfo || "";
      const idx = codeBlockIndex++;
      const isCopied = copiedBlock === idx;

      return (
        <View key={node.key} style={mdStyles.codeBlockContainer}>
          {/* Header with language + copy button */}
          <View style={mdStyles.codeBlockHeader}>
            <Text style={mdStyles.codeBlockLang}>
              {lang || "code"}
            </Text>
            <TouchableOpacity
              style={mdStyles.copyBtn}
              onPress={() => copyCode(content.replace(/\n$/, ""), idx)}
              activeOpacity={0.7}
            >
              {isCopied ? (
                <View style={mdStyles.copyBtnInner}>
                  <IconCheck size={11} color={colors.success} />
                  <Text style={[mdStyles.copyBtnText, { color: colors.success }]}>Copied</Text>
                </View>
              ) : (
                <View style={mdStyles.copyBtnInner}>
                  <IconCopy size={11} color={colors.labelTertiary} />
                  <Text style={mdStyles.copyBtnText}>Copy</Text>
                </View>
              )}
            </TouchableOpacity>
          </View>
          {/* Code content */}
          <View style={mdStyles.codeBlockBody}>
            <Text style={mdStyles.codeBlockText} selectable>
              {content.replace(/\n$/, "")}
            </Text>
          </View>
        </View>
      );
    },

    // ── Inline code (`code`) ──
    code_inline: (node: any) => (
      <Text key={node.key} style={[
        mdStyles.inlineCode,
        isUser && mdStyles.inlineCodeUser,
      ]}>
        {node.content}
      </Text>
    ),

    // ── Blockquotes ──
    blockquote: (node: any, children: any) => (
      <View key={node.key} style={mdStyles.blockquote}>
        {children}
      </View>
    ),

    // ── Links ──
    link: (node: any, children: any) => {
      const url = node.attributes?.href;
      return (
        <Text
          key={node.key}
          style={mdStyles.link}
          onPress={() => {
            if (url) Linking.openURL(url).catch(() => {});
          }}
        >
          {children}
        </Text>
      );
    },

    // ── Tables ──
    table: (node: any, children: any) => (
      <View key={node.key} style={mdStyles.table}>
        {children}
      </View>
    ),
    tr: (node: any, children: any) => (
      <View key={node.key} style={mdStyles.tableRow}>
        {children}
      </View>
    ),
    th: (node: any, children: any) => (
      <View key={node.key} style={mdStyles.tableHeaderCell}>
        {children}
      </View>
    ),
    td: (node: any, children: any) => (
      <View key={node.key} style={mdStyles.tableCell}>
        {children}
      </View>
    ),

    // ── Horizontal rule ──
    hr: (node: any) => (
      <View key={node.key} style={mdStyles.hr} />
    ),
  };

  // Base text color depends on user vs assistant
  const textColor = isUser ? colors.userBubbleText : colors.label;

  const markdownStyles = {
    body: { color: textColor, fontSize: 15, lineHeight: 22 },
    paragraph: { marginTop: 0, marginBottom: 6 },
    // Headings
    heading1: { color: textColor, fontSize: 22, fontWeight: "700" as const, marginTop: 16, marginBottom: 8 },
    heading2: { color: textColor, fontSize: 19, fontWeight: "700" as const, marginTop: 14, marginBottom: 6 },
    heading3: { color: textColor, fontSize: 16, fontWeight: "700" as const, marginTop: 12, marginBottom: 4 },
    heading4: { color: textColor, fontSize: 15, fontWeight: "700" as const, marginTop: 10, marginBottom: 4 },
    // Lists
    bullet_list: { marginTop: 4, marginBottom: 4 },
    ordered_list: { marginTop: 4, marginBottom: 4 },
    list_item: { marginTop: 2, marginBottom: 2, flexDirection: "row" as const },
    bullet_list_icon: { color: colors.labelTertiary, fontSize: 14, marginRight: 8, lineHeight: 22 },
    ordered_list_icon: { color: colors.labelTertiary, fontSize: 13, fontWeight: "600" as const, marginRight: 8, lineHeight: 22 },
    bullet_list_content: { flex: 1 },
    ordered_list_content: { flex: 1 },
    // Strong / Emphasis
    strong: { fontWeight: "600" as const },
    em: { fontStyle: "italic" as const },
    s: { textDecorationLine: "line-through" as const, color: colors.labelSecondary },
    // Links
    link: { color: colors.accent, textDecorationLine: "underline" as const },
    // Images
    image: { borderRadius: 12, marginVertical: 8 },
  };

  return (
    <MarkdownErrorBoundary fallback={children}>
      <Markdown
        style={markdownStyles}
        rules={rules}
        mergeStyle
      >
        {children}
      </Markdown>
    </MarkdownErrorBoundary>
  );
}

const mdStyles = StyleSheet.create({
  // Code blocks
  codeBlockContainer: {
    backgroundColor: colors.codeBg,
    borderWidth: 1,
    borderColor: colors.codeBorder,
    borderRadius: 12,
    overflow: "hidden",
    marginVertical: 8,
  },
  codeBlockHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: colors.codeBorder,
    backgroundColor: colors.codeBg,
  },
  codeBlockLang: {
    fontSize: 11,
    fontWeight: "600",
    color: colors.labelTertiary,
    textTransform: "lowercase",
  },
  copyBtn: {
    padding: 4,
  },
  copyBtnInner: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
  },
  copyBtnText: {
    fontSize: 11,
    fontWeight: "600",
    color: colors.labelTertiary,
  },
  codeBlockBody: {
    padding: 14,
  },
  codeBlockText: {
    fontFamily: MONO,
    fontSize: 13,
    lineHeight: 20,
    color: colors.label,
  },

  // Inline code
  inlineCode: {
    fontFamily: MONO,
    fontSize: 13,
    backgroundColor: colors.inlineCodeBg,
    paddingHorizontal: 6,
    paddingVertical: 1,
    borderRadius: 5,
    color: colors.label,
  },
  inlineCodeUser: {
    backgroundColor: "rgba(255,255,255,0.1)",
    color: colors.userBubbleText,
  },

  // Blockquote
  blockquote: {
    borderLeftWidth: 3,
    borderLeftColor: colors.blockquoteBorder,
    paddingLeft: 14,
    marginVertical: 6,
  },

  // Link
  link: {
    color: colors.accent,
    textDecorationLine: "underline",
  },

  // Table
  table: {
    borderWidth: 1,
    borderColor: colors.tableBorder,
    borderRadius: 8,
    overflow: "hidden",
    marginVertical: 8,
  },
  tableRow: {
    flexDirection: "row",
    borderBottomWidth: 1,
    borderBottomColor: colors.tableBorder,
  },
  tableHeaderCell: {
    flex: 1,
    padding: 10,
    backgroundColor: colors.tableHeaderBg,
  },
  tableCell: {
    flex: 1,
    padding: 10,
  },

  // HR
  hr: {
    height: 1,
    backgroundColor: colors.tableBorder,
    marginVertical: 12,
  },
});
