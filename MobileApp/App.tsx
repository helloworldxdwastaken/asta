import React, { useState, useEffect, useRef } from "react";
import { StatusBar } from "expo-status-bar";
import { ActivityIndicator, View } from "react-native";
import { NavigationContainer, DefaultTheme } from "@react-navigation/native";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { colors } from "./src/theme/colors";
import { getJwt } from "./src/lib/auth";
import { checkHealth, getMe, getThinking, getDefaultAI } from "./src/lib/api";

import LoginScreen from "./src/screens/LoginScreen";
import ChatScreen from "./src/screens/ChatScreen";
import ConversationsScreen from "./src/screens/ConversationsScreen";
import SettingsScreen from "./src/screens/SettingsScreen";

const Tab = createBottomTabNavigator();

const AstaDark = {
  ...DefaultTheme,
  dark: true,
  colors: {
    ...DefaultTheme.colors,
    primary: colors.accent,
    background: colors.surface,
    card: colors.surfaceRaised,
    text: colors.label,
    border: colors.separatorOpaque,
    notification: colors.accent,
  },
};

// Placeholder — tab labels handle identification for now

export default function App() {
  const [authed, setAuthed] = useState<boolean | null>(null); // null = loading
  const [needsLogin, setNeedsLogin] = useState(false);
  const [conversationId, setConversationId] = useState<string | undefined>();
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const [provider, setProvider] = useState("claude");
  const [thinkingLevel, setThinkingLevel] = useState("off");

  useEffect(() => {
    (async () => {
      const jwt = await getJwt();
      if (!jwt) {
        // No JWT — check if backend needs login
        try {
          await getMe();
          // No error = single-user mode, proceed
          setAuthed(true);
          setNeedsLogin(false);
        } catch {
          setNeedsLogin(true);
          setAuthed(false);
        }
        return;
      }
      // Has JWT — validate
      try {
        await getMe();
        setAuthed(true);
      } catch {
        // JWT invalid but might be offline — trust it
        setAuthed(true);
      }
    })();
  }, []);

  useEffect(() => {
    if (!authed) return;
    getDefaultAI().then((r) => setProvider(r.provider || "claude")).catch(() => {});
    getThinking().then((r) => setThinkingLevel(r.thinking_level || "off")).catch(() => {});
  }, [authed]);

  // Loading
  if (authed === null) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.surface, justifyContent: "center", alignItems: "center" }}>
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
      <NavigationContainer theme={AstaDark}>
        <Tab.Navigator
          screenOptions={{
            headerShown: false,
            tabBarStyle: {
              backgroundColor: colors.surfaceRaised,
              borderTopColor: colors.separator,
              borderTopWidth: 1,
              height: 80,
              paddingBottom: 20,
              paddingTop: 8,
            },
            tabBarActiveTintColor: colors.accent,
            tabBarInactiveTintColor: colors.labelTertiary,
            tabBarLabelStyle: { fontSize: 11, fontWeight: "500" },
          }}
        >
          <Tab.Screen name="Chat" options={{ tabBarLabel: "Chat" }}>
            {() => (
              <ChatScreen
                conversationId={conversationId}
                onConversationCreated={(id) => {
                  setConversationId(id);
                  setRefreshTrigger((n) => n + 1);
                }}
                provider={provider}
                thinkingLevel={thinkingLevel}
              />
            )}
          </Tab.Screen>
          <Tab.Screen name="Chats" options={{ tabBarLabel: "History" }}>
            {() => (
              <ConversationsScreen
                refreshTrigger={refreshTrigger}
                onSelect={(id) => setConversationId(id)}
                onNewChat={() => setConversationId(undefined)}
              />
            )}
          </Tab.Screen>
          <Tab.Screen name="Settings" options={{ tabBarLabel: "Settings" }}>
            {() => (
              <SettingsScreen onLogout={() => { setAuthed(false); setNeedsLogin(true); }} />
            )}
          </Tab.Screen>
        </Tab.Navigator>
      </NavigationContainer>
      <StatusBar style="light" />
    </SafeAreaProvider>
  );
}
