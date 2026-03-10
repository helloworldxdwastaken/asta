import React, { useState, useEffect, useCallback } from "react";
import {
  View, Text, TouchableOpacity, TextInput,
  StyleSheet, Alert, Platform, ScrollView,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { colors, spacing, radius } from "../theme/colors";
import {
  listConversations, deleteConversation, listFolders,
  createFolder, deleteFolder, renameFolder, assignConversationFolder,
  truncateConversation,
} from "../lib/api";
import { clearAuth, getUser } from "../lib/auth";
import type { Conversation, Folder, User } from "../lib/types";
import {
  IconPlus, IconFolder, IconSearch, IconSettings,
  IconLogout, IconX, IconWifi, IconWifiOff,
  IconNewFolder, IconChevronDown, IconChevronRight,
} from "./Icons";

interface Props {
  conversationId?: string;
  serverOk: boolean | null;
  onSelectConversation: (id: string) => void;
  onNewChat: () => void;
  onOpenSettings: () => void;
  onLogout: () => void;
  onClose: () => void;
  refreshTrigger: number;
}

export default function Drawer({
  conversationId, serverOk, onSelectConversation, onNewChat,
  onOpenSettings, onLogout, onClose, refreshTrigger,
}: Props) {
  const insets = useSafeAreaInsets();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [folders, setFolders] = useState<Folder[]>([]);
  const [user, setUserState] = useState<User | null>(null);
  const [search, setSearch] = useState("");
  const [showSearch, setShowSearch] = useState(false);
  const [newFolderName, setNewFolderName] = useState("");
  const [showNewFolder, setShowNewFolder] = useState(false);
  const [moveConvId, setMoveConvId] = useState<string | null>(null);
  const [collapsedFolders, setCollapsedFolders] = useState<Set<string>>(new Set());

  const load = useCallback(async () => {
    listConversations(80).then((r) => setConversations(r.conversations || [])).catch(() => {});
    listFolders().then((r) => setFolders(r.folders || [])).catch(() => {});
    getUser().then(setUserState);
  }, []);

  useEffect(() => { load(); }, [load, refreshTrigger]);

  const filtered = search
    ? conversations.filter((c) => (c.title || "").toLowerCase().includes(search.toLowerCase()))
    : conversations;

  const unfiled = filtered.filter((c) => !c.folder_id);
  const getProjectChats = (fId: string) => filtered.filter((c) => c.folder_id === fId);

  function toggleFolderCollapse(id: string) {
    setCollapsedFolders(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  async function handleCreateFolder() {
    const name = newFolderName.trim();
    if (!name) return;
    try {
      await createFolder(name);
      setNewFolderName("");
      setShowNewFolder(false);
      const r = await listFolders();
      setFolders(r.folders || []);
    } catch {}
  }

  function confirmDeleteFolder(f: Folder) {
    if (Platform.OS === "web") {
      if (confirm(`Delete folder "${f.name}"?`)) doDeleteFolder(f.id);
      return;
    }
    Alert.alert("Delete Folder", `Delete "${f.name}"? Conversations won't be deleted.`, [
      { text: "Cancel", style: "cancel" },
      { text: "Delete", style: "destructive", onPress: () => doDeleteFolder(f.id) },
    ]);
  }

  async function doDeleteFolder(id: string) {
    try {
      await deleteFolder(id);
      setFolders(p => p.filter(f => f.id !== id));
      // unfile conversations that were in this folder
      setConversations(p => p.map(c => c.folder_id === id ? { ...c, folder_id: null } : c));
    } catch {}
  }

  async function moveConversation(convId: string, folderId: string | null) {
    try {
      await assignConversationFolder(convId, folderId);
      setConversations(p => p.map(c => c.id === convId ? { ...c, folder_id: folderId } : c));
    } catch {}
    setMoveConvId(null);
  }

  async function keepLast10(id: string) {
    try {
      await truncateConversation(id, 10);
      // Refresh to show updated state
      load();
    } catch {}
  }

  function showConversationActions(item: Conversation) {
    if (Platform.OS === "web") {
      const action = prompt("Type 'delete' to delete, 'move' to move, 'trim' to keep last 10:");
      if (action === "delete") doDelete(item.id);
      else if (action === "move") setMoveConvId(item.id);
      else if (action === "trim") keepLast10(item.id);
      return;
    }
    const buttons: any[] = [
      { text: "Cancel", style: "cancel" },
      { text: "Move to Folder", onPress: () => setMoveConvId(item.id) },
      { text: "Keep Last 10 Messages", onPress: () => keepLast10(item.id) },
      { text: "Delete", style: "destructive", onPress: () => doDelete(item.id) },
    ];
    if (item.folder_id) {
      buttons.splice(1, 0, { text: "Remove from Folder", onPress: () => moveConversation(item.id, null) });
    }
    Alert.alert(item.title || "New chat", undefined, buttons);
  }

  function confirmDelete(id: string) {
    if (Platform.OS === "web") {
      if (confirm("Delete this conversation?")) doDelete(id);
      return;
    }
    Alert.alert("Delete", "Delete this conversation?", [
      { text: "Cancel", style: "cancel" },
      { text: "Delete", style: "destructive", onPress: () => doDelete(id) },
    ]);
  }

  async function doDelete(id: string) {
    await deleteConversation(id).catch(() => {});
    setConversations((p) => p.filter((c) => c.id !== id));
  }

  function handleLogout() {
    if (Platform.OS === "web") {
      if (confirm("Sign out?")) { clearAuth().then(onLogout); }
      return;
    }
    Alert.alert("Sign Out", "Are you sure?", [
      { text: "Cancel", style: "cancel" },
      { text: "Sign Out", style: "destructive", onPress: () => clearAuth().then(onLogout) },
    ]);
  }

  function fmtTime(d?: string): string {
    if (!d) return "";
    try {
      const diff = Date.now() - new Date(d).getTime();
      if (diff < 60_000) return "now";
      if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m`;
      if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h`;
      return `${Math.floor(diff / 86_400_000)}d`;
    } catch { return ""; }
  }

  function fmtTokens(t?: number): string {
    if (!t) return "";
    return t >= 1000 ? `${(t / 1000).toFixed(1)}k` : String(t);
  }

  function ChatRow({ item }: { item: Conversation }) {
    const active = item.id === conversationId;
    return (
      <TouchableOpacity
        style={[styles.chatRow, active && styles.chatRowActive]}
        onPress={() => { onSelectConversation(item.id); onClose(); }}
        onLongPress={() => showConversationActions(item)}
        activeOpacity={0.7}
      >
        <View style={[styles.chatDotWrap, active && styles.chatDotActive]} />
        <View style={styles.chatRowLeft}>
          <Text style={[styles.chatTitle, active && styles.chatTitleActive]} numberOfLines={1}>
            {item.title || "New chat"}
          </Text>
          <View style={styles.chatMeta}>
            {item.approx_tokens ? (
              <View style={styles.chatTokenBadge}>
                <Text style={styles.chatTokens}>{fmtTokens(item.approx_tokens)}</Text>
              </View>
            ) : null}
            {item.last_active ? <Text style={styles.chatTime}>{fmtTime(item.last_active)}</Text> : null}
          </View>
        </View>
      </TouchableOpacity>
    );
  }

  return (
    <View style={[styles.container, { paddingTop: insets.top + 8, paddingBottom: insets.bottom + 8 }]}>
      {/* New Chat button */}
      <TouchableOpacity style={styles.newChatBtn} onPress={() => { onNewChat(); onClose(); }} activeOpacity={0.7}>
        <IconPlus size={16} color="#fff" />
        <Text style={styles.newChatText}>New Chat</Text>
      </TouchableOpacity>

      {/* Search toggle */}
      <View style={styles.searchToggleRow}>
        <TouchableOpacity style={styles.searchBtn} onPress={() => setShowSearch(!showSearch)}>
          {showSearch ? <IconX size={16} color={colors.labelTertiary} /> : <IconSearch size={16} color={colors.labelTertiary} />}
        </TouchableOpacity>
        {showSearch && (
          <TextInput
            style={styles.searchInput}
            value={search}
            onChangeText={setSearch}
            placeholder="Search chats..."
            placeholderTextColor={colors.labelTertiary}
            autoFocus
          />
        )}
      </View>

      {/* Main scrollable area: Projects then Recents */}
      <ScrollView style={styles.chatList} showsVerticalScrollIndicator={false}>
        {/* ── Projects section ── */}
        {(folders.length > 0 || showNewFolder) && (
          <View style={styles.sectionBlock}>
            <View style={styles.sectionHeaderRow}>
              <Text style={styles.sectionLabel}>PROJECTS</Text>
              <TouchableOpacity onPress={() => setShowNewFolder(!showNewFolder)} activeOpacity={0.7}>
                {showNewFolder
                  ? <IconX size={12} color={colors.labelTertiary} />
                  : <IconNewFolder size={12} color={colors.accent} />
                }
              </TouchableOpacity>
            </View>
            {showNewFolder && (
              <View style={styles.newFolderRow}>
                <TextInput style={styles.newFolderInput} value={newFolderName}
                  onChangeText={setNewFolderName} placeholder="Folder name"
                  placeholderTextColor={colors.labelTertiary} autoFocus
                  onSubmitEditing={handleCreateFolder} />
                <TouchableOpacity onPress={handleCreateFolder} activeOpacity={0.7}>
                  <IconPlus size={16} color={colors.accent} />
                </TouchableOpacity>
              </View>
            )}
            {folders.map((f) => {
              const chats = getProjectChats(f.id);
              const collapsed = collapsedFolders.has(f.id);
              return (
                <View key={f.id} style={styles.folderBlock}>
                  <TouchableOpacity
                    style={styles.folderHeader}
                    onPress={() => toggleFolderCollapse(f.id)}
                    onLongPress={() => confirmDeleteFolder(f)}
                    activeOpacity={0.7}
                  >
                    {collapsed
                      ? <IconChevronRight size={12} color={colors.labelTertiary} />
                      : <IconChevronDown size={12} color={colors.labelTertiary} />
                    }
                    <IconFolder size={14} color={f.color || colors.accent} />
                    <Text style={styles.folderName}>{f.name}</Text>
                    <Text style={styles.folderCount}>{chats.length}</Text>
                  </TouchableOpacity>
                  {!collapsed && chats.map((c) => <ChatRow key={c.id} item={c} />)}
                </View>
              );
            })}
          </View>
        )}

        {/* ── Recents section ── */}
        <View style={styles.sectionBlock}>
          <Text style={styles.sectionLabel}>RECENTS</Text>
          {unfiled.length > 0 ? (
            unfiled.map((c) => <ChatRow key={c.id} item={c} />)
          ) : (
            <Text style={styles.emptyText}>No conversations yet</Text>
          )}
        </View>

        {/* Move to folder overlay */}
        {moveConvId && (
          <View style={styles.moveOverlay}>
            <Text style={styles.moveTitle}>Move to folder</Text>
            <TouchableOpacity style={styles.moveOption} onPress={() => moveConversation(moveConvId, null)} activeOpacity={0.7}>
              <Text style={styles.moveOptionText}>No folder (unfiled)</Text>
            </TouchableOpacity>
            {folders.map((f) => (
              <TouchableOpacity key={f.id} style={styles.moveOption} onPress={() => moveConversation(moveConvId, f.id)} activeOpacity={0.7}>
                <IconFolder size={14} color={f.color || colors.accent} />
                <Text style={styles.moveOptionText}>{f.name}</Text>
              </TouchableOpacity>
            ))}
            <TouchableOpacity style={[styles.moveOption, { marginTop: 8 }]} onPress={() => setMoveConvId(null)} activeOpacity={0.7}>
              <Text style={{ fontSize: 13, color: colors.danger, fontWeight: "600" }}>Cancel</Text>
            </TouchableOpacity>
          </View>
        )}
      </ScrollView>

      {/* Bottom: profile + settings */}
      <View style={styles.bottomBar}>
        <View style={styles.statusRow}>
          {serverOk ? <IconWifi size={12} /> : <IconWifiOff size={12} />}
          <Text style={[styles.statusText, { color: serverOk ? colors.success : colors.danger }]}>
            {serverOk ? "Online" : "Offline"}
          </Text>
        </View>

        <View style={styles.profileRow}>
          <View style={styles.avatar}>
            <Text style={styles.avatarLetter}>
              {user?.username?.[0]?.toUpperCase() || "?"}
            </Text>
          </View>
          <View style={styles.profileInfo}>
            <Text style={styles.profileName} numberOfLines={1}>{user?.username || "User"}</Text>
            {user?.role && (
              <View style={styles.roleBadge}>
                <Text style={styles.roleBadgeText}>{user.role}</Text>
              </View>
            )}
          </View>
        </View>

        <View style={styles.bottomActions}>
          <TouchableOpacity
            style={styles.bottomBtn}
            onPress={() => { onOpenSettings(); onClose(); }}
            activeOpacity={0.7}
          >
            <IconSettings size={18} color={colors.labelSecondary} />
            <Text style={styles.bottomBtnText}>Settings</Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.bottomBtn} onPress={handleLogout} activeOpacity={0.7}>
            <IconLogout size={18} color={colors.danger} />
            <Text style={[styles.bottomBtnText, { color: colors.danger }]}>Sign Out</Text>
          </TouchableOpacity>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.surfaceRaised,
    paddingHorizontal: spacing.md,
  },

  // New Chat
  newChatBtn: {
    flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 8,
    backgroundColor: colors.accent,
    borderRadius: radius.md,
    paddingVertical: 12,
    marginBottom: spacing.md,
  },
  newChatText: { color: "#fff", fontSize: 14, fontWeight: "600" },

  // Search toggle
  searchToggleRow: {
    flexDirection: "row", alignItems: "center", gap: 8,
    marginBottom: spacing.sm,
  },
  searchBtn: { padding: 6 },
  searchInput: {
    flex: 1, fontSize: 13, color: colors.label,
    backgroundColor: colors.white05,
    borderRadius: radius.sm,
    paddingHorizontal: spacing.sm, paddingVertical: 8,
    borderWidth: 1, borderColor: colors.separator,
  },

  // Section
  sectionBlock: { marginBottom: spacing.md },
  sectionHeaderRow: {
    flexDirection: "row", alignItems: "center", justifyContent: "space-between",
    paddingHorizontal: spacing.sm, marginBottom: 6,
  },
  sectionLabel: {
    fontSize: 10, fontWeight: "700", color: colors.labelTertiary,
    textTransform: "uppercase", letterSpacing: 1.2,
  },

  // Chat list
  chatList: { flex: 1 },
  chatRow: {
    flexDirection: "row", alignItems: "center", gap: 8,
    paddingHorizontal: spacing.sm,
    paddingVertical: 10,
    borderRadius: radius.sm,
    marginBottom: 1,
  },
  chatRowActive: { backgroundColor: colors.accentSubtle },
  chatDotWrap: {
    width: 3, height: 24, borderRadius: 1.5,
    backgroundColor: "transparent",
  },
  chatDotActive: { backgroundColor: colors.accent },
  chatRowLeft: { flex: 1, gap: 3 },
  chatTitle: { fontSize: 13, fontWeight: "500", color: colors.label },
  chatTitleActive: { color: colors.accent, fontWeight: "600" },
  chatMeta: { flexDirection: "row", alignItems: "center", gap: 6 },
  chatTokenBadge: {
    backgroundColor: colors.white05,
    borderRadius: radius.full,
    paddingHorizontal: 5, paddingVertical: 1,
  },
  chatTokens: { fontSize: 9, color: colors.labelTertiary, fontWeight: "700" },
  chatTime: { fontSize: 10, color: colors.labelTertiary },

  // Folders
  folderBlock: { marginBottom: spacing.md },
  folderHeader: {
    flexDirection: "row", alignItems: "center", gap: 6,
    paddingHorizontal: spacing.sm,
    paddingVertical: 6,
  },
  folderName: { fontSize: 12, fontWeight: "700", color: colors.labelSecondary, flex: 1 },
  folderCount: { fontSize: 10, color: colors.labelTertiary },

  // New folder
  newFolderRow: {
    flexDirection: "row", alignItems: "center", gap: 8,
    marginBottom: spacing.sm, paddingHorizontal: spacing.sm,
  },
  newFolderInput: {
    flex: 1, fontSize: 13, color: colors.label,
    backgroundColor: colors.white05, borderRadius: radius.sm,
    paddingHorizontal: 10, paddingVertical: 8,
    borderWidth: 1, borderColor: colors.separator,
  },
  // Move to folder
  moveOverlay: {
    position: "absolute", left: spacing.md, right: spacing.md,
    top: 120, backgroundColor: colors.surfaceRaised,
    borderRadius: radius.md, padding: spacing.md,
    borderWidth: 1, borderColor: colors.separator,
    shadowColor: "#000", shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3, shadowRadius: 12, elevation: 20,
    zIndex: 100,
  },
  moveTitle: {
    fontSize: 14, fontWeight: "700", color: colors.label,
    marginBottom: spacing.sm,
  },
  moveOption: {
    flexDirection: "row", alignItems: "center", gap: 8,
    paddingVertical: 10, paddingHorizontal: spacing.sm,
    borderRadius: radius.sm,
  },
  moveOptionText: { fontSize: 13, color: colors.label, fontWeight: "500" },

  // Empty
  emptyText: { fontSize: 13, color: colors.labelTertiary, textAlign: "center", paddingTop: 40 },

  // Bottom bar
  bottomBar: {
    borderTopWidth: 1, borderTopColor: colors.separator,
    paddingTop: spacing.md,
  },
  statusRow: {
    flexDirection: "row", alignItems: "center", gap: 6,
    marginBottom: spacing.sm,
  },
  statusText: { fontSize: 11, fontWeight: "600" },

  profileRow: {
    flexDirection: "row", alignItems: "center", gap: spacing.sm,
    marginBottom: spacing.md,
  },
  avatar: {
    width: 32, height: 32, borderRadius: 16,
    backgroundColor: colors.accent,
    alignItems: "center", justifyContent: "center",
  },
  avatarLetter: { color: "#fff", fontSize: 14, fontWeight: "700" },
  profileInfo: { flex: 1, flexDirection: "row", alignItems: "center", gap: 6 },
  profileName: { fontSize: 14, fontWeight: "600", color: colors.label },
  roleBadge: {
    backgroundColor: colors.accentSubtle,
    paddingHorizontal: 6, paddingVertical: 1,
    borderRadius: radius.full,
  },
  roleBadgeText: { fontSize: 9, color: colors.accent, fontWeight: "700", textTransform: "uppercase" },

  bottomActions: { flexDirection: "row", gap: spacing.sm },
  bottomBtn: {
    flex: 1, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 6,
    backgroundColor: colors.white05,
    borderRadius: radius.sm,
    paddingVertical: 10,
    borderWidth: 1, borderColor: colors.separator,
  },
  bottomBtnText: { fontSize: 12, fontWeight: "600", color: colors.labelSecondary },
});
