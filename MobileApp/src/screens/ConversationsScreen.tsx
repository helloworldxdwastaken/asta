import React, { useState, useEffect, useCallback } from "react";
import {
  View, Text, FlatList, TouchableOpacity, StyleSheet, RefreshControl,
} from "react-native";
import { colors, spacing, radius } from "../theme/colors";
import { listConversations, deleteConversation } from "../lib/api";
import type { Conversation } from "../lib/types";

interface Props {
  onSelect: (id: string) => void;
  onNewChat: () => void;
  refreshTrigger?: number;
}

export default function ConversationsScreen({ onSelect, onNewChat, refreshTrigger }: Props) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await listConversations();
      setConversations(res.conversations || []);
    } catch {}
  }, []);

  useEffect(() => { load(); }, [load, refreshTrigger]);

  async function onRefresh() {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  }

  async function handleDelete(id: string) {
    try {
      await deleteConversation(id);
      setConversations((prev) => prev.filter((c) => c.id !== id));
    } catch {}
  }

  function formatTime(dateStr?: string): string {
    if (!dateStr) return "";
    try {
      const d = new Date(dateStr);
      const now = new Date();
      const diff = now.getTime() - d.getTime();
      if (diff < 60_000) return "now";
      if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m`;
      if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h`;
      return `${Math.floor(diff / 86_400_000)}d`;
    } catch { return ""; }
  }

  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Chats</Text>
        <TouchableOpacity style={styles.newBtn} onPress={onNewChat}>
          <Text style={styles.newBtnText}>+ New</Text>
        </TouchableOpacity>
      </View>

      <FlatList
        data={conversations}
        keyExtractor={(c) => c.id}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.accent} />}
        contentContainerStyle={styles.list}
        renderItem={({ item }) => (
          <TouchableOpacity
            style={styles.row}
            onPress={() => onSelect(item.id)}
            onLongPress={() => handleDelete(item.id)}
          >
            <View style={styles.rowContent}>
              <Text style={styles.rowTitle} numberOfLines={1}>
                {item.title || "New chat"}
              </Text>
              <Text style={styles.rowMeta}>
                {item.approx_tokens ? `${Math.round(item.approx_tokens / 1000)}k` : ""}
                {item.last_active ? ` \u00B7 ${formatTime(item.last_active)}` : ""}
              </Text>
            </View>
          </TouchableOpacity>
        )}
        ListEmptyComponent={
          <View style={styles.empty}>
            <Text style={styles.emptyText}>No conversations yet</Text>
            <TouchableOpacity style={styles.emptyBtn} onPress={onNewChat}>
              <Text style={styles.emptyBtnText}>Start chatting</Text>
            </TouchableOpacity>
          </View>
        }
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface },
  header: {
    flexDirection: "row", justifyContent: "space-between", alignItems: "center",
    paddingHorizontal: spacing.lg, paddingTop: spacing.lg, paddingBottom: spacing.md,
  },
  headerTitle: { fontSize: 22, fontWeight: "700", color: colors.label },
  newBtn: {
    backgroundColor: colors.accent,
    borderRadius: radius.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: 6,
  },
  newBtnText: { color: "#fff", fontSize: 13, fontWeight: "600" },
  list: { padding: spacing.md },
  row: {
    backgroundColor: colors.surfaceRaised,
    borderRadius: radius.md,
    padding: spacing.lg,
    marginBottom: spacing.sm,
  },
  rowContent: { gap: 4 },
  rowTitle: { fontSize: 15, fontWeight: "500", color: colors.label },
  rowMeta: { fontSize: 12, color: colors.labelTertiary },
  empty: { alignItems: "center", paddingTop: 60, gap: spacing.md },
  emptyText: { fontSize: 15, color: colors.labelSecondary },
  emptyBtn: { backgroundColor: colors.accent, borderRadius: radius.md, paddingHorizontal: 20, paddingVertical: 10 },
  emptyBtnText: { color: "#fff", fontSize: 14, fontWeight: "600" },
});
