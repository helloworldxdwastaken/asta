import React from "react";
import { View, Text, StyleSheet } from "react-native";

// Provider brand colors
const PROVIDER_COLORS: Record<string, string> = {
  claude: "#D97757",
  anthropic: "#D97757",
  openai: "#10A37F",
  google: "#4285F4",
  gemini: "#4285F4",
  groq: "#F55036",
  openrouter: "#6366F1",
  ollama: "#FFFFFF",
  local: "#34C759",
  telegram: "#26A5E4",
  notion: "#FFFFFF",
};

const PROVIDER_LABELS: Record<string, string> = {
  claude: "Claude",
  anthropic: "Claude",
  openai: "GPT",
  google: "Gemini",
  gemini: "Gemini",
  groq: "Groq",
  openrouter: "OpenRouter",
  ollama: "Local",
  local: "Local",
};

function hashColor(name: string): string {
  let h = 0;
  for (let i = 0; i < name.length; i++) h = ((h << 5) - h + name.charCodeAt(i)) | 0;
  return `hsl(${Math.abs(h) % 360}, 55%, 55%)`;
}

export function getProviderColor(provider?: string): string {
  if (!provider) return "#94A3B8";
  return PROVIDER_COLORS[provider.toLowerCase()] || hashColor(provider);
}

export function getProviderLabel(provider?: string): string {
  if (!provider) return "";
  return PROVIDER_LABELS[provider.toLowerCase()] || provider;
}

export function ProviderDot({ provider, size = 8 }: { provider?: string; size?: number }) {
  const color = getProviderColor(provider);
  return <View style={[styles.dot, { width: size, height: size, borderRadius: size / 2, backgroundColor: color }]} />;
}

export function ProviderBadge({ provider, size = "sm" }: { provider?: string; size?: "sm" | "md" }) {
  const color = getProviderColor(provider);
  const label = getProviderLabel(provider);
  const isSm = size === "sm";
  return (
    <View style={[styles.badge, { borderColor: color + "30", backgroundColor: color + "15" }]}>
      <View style={[styles.badgeDot, { width: isSm ? 6 : 8, height: isSm ? 6 : 8, borderRadius: isSm ? 3 : 4, backgroundColor: color }]} />
      <Text style={[styles.badgeText, { color, fontSize: isSm ? 10 : 12 }]}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  dot: {},
  badge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 9999,
    borderWidth: 1,
  },
  badgeDot: {},
  badgeText: { fontWeight: "600" },
});
