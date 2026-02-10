import { useState, useEffect, useCallback } from "react";
import { api } from "../api/client";

const KEY_LABELS: Record<string, string> = {
  groq_api_key: "Groq",
  gemini_api_key: "Google Gemini",
  google_ai_key: "Google AI (alternative)",
  anthropic_api_key: "Anthropic (Claude)",
  openai_api_key: "OpenAI",
  openrouter_api_key: "OpenRouter",
  telegram_bot_token: "Telegram Bot (from @BotFather)",
};

const PROVIDER_LABELS: Record<string, string> = {
  groq: "Groq",
  google: "Google (Gemini)",
  claude: "Claude",
  ollama: "Ollama",
  openai: "OpenAI",
  openrouter: "OpenRouter",
};

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
      setDone("Backend has stopped. Start it again in your terminal (e.g. cd backend && uvicorn app.main:app --port 8000) — the indicator above will turn green when it’s back.");
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
  const [provider, setProvider] = useState("groq");
  const [loading, setLoading] = useState(true);
  const [connected, setConnected] = useState<Record<string, boolean>>({});
  useEffect(() => {
    Promise.all([api.getDefaultAi(), api.status()]).then(([r, status]) => {
      setConnected(status.apis ?? {});
      setLoading(false);
      setProvider(r.provider);
    });
  }, []);
  useEffect(() => {
    if (loading || Object.keys(connected).length === 0) return;
    const connectedIds = (["groq", "google", "claude", "ollama", "openai", "openrouter"] as const).filter(
      (id) => connected[PROVIDER_STATUS_KEYS[id]]
    );
    if (connectedIds.length > 0 && !connectedIds.includes(provider as typeof connectedIds[number])) {
      const fallback = connectedIds[0];
      setProvider(fallback);
      api.setDefaultAi(fallback).catch(() => {});
    }
  }, [loading, connected, provider]);
  const change = (p: string) => {
    setProvider(p);
    api.setDefaultAi(p).catch(() => setProvider(provider));
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
  return (
    <div className="field">
      <select value={value} onChange={(e) => change(e.target.value)} className="select" style={{ maxWidth: 320 }}>
        {connectedProviders.map((id) => (
          <option key={id} value={id}>
            {DEFAULT_AI_LABELS[id]}
          </option>
        ))}
      </select>
      <p className="help" style={{ marginTop: "0.35rem" }}>
        Choose which connected API to use by default. Set the model name in &quot;Model per provider&quot; below (e.g. for OpenRouter: any model from openrouter.ai/models).
      </p>
    </div>
  );
}

function WhatsAppQr() {
  const [state, setState] = useState<{ connected?: boolean; qr?: string | null; error?: string } | null>(null);
  const fetchQr = useCallback(() => {
    api.whatsappQr()
      .then(setState)
      .catch((e) => setState({ connected: false, qr: null, error: e.message }));
  }, []);
  useEffect(() => {
    fetchQr();
    const t = setInterval(fetchQr, 4000);
    return () => clearInterval(t);
  }, [fetchQr]);
  if (state?.error && !state?.qr) {
    return (
      <div className="alert alert-error">
        {state.error} Then run: <code>cd services/whatsapp &amp;&amp; npm install &amp;&amp; npm run start</code>
      </div>
    );
  }
  if (state?.connected) {
    return <p className="status-ok">WhatsApp connected.</p>;
  }
  if (state?.qr) {
    return (
      <div>
        <p className="help" style={{ marginBottom: "0.5rem" }}>
          Scan with WhatsApp (Linked Devices): open WhatsApp → Settings → Linked devices → Link a device.
        </p>
        <img src={state.qr} alt="WhatsApp QR" style={{ maxWidth: 256, height: "auto", border: "1px solid var(--border)", borderRadius: 8 }} />
      </div>
    );
  }
  return <p className="help">Loading… Start the WhatsApp bridge if you have not.</p>;
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
            placeholder={provider === "openrouter" ? "e.g. arcee-ai/trinity-large-preview:free (see openrouter.ai/models)" : (defaults[provider] ?? "e.g. llama-3.3-70b-versatile")}
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

  useEffect(() => {
    api.providers().then((r) => setProviders(r.providers));
    api.getSettingsKeys().then(setKeysStatus);
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
        msg = "API not found. Is the backend running? Start it with: cd backend && source .venv/bin/activate && uvicorn app.main:app --port 8000. If you use port 8001, run: VITE_API_URL=http://localhost:8001 npm run dev";
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
            <span className="acc-meta">Groq, Gemini, Claude, Telegram…</span>
          </summary>
          <div className="acc-body">
            <p className="help">
              Keys are stored in your local database (<code>backend/asta.db</code>) and are never committed to git. Restart the backend if you change the Telegram token.
            </p>

            <RestartBackendButton />

            {Object.entries(KEY_LABELS).map(([keyName, label]) => (
              <div key={keyName} className="field">
                <div className="field-row">
                  <label className="label" htmlFor={keyName}>{label}</label>
                  {keysStatus[keyName] && <span className="status-ok">Set</span>}
                </div>
                <div className="actions">
                  <input
                    id={keyName}
                    type="password"
                    placeholder={keysStatus[keyName] ? "Leave blank to keep current" : "Paste key"}
                    value={keys[keyName] ?? ""}
                    onChange={(e) => setKeys((k) => ({ ...k, [keyName]: e.target.value }))}
                    className="input"
                    style={{ maxWidth: 520 }}
                  />
                  {keyName === "groq_api_key" ? <TestGroqButton /> : null}
                </div>
              </div>
            ))}

            <div className="actions">
              <button type="button" onClick={handleSaveKeys} disabled={saving} className="btn btn-primary">
                {saving ? "Saving…" : "Save API keys"}
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
            </p>
            <ModelsForm />
          </div>
        </details>

        <details>
          <summary>
            <span>Channels</span>
            <span className="acc-meta">Telegram + WhatsApp</span>
          </summary>
          <div className="acc-body">
            <h3 style={{ marginTop: 0 }}>Telegram</h3>
            <p className="help">
              Create a bot at <a href="https://t.me/BotFather" target="_blank" rel="noreferrer" className="link">t.me/BotFather</a>,
              paste the token above, save, then restart the backend.
            </p>

            <h3>WhatsApp</h3>
            <WhatsAppQr />
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
