// ── API client for Asta backend ───────────────────────────────────────────────
// Uses Tauri HTTP plugin (bypasses CORS) when running inside Tauri,
// falls back to standard fetch in plain browser.

import { fetch as tauriFetch } from "@tauri-apps/plugin-http";

// Pick the right fetch: Tauri plugin (Rust-side, no CORS) or browser native.
// Tauri v2: check for __TAURI_INTERNALS__ (v2 marker) or __TAURI__ (v1 compat).
const _fetch: typeof globalThis.fetch = (() => {
  try {
    // @ts-ignore — Tauri runtime check
    if (window.__TAURI_INTERNALS__ || window.__TAURI__) return tauriFetch as unknown as typeof globalThis.fetch;
  } catch {}
  return globalThis.fetch;
})();

import { getJwt, clearAuth } from "./auth";

// Migrate: clear old localhost URL so it falls back to the hardcoded remote
if (localStorage.getItem("backendURL") === "http://localhost:8010") {
  localStorage.removeItem("backendURL");
}
let _backendUrl = localStorage.getItem("backendURL") ?? "https://asta.noxamusic.com";
// Legacy auth token (for backward compat when no users exist)
let _authToken = localStorage.getItem("authToken") ?? "";

export function getBackendUrl(): string { return _backendUrl; }
export function setBackendUrl(url: string): void {
  _backendUrl = url.replace(/\/$/, "");
  localStorage.setItem("backendURL", _backendUrl);
}

export function getAuthToken(): string { return _authToken; }
export function setAuthToken(token: string): void {
  _authToken = token.trim();
  if (_authToken) localStorage.setItem("authToken", _authToken);
  else localStorage.removeItem("authToken");
}

/** Build auth headers: prefer JWT, fall back to legacy Bearer token. */
function _authHeaders(): Record<string, string> {
  const jwt = getJwt();
  if (jwt) return { Authorization: `Bearer ${jwt}` };
  return _authToken ? { Authorization: `Bearer ${_authToken}` } : {};
}

/** Probe a URL for /api/health (fast timeout). */
async function _probe(url: string): Promise<boolean> {
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 5000);
    const opts: any = { signal: controller.signal, headers: _authHeaders() };
    // Tauri HTTP plugin: accept certs on remote HTTPS URLs (e.g. Cloudflare Tunnel)
    if (url.startsWith("https://")) {
      opts.danger = { acceptInvalidCerts: true, acceptInvalidHostnames: true };
    }
    const res = await _fetch(`${url}/api/health`, opts);
    clearTimeout(timer);
    return res.ok;
  } catch { return false; }
}

/** Probe the configured backend URL. Returns true if reachable. */
export async function autoResolveBackend(): Promise<boolean> {
  return _probe(_backendUrl);
}

async function req<T>(method: string, path: string, body?: unknown, query?: Record<string, string>): Promise<T> {
  let url = `${_backendUrl}${path}`;
  if (query) {
    const params = new URLSearchParams(query);
    url += `?${params}`;
  }
  const headers: Record<string, string> = { ..._authHeaders() };
  if (body) headers["Content-Type"] = "application/json";
  const opts: any = {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  };
  // Tauri HTTP plugin: accept certs on remote HTTPS (e.g. Cloudflare Tunnel)
  if (_backendUrl.startsWith("https://")) {
    opts.danger = { acceptInvalidCerts: true, acceptInvalidHostnames: true };
  }
  const res = await _fetch(url, opts);
  if (!res.ok) {
    if (res.status === 401 && getJwt()) {
      clearAuth();
      window.dispatchEvent(new Event("auth-expired"));
    }
    throw new Error(`${method} ${path} → ${res.status}`);
  }
  const text = await res.text();
  return text ? JSON.parse(text) : ({} as T);
}

// ── Health & Status ───────────────────────────────────────────────────────────
export const checkHealth = () => {
  const opts: any = { headers: _authHeaders() };
  if (_backendUrl.startsWith("https://")) {
    opts.danger = { acceptInvalidCerts: true, acceptInvalidHostnames: true };
  }
  return _fetch(`${_backendUrl}/api/health`, opts).then(r => r.ok).catch(() => false);
};
export const getHealth = () => req<any>("GET", "/api/health");
export const getStatus = () => req<any>("GET", "/api/status");
export const getServerStatus = () => req<any>("GET", "/api/settings/server-status");

// ── Conversations ─────────────────────────────────────────────────────────────
export const listConversations = (limit?: number) =>
  req<{ conversations: any[] }>("GET", "/api/chat/conversations", undefined,
    { channel: "web", ...(limit ? { limit: String(limit) } : {}) });

export const deleteConversation = (id: string) =>
  req("DELETE", `/api/chat/conversations/${id}`);

export const truncateConversation = (id: string, keepCount: number) =>
  req("POST", `/api/chat/conversations/${id}/truncate`, { keep_count: keepCount });

export const loadMessages = (conversationId: string, limit?: number) =>
  req<{ messages: any[] }>("GET", "/api/chat/messages", undefined,
    { conversation_id: conversationId, ...(limit ? { limit: String(limit) } : {}) });

// ── Folders ───────────────────────────────────────────────────────────────────
export const listFolders = () =>
  req<{ folders: any[] }>("GET", "/api/chat/folders", undefined, { channel: "web" });

export const createFolder = (name: string) =>
  req("POST", "/api/chat/folders", { name, channel: "web" });

export const renameFolder = (id: string, name: string) =>
  req("PATCH", `/api/chat/folders/${id}`, { name });

export const deleteFolder = (id: string) =>
  req("DELETE", `/api/chat/folders/${id}`);

export const assignConversationFolder = (id: string, folderId: string | null) =>
  req("PUT", `/api/chat/conversations/${id}/folder`, { folder_id: folderId });

// ── Chat ──────────────────────────────────────────────────────────────────────
export interface SendMessageOpts {
  text: string;
  provider?: string;
  conversation_id?: string;
  agent_id?: string;
  web_enabled?: boolean;
  channel?: string;
  user_id?: string;
}

export const sendMessage = (opts: SendMessageOpts) =>
  req<{ conversation_id: string; reply: string }>("POST", "/api/chat", {
    ...opts, channel: opts.channel ?? "web",
  });

/** Normalise backend SSE event names to UI types. */
function normaliseEventType(name: string): string {
  switch (name) {
    case "assistant": return "text";
    case "reasoning": return "thinking";
    default: return name; // tool_start, tool_end, done, error, status, meta
  }
}

export interface StreamChunk {
  type: string;
  delta?: string;
  text?: string;
  reply?: string;
  conversation_id?: string;
  provider?: string;
  name?: string;      // tool name (tool_start/tool_end)
  label?: string;     // tool display label
  error?: string;
}

export function streamChat(
  opts: SendMessageOpts,
  onChunk: (data: StreamChunk) => void,
  onDone: (conversationId?: string) => void,
  onError: (err: Error) => void,
): () => void {
  let aborted = false;
  let finished = false;
  const controller = new AbortController();
  const safeOnDone = (convId?: string) => { if (!finished) { finished = true; onDone(convId); } };

  const fetchOpts: any = {
    method: "POST",
    headers: { "Content-Type": "application/json", ..._authHeaders() },
    body: JSON.stringify({
      ...opts, channel: opts.channel ?? "web",
    }),
    signal: controller.signal,
  };
  if (_backendUrl.startsWith("https://")) {
    fetchOpts.danger = { acceptInvalidCerts: true, acceptInvalidHostnames: true };
  }
  _fetch(`${_backendUrl}/api/chat/stream`, fetchOpts).then(async (res) => {
    if (!res.ok || !res.body) {
      if (res.status === 401 && getJwt()) {
        clearAuth();
        window.dispatchEvent(new Event("auth-expired"));
      }
      throw new Error(`Stream error: ${res.status}`);
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    let lastConvId: string | undefined;

    while (true) {
      const { done, value } = await reader.read();
      if (done || aborted) break;
      buf += decoder.decode(value, { stream: true });

      // SSE spec: blocks separated by blank lines
      const blocks = buf.split("\n\n");
      buf = blocks.pop() ?? "";

      for (const block of blocks) {
        const lines = block.split("\n");
        let eventName: string | null = null;
        let dataStr: string | null = null;

        for (const line of lines) {
          if (line.startsWith("event: ")) {
            eventName = line.slice(7).trim();
          } else if (line.startsWith("data: ")) {
            dataStr = line.slice(6);
          } else if (line.startsWith("data:")) {
            dataStr = line.slice(5);
          }
        }

        if (dataStr === null) continue;
        const raw = dataStr.trim();
        if (raw === "[DONE]") { safeOnDone(lastConvId); return; }

        try {
          const parsed = JSON.parse(raw) as StreamChunk;
          parsed.type = normaliseEventType(eventName ?? parsed.type ?? "");
          if (parsed.conversation_id) lastConvId = parsed.conversation_id;
          onChunk(parsed);
        } catch {
          onChunk({ type: "text", delta: raw });
        }
      }
    }
    safeOnDone(lastConvId);
  }).catch((err) => { if (!aborted) onError(err); });

  return () => {
    aborted = true;
    controller.abort();
    // Ensure UI resets even when abort races with reader
    setTimeout(() => safeOnDone(undefined), 0);
  };
}

// ── Settings — GET ────────────────────────────────────────────────────────────
export const getDefaultAI = () => req<any>("GET", "/api/settings/default-ai");
export const getThinking = () => req<any>("GET", "/api/settings/thinking");
export const getReasoning = () => req<any>("GET", "/api/settings/reasoning");
export const getMoodSetting = () => req<any>("GET", "/api/settings/mood");
export const getProviders = () => req<any>("GET", "/api/providers");
export const getProviderFlow = () => req<any>("GET", "/api/settings/provider-flow");
export const getFinalMode = () => req<any>("GET", "/api/settings/final-mode");
export const getVision = () => req<any>("GET", "/api/settings/vision");
export const getFallback = () => req<any>("GET", "/api/settings/fallback");
export const getModels = () => req<any>("GET", "/api/settings/models");
export const getAvailableModels = () => req<any>("GET", "/api/settings/available-models");
export const getKeyStatus = () => req<any>("GET", "/api/settings/keys");
export const getSkills = () => req<any>("GET", "/api/settings/skills");
export const getPersona = () => req<any>("GET", "/api/settings/persona");
export const getTelegramUsername = () => req<any>("GET", "/api/settings/telegram/username");
export const getPingram = () => req<any>("GET", "/api/settings/pingram");
export const getSecurityAudit = () => req<any>("GET", "/api/settings/security-audit");
export const getMemoryHealth = (force?: boolean) =>
  req<any>("GET", "/api/settings/memory-health", undefined, force ? { force: "true" } : {});
export const checkUpdate = () => req<any>("GET", "/api/settings/check-update");
export const getNotes = (limit?: number) =>
  req<any>("GET", "/api/settings/notes", undefined, limit ? { limit: String(limit) } : {});
export const getUsage = (days?: number) =>
  req<any>("GET", "/api/settings/usage", undefined, days ? { days: String(days) } : {});
export const testKey = (provider: string) =>
  req<any>("GET", "/api/settings/test-key", undefined, { provider });
export const getApiTokenStatus = () => req<any>("GET", "/api/settings/api-token");
export const setApiToken = (action: "generate" | "set" | "clear", token?: string) =>
  req<any>("POST", "/api/settings/api-token", { action, token });

// ── Settings — PUT/POST ───────────────────────────────────────────────────────
export const setDefaultAI = (provider: string) =>
  req("PUT", "/api/settings/default-ai", { provider });
export const setThinking = (level: string) =>
  req("PUT", "/api/settings/thinking", { thinking_level: level });
export const setReasoning = (mode: string) =>
  req("PUT", "/api/settings/reasoning", { reasoning_mode: mode });
export const setMoodSetting = (mood: string) =>
  req("PUT", "/api/settings/mood", { mood });
export const setPersona = (data: { soul?: string; user?: string }) =>
  req("PUT", "/api/settings/persona", data);
export const setProviderEnabled = (provider: string, enabled: boolean) =>
  req("PUT", "/api/settings/provider-flow/provider-enabled", { provider, enabled });
export const setFinalMode = (mode: string) =>
  req("PUT", "/api/settings/final-mode", { final_mode: mode });
export const setVision = (preprocess: boolean, providerOrder = "openrouter,ollama", openrouterModel = "") =>
  req("PUT", "/api/settings/vision", { preprocess, provider_order: providerOrder, openrouter_model: openrouterModel });
export const setModel = (provider: string, model: string) =>
  req("PUT", "/api/settings/models", { provider, model });
export const setKeys = (keys: Record<string, string>) =>
  req("PUT", "/api/settings/keys", keys);
export const toggleSkill = (skillId: string, enabled: boolean) =>
  req("PUT", "/api/settings/skills", { skill_id: skillId, enabled });
export const setTelegramUsername = (username: string) =>
  req("POST", "/api/settings/telegram/username", { username });
export const setPingram = (data: any) =>
  req("POST", "/api/settings/pingram", data);
export const testPingramCall = (testNumber: string) =>
  req("POST", "/api/settings/pingram/test-call", { test_number: testNumber });
export const triggerUpdate = () =>
  req("POST", "/api/settings/update");

// ── Auth ──────────────────────────────────────────────────────────────────────
export const login = (username: string, password: string) =>
  req<{ access_token: string; user: { id: string; username: string; role: string } }>(
    "POST", "/api/auth/login", { username, password });
export const register = (username: string, password: string) =>
  req("POST", "/api/auth/register", { username, password });
export const getMe = () => req<{ id: string; username: string; role: string }>("GET", "/api/auth/me");
export const changePassword = (current_password: string, new_password: string) =>
  req("POST", "/api/auth/change-password", { current_password, new_password });
export const listUsers = () => req<{ users: any[] }>("GET", "/api/auth/users");
export const createUser = (username: string, password: string, role: string) =>
  req("POST", "/api/auth/users", { username, password, role });
export const deleteUser = (userId: string) => req("DELETE", `/api/auth/users/${userId}`);
export const resetUserPassword = (userId: string, new_password: string) =>
  req("PUT", `/api/auth/users/${userId}/reset-password`, { new_password });

// ── Spotify ───────────────────────────────────────────────────────────────────
export const spotifyStatus = () => req<any>("GET", "/api/spotify/status");
export const spotifyDevices = () => req<any>("GET", "/api/spotify/devices");
export const spotifyConnectUrl = () => {
  const jwt = getJwt();
  return `${_backendUrl}/api/spotify/connect${jwt ? `?token=${jwt}` : ""}`;
};
export const spotifyDisconnect = () => req("POST", "/api/spotify/disconnect");

// ── Cron Jobs ─────────────────────────────────────────────────────────────────
export const listCron = () => req<any>("GET", "/api/cron");
export const createCron = (job: any) => req("POST", "/api/cron", job);
export const updateCron = (id: string, job: any) => req("PUT", `/api/cron/${id}`, job);
export const deleteCron = (id: string) => req("DELETE", `/api/cron/${id}`);

// ── Notifications ─────────────────────────────────────────────────────────────
export const getNotifications = (limit?: number) =>
  req<any>("GET", "/api/notifications", undefined, limit ? { limit: String(limit) } : {});
export const deleteNotification = (id: string) =>
  req("DELETE", `/api/notifications/${id}`);

// ── RAG / Knowledge ──────────────────────────────────────────────────────────
export const ragStatus = () => req<any>("GET", "/api/rag/status");
export const ragLearned = () => req<any>("GET", "/api/rag/learned");
export const ragDeleteTopic = (topic: string) =>
  req("DELETE", `/api/rag/topic/${encodeURIComponent(topic)}`);

// ── Agents ────────────────────────────────────────────────────────────────────
export const listAgents = (q?: string, activeOnly?: boolean, inactiveOnly?: boolean) => {
  const query: Record<string, string> = {};
  if (q) query.q = q;
  if (activeOnly) query.active_only = "true";
  if (inactiveOnly) query.inactive_only = "true";
  return req<any>("GET", "/api/agents", undefined, Object.keys(query).length ? query : undefined);
};
export const createAgent = (agent: any) => req("POST", "/api/agents", agent);
export const updateAgent = (id: string, agent: any) => req("PATCH", `/api/agents/${id}`, agent);
export const deleteAgent = (id: string) => req("DELETE", `/api/agents/${id}`);
export const toggleAgent = (id: string, enabled: boolean) => req("PUT", `/api/agents/${id}/enabled`, { enabled });

// ── Skills Upload ─────────────────────────────────────────────────────────────
export async function uploadSkill(file: File): Promise<any> {
  const form = new FormData();
  form.append("file", file);
  const uploadOpts: any = { method: "POST", body: form, headers: _authHeaders() };
  if (_backendUrl.startsWith("https://")) {
    uploadOpts.danger = { acceptInvalidCerts: true, acceptInvalidHostnames: true };
  }
  const res = await _fetch(`${_backendUrl}/api/skills/upload`, uploadOpts);
  if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
  return res.json();
}

// ── Downloads ─────────────────────────────────────────────────────────────────
export async function downloadPdf(filename: string): Promise<void> {
  const url = `${_backendUrl}/api/files/download-pdf/${encodeURIComponent(filename)}`;
  const dlOpts: any = { headers: _authHeaders() };
  if (_backendUrl.startsWith("https://")) {
    dlOpts.danger = { acceptInvalidCerts: true, acceptInvalidHostnames: true };
  }
  const res = await _fetch(url, dlOpts);
  if (!res.ok) throw new Error(`Download failed: ${res.status}`);
  const blob = await res.blob();
  const blobUrl = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = blobUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(blobUrl);
}

// ── System ────────────────────────────────────────────────────────────────────
export const restartBackend = () => req("POST", "/api/restart");
