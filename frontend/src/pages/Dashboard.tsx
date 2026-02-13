import { useEffect, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import type { Status } from "../api/client";
import { api } from "../api/client";

type NotificationItem = { id: number; message: string; run_at: string; status: string; channel: string; created_at: string };

const PROVIDER_LOGOS: Record<string, { url: string; initial: string }> = {
  groq: { url: "https://groq.com/favicon.ico", initial: "G" },
  gemini: { url: "https://www.google.com/favicon.ico", initial: "G" },
  google: { url: "https://www.google.com/favicon.ico", initial: "G" },
  claude: { url: "https://anthropic.com/favicon.ico", initial: "C" },
  openai: { url: "https://openai.com/favicon.ico", initial: "O" },
  openrouter: { url: "https://openrouter.ai/favicon.ico", initial: "R" },
  ollama: { url: "https://ollama.com/favicon.ico", initial: "O" },
};

function ProviderLogo({ providerKey, size = 32 }: { providerKey: string; size?: number }) {
  const [fallback, setFallback] = useState(false);
  const info = PROVIDER_LOGOS[providerKey] ?? { url: "", initial: providerKey.slice(0, 1).toUpperCase() };
  if (fallback || !info.url) {
    return (
      <div
        className="provider-logo-fallback"
        style={{
          width: size,
          height: size,
          borderRadius: 10,
          background: "var(--accent-soft, rgba(99, 102, 241, 0.15))",
          color: "var(--accent, #6366f1)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontWeight: 700,
          fontSize: size * 0.5,
          flexShrink: 0,
        }}
      >
        {info.initial}
      </div>
    );
  }
  return (
    <img
      src={info.url}
      alt=""
      width={size}
      height={size}
      className="provider-logo-img"
      style={{ borderRadius: 10, objectFit: "contain", background: "var(--bg-main)", flexShrink: 0 }}
      onError={() => setFallback(true)}
    />
  );
}

export default function Dashboard() {
  const [status, setStatus] = useState<Status | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [_defaultAi, setDefaultAi] = useState<string | null>(null);
  const [serverStatus, setServerStatus] = useState<any>(null);
  const [models, setModels] = useState<Record<string, string>>({});
  const [defaults, setDefaults] = useState<Record<string, string>>({});
  const [availableModels, setAvailableModels] = useState<{ ollama: string[] }>({ ollama: [] });
  const [cronCount, setCronCount] = useState(0);
  const [updateInfo, setUpdateInfo] = useState<{ available: boolean; local: string; remote: string } | null>(null);
  const [isUpdating, setIsUpdating] = useState(false);

  const refresh = useCallback(() => {
    setError(null);
    api
      .status()
      .then((s) => { setStatus(s); setError(null); })
      .catch(() => setError("Cannot reach Asta API. Is the backend running on port 8010?"));
    api.getNotifications(50).then((r) => setNotifications(r.notifications || [])).catch(() => setNotifications([]));
    api.getDefaultAi().then((r) => setDefaultAi(r.provider)).catch(() => setDefaultAi(null));
    api.getServerStatus().then(r => setServerStatus(r)).catch(() => setServerStatus(null));
    api.getModels().then((r) => { setModels(r.models); setDefaults(r.defaults); }).catch(() => { });
    api.getAvailableModels().then(setAvailableModels).catch(() => setAvailableModels({ ollama: [] }));
    api.getCronJobs().then((r) => setCronCount((r.cron_jobs || []).length)).catch(() => setCronCount(0));
    api.checkUpdate().then(r => setUpdateInfo({ available: r.update_available, local: r.local, remote: r.remote })).catch(() => { });
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

  const handleUpdate = async () => {
    if (!confirm("Are you sure you want to update Asta to the latest version? The system will restart.")) return;
    setIsUpdating(true);
    try {
      await api.triggerUpdate();
      // Poll for health
      let attempts = 0;
      const interval = setInterval(async () => {
        attempts++;
        try {
          const res = await api.health();
          if (res.status === 'ok') {
            clearInterval(interval);
            window.location.reload();
          }
        } catch (e) {
          if (attempts > 30) { // 30s timeout
            clearInterval(interval);
            setIsUpdating(false);
            alert("Update timed out or failed to restart correctly.");
          }
        }
      }, 2000);
    } catch (e) {
      setIsUpdating(false);
      alert("Failed to trigger update: " + e);
    }
  };

  const apis = status?.apis ?? {};
  const integrations = status?.integrations ?? {};
  const skills = status?.skills ?? [];
  const activeSkillsCount = skills.filter(s => s.enabled && s.available).length;
  const connected = !error && status;
  const pendingReminders = notifications.filter(n => n.status === 'pending');

  return (
    <div className="dashboard-container">
      {/* ─── HEADER ─── */}
      <header className="dashboard-header">
        <div>
          <h1 className="title">Asta Dashboard</h1>
          <p className="subtitle">System Overview & Diagnostics</p>
        </div>
        <div className={`system-status-badge ${connected ? 'ok' : 'error'}`}>
          <span className="dot"></span>
          {connected ? `System Online v${status?.version}` : 'System Offline'}
          {updateInfo?.available && <span className="update-badge">Update Available</span>}
        </div>
      </header>

      {error ? (
        <div className="error-banner">
          <h3>⚠️ Connection Lost</h3>
          <p>Cannot reach the Asta backend. Ensure the server is running on port 8010.</p>
          <code>cd backend && uvicorn app.main:app --port 8010</code>
          <button onClick={refresh} className="btn btn-secondary retry-btn">Retry Connection</button>
        </div>
      ) : (
        <div className="bento-grid">

          {/* ─── 1. THE BRAIN (AI) ─── */}
          <div className="bento-card brain-section">
            <div className="card-header">
              <div className="icon">🧠</div>
              <div>
                <h2>The Brain</h2>
                <p className="desc">Active AI Models & Intelligence Providers</p>
              </div>
            </div>
            <div className="status-list">
              {[
                { key: "groq", label: "Groq" },
                { key: "gemini", label: "Gemini" },
                { key: "claude", label: "Claude" },
                { key: "openai", label: "OpenAI" },
                { key: "openrouter", label: "OpenRouter" },
                { key: "ollama", label: "Ollama" },
              ]
                .filter(({ key }) => apis[key])
                .map(({ key, label }) => {
                  const configured = models[key] || defaults[key] || "Default";
                  const ollamaList = key === "ollama" ? (availableModels.ollama || []) : [];
                  const configuredInList = key === "ollama" && ollamaList.length > 0 &&
                    ollamaList.some((m: string) => m === configured || m.startsWith(configured + ":"));
                  const modelName = key === "ollama" && ollamaList.length > 0 && !configuredInList
                    ? ollamaList[0]
                    : configured;
                  return (
                    <div key={key} className="status-row active">
                      <div className="status-row-content">
                        <span className="label">{label}</span>
                        <span className="model-name">{modelName}</span>
                        {ollamaList.length > 1 && (
                          <span className="model-list">{ollamaList.join(", ")}</span>
                        )}
                      </div>
                      <span className="state">Active</span>
                    </div>
                  );
                })}
              {Object.keys(apis).every(k => !apis[k]) && (
                <div className="empty-state">
                  No AI providers connected. <Link to="/settings" className="dashboard-inline-link">Add API keys in Settings</Link>.
                </div>
              )}
            </div>
          </div>

          {/* ─── 2. THE BODY (Server) ─── */}
          <div className="bento-card body-section">
            <div className="card-header" style={{ alignItems: 'center' }}>
              <div className="icon">🫀</div>
              <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                <h2 style={{ marginBottom: '2px' }}>The Body</h2>
                <p className="desc" style={{ margin: 0 }}>Server Health & Vital Signs</p>
              </div>
            </div>
            {serverStatus?.ok ? (
              <div className="vitals-grid">
                <div className="vital-item">
                  <span className="vital-label">CPU</span>
                  <div className="progress-bar">
                    <div className="fill" style={{ width: `${Math.min(100, serverStatus.cpu_percent)}%` }}></div>
                  </div>
                  <div className="vital-stats">
                    <span className="vital-value">{serverStatus.cpu_percent}%</span>
                    <span className="vital-sub">
                      {[serverStatus.cpu_model, serverStatus.cpu_count ? `${serverStatus.cpu_count} cores` : null].filter(Boolean).join(" · ") || "—"}
                    </span>
                  </div>
                </div>
                <div className="vital-item">
                  <span className="vital-label">RAM Usage</span>
                  <div className="progress-bar">
                    <div className="fill" style={{ width: `${serverStatus.ram.percent}%` }}></div>
                  </div>
                  <div className="vital-stats">
                    <span className="vital-value">{serverStatus.ram.percent}%</span>
                    <span className="vital-sub">{serverStatus.ram.used_gb} / {serverStatus.ram.total_gb} GB</span>
                  </div>
                </div>
                <div className="vital-item">
                  <span className="vital-label">Disk Space</span>
                  <div className="progress-bar">
                    <div className="fill" style={{ width: `${serverStatus.disk.percent}%` }}></div>
                  </div>
                  <div className="vital-stats">
                    <span className="vital-value">{serverStatus.disk.percent}%</span>
                    <span className="vital-sub">{serverStatus.disk.used_gb} / {serverStatus.disk.total_gb} GB</span>
                  </div>
                </div>
                <div className="uptime-box">
                  <small>System Uptime</small>
                  <strong>{serverStatus.uptime_str}</strong>
                </div>
                {updateInfo?.available && (
                  <div className="update-prompt">
                    <p>New version ready ({updateInfo.remote})</p>
                    <button onClick={handleUpdate} className="btn btn-primary btn-sm">Update Asta</button>
                  </div>
                )}
              </div>
            ) : (
              <div className="loading-state">Checking Vitals...</div>
            )}
          </div>

          {/* ─── 2b. THE EYES (Vision) — next to Brain & Body ─── */}
          <div className="bento-card vision-section">
            <div className="card-header">
              <div className="icon">👀</div>
              <div>
                <h2>The Eyes</h2>
                <p className="desc">Visual Intelligence</p>
              </div>
            </div>
            <div className="vision-status">
              <div className="model-badge">
                <span className="model-label">Multimodal VL</span>
                <span className="model-name">{apis.openrouter ? "Nemotron-Nano 12B" : "—"}</span>
              </div>
              {apis.openrouter ? (
                <>
                  <div className="vision-active">
                    <div className="vision-dot"></div>
                    <span>Vision Ready</span>
                  </div>
                  <p className="vision-info">
                    Detects images on <strong>Telegram</strong> and uses a vision model for analysis.
                  </p>
                  <div style={{ marginTop: 'auto', textAlign: 'center', fontSize: '0.75rem', opacity: 0.6 }}>
                    nvidia/nemotron-nano-12b-v2-vl:free
                  </div>
                </>
              ) : (
                <>
                  <div className="vision-inactive" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
                    <span style={{ opacity: 0.7 }}>Vision not configured</span>
                  </div>
                  <p className="vision-info">
                    Add an <strong>OpenRouter</strong> API key in Settings to enable image support on Telegram.
                  </p>
                </>
              )}
            </div>
          </div>

          {/* ─── 3. CONNECTORS (Channels) ─── */}
          <div className="bento-card connectors-section">
            <div className="card-header">
              <div className="icon">🔌</div>
              <div>
                <h2>Channels</h2>
                <p className="desc">External Communication Interfaces</p>
              </div>
            </div>
            <div className="connectors-list">
              <div className={`connector-card ${integrations.whatsapp ? 'on' : 'off'}`}>
                <div className="connector-icon whatsapp">
                  <svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413Z" /></svg>
                </div>
                <div className="connector-info">
                  <strong>WhatsApp</strong>
                  <span>{integrations.whatsapp ? 'Connected' : 'Disconnected'}</span>
                </div>
              </div>
              <div className={`connector-card ${integrations.telegram ? 'on' : 'off'}`}>
                <div className="connector-icon telegram">
                  <svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor"><path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z" /></svg>
                </div>
                <div className="connector-info">
                  <strong>Telegram</strong>
                  <span>{integrations.telegram ? 'Connected' : 'Disconnected'}</span>
                </div>
              </div>
            </div>
            <Link to="/channels" className="setup-link">Configure Channels →</Link>
          </div>

          {/* ─── 3b. TASKS (Reminders) ─── */}
          <div className="bento-card memory-section">
            <div className="card-header">
              <div className="icon">📝</div>
              <div>
                <h2>Tasks</h2>
                <p className="desc">Pending reminders</p>
              </div>
            </div>
            <div className="memory-list">
              {pendingReminders.length === 0 ? (
                <div className="empty-state">No active reminders.</div>
              ) : (
                <ul>
                  {pendingReminders.slice(0, 5).map(n => (
                    <li key={n.id}>
                      <span className="time">{new Date(n.run_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                      <span className="msg">{n.message}</span>
                      <button onClick={() => handleDeleteNotification(n.id)} className="del-btn">×</button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          {/* ─── 3c. CRON ─── */}
          <div className="bento-card cron-section">
            <div className="card-header">
              <div className="icon">⏰</div>
              <div>
                <h2>Schedule</h2>
                <p className="desc">Recurring jobs</p>
              </div>
            </div>
            <div className="stat-and-link">
              <div className="stat-value">{cronCount}</div>
              <div className="stat-label">{cronCount === 1 ? "scheduled job" : "scheduled jobs"}</div>
              <Link to="/cron" className="setup-link">Cron →</Link>
            </div>
          </div>

          {/* ─── 4. CAPABILITIES (Skills count) ─── */}
          <div className="bento-card skills-section">
            <div className="card-header">
              <div className="icon">⚡</div>
              <div>
                <h2>Capabilities</h2>
                <p className="desc">Active skills</p>
              </div>
            </div>
            <div className="stat-and-link">
              <div className="stat-value">{activeSkillsCount}</div>
              <div className="stat-label">{activeSkillsCount === 1 ? "active skill" : "active skills"}</div>
              <Link to="/skills" className="setup-link">Manage Skills →</Link>
            </div>
          </div>

        </div>
      )}

      {isUpdating && (
        <div className="update-overlay">
          <div className="update-modal">
            <div className="spinner"></div>
            <h2>System Restarting...</h2>
            <p>Asta is pulling the latest code and restarting all services to apply the update. This page will automatically refresh once the system is back online.</p>
          </div>
        </div>
      )}

      <style>{`
        .dashboard-container {
            width: 100%;
            max-width: 1600px;
            margin: 0 auto;
            padding: 0 2.5rem 4rem;
            box-sizing: border-box;
        }
        .dashboard-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 2.5rem;
            padding: 1.5rem 0;
            border-bottom: 1px solid var(--border);
        }
        .dashboard-header .title {
            font-size: 1.85rem;
            font-weight: 800;
            margin: 0;
            color: var(--text-main);
            letter-spacing: -0.03em;
        }
        .dashboard-header .subtitle {
            margin: 0;
            color: var(--muted);
            font-size: 0.95rem;
            margin-top: 0.2rem;
        }
        .system-status-badge {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.5rem 1rem;
            border-radius: 99px;
            font-weight: 500;
            font-size: 0.9rem;
            border: 1px solid transparent;
        }
        .system-status-badge.ok {
            background: rgba(var(--rgb-success), 0.1);
            color: var(--success);
            border-color: rgba(var(--rgb-success), 0.2);
        }
        .system-status-badge.error {
            background: rgba(var(--rgb-destroy), 0.1);
            color: var(--destroy);
            border-color: rgba(var(--rgb-destroy), 0.2);
        }
        .dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: currentColor;
            box-shadow: 0 0 8px currentColor;
        }
        .update-badge {
            margin-left: 0.5rem;
            background: var(--primary);
            color: #000000;
            font-size: 0.7rem;
            font-weight: 700;
            padding: 2px 6px;
            border-radius: 4px;
            animation: bounce 2s infinite;
        }
        @keyframes bounce {
            0%, 20%, 50%, 80%, 100% {transform: translateY(0);}
            40% {transform: translateY(-3px);}
            60% {transform: translateY(-2px);}
        }

        .error-banner {
            background: rgba(var(--rgb-destroy), 0.05);
            border: 1px solid var(--destroy);
            padding: 2rem;
            border-radius: 12px;
            text-align: center;
        }
        .retry-btn { margin-top: 1rem; }

        /* BENTO GRID — 4 cols, more space */
        .bento-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 2rem;
        }
        .bento-card {
            background: #ffffff;
            border: 1px solid var(--border);
            border-radius: 20px;
            padding: 2rem;
            display: flex;
            flex-direction: column;
            transition: transform 0.2s ease, box-shadow 0.25s ease, border-color 0.2s;
            box-shadow: 0 1px 3px rgba(0,0,0,0.06), 0 6px 16px -4px rgba(0,0,0,0.08);
        }
        .bento-card:hover {
            transform: translateY(-3px);
            box-shadow: 0 4px 6px -1px rgba(0,0,0,0.07), 0 12px 24px -8px rgba(0,0,0,0.12);
            border-color: var(--accent-dim, rgba(99, 102, 241, 0.25));
        }
        .card-header {
            display: flex;
            gap: 1.25rem;
            margin-bottom: 1.5rem;
            border-bottom: 1px solid var(--border);
            padding-bottom: 1.25rem;
        }
        .icon {
            font-size: 1.9rem;
            width: 56px;
            height: 56px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 16px;
            flex-shrink: 0;
        }
        .brain-section .icon { background: linear-gradient(135deg, rgba(99, 102, 241, 0.2), rgba(139, 92, 246, 0.15)); border: 1px solid rgba(99, 102, 241, 0.2); }
        .body-section .icon { background: linear-gradient(135deg, rgba(34, 197, 94, 0.2), rgba(16, 185, 129, 0.15)); border: 1px solid rgba(34, 197, 94, 0.2); }
        .connectors-section .icon { background: linear-gradient(135deg, rgba(59, 130, 246, 0.2), rgba(14, 165, 233, 0.15)); border: 1px solid rgba(59, 130, 246, 0.2); }
        .memory-section .icon { background: linear-gradient(135deg, rgba(245, 158, 11, 0.2), rgba(234, 179, 8, 0.15)); border: 1px solid rgba(245, 158, 11, 0.25); }
        .skills-section .icon { background: linear-gradient(135deg, rgba(168, 85, 247, 0.2), rgba(139, 92, 246, 0.15)); border: 1px solid rgba(168, 85, 247, 0.2); }
        .vision-section .icon { background: linear-gradient(135deg, rgba(236, 72, 153, 0.2), rgba(244, 114, 182, 0.15)); border: 1px solid rgba(236, 72, 153, 0.2); }
        .card-header h2 { margin: 0; font-size: 1.2rem; font-weight: 700; letter-spacing: -0.02em; }
        .card-header .desc { margin: 0; font-size: 0.85rem; color: var(--muted); margin-top: 3px; }

        /* Row 1: Brain | Body | Eyes. Row 2: Channels | Tasks | Cron | Skills */
        .brain-section { grid-column: span 1; }
        .body-section { grid-column: span 2; }
        .vision-section { grid-column: span 1; }
        .connectors-section { grid-column: span 1; }
        .memory-section { grid-column: span 1; }
        .cron-section { grid-column: span 1; }
        .skills-section { grid-column: span 1; }

        .cron-section .icon { background: linear-gradient(135deg, rgba(20, 184, 166, 0.2), rgba(6, 182, 212, 0.15)); border: 1px solid rgba(20, 184, 166, 0.25); }
        .stat-and-link {
            display: flex;
            flex-direction: column;
            align-items: flex-start;
            gap: 0.25rem;
            margin-top: 0.25rem;
        }
        .stat-value { font-size: 2rem; font-weight: 800; color: var(--text); letter-spacing: -0.03em; line-height: 1; }
        .stat-label { font-size: 0.85rem; color: var(--muted); }
        .stat-and-link .setup-link { margin-top: 0.5rem; }

        /* Responsive */
        @media (max-width: 1100px) {
            .bento-grid { grid-template-columns: 1fr 1fr; gap: 1.5rem; }
            .brain-section, .body-section, .vision-section, .connectors-section, .memory-section, .cron-section, .skills-section { grid-column: span 1; }
            .body-section { grid-column: span 2; }
        }
        @media (max-width: 700px) {
            .dashboard-container { padding: 0 1rem 3rem; }
            .bento-grid { grid-template-columns: 1fr; gap: 1.25rem; }
            .body-section { grid-column: span 1; }
            .bento-card { padding: 1.5rem; }
        }

        /* Brain Lists */
        .status-list { display: flex; flex-direction: column; gap: 0.75rem; }
        .status-list .empty-state { text-align: center; padding: 1.5rem; color: var(--muted); font-size: 0.9rem; font-style: italic; }
        .status-row {
            display: flex;
            align-items: center;
            gap: 0.85rem;
            padding: 0.85rem 1.15rem;
            border-radius: 12px;
            background: var(--bg-main);
            transition: all 0.2s;
        }
        .status-row.active {
            background: linear-gradient(135deg, rgba(var(--rgb-success), 0.12), rgba(var(--rgb-success), 0.06));
            border: 1px solid rgba(var(--rgb-success), 0.25);
        }
        .status-row-content { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 1px; }
        .status-row .label { font-weight: 600; color: var(--text); font-size: 0.95rem; }
        .status-row.active .label { color: var(--success-dark, #15803d); }
        .status-row .model-name { font-size: 0.75rem; opacity: 0.85; color: var(--muted); }
        .status-row .model-list { font-size: 0.75rem; opacity: 0.8; color: var(--muted); display: block; margin-top: 0.2rem; }
        .status-row .state { font-size: 0.7rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; color: var(--success); }
        .provider-logo-img { border: 1px solid var(--border); }

        /* Body Vitals */
        .vitals-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 1.25rem;
            align-items: center;
        }
        .vital-item {
            text-align: center;
            background: var(--bg-main);
            padding: 1.25rem 1rem;
            border-radius: 14px;
            border: 1px solid transparent;
        }
        .vital-label { font-size: 0.75rem; color: var(--muted); display: block; margin-bottom: 0.5rem; }
        .vital-stats { display: flex; flex-direction: column; align-items: center; }
        .vital-value { font-size: 1.2rem; font-weight: 700; color: var(--text-main); line-height: 1.2; }
        .vital-sub { font-size: 0.75rem; color: var(--muted); margin-top: 0.2rem; }
        .progress-bar {
            height: 4px;
            background: var(--border);
            border-radius: 2px;
            margin: 0.5rem 0;
            overflow: hidden;
        }
        .progress-bar .fill { height: 100%; background: var(--primary); }
        .uptime-box {
            grid-column: span 3;
            text-align: center;
            background: var(--bg-main);
            padding: 0.75rem;
            border-radius: 8px;
            margin-top: 1rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0 1.5rem;
            height: 40px;
        }
        .update-prompt {
            grid-column: span 3;
            background: rgba(var(--rgb-primary), 0.1);
            border: 1px solid var(--primary);
            padding: 0.75rem 1.5rem;
            border-radius: 12px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-top: 1rem;
        }
        .update-prompt p { margin: 0; font-weight: 600; font-size: 0.9rem; color: var(--primary); }
        .btn-sm { padding: 4px 12px; font-size: 0.8rem; }

        /* Connectors */
        .connectors-list { display: grid; grid-template-columns: 1fr 1fr; gap: 1.25rem; margin-bottom: 1.25rem; }
        .connector-card {
            display: flex;
            align-items: center;
            gap: 1rem;
            padding: 1rem 1.25rem;
            border-radius: 14px;
            background: var(--bg-main);
            border: 1px solid var(--border);
            transition: border-color 0.2s, background 0.2s;
        }
        .connector-card.on { border-color: rgba(var(--rgb-success), 0.35); background: linear-gradient(135deg, rgba(var(--rgb-success), 0.08), rgba(var(--rgb-success), 0.03)); }
        .connector-icon {
            width: 32px;
            height: 32px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            border-radius: 6px;
            font-weight: bold;
            font-size: 0.8rem;
        }
        .connector-icon.whatsapp { background: #25D366; }
        .connector-icon.telegram { background: #229ED9; }
        .connector-info { display: flex; flex-direction: column; font-size: 0.8rem; }
        .connector-info span { font-size: 0.7rem; opacity: 0.7; }

        /* Memory */
        .memory-list ul { list-style: none; padding: 0; margin: 0; }
        .memory-list li {
            display: flex;
            gap: 0.85rem;
            padding: 0.85rem 0;
            border-bottom: 1px solid var(--border);
            font-size: 0.9rem;
        }
        .memory-list .time { color: var(--muted); font-mono: monospace; font-size: 0.8rem; }
        .memory-list .msg { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .del-btn { background: none; border: none; color: var(--muted); cursor: pointer; }
        .del-btn:hover { color: var(--destroy); }
        .empty-state { text-align: center; padding: 2rem; color: var(--muted); font-size: 0.9rem; font-style: italic; }

        .setup-link {
            display: block;
            text-align: right;
            font-size: 0.85rem;
            color: var(--primary);
            text-decoration: none;
            margin-top: auto;
        }
        .setup-link:hover { text-decoration: underline; }
        .dashboard-inline-link { color: var(--primary); font-weight: 500; text-decoration: none; }
        .dashboard-inline-link:hover { text-decoration: underline; }

        /* Vision Section specific */
        .vision-section {
            background: linear-gradient(160deg, #ffffff 0%, #faf5ff 35%, #f8fafc 100%);
            border-color: rgba(236, 72, 153, 0.12);
        }
        .vision-status {
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }
        .vision-section .model-badge {
            background: rgba(255,255,255,0.8);
            padding: 0.85rem 1rem;
            border-radius: 14px;
            display: flex;
            flex-direction: column;
            border: 1px solid rgba(236, 72, 153, 0.15);
            box-shadow: 0 1px 2px rgba(0,0,0,0.04);
        }
        .model-label { font-size: 0.7rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.06em; }
        .vision-section .model-name { font-weight: 700; color: var(--primary); font-size: 1rem; }
        .vision-active {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            color: var(--success);
            font-weight: 600;
            font-size: 0.9rem;
        }
        .vision-dot {
            width: 10px;
            height: 10px;
            background: var(--success);
            border-radius: 50%;
            box-shadow: 0 0 10px var(--success);
            animation: pulse-vision 2s infinite;
        }
        @keyframes pulse-vision {
            0% { transform: scale(1); opacity: 1; }
            50% { transform: scale(1.2); opacity: 0.7; }
            100% { transform: scale(1); opacity: 1; }
        }
        .vision-info {
            font-size: 0.85rem;
            color: var(--text);
            line-height: 1.45;
            margin: 0;
            padding: 0.65rem 0.85rem;
            background: rgba(236, 72, 153, 0.04);
            border-radius: 10px;
            border: 1px solid rgba(236, 72, 153, 0.08);
        }

        .update-overlay {
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0,0,0,0.8);
            z-index: 9999;
            display: flex;
            align-items: center;
            justify-content: center;
            backdrop-filter: blur(4px);
        }
        .update-modal {
            background: white;
            padding: 3rem;
            border-radius: 20px;
            text-align: center;
            max-width: 400px;
        }
        .update-modal h2 { margin-top: 1.5rem; }
        .spinner {
            width: 50px;
            height: 50px;
            border: 5px solid var(--bg-main);
            border-top: 5px solid var(--primary);
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

      `}</style>
    </div>
  );
}
