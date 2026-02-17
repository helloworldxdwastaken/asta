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
  thinking?: {
    level: "off" | "minimal" | "low" | "medium" | "high" | "xhigh";
  };
  reasoning?: {
    mode: "off" | "on" | "stream";
  };
  final?: {
    mode: "off" | "strict";
  };
  channels?: {
    telegram?: {
      configured: boolean;
    };
    whatsapp?: {
      configured: boolean;
      reachable: boolean;
      connected: boolean;
      connecting: boolean;
      has_qr: boolean;
      state: string;
      reconnect_attempts?: number | null;
      owner_jid?: string | null;
      last_connected_at?: string | null;
      last_disconnect?: unknown;
      uptime_sec?: number | null;
      error?: string | null;
    };
  };
  skills: { id: string; name: string; description: string; enabled: boolean; available: boolean }[];
  app: string;
  version: string;
};

export type ServerStatus = {
  ok: boolean;
  cpu_percent: number;
  cpu_model?: string;
  cpu_count?: number;
  ram: { total_gb: number; used_gb: number; percent: number };
  disk: { total_gb: number; used_gb: number; percent: number };
  uptime_str: string;
  error?: string;
};

export type Skill = {
  id: string;
  name: string;
  description: string;
  source?: "builtin" | "workspace" | string;
  enabled: boolean;
  available: boolean;
  /** When not available: "Connect" | "Configure paths" | "Set API key" etc. */
  action_hint?: string | null;
  /** From SKILL.md: e.g. "brew tap antoniorodr/memo && brew install antoniorodr/memo/memo" */
  install_cmd?: string | null;
  /** From SKILL.md: e.g. "Install memo via Homebrew" */
  install_label?: string | null;
  /** Binaries that must be in exec allowlist (e.g. ["memo"]). When enabled, backend auto-adds to allowlist. */
  required_bins?: string[];
};

export type CronJob = {
  id: number;
  name: string;
  cron_expr: string;
  tz: string | null;
  message: string;
  channel: string;
  channel_target: string;
  enabled: number;
  payload_kind: string;
  tlg_call: number;
  created_at: string;
};

export type WorkspaceNote = {
  name: string;
  path: string;
  size: number;
  modified_at: string;
};

export type WhatsAppPolicy = {
  allowed_numbers: string[];
  self_chat_only: boolean;
  owner_number: string;
};

export type VisionSettings = {
  preprocess: boolean;
  provider_order: string;
  openrouter_model: string;
};

export type ProviderFlowEntry = {
  provider: "claude" | "ollama" | "openrouter";
  label: string;
  position: number;
  connected: boolean;
  enabled: boolean;
  auto_disabled: boolean;
  disabled_reason: string;
  active: boolean;
  model: string;
  default_model: string;
};

export type ProviderFlow = {
  default_provider: "claude" | "ollama" | "openrouter";
  order: Array<"claude" | "ollama" | "openrouter">;
  providers: ProviderFlowEntry[];
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
  /** Chat can take 60–90s when exec is used (e.g. Apple Notes). Pass signal to cancel or set a timeout. */
  chat: (text: string, provider: string = "groq", conversationId?: string, signal?: AbortSignal) =>
    req<{ reply: string; conversation_id: string; provider: string }>("/chat", {
      method: "POST",
      body: JSON.stringify({ text, provider, user_id: "default", conversation_id: conversationId }),
      ...(signal && { signal }),
    }),
  chatStream: async (
    text: string,
    provider: string = "groq",
    conversationId?: string,
    opts?: {
      signal?: AbortSignal;
      onEvent?: (event: string, payload: Record<string, unknown>) => void;
    }
  ): Promise<{ reply: string; conversation_id: string; provider: string }> => {
    const r = await fetch(API_BASE + "/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, provider, user_id: "default", conversation_id: conversationId }),
      ...(opts?.signal ? { signal: opts.signal } : {}),
    });
    if (!r.ok) throw new Error(await r.text().then((t) => t.slice(0, 300)));
    if (!r.body) throw new Error("Streaming not available in this browser.");

    const reader = r.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";
    let finalReply = "";
    let finalConversationId = conversationId || "default:web";
    let finalProvider = provider;

    const parseBlock = (block: string): { event: string; payload: Record<string, unknown> | null } => {
      let event = "message";
      const dataLines: string[] = [];
      for (const line of block.split(/\r?\n/)) {
        if (!line) continue;
        if (line.startsWith("event:")) {
          event = line.slice("event:".length).trim();
          continue;
        }
        if (line.startsWith("data:")) {
          dataLines.push(line.slice("data:".length).trimStart());
        }
      }
      if (dataLines.length === 0) return { event, payload: null };
      try {
        const payload = JSON.parse(dataLines.join("\n")) as Record<string, unknown>;
        return { event, payload };
      } catch {
        return { event, payload: null };
      }
    };

    const handleParsed = (event: string, payload: Record<string, unknown> | null) => {
      if (!payload) return;
      opts?.onEvent?.(event, payload);
      if (event === "done") {
        finalReply = String(payload.reply ?? "");
        finalConversationId = String(payload.conversation_id ?? finalConversationId);
        finalProvider = String(payload.provider ?? finalProvider);
        return;
      }
      if (event === "meta") {
        finalConversationId = String(payload.conversation_id ?? finalConversationId);
        finalProvider = String(payload.provider ?? finalProvider);
        return;
      }
      if (event === "error") {
        const msg = String(payload.error ?? "Stream error");
        throw new Error(msg);
      }
    };

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      while (true) {
        const splitIndex = buffer.indexOf("\n\n");
        if (splitIndex === -1) break;
        const block = buffer.slice(0, splitIndex);
        buffer = buffer.slice(splitIndex + 2);
        const parsed = parseBlock(block);
        handleParsed(parsed.event, parsed.payload);
      }
    }

    buffer += decoder.decode();
    if (buffer.trim()) {
      const parsed = parseBlock(buffer);
      handleParsed(parsed.event, parsed.payload);
    }

    return {
      reply: finalReply,
      conversation_id: finalConversationId,
      provider: finalProvider,
    };
  },
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
  ragStatus: () =>
    req<{ ok: boolean; message: string; provider: string | null; detail?: string | null; ollama_url?: string | null; ollama_reason?: string; ollama_ok?: boolean; store_error?: boolean }>("/rag/status"),
  ragCheckOllama: (url: string) =>
    req<{ ok: boolean; detail: string | null; ollama_url: string; ollama_reason?: string }>(`/rag/check-ollama?url=${encodeURIComponent(url)}`),
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
  getThinking: () =>
    req<{ thinking_level: "off" | "minimal" | "low" | "medium" | "high" | "xhigh" }>("/settings/thinking"),
  setThinking: (thinking_level: "off" | "minimal" | "low" | "medium" | "high" | "xhigh") =>
    req<{ thinking_level: "off" | "minimal" | "low" | "medium" | "high" | "xhigh" }>("/settings/thinking", {
      method: "PUT",
      body: JSON.stringify({ thinking_level }),
    }),
  getReasoning: () =>
    req<{ reasoning_mode: "off" | "on" | "stream" }>("/settings/reasoning"),
  setReasoning: (reasoning_mode: "off" | "on" | "stream") =>
    req<{ reasoning_mode: "off" | "on" | "stream" }>("/settings/reasoning", {
      method: "PUT",
      body: JSON.stringify({ reasoning_mode }),
    }),
  getFinalMode: () =>
    req<{ final_mode: "off" | "strict" }>("/settings/final-mode"),
  setFinalMode: (final_mode: "off" | "strict") =>
    req<{ final_mode: "off" | "strict" }>("/settings/final-mode", {
      method: "PUT",
      body: JSON.stringify({ final_mode }),
    }),
  getVisionSettings: () =>
    req<VisionSettings>("/settings/vision"),
  setVisionSettings: (body: VisionSettings) =>
    req<VisionSettings>("/settings/vision", {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  getProviderFlow: () =>
    req<ProviderFlow>("/settings/provider-flow"),
  setProviderEnabled: (provider: "claude" | "ollama" | "openrouter", enabled: boolean) =>
    req<{ provider: string; enabled: boolean; auto_disabled: boolean; disabled_reason: string }>(
      "/settings/provider-flow/provider-enabled",
      {
        method: "PUT",
        body: JSON.stringify({ provider, enabled }),
      }
    ),
  getFallbackProviders: () =>
    req<{ providers: string }>("/settings/fallback"),
  setFallbackProviders: (providers: string) =>
    req<{ providers: string }>("/settings/fallback", {
      method: "PUT",
      body: JSON.stringify({ providers }),
    }),
  getModels: () =>
    req<{ models: Record<string, string>; defaults: Record<string, string> }>("/settings/models"),
  /** Available models per provider (e.g. Ollama local models for Dashboard Brain) */
  getAvailableModels: () =>
    req<{ ollama: string[]; openrouter?: string[] }>("/settings/available-models"),
  setModel: (provider: string, model: string) =>
    req<{ provider: string; model: string }>("/settings/models", {
      method: "PUT",
      body: JSON.stringify({ provider, model }),
    }),
  whatsappQr: () =>
    req<{ connected: boolean; qr: string | null; error?: string }>("/whatsapp/qr"),
  whatsappLogout: () =>
    req<{ ok: boolean; error?: string }>("/settings/whatsapp/logout", { method: "POST" }),
  whatsappPolicy: () =>
    req<WhatsAppPolicy>("/settings/whatsapp/policy"),
  setWhatsappPolicy: (body: { allowed_numbers: string; self_chat_only: boolean; owner_number?: string }) =>
    req<{ ok: boolean; allowed_numbers: string[]; self_chat_only: boolean; owner_number: string }>("/settings/whatsapp/policy", {
      method: "PUT",
      body: JSON.stringify(body),
    }),
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

  getWorkspaceNotes(limit = 20) {
    return req<{ notes: WorkspaceNote[] }>(`/settings/notes?limit=${limit}`);
  },

  deleteNotification(id: number) {
    return req<{ ok: boolean }>(`/notifications/${id}`, { method: "DELETE" });
  },
  getServerStatus: () => req<ServerStatus>("/settings/server-status"),
  checkUpdate: () => req<{ update_available: boolean; local: string; remote: string; error?: string }>("/settings/check-update"),
  triggerUpdate: () => req<{ ok: boolean; message: string }>("/settings/update", { method: "POST" }),

  /** Cron (scheduled recurring jobs) */
  getCronJobs: (userId = "default") =>
    req<{ cron_jobs: CronJob[] }>(`/cron?user_id=${encodeURIComponent(userId)}`),
  deleteCronJob: (jobId: number) =>
    req<{ ok: boolean; id: number }>(`/cron/${jobId}`, { method: "DELETE" }),
  updateCronJob: (jobId: number, body: { name?: string; cron_expr?: string; tz?: string; message?: string; channel?: string; channel_target?: string; enabled?: boolean; payload_kind?: string; tlg_call?: boolean }) =>
    req<{ ok: boolean; id: number; name?: string; cron_expr?: string; tz?: string | null; channel?: string; channel_target?: string; enabled?: number; payload_kind?: string; tlg_call?: number }>(`/cron/${jobId}`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  addCronJob: (body: { name: string; cron_expr: string; message: string; tz?: string; channel?: string; channel_target?: string; payload_kind?: string; tlg_call?: boolean }) =>
    req<{ id: number; name: string; cron_expr: string }>("/cron", {
      method: "POST",
      body: JSON.stringify({ ...body, channel: body.channel ?? "web", channel_target: body.channel_target ?? "" }),
    }),
  getTelegramUsername: () =>
    req<{ username: string | null }>("/settings/telegram/username"),
  setTelegramUsername: (username: string) =>
    req<{ ok: boolean }>("/settings/telegram/username", {
      method: "POST",
      body: JSON.stringify({ username }),
    }),
  getPingramSettings: () =>
    req<{ client_id: string; client_secret: string; api_key: string; api_key_set: boolean; notification_id: string; template_id: string; phone_number: string; is_secret_set: boolean }>("/settings/pingram"),
  setPingramSettings: (body: { client_id?: string; client_secret?: string; api_key?: string; notification_id?: string; template_id?: string; phone_number?: string }) =>
    req<{ ok: boolean }>("/settings/pingram", {
      method: "POST",
      body: JSON.stringify(body),
    }),
};
