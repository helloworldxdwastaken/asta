// Graphite Luxe — matches desktop app theme
export const colors = {
  // Surfaces
  surface: "#111114",
  surfaceRaised: "#19191D",
  surfaceGlass: "rgba(25,25,29,0.78)",

  // Text
  label: "#F0EDE8",
  labelSecondary: "rgba(240,237,232,0.55)",
  labelTertiary: "rgba(240,237,232,0.28)",

  // Accent (orange → pink gradient)
  accent: "#FF6B2C",
  accentEnd: "#FF3D7F",
  accentGlow: "rgba(255,107,44,0.15)",
  accentSubtle: "rgba(255,107,44,0.12)",

  // Semantic
  success: "#34C759",
  danger: "#FF3B30",
  warning: "#FF9F0A",

  // Borders
  separator: "rgba(255,255,255,0.06)",
  separatorOpaque: "#222226",

  // Thinking
  violet: "#8B5CF6",
  violetSubtle: "rgba(139,92,246,0.12)",
  violetText: "rgba(139,92,246,0.8)",

  // User bubble (dark gray, NOT accent orange)
  userBubble: "#2C2C30",
  userBubbleText: "#F0EDE8",

  // Misc
  white05: "rgba(255,255,255,0.05)",
  white08: "rgba(255,255,255,0.08)",
  white04: "rgba(255,255,255,0.04)",
  white10: "rgba(255,255,255,0.10)",
  separatorBold: "rgba(255,255,255,0.1)",

  // Danger subtle
  dangerSubtle: "rgba(255,59,48,0.2)",

  // Code blocks & markdown
  codeBg: "rgba(255,255,255,0.04)",
  codeBorder: "rgba(255,255,255,0.08)",
  inlineCodeBg: "rgba(255,255,255,0.06)",
  blockquoteBorder: "rgba(255,255,255,0.12)",
  blockquoteText: "rgba(240,237,232,0.55)",
  tableBorder: "rgba(255,255,255,0.08)",
  tableHeaderBg: "rgba(255,255,255,0.04)",
};

export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 20,
  xxl: 24,
};

export const radius = {
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  full: 9999,
};

export const fonts = {
  regular: { fontSize: 15, color: colors.label },
  small: { fontSize: 13, color: colors.label },
  tiny: { fontSize: 11, color: colors.labelTertiary },
  mono: { fontSize: 13, fontFamily: "SpaceMono" },
};
