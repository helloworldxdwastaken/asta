import { useEffect, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import type { Status } from "../api/client";
import { api } from "../api/client";

type NotificationItem = { id: number; message: string; run_at: string; status: string; channel: string; created_at: string };

export default function Dashboard() {
  const [status, setStatus] = useState<Status | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [defaultAi, setDefaultAi] = useState<string | null>(null);

  const refresh = useCallback(() => {
    setError(null);
    api
      .status()
      .then((s) => { setStatus(s); setError(null); })
      .catch(() => setError("Cannot reach Asta API. Is the backend running on port 8010?"));
  }, []);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 5000);
    return () => clearInterval(t);
  }, [refresh]);

  useEffect(() => {
    if (error) return;
    api.getNotifications(10).then((r) => setNotifications(r.notifications || [])).catch(() => setNotifications([]));
  }, [error, status]);

  useEffect(() => {
    if (error) return;
    api.getDefaultAi().then((r) => setDefaultAi(r.provider)).catch(() => setDefaultAi(null));
  }, [error, status]);

  const apis = status?.apis ?? {};
  const integrations = status?.integrations ?? {};
  const skills = status?.skills ?? [];
  const connected = !error && status;

  return (
    <div className="dashboard">
      <header className="dashboard-hero">
        <h1 className="dashboard-title">Control panel</h1>
        <p className="dashboard-tagline">
          One place for AI, WhatsApp, Telegram, files, Drive, and learning.
        </p>
      </header>

      <section className="dashboard-section">
        <div className={`card card-backend ${error ? "card-error" : connected ? "card-success" : ""}`}>
          <div className="card-backend-header">
            <h2>Backend</h2>
            {connected && (
              <span className="backend-badge status-ok">Connected</span>
            )}
            {error && (
              <span className="backend-badge status-pending">Disconnected</span>
            )}
          </div>
          {error ? (
            <>
              <p className="card-backend-message">
                Frontend cannot reach the API. Start the backend:
              </p>
              <code className="card-backend-code">
                cd backend && uvicorn app.main:app --port 8010
              </code>
              <button type="button" onClick={refresh} className="btn btn-secondary" style={{ marginTop: "0.75rem" }}>
                Retry
              </button>
            </>
          ) : status ? (
            <p className="card-backend-message">
              Asta {status.app} v{status.version}. Frontend and backend are talking.
            </p>
          ) : (
            <p className="muted">Checking…</p>
          )}
          <p className="card-backend-hint muted">
            If the browser shows a sign-in prompt, click Cancel — only run the Asta backend on your chosen API port (default 8010).
          </p>
        </div>
      </section>

      {status && (
        <>
          <section className="dashboard-section">
            <h2 className="dashboard-section-title">Status</h2>
            <div className="dashboard-grid">
              <div className="card">
                <h2>API providers</h2>
                <p className="muted" style={{ marginBottom: "0.75rem", fontSize: "0.9rem" }}>
                  AI providers with keys set
                </p>
                <div className="status-grid">
                  {[
                    { key: "groq", label: "Groq" },
                    { key: "gemini", label: "Gemini" },
                    { key: "claude", label: "Claude" },
                    { key: "openai", label: "OpenAI" },
                    { key: "openrouter", label: "OpenRouter" },
                    { key: "ollama", label: "Ollama" },
                  ].map(({ key, label }) => (
                    <div key={key} className="status-item">
                      <span className={apis[key] ? "status-ok" : "status-pending"}>
                        {apis[key] ? "On" : "Off"}
                      </span>
                      <span className="muted">— {label}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="card">
                <h2>Default AI</h2>
                <p className="muted" style={{ marginBottom: "0.75rem", fontSize: "0.9rem" }}>
                  {defaultAi ? (
                    <>Chat uses <strong>{defaultAi === "openrouter" ? "OpenRouter" : defaultAi === "openai" ? "OpenAI" : defaultAi === "groq" ? "Groq" : defaultAi}</strong>. Change in <Link to="/settings" className="link">Settings</Link>.</>
                  ) : (
                    "Set in Settings."
                  )}
                </p>
              </div>

              <div className="card">
                <h2>Channels</h2>
                <p className="muted" style={{ marginBottom: "0.75rem", fontSize: "0.9rem" }}>
                  Telegram & WhatsApp
                </p>
                <div className="status-grid">
                  <div className="status-item">
                    <span className={integrations.telegram ? "status-ok" : "status-pending"}>
                      {integrations.telegram ? "On" : "Off"}
                    </span>
                    <span className="muted">— Telegram</span>
                  </div>
                  <div className="status-item">
                    <span className={integrations.whatsapp ? "status-ok" : "status-pending"}>
                      {integrations.whatsapp ? "On" : "Off"}
                    </span>
                    <span className="muted">— WhatsApp</span>
                  </div>
                </div>
              </div>
            </div>
          </section>

          <section className="dashboard-section">
            <div className="card">
              <div className="card-skills-header">
                <h2>Skills</h2>
                <Link to="/skills" className="btn btn-link">
                  Manage in Skills →
                </Link>
              </div>
              <p className="muted" style={{ marginBottom: "1rem", fontSize: "0.9rem" }}>
                What the AI can use. Turn skills on or off in the Skills tab.
              </p>
              <div className="skills-chips">
                {skills.map((s) => (
                  <span
                    key={s.id}
                    className={`skill-chip ${s.enabled ? "skill-chip-on" : "skill-chip-off"} ${!s.available ? "skill-chip-unavailable" : ""}`}
                    title={!s.available ? "Not configured" : undefined}
                  >
                    {s.name}
                    {!s.available && " · —"}
                  </span>
                ))}
              </div>
            </div>
          </section>

          {notifications.length > 0 && (
            <section className="dashboard-section">
              <div className="card">
                <h2>Recent reminders</h2>
                <p className="muted" style={{ marginBottom: "0.75rem", fontSize: "0.9rem" }}>
                  Alarms and reminders you set. When the time comes, you get the message here (and on Telegram/WhatsApp if connected).
                </p>
                <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
                  {notifications.slice(0, 10).map((n) => (
                    <li key={n.id} style={{ padding: "0.35rem 0", borderBottom: "1px solid var(--border)", fontSize: "0.9rem" }}>
                      <span className={n.status === "sent" ? "status-ok" : "status-pending"}>{n.status === "sent" ? "✓" : "⏳"}</span>{" "}
                      {n.message} — {new Date(n.run_at).toLocaleString(undefined, { dateStyle: "short", timeStyle: "short" })}
                    </li>
                  ))}
                </ul>
              </div>
            </section>
          )}

          <section className="dashboard-section">
            <div className="card card-about">
              <h2>About Asta</h2>
              <p>
                Asta is your agent. It uses the AI you set (Groq, OpenRouter, OpenAI, etc.) for Chat, WhatsApp, and Telegram. Set API keys and default AI in <Link to="/settings" className="link">Settings</Link>; enable or disable skills in the <Link to="/skills" className="link">Skills</Link> tab.
              </p>
            </div>
          </section>
        </>
      )}

      {!status && !error && (
        <div className="card">
          <p className="muted">Loading status…</p>
        </div>
      )}
    </div>
  );
}
