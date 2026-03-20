import React, { useEffect, useRef, useState, useCallback } from "react";
import {
  Animated,
  Text,
  TouchableOpacity,
  StyleSheet,
  Platform,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { colors } from "../theme/colors";

export interface ToastData {
  message: string;
  type: "error" | "success" | "info";
}

// Simple event bus for toast
type ToastListener = (data: ToastData) => void;
const _listeners: ToastListener[] = [];

export function showToast(message: string, type: ToastData["type"] = "error") {
  for (const fn of _listeners) fn({ message, type });
}

export default function Toast() {
  const insets = useSafeAreaInsets();
  const [toast, setToast] = useState<ToastData | null>(null);
  const translateY = useRef(new Animated.Value(-100)).current;
  const opacity = useRef(new Animated.Value(0)).current;
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const dismiss = useCallback(() => {
    Animated.parallel([
      Animated.timing(translateY, { toValue: -100, duration: 200, useNativeDriver: true }),
      Animated.timing(opacity, { toValue: 0, duration: 200, useNativeDriver: true }),
    ]).start(() => setToast(null));
  }, [translateY, opacity]);

  useEffect(() => {
    const listener: ToastListener = (data) => {
      if (timerRef.current) clearTimeout(timerRef.current);
      setToast(data);
      translateY.setValue(-100);
      opacity.setValue(0);
      Animated.parallel([
        Animated.spring(translateY, { toValue: 0, useNativeDriver: true, tension: 80, friction: 12 }),
        Animated.timing(opacity, { toValue: 1, duration: 200, useNativeDriver: true }),
      ]).start();
      timerRef.current = setTimeout(dismiss, 4000);
    };
    _listeners.push(listener);
    return () => {
      const idx = _listeners.indexOf(listener);
      if (idx >= 0) _listeners.splice(idx, 1);
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [dismiss, translateY, opacity]);

  if (!toast) return null;

  const bgColor =
    toast.type === "error"
      ? "rgba(255,59,48,0.22)"
      : toast.type === "success"
        ? "rgba(52,199,89,0.22)"
        : "rgba(255,255,255,0.10)";

  const borderColor =
    toast.type === "error"
      ? "rgba(255,59,48,0.4)"
      : toast.type === "success"
        ? "rgba(52,199,89,0.4)"
        : "rgba(255,255,255,0.15)";

  const textColor =
    toast.type === "error"
      ? "#FF6B6B"
      : toast.type === "success"
        ? "#6BE88B"
        : colors.label;

  return (
    <Animated.View
      style={[
        styles.container,
        {
          top: insets.top + 8,
          backgroundColor: bgColor,
          borderColor,
          transform: [{ translateY }],
          opacity,
        },
      ]}
    >
      <Text style={[styles.message, { color: textColor }]} numberOfLines={3}>
        {toast.message}
      </Text>
      <TouchableOpacity onPress={dismiss} hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}>
        <Text style={styles.close}>{"\u00D7"}</Text>
      </TouchableOpacity>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  container: {
    position: "absolute",
    left: 16,
    right: 16,
    zIndex: 9999,
    borderRadius: 10,
    borderWidth: 1,
    paddingHorizontal: 14,
    paddingVertical: 10,
    flexDirection: "row",
    alignItems: "center",
    ...Platform.select({
      ios: {
        shadowColor: "#000",
        shadowOffset: { width: 0, height: 4 },
        shadowOpacity: 0.3,
        shadowRadius: 8,
      },
      android: { elevation: 8 },
    }),
  },
  message: {
    flex: 1,
    fontSize: 13,
    lineHeight: 18,
  },
  close: {
    color: "rgba(240,237,232,0.55)",
    fontSize: 18,
    paddingLeft: 10,
    lineHeight: 20,
  },
});
