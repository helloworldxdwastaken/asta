import { useState, useRef, useEffect } from "react";
import { api } from "../api/client";

export default function Chat() {
  const [messages, setMessages] = useState<{ role: string; content: string }[]>([]);
  const [input, setInput] = useState("");
  const [provider, setProvider] = useState("default");
  const [providers, setProviders] = useState<string[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.providers().then((r) => setProviders(r.providers));
  }, []);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

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

  return (
    <div className="chat-page">
      <h1 className="page-title">Chat with Asta</h1>
      <p className="page-description">
        Asta is your agent and can use any of the AIs you configured. It has access to your channels, conversation, and learned knowledge.
      </p>
      <div className="card" style={{ marginBottom: "0.5rem" }}>
        <label>
          Asta uses:{" "}
          <select value={provider} onChange={(e) => setProvider(e.target.value)}>
            <option value="default">Default (see Settings)</option>
            {providers.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="card chat-messages">
        {messages.length === 0 && (
          <p style={{ color: "var(--muted)" }}>Send a message to start. Context from files, Drive, and RAG is included.</p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={"chat-msg " + m.role}>
            <strong>{m.role === "user" ? "You" : "Asta"}:</strong> {m.content}
          </div>
        ))}
        {loading && <div className="chat-msg assistant">...</div>}
        <div ref={bottom} />
      </div>
      <div className="chat-input">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && send()}
          placeholder="Message..."
          disabled={loading}
        />
        <button type="button" onClick={send} disabled={loading || !input.trim()}>
          Send
        </button>
      </div>
    </div>
  );
}
