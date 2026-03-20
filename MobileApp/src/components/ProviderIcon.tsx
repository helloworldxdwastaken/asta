import React from "react";
import { View, Text, Image, StyleSheet } from "react-native";
import Svg, { Path, Circle as SvgCircle, G, ClipPath, Defs, Rect } from "react-native-svg";

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

// Static requires for provider logos (React Native Image only supports PNG/JPG, not SVG)
const PROVIDER_IMAGES: Record<string, any> = {
  claude: require("../../assets/providers/calude_anthropic.png"),
  anthropic: require("../../assets/providers/calude_anthropic.png"),
  pingram: require("../../assets/providers/pingramlogo.png"),
};

// ── Inline SVG provider icons (RN Image can't render SVG) ─────────────────

function OpenAIIcon({ size }: { size: number }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="#10A37F">
      <Path d="M22.282 9.821a5.985 5.985 0 00-.516-4.91 6.046 6.046 0 00-6.51-2.9A6.065 6.065 0 0011.735.5a6.046 6.046 0 00-5.77 4.17 6.046 6.046 0 00-4.043 2.927 6.065 6.065 0 00.745 7.1 5.985 5.985 0 00.516 4.91 6.046 6.046 0 006.51 2.9A6.065 6.065 0 0013.214 24a6.046 6.046 0 005.77-4.17 6.046 6.046 0 004.043-2.927 6.065 6.065 0 00-.745-7.082zM13.214 22.584a4.543 4.543 0 01-2.916-1.054l.145-.082 4.844-2.798a.788.788 0 00.398-.685v-6.826l2.047 1.182a.073.073 0 01.04.057v5.658a4.568 4.568 0 01-4.558 4.548zM3.68 18.419a4.536 4.536 0 01-.543-3.043l.145.087 4.844 2.797a.792.792 0 00.795 0l5.914-3.415v2.365a.073.073 0 01-.03.063L9.912 19.88a4.568 4.568 0 01-6.232-1.461zM2.458 7.86a4.536 4.536 0 012.373-1.993v5.765a.788.788 0 00.398.686l5.914 3.415-2.047 1.182a.073.073 0 01-.069.006l-4.893-2.604A4.568 4.568 0 012.458 7.86zm17.124 3.996l-5.914-3.415 2.047-1.182a.073.073 0 01.069-.006l4.893 2.604a4.558 4.558 0 01-1.692 8.18v-5.496a.788.788 0 00-.403-.685zm2.038-3.06l-.144-.087-4.845-2.797a.792.792 0 00-.795 0l-5.914 3.415V6.962a.073.073 0 01.03-.063l4.893-2.604a4.558 4.558 0 016.775 4.502zM9.063 12.835L7.016 11.653a.073.073 0 01-.04-.057V5.938a4.558 4.558 0 017.474-3.5l-.145.082-4.844 2.797a.788.788 0 00-.398.686v6.832zm1.112-2.394l2.634-1.521 2.634 1.521v3.043l-2.634 1.521-2.634-1.521V10.44z" />
    </Svg>
  );
}

function GeminiIcon({ size }: { size: number }) {
  // Simplified Gemini sparkle/star
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M12 2c.25 0 .47.17.53.41a14.3 14.3 0 003.99 7.07 14.3 14.3 0 007.07 3.99c.24.06.41.28.41.53s-.17.47-.41.53a14.3 14.3 0 00-7.07 3.99 14.3 14.3 0 00-3.99 7.07.55.55 0 01-.53.41.55.55 0 01-.53-.41 14.3 14.3 0 00-3.99-7.07 14.3 14.3 0 00-7.07-3.99A.55.55 0 010 12c0-.25.17-.47.41-.53a14.3 14.3 0 007.07-3.99A14.3 14.3 0 0011.47 2.41.55.55 0 0112 2z"
        fill="#4285F4"
      />
    </Svg>
  );
}

function GroqIcon({ size }: { size: number }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 26.3 26.3" fill="none">
      <SvgCircle cx="13.15" cy="13.15" r="13.15" fill="#F55036" />
      <Path
        d="M13.17 6.88a4.43 4.43 0 000 8.85h1.45v-1.66h-1.45a2.77 2.77 0 112.77-2.76v4.07a2.74 2.74 0 01-4.67 2l-1.17 1.13a4.37 4.37 0 003.07 1.29h.06a4.42 4.42 0 004.36-4.4v-4.2a4.43 4.43 0 00-4.42-4.32"
        fill="#fff"
      />
    </Svg>
  );
}

function OpenRouterIcon({ size }: { size: number }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 512 512" fill="#6366F1">
      <Path
        fillRule="evenodd"
        clipRule="evenodd"
        d="M358.5 41.8l154 87.5v1.9l-155.6 86.6.4-45.2-17.5-.6c-22.6-.6-34.4 0-48.4 2.3-22.7 3.7-43.5 12.3-67.1 28.8l-46.2 32.1c-6.1 4.2-10.6 7.2-14.5 9.7l-11 6.9-8.5 5 8.2 4.9 11.3 7.2c10.2 6.7 25 17 57.6 39.8 23.7 16.5 44.4 25.1 67.1 28.8l6.4 1c14.8 1.9 29.3 2 60.3.7l.5-46.1 154 87.6v1.8l-155.6 86.7.3-39.7-13.5.5c-29.6.9-45.6 0-66.9-3.5-36.1-6-69.5-19.8-104.1-43.9l-46-32a467 467 0 00-16.1-10.6l-10-6c-5.4-3.1-10.8-6.2-16.2-9.2C62 314.2 12 301.1 0 301.1v-90.2l3 .1c12-.2 62.1-13.3 81.3-24l21.7-12.4 9.3-5.8c9.1-6 22.9-15.5 57.3-39.5 34.6-24.2 68-38 104.1-43.9 24.6-4.1 42.1-4.5 81.4-3l.4-40.7z"
      />
    </Svg>
  );
}

function OllamaIcon({ size }: { size: number }) {
  // Simplified llama silhouette
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <SvgCircle cx="12" cy="12" r="11" fill="#1a1a2e" stroke="#fff" strokeWidth="0.5" />
      <Path
        d="M8 18v-3c0-1.5.5-2.8 1.5-3.8S11.5 10 13 10h1V7.5c0-.5.2-1 .5-1.3.3-.4.7-.5 1.2-.5s.8.2 1.1.5c.3.3.5.7.5 1.3v4c0 1.5-.5 2.8-1.5 3.8s-2 1.5-3.5 1.5H8z"
        fill="#fff"
      />
      <SvgCircle cx="15.5" cy="9" r="0.8" fill="#1a1a2e" />
    </Svg>
  );
}

// Map of inline SVG icon components
const PROVIDER_SVG_ICONS: Record<string, React.FC<{ size: number }>> = {
  openai: OpenAIIcon,
  google: GeminiIcon,
  gemini: GeminiIcon,
  groq: GroqIcon,
  openrouter: OpenRouterIcon,
  ollama: OllamaIcon,
  local: OllamaIcon,
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

/** Render the correct provider logo */
export function ProviderLogo({ provider, size = 20 }: { provider?: string; size?: number }) {
  const key = (provider || "").toLowerCase();

  // PNG images (Claude, Pingram)
  const imgSource = PROVIDER_IMAGES[key];
  if (imgSource) {
    return (
      <Image
        source={imgSource}
        style={{ width: size, height: size }}
        resizeMode="contain"
      />
    );
  }

  // Inline SVG icons (OpenAI, Gemini, Groq, OpenRouter, Ollama)
  const SvgIcon = PROVIDER_SVG_ICONS[key];
  if (SvgIcon) {
    return <SvgIcon size={size} />;
  }

  // Fallback: colored circle with first letter
  const color = getProviderColor(provider);
  const letter = (provider || "?")[0].toUpperCase();
  return (
    <View style={{ width: size, height: size, borderRadius: size / 2, backgroundColor: color + "20", alignItems: "center", justifyContent: "center" }}>
      <Text style={{ fontSize: size * 0.5, fontWeight: "700", color }}>{letter}</Text>
    </View>
  );
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
  badgeText: { fontWeight: "600" },
});
