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

export type Skill = {
  id: string;
  name: string;
  description: string;
  enabled: boolean;
  available: boolean;
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
  providers: () => req<{ providers: string[] }>("/providers"),
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
  getModels: () =>
    req<{ models: Record<string, string>; defaults: Record<string, string> }>("/settings/models"),
  setModel: (provider: string, model: string) =>
    req<{ provider: string; model: string }>("/settings/models", {
      method: "PUT",
      body: JSON.stringify({ provider, model }),
    }),
  whatsappQr: () =>
    req<{ connected: boolean; qr: string | null; error?: string }>("/whatsapp/qr"),
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
};
