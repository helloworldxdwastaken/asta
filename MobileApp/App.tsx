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
import AutomationsScreen from "./src/screens/AutomationsScreen";
import Drawer from "./src/components/Drawer";

const DRAWER_WIDTH = Math.min(Dimensions.get("window").width * 0.82, 320);
const SCREEN_HEIGHT = Dimensions.get("window").height;

export default function App() {
  const [authed, setAuthed] = useState<boolean | null>(null);
  const [needsLogin, setNeedsLogin] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [automationsOpen, setAutomationsOpen] = useState(false);
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

  // Settings sheet
  const settingsAnim = useRef(new Animated.Value(SCREEN_HEIGHT)).current;
  const settingsOverlayAnim = useRef(new Animated.Value(0)).current;

  // Automations sheet
  const automationsAnim = useRef(new Animated.Value(SCREEN_HEIGHT)).current;
  const automationsOverlayAnim = useRef(new Animated.Value(0)).current;

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

  function openSettings() {
    setSettingsOpen(true);
    Animated.parallel([
      Animated.spring(settingsAnim, { toValue: 0, useNativeDriver: true, tension: 65, friction: 11 }),
      Animated.timing(settingsOverlayAnim, { toValue: 1, duration: 250, useNativeDriver: true }),
    ]).start();
  }

  function closeSettings() {
    Animated.parallel([
      Animated.spring(settingsAnim, { toValue: SCREEN_HEIGHT, useNativeDriver: true, tension: 65, friction: 11 }),
      Animated.timing(settingsOverlayAnim, { toValue: 0, duration: 200, useNativeDriver: true }),
    ]).start(() => setSettingsOpen(false));
  }

  function openAutomations() {
    setAutomationsOpen(true);
    Animated.parallel([
      Animated.spring(automationsAnim, { toValue: 0, useNativeDriver: true, tension: 65, friction: 11 }),
      Animated.timing(automationsOverlayAnim, { toValue: 1, duration: 250, useNativeDriver: true }),
    ]).start();
  }

  function closeAutomations() {
    Animated.parallel([
      Animated.spring(automationsAnim, { toValue: SCREEN_HEIGHT, useNativeDriver: true, tension: 65, friction: 11 }),
      Animated.timing(automationsOverlayAnim, { toValue: 0, duration: 200, useNativeDriver: true }),
    ]).start(() => setAutomationsOpen(false));
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
        {/* Chat wrapped in zIndex:1 so its internal absolute elements stay below drawer overlay */}
        <View style={styles.chatWrap}>
          <ChatScreen
            conversationId={conversationId}
            onConversationCreated={(id) => {
              setConversationId(id);
              setRefreshTrigger((n) => n + 1);
            }}
            provider={provider}
            thinkingLevel={thinkingLevel}
            agents={agents}
            onOpenDrawer={openDrawer}
            onProviderChange={setProvider}
            onThinkingChange={setThinkingLevel}
          />
        </View>

        {/* Automations bottom sheet */}
        {automationsOpen && (
          <>
            <Animated.View style={[styles.settingsOverlay, { opacity: automationsOverlayAnim }]}>
              <TouchableOpacity style={StyleSheet.absoluteFill} onPress={closeAutomations} activeOpacity={1} />
            </Animated.View>
            <Animated.View style={[styles.settingsSheet, { transform: [{ translateY: automationsAnim }] }]}>
              <AutomationsScreen onBack={closeAutomations} />
            </Animated.View>
          </>
        )}

        {/* Settings bottom sheet overlay */}
        {settingsOpen && (
          <>
            <Animated.View style={[styles.settingsOverlay, { opacity: settingsOverlayAnim }]}>
              <TouchableOpacity style={StyleSheet.absoluteFill} onPress={closeSettings} activeOpacity={1} />
            </Animated.View>
            <Animated.View style={[styles.settingsSheet, { transform: [{ translateY: settingsAnim }] }]}>
              <SettingsScreen
                onBack={closeSettings}
                onLogout={() => { setAuthed(false); setNeedsLogin(true); }}
                provider={provider}
                thinkingLevel={thinkingLevel}
                mood={mood}
                onProviderChange={setProvider}
                onThinkingChange={setThinkingLevel}
                onMoodChange={setMood}
              />
            </Animated.View>
          </>
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
              onSelectConversation={(id) => { setConversationId(id); closeDrawer(); }}
              onNewChat={() => { setConversationId(undefined); closeDrawer(); }}
              onOpenSettings={() => { closeDrawer(); setTimeout(openSettings, 300); }}
              onOpenAutomations={() => { closeDrawer(); setTimeout(openAutomations, 300); }}
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
  chatWrap: { flex: 1, zIndex: 1 },
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
    backgroundColor: colors.surfaceRaised,
    shadowColor: "#000",
    shadowOffset: { width: 4, height: 0 },
    shadowOpacity: 0.3,
    shadowRadius: 12,
    elevation: 20,
  },
  settingsOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "rgba(0,0,0,0.4)",
    zIndex: 20,
  },
  settingsSheet: {
    position: "absolute",
    left: 0, right: 0, bottom: 0,
    top: 48,
    backgroundColor: colors.surface,
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    zIndex: 21,
    overflow: "hidden",
    shadowColor: "#000",
    shadowOffset: { width: 0, height: -8 },
    shadowOpacity: 0.3,
    shadowRadius: 20,
    elevation: 30,
  },
});
