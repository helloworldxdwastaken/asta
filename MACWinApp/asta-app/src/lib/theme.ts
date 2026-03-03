// ── Theme management ──────────────────────────────────────────────────────────

export type ThemeMode = "system" | "light" | "dark";

const STORAGE_KEY = "themeMode";

export function getThemeMode(): ThemeMode {
  return (localStorage.getItem(STORAGE_KEY) as ThemeMode) ?? "system";
}

export function setThemeMode(mode: ThemeMode): void {
  localStorage.setItem(STORAGE_KEY, mode);
  applyTheme(mode);
}

export function applyTheme(mode?: ThemeMode): void {
  const m = mode ?? getThemeMode();
  const root = document.documentElement;

  if (m === "system") {
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    root.classList.toggle("dark", prefersDark);
    root.classList.toggle("light", !prefersDark);
  } else {
    root.classList.toggle("dark", m === "dark");
    root.classList.toggle("light", m === "light");
  }
}

// Listen for system theme changes when mode is "system"
export function initThemeListener(): () => void {
  const mq = window.matchMedia("(prefers-color-scheme: dark)");
  const handler = () => {
    if (getThemeMode() === "system") applyTheme("system");
  };
  mq.addEventListener("change", handler);
  applyTheme();
  return () => mq.removeEventListener("change", handler);
}
