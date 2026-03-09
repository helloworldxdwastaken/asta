import React, { useState, useEffect, useCallback } from "react";
import {
  View, Text, TextInput, FlatList, TouchableOpacity, StyleSheet,
  RefreshControl, Alert, Platform,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { colors, spacing, radius } from "../theme/colors";
import { listConversations, deleteConversation } from "../lib/api";
import type { Conversation } from "../lib/types";
import { IconPlus, IconChat, IconChevronRight, IconSearch, IconX } from "../components/Icons";

interface Props {
  onSelect: (id: string) => void;
  onNewChat: () => void;
  refreshTrigger?: number;
}

export default function ConversationsScreen({ onSelect, onNewChat, refreshTrigger }: Props) {
  const insets = useSafeAreaInsets();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [refreshing, setRefreshing] = useState(false);
  const [search, setSearch] = useState("");
  const [showSearch, setShowSearch] = useState(false);

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

  function confirmDelete(id: string) {
    if (Platform.OS === "web") {
      if (confirm("Delete this conversation?")) handleDelete(id);
      return;
    }
    Alert.alert("Delete", "Delete this conversation?", [
      { text: "Cancel", style: "cancel" },
      { text: "Delete", style: "destructive", onPress: () => handleDelete(id) },
    ]);
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
      if (diff < 60_000) return "just now";
      if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`;
      if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
      if (diff < 604_800_000) return `${Math.floor(diff / 86_400_000)}d ago`;
      return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
    } catch { return ""; }
  }

  const filtered = search.trim()
    ? conversations.filter((c) =>
        (c.title || "").toLowerCase().includes(search.toLowerCase())
      )
    : conversations;

  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={[styles.header, { paddingTop: insets.top + 8 }]}>
        <Text style={styles.headerTitle}>History</Text>
        <View style={styles.headerActions}>
          <TouchableOpacity
            style={styles.searchToggle}
            onPress={() => { setShowSearch(!showSearch); if (showSearch) setSearch(""); }}
            activeOpacity={0.7}
          >
            {showSearch
              ? <IconX size={18} color={colors.labelSecondary} />
              : <IconSearch size={18} color={colors.labelSecondary} />
            }
          </TouchableOpacity>
          <TouchableOpacity style={styles.newBtn} onPress={onNewChat} activeOpacity={0.7}>
            <IconPlus size={16} color="#fff" />
            <Text style={styles.newBtnText}>New Chat</Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* Search bar */}
      {showSearch && (
        <View style={styles.searchBar}>
          <IconSearch size={14} color={colors.labelTertiary} />
          <TextInput
            style={styles.searchInput}
            value={search}
            onChangeText={setSearch}
            placeholder="Search conversations..."
            placeholderTextColor={colors.labelTertiary}
            autoFocus
            autoCapitalize="none"
            autoCorrect={false}
          />
          {search.length > 0 && (
            <TouchableOpacity onPress={() => setSearch("")} activeOpacity={0.7}>
              <IconX size={14} color={colors.labelTertiary} />
            </TouchableOpacity>
          )}
        </View>
      )}

      {/* Result count when searching */}
      {search.trim() ? (
        <View style={styles.searchMeta}>
          <Text style={styles.searchMetaText}>
            {filtered.length} result{filtered.length !== 1 ? "s" : ""}
          </Text>
        </View>
      ) : null}

      <FlatList
        data={filtered}
        keyExtractor={(c) => c.id}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.accent} />}
        contentContainerStyle={styles.list}
        renderItem={({ item }) => (
          <TouchableOpacity
            style={styles.row}
            onPress={() => onSelect(item.id)}
            onLongPress={() => confirmDelete(item.id)}
            activeOpacity={0.7}
          >
            <View style={styles.rowIcon}>
              <IconChat size={16} color={colors.labelTertiary} />
            </View>
            <View style={styles.rowContent}>
              <Text style={styles.rowTitle} numberOfLines={1}>
                {item.title || "New chat"}
              </Text>
              <View style={styles.rowMetaRow}>
                {item.approx_tokens ? (
                  <View style={styles.tokenBadge}>
                    <Text style={styles.tokenBadgeText}>{Math.round(item.approx_tokens / 1000)}k</Text>
                  </View>
                ) : null}
                <Text style={styles.rowTime}>{formatTime(item.last_active)}</Text>
              </View>
            </View>
            <IconChevronRight size={16} color={colors.labelTertiary} />
          </TouchableOpacity>
        )}
        ListEmptyComponent={
          search.trim() ? (
            <View style={styles.empty}>
              <IconSearch size={32} color={colors.labelTertiary} />
              <Text style={styles.emptyTitle}>No matches</Text>
              <Text style={styles.emptySubtitle}>Try a different search term</Text>
            </View>
          ) : (
            <View style={styles.empty}>
              <View style={styles.emptyIcon}>
                <IconChat size={32} color={colors.labelTertiary} />
              </View>
              <Text style={styles.emptyTitle}>No conversations yet</Text>
              <Text style={styles.emptySubtitle}>Start a chat to see it here</Text>
              <TouchableOpacity style={styles.emptyBtn} onPress={onNewChat} activeOpacity={0.7}>
                <IconPlus size={16} color="#fff" />
                <Text style={styles.emptyBtnText}>New Chat</Text>
              </TouchableOpacity>
            </View>
          )
        }
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface },
  header: {
    flexDirection: "row", justifyContent: "space-between", alignItems: "center",
    paddingHorizontal: spacing.lg, paddingBottom: 12,
    backgroundColor: colors.surfaceRaised,
    borderBottomWidth: 1, borderBottomColor: colors.separator,
  },
  headerTitle: { fontSize: 28, fontWeight: "700", color: colors.label, letterSpacing: -0.5 },
  headerActions: { flexDirection: "row", alignItems: "center", gap: 8 },
  searchToggle: { padding: 8 },
  newBtn: {
    flexDirection: "row", alignItems: "center", gap: 6,
    backgroundColor: colors.accent,
    borderRadius: radius.full,
    paddingHorizontal: 14,
    paddingVertical: 8,
  },
  newBtnText: { color: "#fff", fontSize: 13, fontWeight: "600" },

  // Search
  searchBar: {
    flexDirection: "row", alignItems: "center", gap: 8,
    backgroundColor: colors.surfaceRaised,
    marginHorizontal: spacing.md, marginTop: spacing.sm,
    paddingHorizontal: spacing.md,
    borderRadius: radius.md,
    borderWidth: 1, borderColor: colors.separator,
  },
  searchInput: {
    flex: 1, fontSize: 14, color: colors.label,
    paddingVertical: 10,
  },
  searchMeta: {
    paddingHorizontal: spacing.lg, paddingTop: spacing.sm,
  },
  searchMetaText: {
    fontSize: 12, color: colors.labelTertiary, fontWeight: "600",
  },

  list: { padding: spacing.md, paddingBottom: 40 },
  row: {
    flexDirection: "row", alignItems: "center",
    backgroundColor: colors.surfaceRaised,
    borderRadius: radius.md,
    padding: spacing.lg,
    marginBottom: spacing.sm,
    borderWidth: 1,
    borderColor: colors.separator,
    gap: spacing.md,
  },
  rowIcon: {
    width: 36, height: 36, borderRadius: 18,
    backgroundColor: colors.white05,
    alignItems: "center", justifyContent: "center",
  },
  rowContent: { flex: 1, gap: 4 },
  rowTitle: { fontSize: 15, fontWeight: "600", color: colors.label },
  rowMetaRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  tokenBadge: {
    backgroundColor: colors.white08,
    borderRadius: radius.full,
    paddingHorizontal: 6, paddingVertical: 1,
  },
  tokenBadgeText: { fontSize: 10, color: colors.labelTertiary, fontWeight: "600" },
  rowTime: { fontSize: 12, color: colors.labelTertiary },
  empty: { alignItems: "center", paddingTop: 80, gap: spacing.sm },
  emptyIcon: {
    width: 64, height: 64, borderRadius: 32,
    backgroundColor: colors.white05,
    alignItems: "center", justifyContent: "center",
    marginBottom: spacing.sm,
  },
  emptyTitle: { fontSize: 18, fontWeight: "600", color: colors.label },
  emptySubtitle: { fontSize: 14, color: colors.labelTertiary, marginBottom: spacing.md },
  emptyBtn: {
    flexDirection: "row", alignItems: "center", gap: 6,
    backgroundColor: colors.accent,
    borderRadius: radius.full,
    paddingHorizontal: 20, paddingVertical: 12,
  },
  emptyBtnText: { color: "#fff", fontSize: 14, fontWeight: "600" },
});
