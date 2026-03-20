import React, { useState, useEffect } from "react";
import { View, Text, ScrollView, TouchableOpacity, Alert, Platform } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { colors } from "../theme/colors";
import { checkHealth, getServerStatus, getUsage, getKeyStatus } from "../lib/api";
import { clearAuth, getUser, isAdmin } from "../lib/auth";
import type { User } from "../lib/types";
import {
  IconChevronLeft, IconChevronRight, IconBrain, IconUser, IconServer,
  IconKey, IconWifi, IconWifiOff, IconPuzzle, IconAgents, IconSend,
  IconInfo, IconSettings, IconPerson, IconClock, IconPlus, IconWarning, IconGlobe, IconMusic,
} from "../components/Icons";
import { st } from "./settings/shared";
import {
  TabGeneral, TabKeys, TabModels, TabAgents, TabSkills, TabPersona,
  TabChannels, TabCron, TabUsers, TabKnowledge, TabPermissions,
  TabConnection, TabGoogle, TabSpotify, TabAbout,
} from "./settings";

/* ── Tab definitions ──────────────────────────────── */

type TabId = "general" | "keys" | "models" | "skills" | "agents" | "persona" | "channels" | "cron" | "users" | "knowledge" | "permissions" | "connection" | "google" | "spotify" | "about";

interface TabDef {
  id: TabId;
  label: string;
  Icon: (props: { size?: number; color?: string }) => React.ReactElement;
  adminOnly: boolean;
}

const TABS: TabDef[] = [
  { id: "general",    label: "General",    Icon: IconSettings,  adminOnly: false },
  { id: "keys",       label: "API Keys",   Icon: IconKey,       adminOnly: true },
  { id: "models",     label: "Models",     Icon: IconServer,    adminOnly: true },
  { id: "agents",     label: "Agents",     Icon: IconAgents,    adminOnly: true },
  { id: "skills",     label: "Skills",     Icon: IconPuzzle,    adminOnly: true },
  { id: "persona",    label: "Persona",    Icon: IconPerson,    adminOnly: false },
  { id: "channels",   label: "Channels",   Icon: IconSend,      adminOnly: true },
  { id: "cron",       label: "Schedule",   Icon: IconClock,     adminOnly: true },
  { id: "users",      label: "Users",      Icon: IconUser,      adminOnly: true },
  { id: "knowledge",  label: "Knowledge",  Icon: IconBrain,     adminOnly: true },
  { id: "permissions", label: "Permissions", Icon: IconWarning, adminOnly: true },
  { id: "connection", label: "Connection", Icon: IconServer,    adminOnly: true },
  { id: "google",     label: "Google",     Icon: IconGlobe,     adminOnly: true },
  { id: "spotify",    label: "Spotify",    Icon: IconMusic,     adminOnly: true },
  { id: "about",      label: "About",      Icon: IconInfo,      adminOnly: false },
];

/* ── Props ────────────────────────────────────────── */

interface Props {
  onBack: () => void;
  onLogout: () => void;
  provider: string;
  thinkingLevel: string;
  mood: string;
  onProviderChange: (p: string) => void;
  onThinkingChange: (t: string) => void;
  onMoodChange: (m: string) => void;
}

export default function SettingsScreen({
  onBack, onLogout, provider, thinkingLevel, mood,
  onProviderChange, onThinkingChange, onMoodChange,
}: Props) {
  const insets = useSafeAreaInsets();
  const [activeTab, setActiveTab] = useState<TabId | null>(null);
  const [admin, setAdmin] = useState(false);
  const [user, setUserState] = useState<User | null>(null);

  const [serverVersion, setServerVersion] = useState("");
  const [serverOk, setServerOk] = useState<boolean | null>(null);
  const [serverStatus, setServerStatus] = useState<any>(null);
  const [usage, setUsage] = useState<any>(null);
  const [keyStatus, setKeyStatus] = useState<Record<string, boolean>>({});

  useEffect(() => {
    getUser().then(setUserState);
    isAdmin().then(setAdmin);
    checkHealth().then((r) => { setServerVersion(r.version || ""); setServerOk(true); }).catch(() => setServerOk(false));
    getServerStatus().then(setServerStatus).catch(() => {});
    getUsage().then(setUsage).catch(() => {});
    getKeyStatus().then(setKeyStatus).catch(() => {});
  }, []);

  const visibleTabs = TABS.filter((t) => !t.adminOnly || admin);

  function doLogout() {
    if (Platform.OS === "web") { if (confirm("Sign out?")) clearAuth().then(onLogout); return; }
    Alert.alert("Sign Out", "Are you sure?", [
      { text: "Cancel", style: "cancel" },
      { text: "Sign Out", style: "destructive", onPress: () => clearAuth().then(onLogout) },
    ]);
  }

  /* ─────── Tab list view (no tab selected) ─────── */

  if (activeTab === null) {
    return (
      <View style={st.container}>
        <View style={st.dragHandle} />
        <View style={st.header}>
          <TouchableOpacity onPress={onBack} activeOpacity={0.7} style={st.headerBack}>
            <IconChevronLeft size={22} color={colors.accent} />
          </TouchableOpacity>
          <Text style={st.headerTitle}>Settings</Text>
          <View style={{ width: 32 }} />
        </View>

        <ScrollView style={st.menuScroll} contentContainerStyle={{ paddingBottom: insets.bottom + 40 }}>
          {/* User card */}
          {user && (
            <View style={st.userCard}>
              <View style={st.userAvatar}>
                <Text style={st.userAvatarLetter}>{user.username?.[0]?.toUpperCase() || "?"}</Text>
              </View>
              <View style={{ flex: 1 }}>
                <Text style={st.userName}>{user.username}</Text>
                <View style={st.userRoleBadge}>
                  <Text style={st.userRoleText}>{user.role}</Text>
                </View>
              </View>
              <View style={st.statusDotWrap}>
                {serverOk ? <IconWifi size={14} /> : <IconWifiOff size={14} />}
              </View>
            </View>
          )}

          {/* Tab list */}
          <Text style={st.menuSectionLabel}>Settings</Text>
          {visibleTabs.map((tab) => (
            <TouchableOpacity
              key={tab.id}
              style={st.menuRow}
              onPress={() => setActiveTab(tab.id)}
              activeOpacity={0.7}
            >
              <View style={st.menuIconWrap}>
                <tab.Icon size={18} color={colors.labelSecondary} />
              </View>
              <Text style={st.menuLabel}>{tab.label}</Text>
              <IconChevronRight size={16} color={colors.labelTertiary} />
            </TouchableOpacity>
          ))}

          {/* Logout */}
          <TouchableOpacity style={st.logoutRow} onPress={doLogout} activeOpacity={0.7}>
            <Text style={st.logoutText}>Sign Out</Text>
          </TouchableOpacity>

          {/* Version */}
          {serverVersion ? (
            <Text style={st.versionText}>Server {serverVersion}</Text>
          ) : null}
        </ScrollView>
      </View>
    );
  }

  /* ─────── Tab content view (tab selected) ─────── */

  const currentTab = TABS.find((t) => t.id === activeTab)!;

  function renderTab() {
    switch (activeTab) {
      case "general":
        return <TabGeneral admin={admin} provider={provider} thinkingLevel={thinkingLevel} mood={mood}
          onProviderChange={onProviderChange} onThinkingChange={onThinkingChange} onMoodChange={onMoodChange} />;
      case "keys":
        return <TabKeys admin={admin} />;
      case "models":
        return <TabModels admin={admin} />;
      case "agents":
        return <TabAgents admin={admin} />;
      case "skills":
        return <TabSkills admin={admin} />;
      case "persona":
        return <TabPersona admin={admin} />;
      case "channels":
        return <TabChannels admin={admin} />;
      case "cron":
        return <TabCron admin={admin} />;
      case "users":
        return <TabUsers admin={admin} />;
      case "knowledge":
        return <TabKnowledge admin={admin} />;
      case "permissions":
        return <TabPermissions admin={admin} />;
      case "connection":
        return <TabConnection admin={admin} serverOk={serverOk} serverVersion={serverVersion} setServerOk={setServerOk} />;
      case "google":
        return <TabGoogle admin={admin} keyStatus={keyStatus} setKeyStatus={setKeyStatus} />;
      case "spotify":
        return <TabSpotify admin={admin} />;
      case "about":
        return <TabAbout admin={admin} serverOk={serverOk} serverVersion={serverVersion} serverStatus={serverStatus} usage={usage} />;
      default:
        return null;
    }
  }

  return (
    <View style={st.container}>
      <View style={st.dragHandle} />
      {/* Header with back to tab list */}
      <View style={st.header}>
        <TouchableOpacity onPress={() => setActiveTab(null)} activeOpacity={0.7} style={st.headerBack}>
          <IconChevronLeft size={22} color={colors.accent} />
        </TouchableOpacity>
        <Text style={st.headerTitle}>{currentTab.label}</Text>
        <View style={{ width: 32 }} />
      </View>

      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={[st.tabContent, { paddingBottom: insets.bottom + 40 }]}
        key={activeTab}
      >
        {renderTab()}
      </ScrollView>
    </View>
  );
}
