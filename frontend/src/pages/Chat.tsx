import { useState, useRef, useEffect, useCallback } from "react";
import { api } from "../api/client";

const PROVIDER_LABELS: Record<string, string> = {
  groq: "Groq",
  google: "Google (Gemini)",
  claude: "Claude",
  ollama: "Ollama",
  openai: "OpenAI",
  openrouter: "OpenRouter",
};

const USER_ID = "default";

type ChatChannel = "web" | "telegram";

export default function Chat() {
  const [channel, setChannel] = useState<ChatChannel>("web");
  const [messages, setMessages] = useState<{ role: "user" | "assistant"; content: string }[]>([]);
  const [input, setInput] = useState("");
  const [provider, setProvider] = useState("default");
  const [providers, setProviders] = useState<string[]>([]);
  const [defaultProvider, setDefaultProvider] = useState<string>("groq");
  const [models, setModels] = useState<Record<string, string>>({});
  const [defaults, setDefaults] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const bottom = useRef<HTMLDivElement>(null);

  const conversationId = `${USER_ID}:${channel}`;

  const loadMessages = useCallback(async () => {
    setLoadingHistory(true);
    try {
      const r = await api.getChatMessages(conversationId, USER_ID);
      setMessages((r.messages ?? []).map((m) => ({ role: m.role as "user" | "assistant", content: m.content })));
    } catch {
      setMessages([]);
    } finally {
      setLoadingHistory(false);
    }
  }, [conversationId]);

  useEffect(() => {
    loadMessages();
  }, [loadMessages]);

  useEffect(() => {
    api.providers().then((r) => setProviders(r.providers));
    api.getDefaultAi().then((r) => setDefaultProvider(r.provider));
    api.getModels().then((r) => {
      setModels(r.models);
      setDefaults(r.defaults);
    });
  }, []);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const resetChat = () => {
    setMessages([]);
    setInput("");
  };

  const send = async () => {
    const text = input.trim();
    if (!text || loading) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", content: text }]);
    setLoading(true);
    try {
      const r = await api.chat(text, provider, conversationId);
      setMessages((m) => [...m, { role: "assistant", content: r.reply }]);
    } catch (e) {
      setMessages((m) => [...m, { role: "assistant", content: "Error: " + (e as Error).message }]);
    } finally {
      setLoading(false);
    }
  };

  const effectiveProvider = provider === "default" ? defaultProvider : provider;
  const modelName = models[effectiveProvider] || defaults[effectiveProvider];
  const channelLabel = channel === "telegram" ? "Telegram" : "Web";

  return (
    <div className="chat-page">
      <header className="chat-header">
        <div className="chat-header-left">
          <h1 className="chat-title">Chat</h1>
          <div className="chat-pills">
            <button
              type="button"
              className={"chat-pill " + (channel === "web" ? "active" : "")}
              onClick={() => setChannel("web")}
              aria-pressed={channel === "web"}
            >
              Web
            </button>
            <button
              type="button"
              className={"chat-pill " + (channel === "telegram" ? "active" : "")}
              onClick={() => setChannel("telegram")}
              aria-pressed={channel === "telegram"}
            >
              Telegram
            </button>
          </div>
        </div>
        <div className="chat-header-right">
          <select
            className="chat-provider-select"
            value={provider}
            onChange={(e) => setProvider(e.target.value)}
            aria-label="AI provider"
          >
            <option value="default">Default ({PROVIDER_LABELS[defaultProvider] ?? defaultProvider})</option>
            {providers.map((p) => (
              <option key={p} value={p}>{PROVIDER_LABELS[p] ?? p}</option>
            ))}
          </select>
          {modelName ? <span className="chat-model-badge" title="Model">{modelName.split(",")[0].trim()}</span> : null}
          <button
            type="button"
            className="chat-new-btn"
            onClick={resetChat}
            disabled={loading || messages.length === 0}
            title="Clear and start new chat"
          >
            New chat
          </button>
        </div>
      </header>

      <div className="chat-main">
        <div className="chat-pane">
          {loadingHistory ? (
            <div className="chat-empty">
              <div className="chat-empty-spinner" aria-hidden />
              <p>Loading conversation…</p>
            </div>
          ) : messages.length === 0 ? (
            <div className="chat-empty">
              <div className="chat-empty-icon" aria-hidden>💬</div>
              <p className="chat-empty-title">{channelLabel} thread</p>
              <p className="chat-empty-hint">Send a message to start. Asta can use files, Drive, and learned knowledge.</p>
            </div>
          ) : (
            <div className="chat-thread">
              {messages.map((m, i) => (
                <div key={i} className={"chat-msg " + m.role}>
                  <span className="chat-msg-label">{m.role === "user" ? "You" : "Asta"}</span>
                  <div className="chat-bubble">{m.content}</div>
                </div>
              ))}
              {loading && (
                <div className="chat-msg assistant">
                  <span className="chat-msg-label">Asta</span>
                  <div className="chat-bubble chat-bubble-typing">
                    <span className="chat-typing-dots"><span></span><span></span><span></span></span>
                  </div>
                </div>
              )}
            </div>
          )}
          <div ref={bottom} />
        </div>

        <div className="chat-input-wrap">
          <textarea
            className="chat-input-field"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
                e.preventDefault();
                send();
              }
            }}
            placeholder={channel === "telegram" ? "Reply here or in Telegram (Ctrl+Enter to send)…" : "Message Asta… (Ctrl+Enter to send)"}
            disabled={loading}
            rows={1}
            aria-label="Message"
          />
          <button
            type="button"
            className="chat-send-btn"
            onClick={send}
            disabled={loading || !input.trim()}
            aria-label="Send"
            title="Send (Enter)"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/></svg>
          </button>
        </div>
      </div>
    </div>
  );
}
