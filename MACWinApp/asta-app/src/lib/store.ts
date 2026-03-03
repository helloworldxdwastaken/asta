// ── Simple localStorage store helpers ────────────────────────────────────────

export function getSetupDone(): boolean {
  return localStorage.getItem("hasCompletedSetup") === "true";
}

export function setSetupDone(): void {
  localStorage.setItem("hasCompletedSetup", "true");
}

export function getShowThinking(): boolean {
  return localStorage.getItem("showThinking") === "true";
}

export function setShowThinking(val: boolean): void {
  localStorage.setItem("showThinking", val ? "true" : "false");
}

export function getWebEnabled(): boolean {
  return localStorage.getItem("webEnabled") === "true";
}

export function setWebEnabled(val: boolean): void {
  localStorage.setItem("webEnabled", val ? "true" : "false");
}

export function getSelectedProvider(): string {
  return localStorage.getItem("selectedProvider") ?? "anthropic";
}

export function setSelectedProvider(p: string): void {
  localStorage.setItem("selectedProvider", p);
}

export function getThinkingLevel(): string {
  return localStorage.getItem("thinkingLevel") ?? "off";
}

export function setThinkingLevel(l: string): void {
  localStorage.setItem("thinkingLevel", l);
}

export function getMood(): string {
  return localStorage.getItem("mood") ?? "normal";
}

export function setMood(m: string): void {
  localStorage.setItem("mood", m);
}
