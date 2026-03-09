import React, { useState, useEffect, useCallback } from "react";
import {
  View, Text, TouchableOpacity, FlatList, TextInput,
  StyleSheet, Alert, Platform, ScrollView,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { colors, spacing, radius } from "../theme/colors";
import {
  listConversations, deleteConversation, listFolders,
  createFolder, deleteFolder, renameFolder, assignConversationFolder,
} from "../lib/api";
import { clearAuth, getUser } from "../lib/auth";
import type { Conversation, Folder, User } from "../lib/types";
import {
  IconPlus, IconChat, IconFolder, IconSearch, IconSettings,
  IconLogout, IconTrash, IconUser, IconX, IconWifi, IconWifiOff,
  IconEdit, IconNewFolder,
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
  const [activeSection, setActiveSection] = useState<"recents" | "projects">("recents");
  const [newFolderName, setNewFolderName] = useState("");
  const [showNewFolder, setShowNewFolder] = useState(false);
  const [moveConvId, setMoveConvId] = useState<string | null>(null);

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

  function showConversationActions(item: Conversation) {
    if (Platform.OS === "web") {
      const action = prompt("Type 'delete' to delete, 'move' to move to folder:");
      if (action === "delete") doDelete(item.id);
      else if (action === "move") setMoveConvId(item.id);
      return;
    }
    const buttons: any[] = [
      { text: "Cancel", style: "cancel" },
      { text: "Move to Folder", onPress: () => setMoveConvId(item.id) },
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
        <View style={styles.chatRowLeft}>
          <Text style={[styles.chatTitle, active && styles.chatTitleActive]} numberOfLines={1}>
            {item.title || "New chat"}
          </Text>
          <View style={styles.chatMeta}>
            {item.approx_tokens ? <Text style={styles.chatTokens}>{fmtTokens(item.approx_tokens)}</Text> : null}
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

      {/* Section tabs */}
      <View style={styles.sectionTabs}>
        <TouchableOpacity
          style={[styles.sectionTab, activeSection === "recents" && styles.sectionTabActive]}
          onPress={() => setActiveSection("recents")}
        >
          <Text style={[styles.sectionTabText, activeSection === "recents" && styles.sectionTabTextActive]}>
            Recents
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.sectionTab, activeSection === "projects" && styles.sectionTabActive]}
          onPress={() => setActiveSection("projects")}
        >
          <Text style={[styles.sectionTabText, activeSection === "projects" && styles.sectionTabTextActive]}>
            Projects
          </Text>
        </TouchableOpacity>
        <View style={{ flex: 1 }} />
        <TouchableOpacity style={styles.searchBtn} onPress={() => setShowSearch(!showSearch)}>
          {showSearch ? <IconX size={16} color={colors.labelTertiary} /> : <IconSearch size={16} color={colors.labelTertiary} />}
        </TouchableOpacity>
      </View>

      {/* Search bar */}
      {showSearch && (
        <View style={styles.searchBar}>
          <IconSearch size={14} color={colors.labelTertiary} />
          <TextInput
            style={styles.searchInput}
            value={search}
            onChangeText={setSearch}
            placeholder="Search chats..."
            placeholderTextColor={colors.labelTertiary}
            autoFocus
          />
        </View>
      )}

      {/* Chat list */}
      <ScrollView style={styles.chatList} showsVerticalScrollIndicator={false}>
        {activeSection === "recents" ? (
          unfiled.length > 0 ? (
            unfiled.map((c) => <ChatRow key={c.id} item={c} />)
          ) : (
            <Text style={styles.emptyText}>No conversations yet</Text>
          )
        ) : (
          <>
            {/* Create folder */}
            {showNewFolder ? (
              <View style={styles.newFolderRow}>
                <TextInput style={styles.newFolderInput} value={newFolderName}
                  onChangeText={setNewFolderName} placeholder="Folder name"
                  placeholderTextColor={colors.labelTertiary} autoFocus
                  onSubmitEditing={handleCreateFolder} />
                <TouchableOpacity onPress={handleCreateFolder} activeOpacity={0.7}>
                  <IconPlus size={16} color={colors.accent} />
                </TouchableOpacity>
                <TouchableOpacity onPress={() => { setShowNewFolder(false); setNewFolderName(""); }} activeOpacity={0.7}>
                  <IconX size={16} color={colors.labelTertiary} />
                </TouchableOpacity>
              </View>
            ) : (
              <TouchableOpacity style={styles.addFolderBtn} onPress={() => setShowNewFolder(true)} activeOpacity={0.7}>
                <IconNewFolder size={14} color={colors.accent} />
                <Text style={{ fontSize: 12, color: colors.accent, fontWeight: "600" }}>New Folder</Text>
              </TouchableOpacity>
            )}

            {folders.map((f) => {
              const chats = getProjectChats(f.id);
              return (
                <View key={f.id} style={styles.folderBlock}>
                  <TouchableOpacity style={styles.folderHeader} onLongPress={() => confirmDeleteFolder(f)} activeOpacity={0.7}>
                    <IconFolder size={14} color={f.color || colors.accent} />
                    <Text style={styles.folderName}>{f.name}</Text>
                    <Text style={styles.folderCount}>{chats.length}</Text>
                  </TouchableOpacity>
                  {chats.map((c) => <ChatRow key={c.id} item={c} />)}
                </View>
              );
            })}
            {folders.length === 0 && !showNewFolder && (
              <Text style={styles.emptyText}>No projects yet</Text>
            )}
          </>
        )}

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

  // Section tabs
  sectionTabs: {
    flexDirection: "row", alignItems: "center", gap: 4,
    marginBottom: spacing.sm,
  },
  sectionTab: {
    paddingHorizontal: 12, paddingVertical: 6,
    borderRadius: radius.full,
  },
  sectionTabActive: { backgroundColor: colors.accentSubtle },
  sectionTabText: { fontSize: 13, fontWeight: "600", color: colors.labelTertiary },
  sectionTabTextActive: { color: colors.accent },
  searchBtn: { padding: 6 },

  // Search
  searchBar: {
    flexDirection: "row", alignItems: "center", gap: 8,
    backgroundColor: colors.white05,
    borderRadius: radius.sm,
    paddingHorizontal: spacing.sm,
    marginBottom: spacing.sm,
    borderWidth: 1, borderColor: colors.separator,
  },
  searchInput: {
    flex: 1, fontSize: 13, color: colors.label,
    paddingVertical: 8,
  },

  // Chat list
  chatList: { flex: 1 },
  chatRow: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 10,
    borderRadius: radius.sm,
    marginBottom: 2,
  },
  chatRowActive: { backgroundColor: colors.accentSubtle },
  chatRowLeft: { gap: 2 },
  chatTitle: { fontSize: 13, fontWeight: "500", color: colors.label },
  chatTitleActive: { color: colors.accent, fontWeight: "600" },
  chatMeta: { flexDirection: "row", gap: 8 },
  chatTokens: { fontSize: 10, color: colors.labelTertiary, fontWeight: "600" },
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
  addFolderBtn: {
    flexDirection: "row", alignItems: "center", gap: 6,
    paddingHorizontal: spacing.sm, paddingVertical: 8,
    marginBottom: spacing.sm,
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
