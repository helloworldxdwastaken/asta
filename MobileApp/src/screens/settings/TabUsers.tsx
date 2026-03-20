import React, { useState, useEffect } from "react";
import { View, Text, TextInput, TouchableOpacity, Alert, Platform } from "react-native";
import { colors, spacing, radius } from "../../theme/colors";
import { listUsers, createUser, deleteUser, resetUserPassword } from "../../lib/api";
import { IconPlus } from "../../components/Icons";
import { Chip, st, TabProps } from "./shared";

export default function TabUsers(_props: TabProps) {
  const [usersList, setUsersList] = useState<any[]>([]);
  const [showAddUser, setShowAddUser] = useState(false);
  const [newUsername, setNewUsername] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newRole, setNewRole] = useState<"user" | "admin">("user");
  const [userSaving, setUserSaving] = useState(false);
  const [userError, setUserError] = useState("");
  const [resetPwId, setResetPwId] = useState<string | null>(null);
  const [resetPwVal, setResetPwVal] = useState("");

  useEffect(() => {
    listUsers().then((r) => setUsersList(r.users || [])).catch(() => {});
  }, []);

  async function handleAddUser() {
    if (!newUsername.trim() || !newPassword.trim()) return;
    setUserSaving(true);
    setUserError("");
    try {
      await createUser(newUsername.trim(), newPassword, newRole);
      const r = await listUsers();
      setUsersList(r.users || []);
      setShowAddUser(false);
      setNewUsername("");
      setNewPassword("");
      setNewRole("user");
    } catch (e: any) {
      const msg = e.message || "";
      if (msg.includes("409")) setUserError("Username already taken");
      else setUserError("Failed to create user");
    }
    setUserSaving(false);
  }

  async function handleDeleteUser(uid: string) {
    const doDelete = async () => {
      await deleteUser(uid).catch(() => {});
      const r = await listUsers().catch(() => ({ users: [] }));
      setUsersList(r.users || []);
    };
    if (Platform.OS === "web") {
      if (confirm("Delete this user?")) await doDelete();
      return;
    }
    Alert.alert("Delete User", "This will prevent them from logging in. Continue?", [
      { text: "Cancel", style: "cancel" },
      { text: "Delete", style: "destructive", onPress: doDelete },
    ]);
  }

  async function handleResetPw() {
    if (!resetPwId || resetPwVal.length < 4) return;
    await resetUserPassword(resetPwId, resetPwVal).catch(() => {});
    setResetPwId(null);
    setResetPwVal("");
  }

  return (
    <>
      <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: spacing.lg }}>
        <Text style={st.desc}>Manage user accounts.</Text>
        <TouchableOpacity
          style={{ flexDirection: "row", alignItems: "center", gap: 4, backgroundColor: colors.accent, borderRadius: radius.md, paddingHorizontal: 12, paddingVertical: 8 }}
          onPress={() => setShowAddUser(!showAddUser)}
          activeOpacity={0.7}
        >
          <IconPlus size={14} color="#fff" />
          <Text style={{ fontSize: 13, fontWeight: "600", color: "#fff" }}>Add</Text>
        </TouchableOpacity>
      </View>

      {/* Add user form */}
      {showAddUser && (
        <View style={[st.card, { padding: 16, marginBottom: spacing.lg, gap: 10 }]}>
          <TextInput
            style={st.keyInput}
            value={newUsername}
            onChangeText={setNewUsername}
            placeholder="Username"
            placeholderTextColor={colors.labelTertiary}
            autoCapitalize="none"
            autoCorrect={false}
          />
          <TextInput
            style={st.keyInput}
            value={newPassword}
            onChangeText={setNewPassword}
            placeholder="Password (min 4 chars)"
            placeholderTextColor={colors.labelTertiary}
            secureTextEntry
          />
          <View style={st.chipRow}>
            <Chip label="User" active={newRole === "user"} color={colors.accent}
              onPress={() => setNewRole("user")} />
            <Chip label="Admin" active={newRole === "admin"} color={colors.accent}
              onPress={() => setNewRole("admin")} />
          </View>
          {userError ? <Text style={{ fontSize: 12, color: colors.danger }}>{userError}</Text> : null}
          <TouchableOpacity
            style={[st.accentBtn, { marginTop: 4, opacity: newUsername.trim() && newPassword.length >= 4 ? 1 : 0.4 }]}
            onPress={handleAddUser}
            disabled={!newUsername.trim() || newPassword.length < 4 || userSaving}
            activeOpacity={0.7}
          >
            <Text style={st.accentBtnText}>{userSaving ? "Creating..." : "Create User"}</Text>
          </TouchableOpacity>
        </View>
      )}

      {usersList.length === 0 && (
        <Text style={st.emptyText}>No users created yet. Running in single-user mode.</Text>
      )}

      {usersList.map((u) => (
        <View key={u.id} style={st.toggleRow}>
          <View style={{ flex: 1 }}>
            <View style={{ flexDirection: "row", alignItems: "center", gap: 8, marginBottom: 2 }}>
              <Text style={st.toggleName}>{u.username}</Text>
              <View style={{
                backgroundColor: u.role === "admin" ? "rgba(99,102,241,0.12)" : colors.white08,
                paddingHorizontal: 6, paddingVertical: 1, borderRadius: radius.full,
              }}>
                <Text style={{
                  fontSize: 10, fontWeight: "700", textTransform: "uppercase",
                  color: u.role === "admin" ? "#818CF8" : colors.labelTertiary,
                }}>{u.role}</Text>
              </View>
            </View>

            {/* Reset password inline */}
            {resetPwId === String(u.id) ? (
              <View style={{ flexDirection: "row", gap: 6, marginTop: 6 }}>
                <TextInput
                  style={[st.keyInput, { flex: 1, paddingVertical: 8 }]}
                  value={resetPwVal}
                  onChangeText={setResetPwVal}
                  placeholder="New password"
                  placeholderTextColor={colors.labelTertiary}
                  secureTextEntry
                  autoFocus
                />
                <TouchableOpacity
                  style={{ backgroundColor: colors.accent, borderRadius: radius.sm, paddingHorizontal: 12, justifyContent: "center" }}
                  onPress={handleResetPw}
                  disabled={resetPwVal.length < 4}
                  activeOpacity={0.7}
                >
                  <Text style={{ fontSize: 12, fontWeight: "600", color: "#fff" }}>Save</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={{ justifyContent: "center", paddingHorizontal: 8 }}
                  onPress={() => { setResetPwId(null); setResetPwVal(""); }}
                  activeOpacity={0.7}
                >
                  <Text style={{ fontSize: 12, fontWeight: "600", color: colors.labelTertiary }}>Cancel</Text>
                </TouchableOpacity>
              </View>
            ) : (
              <View style={{ flexDirection: "row", gap: 12, marginTop: 6 }}>
                <TouchableOpacity onPress={() => { setResetPwId(String(u.id)); setResetPwVal(""); }} activeOpacity={0.7}>
                  <Text style={{ fontSize: 12, fontWeight: "600", color: colors.accent }}>Reset password</Text>
                </TouchableOpacity>
                <TouchableOpacity onPress={() => handleDeleteUser(String(u.id))} activeOpacity={0.7}>
                  <Text style={{ fontSize: 12, fontWeight: "600", color: colors.danger }}>Delete</Text>
                </TouchableOpacity>
              </View>
            )}
          </View>
        </View>
      ))}
    </>
  );
}
