import React from "react";
import { View, Text, TouchableOpacity, Image, ActivityIndicator, StyleSheet } from "react-native";
import { colors, spacing, radius } from "../../theme/colors";
import { resolveAgentIcon } from "../Icons";
import { PixelSprites } from "../PixelSprites";
import type { Agent } from "../../lib/types";

interface ChatEmptyStateProps {
  agents: Agent[];
  loadingMsgs: boolean;
  onAgentSelect: (agentId: string) => void;
  onSuggestionClick: (text: string) => void;
}

export default function ChatEmptyState({
  agents,
  loadingMsgs,
  onAgentSelect,
  onSuggestionClick,
}: ChatEmptyStateProps) {
  if (loadingMsgs) {
    return (
      <View style={styles.loadingCenter}>
        <ActivityIndicator size="small" color={colors.accent} />
        <Text style={styles.loadingText}>Loading messages...</Text>
      </View>
    );
  }

  return (
    <View style={styles.empty}>
      <PixelSprites />
      <View style={styles.emptyContent}>
        <Image source={require("../../../assets/appicon.png")} style={styles.emptyLogo} />
        <Text style={styles.emptyTitle}>What can I help with?</Text>
        <Text style={styles.emptySubtitle}>Ask anything, or try a suggestion</Text>
        <View style={styles.suggestions}>
          {agents.slice(0, 4).map((a) => {
            const ai = resolveAgentIcon(a);
            return (
              <TouchableOpacity key={a.id} style={styles.agentCard}
                onPress={() => onAgentSelect(a.id)}
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
              <TouchableOpacity style={styles.suggestionChip} onPress={() => onSuggestionClick("What's on my schedule today?")} activeOpacity={0.7}>
                <Text style={styles.suggestionText}>My schedule today</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.suggestionChip} onPress={() => onSuggestionClick("Summarize my recent notes")} activeOpacity={0.7}>
                <Text style={styles.suggestionText}>Summarize notes</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.suggestionChip} onPress={() => onSuggestionClick("What's the weather like?")} activeOpacity={0.7}>
                <Text style={styles.suggestionText}>Check the weather</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.suggestionChip} onPress={() => onSuggestionClick("Write a quick email draft")} activeOpacity={0.7}>
                <Text style={styles.suggestionText}>Draft an email</Text>
              </TouchableOpacity>
            </>
          )}
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  loadingCenter: {
    flex: 1, minHeight: 300,
    justifyContent: "center", alignItems: "center", gap: 12,
  },
  loadingText: { fontSize: 13, color: colors.labelTertiary },
  empty: { flex: 1, minHeight: 400, justifyContent: "center", alignItems: "center" },
  emptyContent: { alignItems: "center", zIndex: 1 },
  emptyLogo: {
    width: 56, height: 56, borderRadius: 14,
    marginBottom: spacing.lg,
    shadowColor: colors.accent,
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.5,
    shadowRadius: 24,
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
});
