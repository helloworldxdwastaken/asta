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
    image_base64?: string;
    image_mime?: string;
  },
  onChunk: (chunk: StreamChunk) => void,
  onDone: (conversationId?: string) => void,
  onError: (err: string) => void,
): Promise<() => void> {
  const base = await getBackendUrl();
  const headers = await authHeaders();
  const controller = new AbortController();

  try {
    const res = await fetch(`${base}/api/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...headers },
      body: JSON.stringify({
        text: opts.text,
        channel: "mobile",
        ...(opts.conversation_id ? { conversation_id: opts.conversation_id } : {}),
        ...(opts.provider ? { provider: opts.provider } : {}),
        ...(opts.agent_id ? { agent_id: opts.agent_id } : {}),
        ...(opts.image_base64 ? { image_base64: opts.image_base64, image_mime: opts.image_mime || "image/jpeg" } : {}),
      }),
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
export const truncateConversation = (id: string, keepCount: number) =>
  req("POST", `/api/chat/conversations/${id}/truncate`, { keep_count: keepCount });

// ── Folders / Projects ──────────────────────────────────────
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
export const getProviders = () => req("GET", "/api/providers");
export const getVision = () => req("GET", "/api/settings/vision");
export const setVision = (v: any) => req("PUT", "/api/settings/vision", v);
export const getReasoning = () => req("GET", "/api/settings/reasoning");
export const setReasoning = (mode: string) =>
  req("PUT", "/api/settings/reasoning", { reasoning_mode: mode });
export const getFinalMode = () => req("GET", "/api/settings/final-mode");
export const setFinalMode = (mode: string) =>
  req("PUT", "/api/settings/final-mode", { final_mode: mode });
export const getPersona = () => req("GET", "/api/settings/persona");
export const setPersona = (p: any) => req("PUT", "/api/settings/persona", p);
export const getSkills = () => req("GET", "/api/settings/skills");
export const toggleSkill = (skill_id: string, enabled: boolean) =>
  req("PUT", "/api/settings/skills", { skill_id, enabled });

// ── Agents ──────────────────────────────────────────────────
export const listAgents = () => req<{ agents: Agent[] }>("GET", "/api/agents");
export const createAgent = (agent: any) => req("POST", "/api/agents", agent);
export const updateAgent = (id: string, agent: any) => req("PATCH", `/api/agents/${id}`, agent);
export const deleteAgent = (id: string) => req("DELETE", `/api/agents/${id}`);
export const toggleAgent = (id: string, enabled: boolean) =>
  req("PUT", `/api/agents/${id}/enabled`, { enabled });

// ── User Management ────────────────────────────────────────
export const listUsers = () => req("GET", "/api/auth/users");
export const createUser = (username: string, password: string, role: string) =>
  req("POST", "/api/auth/users", { username, password, role });
export const deleteUser = (userId: string) => req("DELETE", `/api/auth/users/${userId}`);
export const resetUserPassword = (userId: string, new_password: string) =>
  req("PUT", `/api/auth/users/${userId}/reset-password`, { new_password });

// ── Cron ────────────────────────────────────────────────────
export const listCron = () => req("GET", "/api/cron");
export const createCron = (job: any) => req("POST", "/api/cron", job);
export const updateCron = (id: string, job: any) => req("PUT", `/api/cron/${id}`, job);
export const deleteCron = (id: string) => req("DELETE", `/api/cron/${id}`);

// ── Models ─────────────────────────────────────────────────
export const getModels = () => req("GET", "/api/settings/models");
export const getAvailableModels = () => req("GET", "/api/settings/available-models");
export const setModel = (provider: string, model: string) =>
  req("PUT", "/api/settings/models", { provider, model });

// ── Knowledge / RAG ────────────────────────────────────────
export const ragStatus = () => req("GET", "/api/rag/status");
export const ragLearned = () => req("GET", "/api/rag/learned");
export const getMemoryHealth = () => req("GET", "/api/rag/health?detail=true");
export const ragDeleteTopic = (topic: string) => req("DELETE", `/api/rag/learned/${encodeURIComponent(topic)}`);

// ── Security ────────────────────────────────────────────────
export const getSecurityAudit = () => req("GET", "/api/settings/security-audit");

// ── Channels (Telegram / Pingram) ───────────────────────────
export const getTelegramUsername = () => req("GET", "/api/settings/telegram/username");
export const setTelegramUsername = (username: string) =>
  req("POST", "/api/settings/telegram/username", { username });
export const getPingram = () => req("GET", "/api/settings/pingram");
export const setPingram = (data: any) => req("POST", "/api/settings/pingram", data);
export const testPingramCall = (testNumber: string) =>
  req("POST", "/api/settings/pingram/test-call", { test_number: testNumber });

// ── Notifications ───────────────────────────────────────────
export const getNotifications = (limit = 20) => req("GET", `/api/notifications?limit=${limit}`);
export const deleteNotification = (id: string) => req("DELETE", `/api/notifications/${id}`);
