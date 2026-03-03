// ── Core types for Asta desktop app ──────────────────────────────────────────

export interface Conversation {
  id: string;
  title: string;
  folder_id?: string | null;
  approx_tokens?: number;
  last_active?: string;
}

export interface Folder {
  id: string;
  name: string;
  color?: string;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  thinking?: string;
  timestamp?: string;
}

export interface Agent {
  id: string;
  name: string;
  description?: string;
  system_prompt?: string;
  icon?: string;
  avatar?: string;
  model_override?: string;
  thinking_level?: string;
  skills?: string[];
  enabled: boolean;
}

export interface Skill {
  id: string;
  name: string;
  description?: string;
  enabled: boolean;
  path?: string;
}

export interface CronJob {
  id: string;
  name: string;
  cron: string;
  next_run?: string;
  enabled: boolean;
}

export interface Settings {
  default_ai_provider?: string;
  thinking_level?: string;
  reasoning_mode?: string;
  mood?: string;
  web_enabled?: boolean;
}

export interface Provider {
  key: string;
  name: string;
  model?: string;
  status?: "connected" | "auto-disabled" | "not-connected";
  enabled?: boolean;
}

export const PROVIDERS: Provider[] = [
  { key: "anthropic", name: "Claude" },
  { key: "openai", name: "GPT" },
  { key: "google", name: "Gemini" },
  { key: "groq", name: "Groq" },
  { key: "openrouter", name: "OR" },
  { key: "ollama", name: "Local" },
];

export const THINKING_LEVELS = ["off", "minimal", "low", "medium", "high", "xhigh"] as const;
export const MOODS = ["normal", "friendly", "serious"] as const;
