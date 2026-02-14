import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import type { CronJob } from "../api/client";
import { api } from "../api/client";

const PROVIDER_LABELS: Record<string, string> = {
  groq: "Groq",
  google: "Google (Gemini)",
  claude: "Claude",
  ollama: "Ollama",
  openai: "OpenAI",
  openrouter: "OpenRouter",
};

/** Logo URL or fallback initial for provider cards */
const PROVIDER_LOGOS: Record<string, { url: string; initial: string }> = {
  groq: { url: "https://groq.com/favicon.ico", initial: "G" },
  google: { url: "https://www.google.com/favicon.ico", initial: "G" },
  claude: { url: "https://anthropic.com/favicon.ico", initial: "C" },
  openai: { url: "https://openai.com/favicon.ico", initial: "O" },
  openrouter: { url: "https://openrouter.ai/favicon.ico", initial: "R" },
  giphy: { url: "https://giphy.com/favicon.ico", initial: "G" },
};

/** AI providers: single key each (except Google has two optional keys) */
const AI_PROVIDER_ENTRIES: { id: string; name: string; keys: { key: string; label: string }[]; logoKey: string; testKey?: string; getKeyUrl: string }[] = [
  { id: "groq", name: "Groq", keys: [{ key: "groq_api_key", label: "API key" }], logoKey: "groq", testKey: "groq_api_key", getKeyUrl: "https://console.groq.com/keys" },
  { id: "google", name: "Google (Gemini)", keys: [{ key: "gemini_api_key", label: "Gemini API key" }, { key: "google_ai_key", label: "Google AI key (alt)" }], logoKey: "google", getKeyUrl: "https://aistudio.google.com/apikey" },
  { id: "claude", name: "Anthropic (Claude)", keys: [{ key: "anthropic_api_key", label: "API key" }], logoKey: "claude", getKeyUrl: "https://console.anthropic.com/settings/keys" },
  { id: "openai", name: "OpenAI", keys: [{ key: "openai_api_key", label: "API key" }], logoKey: "openai", getKeyUrl: "https://platform.openai.com/api-keys" },
  { id: "openrouter", name: "OpenRouter", keys: [{ key: "openrouter_api_key", label: "API key" }], logoKey: "openrouter", getKeyUrl: "https://openrouter.ai/keys" },
];

/** Channel extras (Telegram is on Channels page) */
const OTHER_KEYS: { id: string; name: string; key: string; logoKey: string; getKeyUrl: string }[] = [
  { id: "giphy", name: "Giphy (GIF skill)", key: "giphy_api_key", logoKey: "giphy", getKeyUrl: "https://developers.giphy.com/dashboard/" },
];

function ProviderLogo({ logoKey, size = 40 }: { logoKey: string; size?: number }) {
  const [fallback, setFallback] = useState(false);
  const info = PROVIDER_LOGOS[logoKey] ?? { url: "", initial: "?" };
  if (fallback || !info.url) {
    return (
      <div
        style={{
          width: size,
          height: size,
          borderRadius: 10,
          background: "var(--accent-soft)",
          color: "var(--accent)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontWeight: 700,
          fontSize: size * 0.5,
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
      style={{ borderRadius: 10, objectFit: "contain", background: "var(--surface-hover)" }}
      onError={() => setFallback(true)}
    />
  );
}

function RestartBackendButton() {
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState<string | null>(null);
  const [isError, setIsError] = useState(false);
  const run = async () => {
    setLoading(true);
    setDone(null);
    setIsError(false);
    try {
      await api.restartBackend();
      setDone("Backend has stopped. Start it again in your terminal (e.g. cd backend && uvicorn app.main:app --port 8010) — the indicator above will turn green when it’s back.");
    } catch (e) {
      setIsError(true);
      setDone("Request failed: " + ((e as Error).message || String(e)).slice(0, 80) + " — If backend is running, you should see Restart requested in the terminal when it works.");
    } finally {
      setLoading(false);
    }
  };
  return (
    <div className="field">
      <div className="actions">
        <button type="button" onClick={run} disabled={loading} className="btn btn-danger">
          {loading ? "Stopping…" : "Stop backend"}
        </button>
      </div>
      {done && (
        <div className={isError ? "alert alert-error" : "alert"} style={{ marginTop: "0.75rem" }}>
          {done}
        </div>
      )}
      <p className="help">This sends a stop request to the backend process. Start it again in your terminal afterwards.</p>
    </div>
  );
}

function AutoUpdaterSettings({
  cronJobs,
  onSave,
  saving,
  setSaving,
  message,
  setMessage,
}: {
  cronJobs: CronJob[];
  onSave: () => void;
  saving: boolean;
  setSaving: (v: boolean) => void;
  message: string | null;
  setMessage: (v: string | null) => void;
}) {
  const job = cronJobs.find((j) => (j.name || "").trim() === "Daily Auto-Update");
  const [cronExpr, setCronExpr] = useState(job?.cron_expr ?? "0 4 * * *");
  const [tz, setTz] = useState(job?.tz ?? "");
  useEffect(() => {
    if (job) {
      setCronExpr(job.cron_expr ?? "0 4 * * *");
      setTz(job.tz ?? "");
    }
  }, [job?.id, job?.cron_expr, job?.tz]);

  if (!job) {
    return (
      <details>
        <summary>
          <span>Auto-updater</span>
          <span className="acc-meta">Daily Asta &amp; skills update</span>
        </summary>
        <div className="acc-body">
          <p className="help">
            The Daily Auto-Update cron is created automatically when the auto-updater skill is installed (<code>workspace/skills/auto-updater-100</code>). Restart the backend to create it, or manage cron jobs in the <Link to="/cron" className="link">Cron</Link> tab.
          </p>
        </div>
      </details>
    );
  }

  const handleSave = async () => {
    setSaving(true);
    setMessage(null);
    try {
      await api.updateCronJob(job.id, { cron_expr: cronExpr.trim() || undefined, tz: tz.trim() || undefined });
      setMessage("Auto-updater schedule saved.");
      onSave();
    } catch (e) {
      setMessage("Error: " + (e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <details>
      <summary>
        <span>Auto-updater</span>
        <span className="acc-meta">Daily Asta &amp; skills update</span>
      </summary>
      <div className="acc-body">
        <p className="help">
          Run a daily check for Asta and skill updates. The cron job sends a message to the AI at the scheduled time; the reply is delivered to you (web or channels).
        </p>
        <div className="field">
          <label className="label" htmlFor="auto-updater-cron">Schedule (5-field cron)</label>
          <input
            id="auto-updater-cron"
            type="text"
            value={cronExpr}
            onChange={(e) => setCronExpr(e.target.value)}
            placeholder="0 4 * * *"
            className="input"
            style={{ maxWidth: 220 }}
          />
          <p className="help">e.g. <code>0 4 * * *</code> = daily at 4:00 AM</p>
        </div>
        <div className="field">
          <label className="label" htmlFor="auto-updater-tz">Timezone (optional)</label>
          <input
            id="auto-updater-tz"
            type="text"
            value={tz}
            onChange={(e) => setTz(e.target.value)}
            placeholder="e.g. America/Los_Angeles"
            className="input"
            style={{ maxWidth: 280 }}
          />
        </div>
        <div className="actions">
          <button type="button" onClick={handleSave} disabled={saving} className="btn btn-primary">
            {saving ? "Saving…" : "Save schedule"}
          </button>
        </div>
        {message && (
          <div className={message.startsWith("Error") ? "alert alert-error" : "alert"} style={{ marginTop: "0.75rem" }}>
            {message}
          </div>
        )}
        <p className="help" style={{ marginTop: "0.5rem" }}>
          View or remove this job in the <Link to="/cron" className="link">Cron</Link> tab.
        </p>
      </div>
    </details>
  );
}

function TestGroqButton() {
  const [testing, setTesting] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const run = async () => {
    setTesting(true);
    setResult(null);
    try {
      const r = await api.testApiKey("groq");
      if (r.ok) {
        setResult("Key works.");
      } else {
        setResult(r.error || "Unknown error");
      }
    } catch (e) {
      setResult((e as Error).message || "Request failed");
    } finally {
      setTesting(false);
    }
  };
  return (
    <span className="actions">
      <button type="button" onClick={run} disabled={testing} className="btn btn-secondary">
        {testing ? "Testing…" : "Test"}
      </button>
      {result && <span className={result === "Key works." ? "status-ok" : "status-pending"}>{result}</span>}
    </span>
  );
}

// Provider id -> status key (backend status uses "gemini" for Google)
const PROVIDER_STATUS_KEYS: Record<string, string> = {
  groq: "groq",
  google: "gemini",
  claude: "claude",
  ollama: "ollama",
  openai: "openai",
  openrouter: "openrouter",
};

const DEFAULT_AI_LABELS: Record<string, string> = {
  groq: "Groq",
  google: "Google (Gemini)",
  claude: "Claude",
  ollama: "Ollama",
  openai: "OpenAI",
  openrouter: "OpenRouter",
};

function DefaultAiSelect() {
  const [provider, setProvider] = useState("");
  const [model, setModel] = useState("");
  const [defaults, setDefaults] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [savingModel, setSavingModel] = useState(false);
  const [connected, setConnected] = useState<Record<string, boolean>>({});
  useEffect(() => {
    Promise.all([api.getDefaultAi(), api.status(), api.getModels()]).then(([r, status, modelsResp]) => {
      setConnected(status.apis ?? {});
      setDefaults(modelsResp.defaults ?? {});
      setModel((modelsResp.models ?? {})[r.provider] ?? "");
      setLoading(false);
      setProvider(r.provider);
    });
  }, []);
  useEffect(() => {
    if (loading || !provider || Object.keys(connected).length === 0) return;
    const connectedIds = (["groq", "google", "claude", "ollama", "openai", "openrouter"] as const).filter(
      (id) => connected[PROVIDER_STATUS_KEYS[id]]
    );
    if (connectedIds.length > 0 && !connectedIds.includes(provider as typeof connectedIds[number])) {
      const fallback = connectedIds[0];
      setProvider(fallback);
      api.setDefaultAi(fallback).catch(() => { });
    }
  }, [loading, connected, provider]);
  useEffect(() => {
    if (!provider || loading) return;
    api.getModels().then((r) => {
      setModel(r.models[provider] ?? "");
      setDefaults(r.defaults ?? {});
    });
  }, [provider, loading]);
  const change = (p: string) => {
    setProvider(p);
    api.setDefaultAi(p).catch(() => setProvider(provider));
  };
  const saveModel = () => {
    if (!provider) return;
    setSavingModel(true);
    api.setModel(provider, model.trim()).finally(() => setSavingModel(false));
  };
  const connectedProviders = (["groq", "google", "claude", "ollama", "openai", "openrouter"] as const).filter(
    (id) => connected[PROVIDER_STATUS_KEYS[id]]
  );
  if (loading) return <p style={{ color: "var(--muted)" }}>Loading…</p>;
  if (connectedProviders.length === 0) {
    return (
      <p className="help">
        No API connected yet. Add at least one key above (Groq, OpenRouter, etc.) and save, then choose the default AI here. Set the model name in &quot;Model per provider&quot; below.
      </p>
    );
  }
  const value = connectedProviders.includes(provider as typeof connectedProviders[number]) ? provider : connectedProviders[0];
  const defaultModel = defaults[provider] ?? "";
  return (
    <div>
      <div className="field">
        <label className="label" htmlFor="default-ai-select">Default AI provider</label>
        <select id="default-ai-select" value={value} onChange={(e) => change(e.target.value)} className="select" style={{ maxWidth: 320 }}>
          {connectedProviders.map((id) => (
            <option key={id} value={id}>
              {DEFAULT_AI_LABELS[id]}
            </option>
          ))}
        </select>
      </div>
      <div className="field">
        <div className="field-row">
          <label className="label" htmlFor="default-ai-model">Model (optional)</label>
          {defaultModel && <span className="help">default: {defaultModel}</span>}
        </div>
        <div className="actions" style={{ flexWrap: "wrap", gap: "0.5rem" }}>
          <input
            id="default-ai-model"
            type="text"
            placeholder={provider === "openrouter" ? "e.g. anthropic/claude-3.5-sonnet or model,fallback (comma-separated)" : (defaultModel || "e.g. llama-3.3-70b-versatile")}
            value={model}
            onChange={(e) => setModel(e.target.value)}
            onBlur={saveModel}
            className="input"
            style={{ maxWidth: 420, flex: "1 1 200px" }}
          />
          <button type="button" onClick={saveModel} disabled={savingModel} className="btn btn-secondary">
            {savingModel ? "Saving…" : "Save model"}
          </button>
        </div>
        <p className="help" style={{ marginTop: "0.35rem" }}>
          Leave blank to use the provider default. For OpenRouter, use a model ID from{" "}
          <a href="https://openrouter.ai/models" target="_blank" rel="noreferrer" className="link">openrouter.ai/models</a>.
        </p>
      </div>
    </div>
  );
}

function FallbackProviderSelect() {
  const [fallbackCsv, setFallbackCsv] = useState("");
  const [defaultProvider, setDefaultProvider] = useState("");
  const [connected, setConnected] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      api.getFallbackProviders(),
      api.getDefaultAi(),
      api.status(),
    ]).then(([fb, ai, status]) => {
      setFallbackCsv(fb.providers || "");
      setDefaultProvider(ai.provider);
      setConnected(status.apis ?? {});
      setLoading(false);
    });
  }, []);

  const connectedProviders = (["groq", "google", "claude", "ollama", "openai", "openrouter"] as const).filter(
    (id) => connected[PROVIDER_STATUS_KEYS[id]] && id !== defaultProvider
  );

  const selected = fallbackCsv
    .split(",")
    .map((s) => s.trim())
    .filter((s) => s && connectedProviders.includes(s as any));

  const toggle = (provider: string) => {
    let next: string[];
    if (selected.includes(provider)) {
      next = selected.filter((p) => p !== provider);
    } else {
      next = [...selected, provider];
    }
    const csv = next.join(",");
    setFallbackCsv(csv);
    setSaving(true);
    setMsg(null);
    api.setFallbackProviders(csv)
      .then(() => {
        setMsg(next.length ? `Fallback order: ${next.map(p => DEFAULT_AI_LABELS[p]).join(" → ")}` : "Auto-detect (all available keys)");
      })
      .catch(() => setMsg("Failed to save"))
      .finally(() => setSaving(false));
  };

  if (loading) return <p style={{ color: "var(--muted)" }}>Loading…</p>;
  if (connectedProviders.length === 0) {
    return (
      <p className="help" style={{ marginTop: "0.5rem" }}>
        No other providers connected. Add more API keys above to enable fallback.
      </p>
    );
  }

  return (
    <div style={{ marginTop: "1rem" }}>
      <p className="help" style={{ marginBottom: "0.5rem" }}>
        If <strong>{DEFAULT_AI_LABELS[defaultProvider] || defaultProvider}</strong> fails (rate limit, timeout, etc.), Asta will try these providers in order.
        {!fallbackCsv && " Currently auto-detecting from all available keys."}
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: "0.4rem" }}>
        {connectedProviders.map((id) => (
          <label
            key={id}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "0.5rem",
              cursor: "pointer",
              padding: "0.35rem 0.5rem",
              borderRadius: 6,
              background: selected.includes(id) ? "var(--bg-hover)" : "transparent",
              transition: "background 0.15s",
            }}
          >
            <input
              type="checkbox"
              checked={selected.includes(id)}
              onChange={() => toggle(id)}
              disabled={saving}
              style={{ accentColor: "var(--primary)" }}
            />
            <span>{DEFAULT_AI_LABELS[id]}</span>
            {selected.includes(id) && (
              <span className="help" style={{ marginLeft: "auto" }}>
                #{selected.indexOf(id) + 1}
              </span>
            )}
          </label>
        ))}
      </div>
      {msg && <p className="help" style={{ marginTop: "0.5rem", color: "var(--success)" }}>{msg}</p>}
    </div>
  );
}



function TestSpotifyButton() {
  const [testing, setTesting] = useState(false);
  const [result, setResult] = useState<{ ok: boolean; text: string } | null>(null);
  const run = async () => {
    setTesting(true);
    setResult(null);
    try {
      const r = await api.testApiKey("spotify");
      if (r.ok) {
        setResult({ ok: true, text: r.message || "Spotify credentials work." });
      } else {
        setResult({ ok: false, text: r.error || "Unknown error" });
      }
    } catch (e) {
      setResult({ ok: false, text: (e as Error).message || "Request failed" });
    } finally {
      setTesting(false);
    }
  };
  return (
    <span className="actions">
      <button type="button" onClick={run} disabled={testing} className="btn btn-secondary">
        {testing ? "Testing…" : "Test credentials"}
      </button>
      {result && (
        <span className={result.ok ? "status-ok" : "status-pending"}>{result.text}</span>
      )}
    </span>
  );
}

function SpotifySetup({ keysStatus, onSaved }: { keysStatus: Record<string, boolean>; onSaved: () => void }) {
  const [setup, setSetup] = useState<{ dashboard_url: string; docs_url: string; steps: string[]; redirect_uri?: string; connect_url?: string } | null>(null);
  const [spotifyConnected, setSpotifyConnected] = useState<boolean | null>(null);
  const [clientId, setClientId] = useState("");
  const [clientSecret, setClientSecret] = useState("");
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  useEffect(() => {
    api.getSpotifySetup().then(setSetup).catch(() => setSetup(null));
    api.getSpotifyStatus().then((r) => setSpotifyConnected(r.connected)).catch(() => setSpotifyConnected(false));
  }, []);
  const save = async () => {
    setSaving(true);
    setMsg(null);
    try {
      await api.setSettingsKeys({
        spotify_client_id: clientId.trim() || null,
        spotify_client_secret: clientSecret.trim() || null,
      });
      onSaved();
      setClientId("");
      setClientSecret("");
      setMsg("Spotify credentials saved. For playback, click 'Connect Spotify' below to authorize your account.");
      api.getSpotifyStatus().then((r) => setSpotifyConnected(r.connected));
    } catch (e) {
      setMsg("Error: " + ((e as Error).message || String(e)));
    } finally {
      setSaving(false);
    }
  };
  const idSet = keysStatus["spotify_client_id"];
  const secretSet = keysStatus["spotify_client_secret"];
  return (
    <div>
      {setup && (
        <div className="alert" style={{ marginBottom: "1rem" }}>
          <p style={{ marginTop: 0, marginBottom: "0.5rem" }}>
            <a href={setup.dashboard_url} target="_blank" rel="noreferrer" className="link">Spotify Developer Dashboard</a>
            {" · "}
            <a href={setup.docs_url} target="_blank" rel="noreferrer" className="link">Web API docs</a>
          </p>
          <ol style={{ margin: 0, paddingLeft: "1.25rem" }} className="help">
            {setup.steps.map((step, i) => (
              <li
                key={i}
                style={{ marginBottom: "0.35rem" }}
                dangerouslySetInnerHTML={{ __html: step.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>") }}
              />
            ))}
            {spotifyConnected !== true && setup.connect_url && (
              <li style={{ marginBottom: "0.35rem" }}>
                To play on your devices (phone, speaker, etc.), connect your Spotify account once:{" "}
                <a href={setup.connect_url} className="link">Connect Spotify</a>
              </li>
            )}
          </ol>
        </div>
      )}
      <div className="field">
        <div className="field-row">
          <label className="label" htmlFor="spotify-client-id">Client ID</label>
          {idSet && <span className="status-ok">Set</span>}
        </div>
        <input
          id="spotify-client-id"
          type="password"
          placeholder={idSet ? "Leave blank to keep current" : "Paste Client ID"}
          value={clientId}
          onChange={(e) => setClientId(e.target.value)}
          className="input"
          style={{ maxWidth: 420 }}
        />
      </div>
      <div className="field">
        <div className="field-row">
          <label className="label" htmlFor="spotify-client-secret">Client secret</label>
          {secretSet && <span className="status-ok">Set</span>}
        </div>
        <input
          id="spotify-client-secret"
          type="password"
          placeholder={secretSet ? "Leave blank to keep current" : "Paste Client secret"}
          value={clientSecret}
          onChange={(e) => setClientSecret(e.target.value)}
          className="input"
          style={{ maxWidth: 420 }}
        />
      </div>
      <div className="actions">
        <button type="button" onClick={save} disabled={saving} className="btn btn-primary">
          {saving ? "Saving…" : "Save Spotify credentials"}
        </button>
        <TestSpotifyButton />
      </div>
      {msg && <div className="alert" style={{ marginTop: "0.75rem" }}>{msg}</div>}
      <div style={{ marginTop: "1rem" }}>
        <p className="help" style={{ marginBottom: "0.5rem" }}>
          {spotifyConnected === true ? (
            <span className="status-ok">Spotify connected for playback. You can say &quot;play X on Spotify&quot; in Chat and choose a device.</span>
          ) : (
            <span className="muted">Spotify not connected for playback yet.</span>
          )}
        </p>
      </div>
    </div>
  );
}



function ModelsForm() {
  const [models, setModels] = useState<Record<string, string>>({});
  const [defaults, setDefaults] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    api.getModels().then((r) => {
      setModels(r.models);
      setDefaults(r.defaults);
      setLoading(false);
    });
  }, []);
  const save = async () => {
    setSaving(true);
    try {
      for (const provider of ["groq", "google", "claude", "ollama", "openai", "openrouter"]) {
        await api.setModel(provider, models[provider] ?? "");
      }
    } finally {
      setSaving(false);
    }
  };
  if (loading) return <p style={{ color: "var(--muted)" }}>Loading…</p>;
  return (
    <div>
      {(["groq", "google", "claude", "ollama", "openai", "openrouter"] as const).map((provider) => (
        <div key={provider} className="field">
          <div className="field-row">
            <label className="label" htmlFor={"model-" + provider}>
              {PROVIDER_LABELS[provider]}
            </label>
            <span className="help">default: {defaults[provider] ?? "—"}</span>
          </div>
          <input
            id={"model-" + provider}
            type="text"
            placeholder={provider === "openrouter" ? "main-model, fallback1, fallback2 (comma-separated)" : (defaults[provider] ?? "e.g. llama-3.3-70b-versatile")}
            value={models[provider] ?? ""}
            onChange={(e) => setModels((m) => ({ ...m, [provider]: e.target.value }))}
            className="input"
            style={{ maxWidth: 520 }}
          />
        </div>
      ))}
      <button type="button" onClick={save} disabled={saving} className="btn btn-primary">
        {saving ? "Saving…" : "Save models"}
      </button>
    </div>
  );
}

export default function Settings() {
  const [providers, setProviders] = useState<string[]>([]);
  const [keysStatus, setKeysStatus] = useState<Record<string, boolean>>({});
  const [keys, setKeys] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [cronJobs, setCronJobs] = useState<CronJob[]>([]);
  const [autoUpdaterSaving, setAutoUpdaterSaving] = useState(false);
  const [autoUpdaterMessage, setAutoUpdaterMessage] = useState<string | null>(null);

  useEffect(() => {
    api.providers().then((r) => setProviders(r.providers));
    api.getSettingsKeys().then(setKeysStatus);
    api.getCronJobs().then((r) => setCronJobs(r.cron_jobs || [])).catch(() => setCronJobs([]));
  }, []);

  const handleSaveKeys = async () => {
    setSaving(true);
    setMessage(null);
    try {
      const payload: Record<string, string | null> = {};
      for (const [name, value] of Object.entries(keys)) {
        payload[name] = value?.trim() || null;
      }
      await api.setSettingsKeys(payload);
      const next = await api.getSettingsKeys();
      setKeysStatus(next);
      setKeys({});
      setMessage("API keys saved. Restart the backend if you added or changed the Telegram token (so the bot connects). Groq/Gemini/Claude keys work immediately.");
    } catch (e) {
      const err = e as Error & { status?: number };
      let msg = err.message || String(e);
      if (msg.includes("Not Found") || msg.includes("404")) {
        msg = "API not found. Is the backend running? Start it with: cd backend && source .venv/bin/activate && uvicorn app.main:app --port 8010. If you use another port, run: VITE_API_URL=http://localhost:YOUR_PORT npm run dev";
      }
      setMessage("Error: " + msg);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      <h1 className="page-title">Settings</h1>

      <div className="accordion">
        <details open>
          <summary>
            <span>API keys</span>
            <span className="acc-meta">Providers & channels</span>
          </summary>
          <div className="acc-body">
            <p className="help" style={{ marginBottom: "1rem" }}>
              Keys are stored in your local database (<code>backend/asta.db</code>) and are never committed to git. Restart the backend if you change the Telegram token.
            </p>
            <RestartBackendButton />

            <h3 className="settings-section-title">AI providers</h3>
            <div className="provider-cards">
              {AI_PROVIDER_ENTRIES.map((entry) => (
                <div key={entry.id} className="provider-card">
                  <div className="provider-card-header">
                    <ProviderLogo logoKey={entry.logoKey} size={44} />
                    <div className="provider-card-title-wrap">
                      <span className="provider-card-title">{entry.name}</span>
                      {entry.keys.every((k) => keysStatus[k.key]) && (
                        <span className="status-ok">All set</span>
                      )}
                    </div>
                  </div>
                  <div className="provider-card-fields">
                    {entry.keys.map(({ key: keyName, label }) => (
                      <div key={keyName} className="field">
                        <div className="field-row">
                          <label className="label" htmlFor={keyName}>{label}</label>
                          {keysStatus[keyName] && <span className="status-ok">Set</span>}
                        </div>
                        <div className="actions" style={{ flexWrap: "wrap", gap: "0.5rem" }}>
                          <input
                            id={keyName}
                            type="password"
                            placeholder={keysStatus[keyName] ? "Leave blank to keep current" : "Paste key"}
                            value={keys[keyName] ?? ""}
                            onChange={(e) => setKeys((k) => ({ ...k, [keyName]: e.target.value }))}
                            className="input"
                            style={{ flex: "1 1 200px", minWidth: 0 }}
                          />
                          {entry.testKey === keyName && <TestGroqButton />}
                        </div>
                      </div>
                    ))}
                  </div>
                  <div className="actions" style={{ marginTop: "0.5rem" }}>
                    <button type="button" onClick={handleSaveKeys} disabled={saving} className="btn btn-primary">
                      {saving ? "Saving…" : "Save"}
                    </button>
                  </div>
                  <p className="help provider-card-get-key">
                    Get your API key: <a href={entry.getKeyUrl} target="_blank" rel="noreferrer" className="link">{entry.getKeyUrl}</a>
                  </p>
                </div>
              ))}
            </div>

            <h3 className="settings-section-title">Channels & extras</h3>
            <div className="provider-cards provider-cards--small">
              {OTHER_KEYS.map((entry) => (
                <div key={entry.id} className="provider-card">
                  <div className="provider-card-header">
                    <ProviderLogo logoKey={entry.logoKey} size={36} />
                    <div className="provider-card-title-wrap">
                      <span className="provider-card-title">{entry.name}</span>
                      {keysStatus[entry.key] && <span className="status-ok">Set</span>}
                    </div>
                  </div>
                  <div className="provider-card-fields">
                    <input
                      id={entry.key}
                      type="password"
                      placeholder={keysStatus[entry.key] ? "Leave blank to keep current" : "Paste key"}
                      value={keys[entry.key] ?? ""}
                      onChange={(e) => setKeys((k) => ({ ...k, [entry.key]: e.target.value }))}
                      className="input"
                      style={{ width: "100%" }}
                    />
                  </div>
                  <div className="actions" style={{ marginTop: "0.5rem" }}>
                    <button type="button" onClick={handleSaveKeys} disabled={saving} className="btn btn-primary">
                      {saving ? "Saving…" : "Save"}
                    </button>
                  </div>
                  <p className="help provider-card-get-key">
                    Get your API key: <a href={entry.getKeyUrl} target="_blank" rel="noreferrer" className="link">{entry.getKeyUrl}</a>
                  </p>
                </div>
              ))}
            </div>

            <div className="actions" style={{ marginTop: "1rem" }}>
              <button type="button" onClick={handleSaveKeys} disabled={saving} className="btn btn-primary">
                {saving ? "Saving…" : "Save all API keys"}
              </button>
            </div>
            {message && (
              <div className={message.startsWith("Error:") ? "alert alert-error" : "alert"} style={{ marginTop: "0.75rem" }}>
                {message}
              </div>
            )}
          </div>
        </details>

        <details>
          <summary>
            <span>Default AI</span>
            <span className="acc-meta">Used across chat + channels</span>
          </summary>
          <div className="acc-body">
            <p className="help">Asta uses this provider by default for Chat, WhatsApp, and Telegram.</p>
            <DefaultAiSelect />
            <h3 style={{ marginTop: "1.25rem", marginBottom: "0.25rem" }}>Fallback providers</h3>
            <FallbackProviderSelect />
          </div>
        </details>

        <details>
          <summary>
            <span>Models per provider</span>
            <span className="acc-meta">Optional overrides</span>
          </summary>
          <div className="acc-body">
            <p className="help">
              Leave blank to use defaults. For <strong>OpenRouter</strong>, use a model ID (browse at{" "}
              <a href="https://openrouter.ai/models" target="_blank" rel="noreferrer" className="link">openrouter.ai/models</a>).
              You can add <strong>fallback models</strong> separated by commas — if the first model fails, the next one is tried automatically.
            </p>
            <ModelsForm />
          </div>
        </details>



        <details>
          <summary>
            <span>Spotify</span>
            <span className="acc-meta">Search + playback</span>
          </summary>
          <div className="acc-body">
            <p className="help">
              Set your Spotify app credentials so Asta can search songs and (optionally) control playback on your devices.
            </p>
            <SpotifySetup keysStatus={keysStatus} onSaved={() => api.getSettingsKeys().then(setKeysStatus)} />
          </div>
        </details>

        <AutoUpdaterSettings
          cronJobs={cronJobs}
          onSave={() => api.getCronJobs().then((r) => setCronJobs(r.cron_jobs || []))}
          saving={autoUpdaterSaving}
          setSaving={setAutoUpdaterSaving}
          message={autoUpdaterMessage}
          setMessage={setAutoUpdaterMessage}
        />

        <details>
          <summary>
            <span>Run the API</span>
            <span className="acc-meta">When “API off” shows</span>
          </summary>
          <div className="acc-body">
            <p className="help">Start the backend from the project root (default port: 8010):</p>
            <pre className="file-preview" style={{ maxWidth: 820 }}>
              {`# Linux / macOS
./asta.sh start

# Or manually:
cd backend && source .venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8010`}
            </pre>
            <p className="help">
              API is <strong>http://localhost:8010</strong> (or the URL in <code>VITE_API_URL</code>); panel is{" "}
              <strong>http://localhost:5173</strong>.
            </p>
          </div>
        </details>

        <details>
          <summary>
            <span>About providers & files</span>
            <span className="acc-meta">Quick reference</span>
          </summary>
          <div className="acc-body">
            <h3 style={{ marginTop: 0 }}>AI providers</h3>
            <p className="help">
              Available for Asta: {providers.join(", ")}. Ollama needs no key; set <code>OLLAMA_BASE_URL</code> in <code>backend/.env</code> if needed.
            </p>

            <h3>Files</h3>
            <p className="help">
              <code>ASTA_ALLOWED_PATHS</code> in <code>backend/.env</code> controls which directories the panel/AI can read.
            </p>

            <h3>Audio notes</h3>
            <p className="help">Transcription runs locally (faster-whisper). Formatting uses your default AI.</p>
          </div>
        </details>
      </div>
    </div>
  );
}
