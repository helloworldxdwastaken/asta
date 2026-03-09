import React, { useState } from "react";
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet,
  KeyboardAvoidingView, Platform, ActivityIndicator,
} from "react-native";
import { colors, spacing, radius } from "../theme/colors";
import { login, register } from "../lib/api";
import { setJwt, setUser } from "../lib/auth";

interface Props {
  onLogin: () => void;
}

export default function LoginScreen({ onLogin }: Props) {
  const [mode, setMode] = useState<"signin" | "register">("signin");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit() {
    if (!username.trim() || !password.trim()) return;
    setError("");
    setLoading(true);
    try {
      const fn = mode === "signin" ? login : register;
      const res = await fn(username.trim(), password);
      if (res.access_token) {
        await setJwt(res.access_token);
        if (res.user) await setUser(res.user);
        onLogin();
      } else {
        setError(res.detail || res.error || "Failed");
      }
    } catch (e: any) {
      setError(e.message || "Connection failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <KeyboardAvoidingView style={styles.container} behavior={Platform.OS === "ios" ? "padding" : undefined}>
      <View style={styles.card}>
        <Text style={styles.title}>Asta</Text>
        <Text style={styles.subtitle}>
          {mode === "signin" ? "Sign in to continue" : "Create your account"}
        </Text>

        {error ? <Text style={styles.error}>{error}</Text> : null}

        <TextInput
          style={styles.input}
          placeholder="Username"
          placeholderTextColor={colors.labelTertiary}
          value={username}
          onChangeText={setUsername}
          autoCapitalize="none"
          autoCorrect={false}
        />
        <TextInput
          style={styles.input}
          placeholder="Password"
          placeholderTextColor={colors.labelTertiary}
          value={password}
          onChangeText={setPassword}
          secureTextEntry
        />

        <TouchableOpacity style={styles.button} onPress={handleSubmit} disabled={loading}>
          {loading ? (
            <ActivityIndicator color="#fff" size="small" />
          ) : (
            <Text style={styles.buttonText}>{mode === "signin" ? "Sign In" : "Register"}</Text>
          )}
        </TouchableOpacity>

        <TouchableOpacity onPress={() => { setMode(mode === "signin" ? "register" : "signin"); setError(""); }}>
          <Text style={styles.toggle}>
            {mode === "signin" ? "Don't have an account? Register" : "Already have an account? Sign in"}
          </Text>
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.surface,
    justifyContent: "center",
    alignItems: "center",
    padding: spacing.xl,
  },
  card: {
    width: "100%",
    maxWidth: 360,
    backgroundColor: colors.surfaceRaised,
    borderRadius: radius.lg,
    padding: spacing.xxl,
    gap: spacing.md,
  },
  title: {
    fontSize: 28,
    fontWeight: "700",
    color: colors.accent,
    textAlign: "center",
  },
  subtitle: {
    fontSize: 14,
    color: colors.labelSecondary,
    textAlign: "center",
    marginBottom: spacing.sm,
  },
  error: {
    fontSize: 13,
    color: colors.danger,
    textAlign: "center",
    backgroundColor: "rgba(255,59,48,0.1)",
    padding: spacing.sm,
    borderRadius: radius.sm,
    overflow: "hidden",
  },
  input: {
    backgroundColor: colors.white05,
    borderWidth: 1,
    borderColor: colors.separator,
    borderRadius: radius.md,
    paddingHorizontal: spacing.lg,
    paddingVertical: 14,
    fontSize: 15,
    color: colors.label,
  },
  button: {
    backgroundColor: colors.accent,
    borderRadius: radius.md,
    paddingVertical: 14,
    alignItems: "center",
    marginTop: spacing.sm,
  },
  buttonText: {
    color: "#fff",
    fontSize: 15,
    fontWeight: "600",
  },
  toggle: {
    fontSize: 13,
    color: colors.accent,
    textAlign: "center",
    marginTop: spacing.sm,
  },
});
