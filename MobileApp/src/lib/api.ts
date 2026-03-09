// Asta Mobile API client — mirrors desktop api.ts
import { getJwt, clearAuth } from "./auth";
import type { StreamChunk, Conversation, Folder, Message, Agent } from "./types";
import { getItem, setItem } from "./storage";

const BACKEND_KEY = "asta_backend_url";
const DEFAULT_BACKEND = "https://asta.noxamusic.com";

let _backendUrl: string | null = null;

export async function getBackendUrl(): Promise<string> {
  if (_backendUrl) return _backendUrl;
  const stored = await getItem(BACKEND_KEY);
  _backendUrl = stored || DEFAULT_BACKEND;
  return _backendUrl;
}

export async function setBackendUrl(url: string): Promise<void> {
  _backendUrl = url.replace(/\/$/, "");
  await setItem(BACKEND_KEY, _backendUrl);
}

async function authHeaders(): Promise<Record<string, string>> {
  const jwt = await getJwt();
  return jwt ? { Authorization: `Bearer ${jwt}` } : {};
}

async function req<T = any>(method: string, path: string, body?: any): Promise<T> {
  const base = await getBackendUrl();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(await authHeaders()),
  };
  const res = await fetch(`${base}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (res.status === 401) {
    await clearAuth();
    throw new Error("auth-expired");
  }
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`${res.status}: ${text}`);
  }
  return res.json();
}

// ── Health ──────────────────────────────────────────────────
export const checkHealth = () => req("GET", "/api/health");

// ── Auth ────────────────────────────────────────────────────
export const login = (username: string, password: string) =>
  req("POST", "/api/auth/login", { username, password });
export const register = (username: string, password: string) =>
  req("POST", "/api/auth/register", { username, password });
export const getMe = () => req("GET", "/api/auth/me");

// ── Chat ────────────────────────────────────────────────────
export const sendChat = (text: string, opts?: {
  conversation_id?: string;
  provider?: string;
  agent_id?: string;
  image_base64?: string;
  image_mime?: string;
}) => req("POST", "/api/chat", { text, channel: "mobile", ...opts });

export async function streamChat(
  opts: {
    text: string;
    conversation_id?: string;
    provider?: string;
    agent_id?: string;
  },
  onChunk: (chunk: StreamChunk) => void,
  onDone: (conversationId?: string) => void,
  onError: (err: string) => void,
): Promise<() => void> {
  const base = await getBackendUrl();
  const headers = await authHeaders();
  const controller = new AbortController();

  const params = new URLSearchParams({
    text: opts.text,
    channel: "mobile",
    ...(opts.conversation_id ? { conversation_id: opts.conversation_id } : {}),
    ...(opts.provider ? { provider: opts.provider } : {}),
    ...(opts.agent_id ? { agent_id: opts.agent_id } : {}),
  });

  try {
    const res = await fetch(`${base}/api/chat/stream?${params}`, {
      headers,
      signal: controller.signal,
    });

    if (!res.ok || !res.body) {
      onError(`Stream failed: ${res.status}`);
      return () => {};
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    (async () => {
      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          let eventType = "";
          for (const line of lines) {
            if (line.startsWith("event: ")) {
              eventType = line.slice(7).trim();
            } else if (line.startsWith("data: ")) {
              const data = line.slice(6);
              if (data === "[DONE]") {
                onDone();
                return;
              }
              try {
                const parsed = JSON.parse(data);
                // Normalize event types
                const type = eventType || parsed.type || "text";
                const normalized = type === "reasoning" ? "thinking"
                  : type === "assistant" || type === "assistant_final" ? "assistant_final"
                  : type;
                onChunk({ ...parsed, type: normalized as StreamChunk["type"] });
                if (normalized === "done") {
                  onDone(parsed.conversation_id);
                  return;
                }
              } catch {}
            }
          }
        }
        onDone();
      } catch (e: any) {
        if (e.name !== "AbortError") onError(e.message);
      }
    })();
  } catch (e: any) {
    onError(e.message);
  }

  return () => controller.abort();
}

// ── Conversations ───────────────────────────────────────────
export const listConversations = (limit = 50) =>
  req<{ conversations: Conversation[] }>("GET", `/api/chat/conversations?channel=mobile&limit=${limit}`);
export const loadMessages = (conversationId: string) =>
  req<{ messages: Message[] }>("GET", `/api/chat/messages?conversation_id=${conversationId}`);
export const deleteConversation = (id: string) =>
  req("DELETE", `/api/chat/conversations/${id}`);
export const truncateConversation = (id: string, keep: number) =>
  req("POST", `/api/chat/conversations/${id}/truncate`, { keep_last: keep });

// ── Folders ─────────────────────────────────────────────────
export const listFolders = () => req<{ folders: Folder[] }>("GET", "/api/chat/folders");
export const createFolder = (name: string) => req("POST", "/api/chat/folders", { name });
export const renameFolder = (id: string, name: string) => req("PATCH", `/api/chat/folders/${id}`, { name });
export const deleteFolder = (id: string) => req("DELETE", `/api/chat/folders/${id}`);
export const assignConversationFolder = (convId: string, folderId: string | null) =>
  req("PUT", `/api/chat/conversations/${convId}/folder`, { folder_id: folderId });

// ── Settings ────────────────────────────────────────────────
export const getDefaultAI = () => req("GET", "/api/settings/default-ai");
export const setDefaultAI = (provider: string) => req("PUT", "/api/settings/default-ai", { provider });
export const getThinking = () => req("GET", "/api/settings/thinking");
export const setThinking = (level: string) => req("PUT", "/api/settings/thinking", { thinking_level: level });
export const getMoodSetting = () => req("GET", "/api/settings/mood");
export const setMoodSetting = (mood: string) => req("PUT", "/api/settings/mood", { mood });
export const getKeyStatus = () => req("GET", "/api/settings/keys");
export const setKeys = (keys: Record<string, string>) => req("PUT", "/api/settings/keys", keys);
export const getServerStatus = () => req("GET", "/api/settings/server-status");
export const getUsage = () => req("GET", "/api/settings/usage");

// ── Agents ──────────────────────────────────────────────────
export const listAgents = () => req<{ agents: Agent[] }>("GET", "/api/agents");

// ── Cron ────────────────────────────────────────────────────
export const listCron = () => req("GET", "/api/cron");
export const createCron = (job: any) => req("POST", "/api/cron", job);
export const updateCron = (id: string, job: any) => req("PUT", `/api/cron/${id}`, job);
export const deleteCron = (id: string) => req("DELETE", `/api/cron/${id}`);
