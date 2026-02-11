import { useEffect, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import type { Status } from "../api/client";
import { api } from "../api/client";

type NotificationItem = { id: number; message: string; run_at: string; status: string; channel: string; created_at: string };

export default function Dashboard() {
  const [status, setStatus] = useState<Status | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [_defaultAi, setDefaultAi] = useState<string | null>(null);

  const refresh = useCallback(() => {
    setError(null);
    api
      .status()
      .then((s) => { setStatus(s); setError(null); })
      .catch(() => setError("Cannot reach Asta API. Is the backend running on port 8010?"));
    api.getNotifications(50).then((r) => setNotifications(r.notifications || [])).catch(() => setNotifications([]));
    api.getDefaultAi().then((r) => setDefaultAi(r.provider)).catch(() => setDefaultAi(null));
  }, []);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 5000);
    return () => clearInterval(t);
  }, [refresh]);

  const handleDeleteNotification = async (id: number) => {
    if (!confirm("Delete this reminder?")) return;
    try {
      await api.deleteNotification(id);
      setNotifications((prev) => prev.filter((n) => n.id !== id));
    } catch (e) {
      alert("Failed to delete: " + e);
    }
  };

  const apis = status?.apis ?? {};
  const integrations = status?.integrations ?? {};
  const skills = status?.skills ?? [];
  const connected = !error && status;

  const pendingReminders = notifications.filter(n => n.status === 'pending');
  const pastReminders = notifications.filter(n => n.status !== 'pending');

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
            <h2>Backend Status</h2>
            {connected && <span className="backend-badge status-ok">Connected</span>}
            {error && <span className="backend-badge status-pending">Disconnected</span>}
          </div>
          {error ? (
            <>
              <p className="card-backend-message">Frontend cannot reach the API. Start the backend:</p>
              <code className="card-backend-code">cd backend && uvicorn app.main:app --port 8010</code>
              <button type="button" onClick={refresh} className="btn btn-secondary" style={{ marginTop: "0.75rem" }}>Retry</button>
            </>
          ) : status ? (
            <p className="card-backend-message">Asta {status.app} v{status.version} is running.</p>
          ) : (
            <p className="muted">Checking…</p>
          )}
        </div>
      </section>

      {status && (
        <>
          {/* ─── REMINDERS SECTION ─── */}
          <section className="dashboard-section">
            <h2 className="dashboard-section-title">Reminders</h2>
            <div className="dashboard-grid">

              {/* UPCOMING */}
              <div className="card">
                <h2>Upcoming</h2>
                {pendingReminders.length === 0 ? (
                  <p className="muted">No upcoming reminders.</p>
                ) : (
                  <ul className="reminders-list">
                    {pendingReminders.map((n) => (
                      <li key={n.id} className="reminder-item">
                        <div className="reminder-info">
                          <span className="reminder-time">
                            {new Date(n.run_at).toLocaleString(undefined, { weekday: 'short', hour: 'numeric', minute: '2-digit' })}
                          </span>
                          <span className="reminder-msg">{n.message}</span>
                        </div>
                        <button
                          className="btn-quiet btn-sm"
                          onClick={() => handleDeleteNotification(n.id)}
                          title="Delete reminder"
                        >
                          ✕
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              {/* HISTORY */}
              <div className="card">
                <h2>History</h2>
                {pastReminders.length === 0 ? (
                  <p className="muted">No past reminders.</p>
                ) : (
                  <ul className="reminders-list">
                    {pastReminders.slice(0, 5).map((n) => (
                      <li key={n.id} className="reminder-item opacity-50">
                        <div className="reminder-info">
                          <span className="reminder-status">✓</span>
                          <span className="reminder-msg">{n.message}</span>
                        </div>
                        <span className="reminder-time-sm">
                          {new Date(n.run_at).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
                {pastReminders.length > 5 && <p className="muted" style={{ fontSize: "0.8rem", marginTop: "0.5rem" }}>+ {pastReminders.length - 5} more</p>}
              </div>

            </div>
          </section>

          <section className="dashboard-section">
            <h2 className="dashboard-section-title">System Status</h2>
            <div className="dashboard-grid">
              <div className="card">
                <h2>API Providers</h2>
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
                      <span className={apis[key] ? "status-ok" : "status-pending"}>●</span>
                      <span className={apis[key] ? "" : "muted"}>{label}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="card">
                <h2>Channels</h2>
                <div className="status-grid">
                  <div className="status-item">
                    <span className={integrations.telegram ? "status-ok" : "status-pending"}>●</span>
                    <span>Telegram</span>
                  </div>
                  <div className="status-item">
                    <span className={integrations.whatsapp ? "status-ok" : "status-pending"}>●</span>
                    <span>WhatsApp</span>
                  </div>
                </div>
              </div>
            </div>
          </section>

          <section className="dashboard-section">
            <div className="card">
              <div className="card-skills-header">
                <h2>Active Skills</h2>
                <Link to="/skills" className="btn btn-link">Manage →</Link>
              </div>
              <div className="skills-chips">
                {skills.filter(s => s.enabled).map((s) => (
                  <span key={s.id} className="skill-chip skill-chip-on">{s.name}</span>
                ))}
                {skills.every(s => !s.enabled) && <span className="muted">No skills enabled.</span>}
              </div>
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
