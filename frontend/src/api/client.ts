// Use relative path so it works in dev (via proxy) and prod (same origin)
// Or use VITE_API_URL if set.
const API_BASE = import.meta.env.VITE_API_URL || "/api";

async function req<T>(path: string, options?: RequestInit): Promise<T> {
  const r = await fetch(API_BASE + path, {
    ...options,
    headers: { "Content-Type": "application/json", ...options?.headers },
  });
  if (!r.ok) throw new Error(await r.text().then((t) => t.slice(0, 200)));
  return r.json();
}

export type Status = {
  apis: Record<string, boolean>;
  integrations: Record<string, boolean>;
  skills: { id: string; name: string; description: string; enabled: boolean; available: boolean }[];
  app: string;
  version: string;
};

export type ServerStatus = {
  ok: boolean;
  cpu_percent: number;
  ram: { total_gb: number; used_gb: number; percent: number };
  disk: { total_gb: number; used_gb: number; percent: number };
  uptime_str: string;
  error?: string;
};

export type Skill = {
  id: string;
  name: string;
  description: string;
  enabled: boolean;
  available: boolean;
  /** When not available: "Connect" | "Configure paths" | "Set API key" etc. */
  action_hint?: string | null;
};

export const api = {
  health: () => req<{ status: string; app?: string }>("/health"),
  status: () => req<Status>("/status"),
  getSkills: () => req<{ skills: Skill[] }>("/settings/skills"),
  setSkillToggle: (skillId: string, enabled: boolean) =>
    req<{ skill_id: string; enabled: boolean }>("/settings/skills", {
      method: "PUT",
      body: JSON.stringify({ skill_id: skillId, enabled }),
    }),
  /** Upload a .zip containing an OpenClaw-style skill (folder with SKILL.md). Returns { skill_id, ok }. */
  skillsUploadZip: async (file: File): Promise<{ skill_id: string; ok: boolean }> => {
    const form = new FormData();
    form.append("file", file);
    const r = await fetch(API_BASE + "/skills/upload", {
      method: "POST",
      body: form,
    });
    if (!r.ok) throw new Error(await r.text().then((t) => t.slice(0, 300)));
    return r.json();
  },
  providers: () => req<{ providers: string[] }>("/providers"),
  getChatMessages: (conversationId: string, userId = "default", limit = 50) =>
    req<{ conversation_id: string; messages: { role: string; content: string }[] }>(
      `/chat/messages?conversation_id=${encodeURIComponent(conversationId)}&user_id=${encodeURIComponent(userId)}&limit=${limit}`
    ),
  chat: (text: string, provider: string = "groq", conversationId?: string) =>
    req<{ reply: string; conversation_id: string; provider: string }>("/chat", {
      method: "POST",
      body: JSON.stringify({ text, provider, user_id: "default", conversation_id: conversationId }),
    }),
  filesList: (directory?: string) =>
    req<{ roots?: string[]; root?: string; entries: { name: string; path: string; dir: boolean; size?: number }[] }>(
      "/files/list" + (directory ? `?directory=${encodeURIComponent(directory)}` : "")
    ),
  filesRead: (path: string) => req<{ path: string; content: string }>("/files/read?path=" + encodeURIComponent(path)),
  /** Returns 403 body when path not allowed: { code: "PATH_ACCESS_REQUEST", requested_path } */
  filesReadWithAccess: async (path: string): Promise<{ path: string; content: string } | { code: string; requested_path: string; error: string }> => {
    const r = await fetch(API_BASE + "/files/read?path=" + encodeURIComponent(path), { headers: { "Content-Type": "application/json" } });
    const body = await r.json().catch(() => ({}));
    if (r.status === 403 && body.code === "PATH_ACCESS_REQUEST") return body as { code: string; requested_path: string; error: string };
    if (!r.ok) throw new Error((body as { error?: string })?.error || r.statusText);
    return body as { path: string; content: string };
  },
  filesAllowPath: (path: string) =>
    req<{ path: string; ok: boolean }>("/files/allow-path", { method: "POST", body: JSON.stringify({ path }) }),
  filesAllowedPaths: () => req<{ paths: string[] }>("/files/allowed-paths"),
  filesWrite: (path: string, content: string) =>
    req<{ path: string; ok: boolean }>("/files/write?path=" + encodeURIComponent(path), {
      method: "PUT",
      body: JSON.stringify({ content }),
    }),
  driveStatus: () => req<{ connected: boolean; summary: string }>("/drive/status"),
  driveList: () => req<{ files: unknown[]; connected: boolean }>("/drive/list"),
  ragLearn: (topic: string, text: string) =>
    req<{ ok: boolean; topic: string }>("/rag/learn", {
      method: "POST",
      body: JSON.stringify({ topic, text }),
    }),
  ragLearned: () =>
    req<{ has_learned: boolean; topics: { topic: string; chunks_count: number }[] }>("/rag/learned"),
  ragAsk: (question: string, topic?: string) =>
    req<{ summary: string }>("/rag/ask", {
      method: "POST",
      body: JSON.stringify({ question, topic, k: 5 }),
    }),
  ragDeleteTopic: (topic: string) =>
    req<{ ok: boolean; topic: string; deleted_chunks: number }>(`/rag/topic/${encodeURIComponent(topic)}`, {
      method: "DELETE",
    }),
  ragGetTopic: (topic: string) =>
    req<{ topic: string; content: string }>(`/rag/topic/${encodeURIComponent(topic)}`),
  ragUpdateTopic: (topic: string, content: string) =>
    req<{ ok: boolean; topic: string }>(`/rag/topic/${encodeURIComponent(topic)}`, {
      method: "PUT",
      body: JSON.stringify({ content }),
    }),
  tasksLearn: (topic: string, durationMinutes: number, sources: string[]) =>
    req<{ job_id: string; topic: string }>("/tasks/learn", {
      method: "POST",
      body: JSON.stringify({ topic, duration_minutes: durationMinutes, sources, user_id: "default" }),
    }),
  getSettingsKeys: () =>
    req<Record<string, boolean>>("/settings/keys"),
  testApiKey: (provider: string) =>
    req<{ ok: boolean; error?: string; message?: string }>("/settings/test-key?provider=" + encodeURIComponent(provider)),
  restartBackend: () =>
    req<{ message: string }>("/restart", { method: "POST" }),
  setSettingsKeys: (keys: Record<string, string | null>) =>
    req<{ ok: boolean }>("/settings/keys", {
      method: "PUT",
      body: JSON.stringify(keys),
    }),
  getDefaultAi: () => req<{ provider: string }>("/settings/default-ai"),
  setDefaultAi: (provider: string) =>
    req<{ provider: string }>("/settings/default-ai", {
      method: "PUT",
      body: JSON.stringify({ provider }),
    }),
  getFallbackProviders: () =>
    req<{ providers: string }>("/settings/fallback"),
  setFallbackProviders: (providers: string) =>
    req<{ providers: string }>("/settings/fallback", {
      method: "PUT",
      body: JSON.stringify({ providers }),
    }),
  getModels: () =>
    req<{ models: Record<string, string>; defaults: Record<string, string> }>("/settings/models"),
  setModel: (provider: string, model: string) =>
    req<{ provider: string; model: string }>("/settings/models", {
      method: "PUT",
      body: JSON.stringify({ provider, model }),
    }),
  whatsappQr: () =>
    req<{ connected: boolean; qr: string | null; error?: string }>("/whatsapp/qr"),
  whatsappLogout: () =>
    req<{ ok: boolean; error?: string }>("/settings/whatsapp/logout", { method: "POST" }),
  getSpotifySetup: () =>
    req<{ dashboard_url: string; docs_url: string; steps: string[]; redirect_uri: string; connect_url: string }>("/spotify/setup"),
  getSpotifyStatus: () =>
    req<{ connected: boolean }>("/spotify/status"),
  processAudio: async (file: File, instruction: string, user_id: string = "default", whisperModel: string = "base") => {
    const form = new FormData();
    form.append("file", file);
    form.append("instruction", instruction);
    form.append("user_id", user_id);
    form.append("whisper_model", whisperModel);
    form.append("async_mode", "1");
    const r = await fetch(API_BASE + "/audio/process", {
      method: "POST",
      body: form,
      credentials: "include",
    });
    if (!r.ok) throw new Error(await r.text().then((t) => t.slice(0, 300)));
    const body = (await r.json()) as { job_id?: string; transcript?: string; formatted?: string };
    if (r.status === 202 && body.job_id) return { job_id: body.job_id };
    return { transcript: body.transcript ?? "", formatted: body.formatted ?? "" };
  },
  audioStatus: (jobId: string) =>
    req<{ stage: string; transcript?: string; formatted?: string; error?: string }>("/audio/status/" + encodeURIComponent(jobId)),
  getNotifications(limit = 50) {
    return req<{ notifications: any[] }>(`/notifications?limit=${limit}`);
  },

  deleteNotification(id: number) {
    return req<{ ok: boolean }>(`/notifications/${id}`, { method: "DELETE" });
  },
  getServerStatus: () => req<ServerStatus>("/settings/server-status"),
  checkUpdate: () => req<{ update_available: boolean; local: string; remote: string; error?: string }>("/settings/check-update"),
  triggerUpdate: () => req<{ ok: boolean; message: string }>("/settings/update", { method: "POST" }),
};

