import React, { useState, useRef, useEffect } from "react";
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet,
  KeyboardAvoidingView, Platform, ActivityIndicator, Image,
  Animated, Dimensions,
} from "react-native";
import Svg, { Rect as SvgRect } from "react-native-svg";
import { colors, spacing, radius } from "../theme/colors";
import { login, register } from "../lib/api";
import { setJwt, setUser } from "../lib/auth";

interface Props {
  onLogin: () => void;
}

const { width: SCREEN_W, height: SCREEN_H } = Dimensions.get("window");

/* ── Pixel sprite shapes (pure SVG, matches desktop) ────────────────────── */

type SpriteShape = "cross" | "diamond" | "heart" | "star" | "block";

function PixelSprite({ shape, color, px, top, left }: {
  shape: SpriteShape; color: string; px: number; top: number; left: number;
}) {
  const floatAnim = useRef(new Animated.Value(0)).current;
  const opacityAnim = useRef(new Animated.Value(0.6)).current;

  useEffect(() => {
    const duration = 4000 + Math.random() * 4000;
    Animated.loop(
      Animated.sequence([
        Animated.timing(floatAnim, { toValue: -8, duration, useNativeDriver: true }),
        Animated.timing(floatAnim, { toValue: 8, duration, useNativeDriver: true }),
      ]),
    ).start();
    Animated.loop(
      Animated.sequence([
        Animated.timing(opacityAnim, { toValue: 0.3, duration: duration * 0.8, useNativeDriver: true }),
        Animated.timing(opacityAnim, { toValue: 0.7, duration: duration * 0.8, useNativeDriver: true }),
      ]),
    ).start();
  }, []);

  const sprites: Record<SpriteShape, { w: number; h: number; rects: { x: number; y: number; w?: number; o?: number }[] }> = {
    cross: { w: 5, h: 5, rects: [
      { x: 2, y: 0 }, { x: 1, y: 1 }, { x: 2, y: 2 }, { x: 3, y: 1 },
      { x: 0, y: 2 }, { x: 4, y: 2 }, { x: 1, y: 3 }, { x: 3, y: 3 }, { x: 2, y: 4 },
    ] },
    diamond: { w: 5, h: 5, rects: [
      { x: 2, y: 0 }, { x: 1, y: 1 }, { x: 3, y: 1 },
      { x: 0, y: 2 }, { x: 4, y: 2 }, { x: 1, y: 3 }, { x: 3, y: 3 }, { x: 2, y: 4 },
    ] },
    heart: { w: 7, h: 6, rects: [
      { x: 1, y: 0, w: 2 }, { x: 4, y: 0, w: 2 },
      { x: 0, y: 1, w: 7 }, { x: 0, y: 2, w: 7 },
      { x: 1, y: 3, w: 5 }, { x: 2, y: 4, w: 3 }, { x: 3, y: 5 },
    ] },
    star: { w: 5, h: 5, rects: [
      { x: 2, y: 0 }, { x: 2, y: 1 }, { x: 1, y: 1, o: 0.5 }, { x: 3, y: 1, o: 0.5 },
      { x: 0, y: 2, w: 5 }, { x: 2, y: 3 }, { x: 1, y: 4 }, { x: 3, y: 4 },
    ] },
    block: { w: 3, h: 3, rects: [
      { x: 0, y: 0, w: 3 }, { x: 0, y: 1, w: 3 }, { x: 0, y: 2, w: 3 },
    ] },
  };

  const s = sprites[shape];

  return (
    <Animated.View style={{
      position: "absolute", top, left,
      opacity: opacityAnim,
      transform: [{ translateY: floatAnim }],
    }}>
      <Svg width={s.w * px} height={s.h * px} viewBox={`0 0 ${s.w} ${s.h}`}>
        {s.rects.map((r, i) => (
          <SvgRect key={i} x={r.x} y={r.y} width={r.w || 1} height="1" fill={color} opacity={r.o ?? 1} />
        ))}
      </Svg>
    </Animated.View>
  );
}

export default function LoginScreen({ onLogin }: Props) {
  const [mode, setMode] = useState<"signin" | "register">("signin");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [registered, setRegistered] = useState(false);

  async function handleSubmit() {
    if (!username.trim() || !password.trim()) return;
    setError("");
    setLoading(true);
    try {
      if (mode === "register") {
        await register(username.trim(), password);
        setRegistered(true);
        setMode("signin");
        setPassword("");
        setLoading(false);
        return;
      }
      const res = await login(username.trim(), password);
      if (res.access_token) {
        await setJwt(res.access_token);
        if (res.user) await setUser(res.user);
        onLogin();
      } else {
        setError(res.detail || res.error || "Failed");
      }
    } catch (e: any) {
      const msg = e.message || "";
      if (msg.includes("401")) setError("Invalid username or password");
      else if (msg.includes("409")) setError("Username already taken");
      else setError("Connection failed");
    } finally {
      setLoading(false);
    }
  }

  function switchMode(m: "signin" | "register") {
    setMode(m);
    setError("");
    setRegistered(false);
  }

  return (
    <KeyboardAvoidingView style={styles.container} behavior={Platform.OS === "ios" ? "padding" : undefined}>
      {/* Floating pixel sprites */}
      <PixelSprite shape="cross" color={colors.accent} px={4} top={SCREEN_H * 0.12} left={SCREEN_W * 0.08} />
      <PixelSprite shape="heart" color="#FF3D7F" px={3} top={SCREEN_H * 0.22} left={SCREEN_W * 0.82} />
      <PixelSprite shape="diamond" color={colors.accent} px={3} top={SCREEN_H * 0.75} left={SCREEN_W * 0.12} />
      <PixelSprite shape="star" color="#FFD700" px={4} top={SCREEN_H * 0.35} left={SCREEN_W * 0.05} />
      <PixelSprite shape="block" color={colors.accent} px={5} top={SCREEN_H * 0.65} left={SCREEN_W * 0.85} />
      <PixelSprite shape="cross" color="#FFD700" px={3} top={SCREEN_H * 0.85} left={SCREEN_W * 0.78} />
      <PixelSprite shape="heart" color={colors.accent} px={2} top={SCREEN_H * 0.08} left={SCREEN_W * 0.65} />
      <PixelSprite shape="block" color="#FF3D7F" px={4} top={SCREEN_H * 0.50} left={SCREEN_W * 0.90} />
      <PixelSprite shape="star" color={colors.accent} px={3} top={SCREEN_H * 0.88} left={SCREEN_W * 0.25} />
      <PixelSprite shape="diamond" color="#A78BFA" px={2} top={SCREEN_H * 0.15} left={SCREEN_W * 0.30} />

      <View style={styles.inner}>
        {/* Logo + Title */}
        <View style={styles.logoContainer}>
          <View style={styles.iconGlow}>
            <Image
              source={require("../../assets/appicon.png")}
              style={styles.appIcon}
            />
          </View>
          <Text style={styles.title}>Asta</Text>
          <Text style={styles.subtitle}>
            {mode === "signin" ? "Welcome back" : "Create account"}
          </Text>
        </View>

        {/* Glass card */}
        <View style={styles.card}>
          {/* Mode toggle */}
          <View style={styles.modeToggle}>
            <TouchableOpacity
              style={[styles.modeBtn, mode === "signin" && styles.modeBtnActive]}
              onPress={() => switchMode("signin")}
              activeOpacity={0.7}
            >
              <Text style={[styles.modeBtnText, mode === "signin" && styles.modeBtnTextActive]}>
                Sign In
              </Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.modeBtn, mode === "register" && styles.modeBtnActive]}
              onPress={() => switchMode("register")}
              activeOpacity={0.7}
            >
              <Text style={[styles.modeBtnText, mode === "register" && styles.modeBtnTextActive]}>
                Register
              </Text>
            </TouchableOpacity>
          </View>

          {/* Inputs */}
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
            onSubmitEditing={handleSubmit}
          />

          {error ? (
            <Text style={styles.errorText}>{error}</Text>
          ) : null}

          {registered && !error ? (
            <Text style={styles.successText}>Account created — sign in below</Text>
          ) : null}

          {/* Submit button with accent gradient look */}
          <TouchableOpacity
            style={[styles.button, loading && styles.buttonLoading]}
            onPress={handleSubmit}
            disabled={loading}
            activeOpacity={0.8}
          >
            {loading ? (
              <ActivityIndicator color="#fff" size="small" />
            ) : (
              <Text style={styles.buttonText}>
                {mode === "signin" ? "Sign In" : "Create Account"}
              </Text>
            )}
          </TouchableOpacity>
        </View>
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
  },
  inner: {
    width: "100%",
    maxWidth: 360,
    paddingHorizontal: spacing.xl,
    zIndex: 20,
  },

  // Logo
  logoContainer: { alignItems: "center", marginBottom: 32 },
  iconGlow: {
    marginBottom: spacing.lg,
    shadowColor: colors.accent,
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.15,
    shadowRadius: 32,
    elevation: 10,
  },
  appIcon: {
    width: 80,
    height: 80,
    borderRadius: 16,
  },
  title: {
    fontSize: 24,
    fontWeight: "700",
    color: colors.label,
    letterSpacing: -0.5,
    marginBottom: 4,
  },
  subtitle: {
    fontSize: 11,
    color: colors.labelTertiary,
    letterSpacing: 2,
    textTransform: "uppercase",
  },

  // Glass card
  card: {
    backgroundColor: colors.surfaceGlass,
    borderRadius: 16,
    padding: 24,
    gap: 12,
    borderWidth: 1,
    borderColor: colors.separator,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 16 },
    shadowOpacity: 0.3,
    shadowRadius: 48,
    elevation: 20,
  },

  // Mode toggle
  modeToggle: {
    flexDirection: "row",
    backgroundColor: colors.white04,
    borderRadius: radius.md,
    padding: 4,
    gap: 4,
    borderWidth: 1,
    borderColor: colors.separator,
    marginBottom: 8,
  },
  modeBtn: {
    flex: 1,
    paddingVertical: 8,
    borderRadius: 8,
    alignItems: "center",
  },
  modeBtnActive: {
    backgroundColor: colors.white10,
  },
  modeBtnText: {
    fontSize: 13,
    fontWeight: "500",
    color: colors.labelTertiary,
  },
  modeBtnTextActive: {
    color: colors.label,
  },

  // Inputs
  input: {
    backgroundColor: colors.white04,
    borderWidth: 1,
    borderColor: colors.separator,
    borderRadius: radius.md,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 13,
    color: colors.label,
  },

  // Error / Success
  errorText: {
    fontSize: 12,
    color: colors.danger,
    textAlign: "center",
    paddingVertical: 2,
  },
  successText: {
    fontSize: 12,
    color: "#4ade80",
    textAlign: "center",
    paddingVertical: 2,
  },

  // Button
  button: {
    backgroundColor: colors.accent,
    borderRadius: radius.md,
    paddingVertical: 12,
    alignItems: "center",
    marginTop: 4,
    shadowColor: colors.accent,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 5,
  },
  buttonLoading: { opacity: 0.8 },
  buttonText: { color: "#fff", fontSize: 14, fontWeight: "600" },
});
