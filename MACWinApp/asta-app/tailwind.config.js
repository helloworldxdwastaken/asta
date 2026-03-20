/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        accent:    { DEFAULT: "#FF6B2C", hover: "#FF8A50", dim: "rgba(255,107,44,0.08)" },
        studio:    { DEFAULT: "#7C3AED", hover: "#8B5CF6", dim: "rgba(124,58,237,0.08)", glow: "rgba(124,58,237,0.25)" },
        surface:   { DEFAULT: "var(--surface)", raised: "var(--surface-raised)", overlay: "var(--surface-overlay)" },
        label:     { DEFAULT: "var(--label)", secondary: "var(--label-secondary)", tertiary: "var(--label-tertiary)" },
        separator: { DEFAULT: "var(--separator)", bold: "var(--separator-bold)" },
        sidebar:   { DEFAULT: "var(--sidebar)", hover: "var(--sidebar-hover)" },
        thinking:  { DEFAULT: "rgba(167,139,250,0.7)", bg: "rgba(167,139,250,0.08)", border: "rgba(167,139,250,0.15)" },
        success:   "#22C55E",
        warning:   "#EAB308",
        danger:    "#EF4444",
      },
      borderRadius: {
        mac: "12px",
        bubble: "20px",
        pill: "9999px",
      },
      fontSize: {
        "10": ["10px", "14px"],
        "11": ["11px", "15px"],
        "12": ["12px", "16px"],
        "13": ["13px", "18px"],
        "14": ["14px", "20px"],
        "15": ["15px", "22px"],
        "16": ["16px", "24px"],
        "18": ["18px", "26px"],
        "22": ["22px", "30px"],
      },
      fontFamily: {
        display: ['"Outfit"', "system-ui", "sans-serif"],
        mono:    ['"JetBrains Mono"', "ui-monospace", "monospace"],
      },
      boxShadow: {
        "glow":   "0 0 20px var(--accent-glow)",
        "glow-sm":"0 0 10px var(--accent-glow)",
        "modal":  "0 25px 60px -15px rgba(0,0,0,0.5), 0 0 1px rgba(255,255,255,0.05)",
        "card":   "0 2px 8px rgba(0,0,0,0.15), 0 0 1px rgba(255,255,255,0.03)",
        "float":  "0 8px 30px -8px rgba(0,0,0,0.4)",
      },
      animation: {
        "bounce-dot":     "bounceDot 1.4s infinite ease-in-out",
        "pulse-thinking": "pulseThinking 0.7s ease-in-out infinite alternate",
        "tool-pill":      "toolPillPulse 0.7s ease-in-out infinite alternate",
        "orb":            "orbFloat 8s ease-in-out infinite",
      },
      keyframes: {
        bounceDot: {
          "0%, 80%, 100%": { transform: "translateY(0)" },
          "40%":           { transform: "translateY(-6px)" },
        },
        pulseThinking: {
          "0%":   { opacity: 0.4, transform: "scale(0.9)" },
          "100%": { opacity: 1, transform: "scale(1.1)" },
        },
        toolPillPulse: {
          "0%":   { backgroundColor: "rgba(255,107,44,0.06)" },
          "100%": { backgroundColor: "rgba(255,107,44,0.16)" },
        },
        orbFloat: {
          "0%, 100%": { transform: "translate(0,0) scale(1)" },
          "25%":      { transform: "translate(20px,-15px) scale(1.05)" },
          "50%":      { transform: "translate(-10px,-25px) scale(0.95)" },
          "75%":      { transform: "translate(-20px,-10px) scale(1.02)" },
        },
      },
      transitionTimingFunction: {
        "spring": "cubic-bezier(0.16, 1, 0.3, 1)",
      },
    },
  },
  plugins: [],
};
