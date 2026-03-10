import React from "react";
import { View, Text, StyleSheet } from "react-native";
import Svg, { Path, Circle, G, Defs, ClipPath, Rect } from "react-native-svg";

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

// ── SVG Provider Logos ──────────────────────────────────────────────

interface LogoProps { size?: number }

/** Claude / Anthropic — simplified sparkle mark */
function ClaudeLogo({ size = 20 }: LogoProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path d="M16.344 7.158L10.382 22h-3.56L12.93 7.158h3.414zM17.178 22l-6.108-14.842h3.56L20.737 22h-3.56z" fill="#D97757" />
    </Svg>
  );
}

/** OpenAI — hexagonal flower shape */
function OpenAILogo({ size = 20 }: LogoProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path d="M22.282 9.821a5.985 5.985 0 00-.516-4.91 6.046 6.046 0 00-6.51-2.9A6.065 6.065 0 0011.81.417a6.043 6.043 0 00-5.77 4.223 6.048 6.048 0 00-4.038 2.929 6.073 6.073 0 00.744 7.11 5.985 5.985 0 00.516 4.911 6.048 6.048 0 006.51 2.9A6.065 6.065 0 0013.218 23.6a6.043 6.043 0 005.77-4.223 6.048 6.048 0 004.038-2.929 6.073 6.073 0 00-.744-7.11v-.517zM13.218 22.1a4.533 4.533 0 01-2.913-1.058l.145-.083 4.838-2.793a.788.788 0 00.396-.685v-6.818l2.044 1.181a.073.073 0 01.04.055v5.649a4.554 4.554 0 01-4.55 4.552zM3.612 18.138a4.524 4.524 0 01-.542-3.044l.145.087 4.838 2.793a.784.784 0 00.788 0l5.908-3.412v2.362a.073.073 0 01-.029.062l-4.892 2.826a4.553 4.553 0 01-6.216-1.674zM2.389 7.96a4.525 4.525 0 012.371-1.99v5.748a.784.784 0 00.392.681l5.908 3.407-2.044 1.18a.073.073 0 01-.069.006l-4.893-2.83A4.554 4.554 0 012.39 7.96zm17.274 4.025l-5.907-3.412 2.044-1.18a.073.073 0 01.069-.006l4.893 2.826a4.55 4.55 0 01-1.65 8.342v-5.89a.784.784 0 00-.393-.68h-.056zm2.036-3.053l-.145-.087-4.838-2.793a.784.784 0 00-.788 0L9.92 9.464V7.103a.073.073 0 01.029-.062l4.892-2.822a4.55 4.55 0 016.757 4.713zM8.727 12.87l-2.045-1.18a.073.073 0 01-.04-.056V5.984a4.551 4.551 0 017.462-3.492l-.144.083-4.839 2.793a.788.788 0 00-.396.685l.002 6.818zm1.11-2.394l2.632-1.52 2.632 1.52v3.04l-2.632 1.52-2.632-1.52v-3.04z" fill="#10A37F" />
    </Svg>
  );
}

/** Gemini — four-pointed star */
function GeminiLogo({ size = 20 }: LogoProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path d="M12 2C12 7.523 7.523 12 2 12c5.523 0 10 4.477 10 10 0-5.523 4.477-10 10-10-5.523 0-10-4.477-10-10z" fill="#4285F4" />
    </Svg>
  );
}

/** Groq — circle with stylized G */
function GroqLogo({ size = 20 }: LogoProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 26.3 26.3" fill="none">
      <Circle cx="13.15" cy="13.15" r="13.15" fill="#F55036" />
      <Path d="M13.17 6.88a4.43 4.43 0 000 8.85h1.45v-1.66h-1.45a2.77 2.77 0 112.77-2.76v4.07a2.74 2.74 0 01-4.67 2l-1.17 1.13a4.37 4.37 0 003.07 1.29h.06a4.42 4.42 0 004.36-4.4v-4.2a4.43 4.43 0 00-4.42-4.32" fill="#fff" />
    </Svg>
  );
}

/** OpenRouter — stylized OR arrows */
function OpenRouterLogo({ size = 20 }: LogoProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path d="M16.7 2l7.2 4.1v.09L16.5 10.2l.02-2.1-.82-.03c-1.06-.03-1.61 0-2.27.11-1.06.18-2.04.58-3.15 1.35L8.12 11c-.28.2-.5.34-.68.46l-.51.32-.4.23.39.23.53.34c.48.31 1.17.8 2.7 1.87 1.11.77 2.08 1.18 3.15 1.35l.3.04c.7.1 1.38.1 2.83.03l.02-2.16 7.22 4.11v.09L16.5 21.9l.01-1.86-.64.02c-1.39.04-2.14 0-3.14-.16-1.7-.28-3.26-.93-4.88-2.06l-2.16-1.5a21.879 21.879 0 00-.76-.5l-.47-.28a39.73 39.73 0 00-.76-.43c-1.48-.82-3.83-1.43-4.4-1.43v-4.23l.14.004c.57-.007 2.91-.62 3.81-1.12l1.02-.58.44-.27c.43-.28 1.07-.73 2.69-1.86 1.62-1.13 3.19-1.78 4.88-2.06 1.15-.19 1.98-.21 3.82-.14l.02-1.91z" fill="#6366F1" />
    </Svg>
  );
}

/** Ollama — llama silhouette */
function OllamaLogo({ size = 20 }: LogoProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path d="M12 3C9.24 3 7 5.24 7 8c0 1.57.73 2.97 1.87 3.88C7.2 12.9 6 14.83 6 17v4h3v-4c0-1.66 1.34-3 3-3s3 1.34 3 3v4h3v-4c0-2.17-1.2-4.1-2.87-5.12A5 5 0 0017 8c0-2.76-2.24-5-5-5zm-1.5 6a1 1 0 110-2 1 1 0 010 2zm3 0a1 1 0 110-2 1 1 0 010 2z" fill="#FFFFFF" />
    </Svg>
  );
}

/** Render the correct provider logo SVG */
export function ProviderLogo({ provider, size = 20 }: { provider?: string; size?: number }) {
  const key = (provider || "").toLowerCase();
  switch (key) {
    case "claude":
    case "anthropic":
      return <ClaudeLogo size={size} />;
    case "openai":
      return <OpenAILogo size={size} />;
    case "google":
    case "gemini":
      return <GeminiLogo size={size} />;
    case "groq":
      return <GroqLogo size={size} />;
    case "openrouter":
      return <OpenRouterLogo size={size} />;
    case "ollama":
    case "local":
      return <OllamaLogo size={size} />;
    default: {
      // Fallback: colored circle with first letter
      const color = getProviderColor(provider);
      const letter = (provider || "?")[0].toUpperCase();
      return (
        <View style={{ width: size, height: size, borderRadius: size / 2, backgroundColor: color + "20", alignItems: "center", justifyContent: "center" }}>
          <Text style={{ fontSize: size * 0.5, fontWeight: "700", color }}>{letter}</Text>
        </View>
      );
    }
  }
}

// ── Dot & Badge (now using logos) ──────────────────────────────────

export function ProviderDot({ provider, size = 8 }: { provider?: string; size?: number }) {
  // For sizes >= 14, use the actual logo
  if (size >= 14) return <ProviderLogo provider={provider} size={size} />;
  // Small sizes: colored dot
  const color = getProviderColor(provider);
  return <View style={[styles.dot, { width: size, height: size, borderRadius: size / 2, backgroundColor: color }]} />;
}

export function ProviderBadge({ provider, size = "sm" }: { provider?: string; size?: "sm" | "md" }) {
  const color = getProviderColor(provider);
  const label = getProviderLabel(provider);
  const isSm = size === "sm";
  return (
    <View style={[styles.badge, { borderColor: color + "30", backgroundColor: color + "15" }]}>
      <ProviderLogo provider={provider} size={isSm ? 12 : 16} />
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
