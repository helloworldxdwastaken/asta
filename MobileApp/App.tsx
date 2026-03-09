import React, { useState, useEffect, useRef } from "react";
import { StatusBar } from "expo-status-bar";
import {
  ActivityIndicator, View, Animated, Dimensions,
  TouchableOpacity, StyleSheet, Platform,
} from "react-native";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { colors } from "./src/theme/colors";
import { getJwt } from "./src/lib/auth";
import { checkHealth, getMe, getThinking, getDefaultAI, getMoodSetting, listAgents } from "./src/lib/api";
import type { Agent } from "./src/lib/types";

import LoginScreen from "./src/screens/LoginScreen";
import ChatScreen from "./src/screens/ChatScreen";
import SettingsScreen from "./src/screens/SettingsScreen";
import Drawer from "./src/components/Drawer";

const DRAWER_WIDTH = Math.min(Dimensions.get("window").width * 0.82, 320);

export default function App() {
  const [authed, setAuthed] = useState<boolean | null>(null);
  const [needsLogin, setNeedsLogin] = useState(false);
  const [screen, setScreen] = useState<"chat" | "settings">("chat");
  const [conversationId, setConversationId] = useState<string | undefined>();
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const [provider, setProvider] = useState("claude");
  const [thinkingLevel, setThinkingLevel] = useState("off");
  const [mood, setMood] = useState("normal");
  const [agents, setAgents] = useState<Agent[]>([]);
  const [serverOk, setServerOk] = useState<boolean | null>(null);

  // Drawer
  const [drawerOpen, setDrawerOpen] = useState(false);
  const drawerAnim = useRef(new Animated.Value(-DRAWER_WIDTH)).current;
  const overlayAnim = useRef(new Animated.Value(0)).current;

  function openDrawer() {
    setDrawerOpen(true);
    Animated.parallel([
      Animated.spring(drawerAnim, { toValue: 0, useNativeDriver: true, tension: 65, friction: 11 }),
      Animated.timing(overlayAnim, { toValue: 1, duration: 250, useNativeDriver: true }),
    ]).start();
  }

  function closeDrawer() {
    Animated.parallel([
      Animated.spring(drawerAnim, { toValue: -DRAWER_WIDTH, useNativeDriver: true, tension: 65, friction: 11 }),
      Animated.timing(overlayAnim, { toValue: 0, duration: 200, useNativeDriver: true }),
    ]).start(() => setDrawerOpen(false));
  }

  useEffect(() => {
    (async () => {
      const jwt = await getJwt();
      if (!jwt) {
        try { await getMe(); setAuthed(true); setNeedsLogin(false); }
        catch { setNeedsLogin(true); setAuthed(false); }
        return;
      }
      try { await getMe(); setAuthed(true); }
      catch { setAuthed(true); } // offline — trust JWT
    })();
  }, []);

  useEffect(() => {
    if (!authed) return;
    getDefaultAI().then((r) => setProvider(r.provider || "claude")).catch(() => {});
    getThinking().then((r) => setThinkingLevel(r.thinking_level || "off")).catch(() => {});
    getMoodSetting().then((r) => setMood(r.mood || "normal")).catch(() => {});
    listAgents().then((r) => setAgents((r.agents || []).filter((a: Agent) => a.enabled))).catch(() => {});
    checkHealth().then(() => setServerOk(true)).catch(() => setServerOk(false));
  }, [authed]);

  // Loading
  if (authed === null) {
    return (
      <View style={styles.loading}>
        <ActivityIndicator size="large" color={colors.accent} />
        <StatusBar style="light" />
      </View>
    );
  }

  // Login
  if (needsLogin && !authed) {
    return (
      <SafeAreaProvider>
        <LoginScreen onLogin={() => { setAuthed(true); setNeedsLogin(false); }} />
        <StatusBar style="light" />
      </SafeAreaProvider>
    );
  }

  return (
    <SafeAreaProvider>
      <View style={styles.root}>
        {/* Main content */}
        {screen === "chat" ? (
          <ChatScreen
            conversationId={conversationId}
            onConversationCreated={(id) => {
              setConversationId(id);
              setRefreshTrigger((n) => n + 1);
            }}
            provider={provider}
            thinkingLevel={thinkingLevel}
            mood={mood}
            agents={agents}
            onOpenDrawer={openDrawer}
            onProviderChange={setProvider}
            onThinkingChange={setThinkingLevel}
            onMoodChange={setMood}
          />
        ) : (
          <SettingsScreen
            onBack={() => setScreen("chat")}
            onLogout={() => { setAuthed(false); setNeedsLogin(true); }}
            provider={provider}
            thinkingLevel={thinkingLevel}
            mood={mood}
            onProviderChange={setProvider}
            onThinkingChange={setThinkingLevel}
            onMoodChange={setMood}
          />
        )}

        {/* Drawer overlay */}
        {drawerOpen && (
          <Animated.View style={[styles.overlay, { opacity: overlayAnim }]}>
            <TouchableOpacity style={StyleSheet.absoluteFill} onPress={closeDrawer} activeOpacity={1} />
          </Animated.View>
        )}

        {/* Drawer */}
        {drawerOpen && (
          <Animated.View style={[styles.drawer, { width: DRAWER_WIDTH, transform: [{ translateX: drawerAnim }] }]}>
            <Drawer
              conversationId={conversationId}
              serverOk={serverOk}
              onSelectConversation={(id) => { setConversationId(id); setScreen("chat"); }}
              onNewChat={() => { setConversationId(undefined); setScreen("chat"); }}
              onOpenSettings={() => setScreen("settings")}
              onLogout={() => { setAuthed(false); setNeedsLogin(true); }}
              onClose={closeDrawer}
              refreshTrigger={refreshTrigger}
            />
          </Animated.View>
        )}
      </View>
      <StatusBar style="light" />
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.surface },
  loading: {
    flex: 1, backgroundColor: colors.surface,
    justifyContent: "center", alignItems: "center",
  },
  overlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "rgba(0,0,0,0.5)",
    zIndex: 10,
  },
  drawer: {
    position: "absolute",
    top: 0, bottom: 0, left: 0,
    zIndex: 11,
    shadowColor: "#000",
    shadowOffset: { width: 4, height: 0 },
    shadowOpacity: 0.3,
    shadowRadius: 12,
    elevation: 20,
  },
});
