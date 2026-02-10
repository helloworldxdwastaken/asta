import { useState, useRef, useEffect } from "react";
import { api } from "../api/client";

const PROVIDER_LABELS: Record<string, string> = {
  groq: "Groq",
  google: "Google (Gemini)",
  claude: "Claude",
  ollama: "Ollama",
  openai: "OpenAI",
  openrouter: "OpenRouter",
};

export default function Chat() {
  const [messages, setMessages] = useState<{ role: "user" | "assistant"; content: string }[]>([]);
  const [input, setInput] = useState("");
  const [provider, setProvider] = useState("default");
  const [providers, setProviders] = useState<string[]>([]);
  const [defaultProvider, setDefaultProvider] = useState<string>("groq");
  const [models, setModels] = useState<Record<string, string>>({});
  const [defaults, setDefaults] = useState<Record<string, string>>({});
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const bottom = useRef<HTMLDivElement>(null);

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
    setConversationId(null);
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
      const r = await api.chat(text, provider, conversationId ?? undefined);
      setConversationId(r.conversation_id);
      setMessages((m) => [...m, { role: "assistant", content: r.reply }]);
    } catch (e) {
      setMessages((m) => [...m, { role: "assistant", content: "Error: " + (e as Error).message }]);
    } finally {
      setLoading(false);
    }
  };

  const effectiveProvider = provider === "default" ? defaultProvider : provider;
  const modelName = models[effectiveProvider] || defaults[effectiveProvider];

  return (
    <div className="chat-page">
      <h1 className="page-title">Chat with Asta</h1>
      <p className="page-description">
        Asta is your agent and can use any of the AIs you configured. It has access to your channels, conversation, and learned knowledge.
      </p>
      <div className="card" style={{ marginBottom: "0.75rem" }}>
        <div className="field-row" style={{ marginBottom: "0.5rem" }}>
          <div>
            <div className="label">Provider</div>
            <p className="help">Pick an AI for this chat. “Default” uses Settings.</p>
          </div>
          <div className="actions">
            <button type="button" className="btn btn-quiet" onClick={resetChat} disabled={loading || messages.length === 0}>
              New chat
            </button>
          </div>
        </div>
        <select className="select" value={provider} onChange={(e) => setProvider(e.target.value)}>
          <option value="default">Default ({PROVIDER_LABELS[defaultProvider] ?? defaultProvider})</option>
          {providers.map((p) => (
            <option key={p} value={p}>
              {PROVIDER_LABELS[p] ?? p}
            </option>
          ))}
        </select>
        {modelName ? (
          <p className="help" style={{ marginTop: "0.5rem" }}>
            Model: <code>{modelName}</code>
          </p>
        ) : null}
      </div>
      <div className="card chat-messages">
        {messages.length === 0 ? (
          <p className="muted">Send a message to start. Context from files, Drive, and learned knowledge may be used.</p>
        ) : null}

        <div className="chat-thread">
          {messages.map((m, i) => (
            <div key={i} className={"chat-msg " + m.role}>
              <div className="chat-msg-meta">{m.role === "user" ? "You" : "Asta"}</div>
              <div className="chat-bubble">{m.content}</div>
            </div>
          ))}
          {loading && (
            <div className="chat-msg assistant">
              <div className="chat-msg-meta">Asta</div>
              <div className="chat-bubble">…</div>
            </div>
          )}
        </div>
        <div ref={bottom} />
      </div>
      <div className="chat-input">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
              e.preventDefault();
              send();
            }
          }}
          placeholder="Message… (Ctrl/⌘ + Enter to send)"
          disabled={loading}
        />
        <button type="button" className="btn btn-primary" onClick={send} disabled={loading || !input.trim()}>
          Send
        </button>
      </div>
    </div>
  );
}
