import { useState, useEffect, useCallback } from "react";
import { api } from "../api/client";

const KEY_LABELS: Record<string, string> = {
  groq_api_key: "Groq",
  gemini_api_key: "Google Gemini",
  google_ai_key: "Google AI (alternative)",
  anthropic_api_key: "Anthropic (Claude)",
  openai_api_key: "OpenAI",
  telegram_bot_token: "Telegram Bot (from @BotFather)",
};

const PROVIDER_LABELS: Record<string, string> = {
  groq: "Groq",
  google: "Google (Gemini)",
  claude: "Claude",
  ollama: "Ollama",
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
    <p style={{ marginBottom: "1rem" }}>
      <button
        type="button"
        onClick={run}
        disabled={loading}
        style={{ padding: "0.35rem 0.75rem", fontSize: "0.9rem", background: "var(--accent)", color: "var(--bg)", border: "none", borderRadius: 8, cursor: loading ? "not-allowed" : "pointer" }}
      >
        {loading ? "Stopping…" : "Stop backend (start again in terminal)"}
      </button>
      {done && <span style={{ marginLeft: "0.5rem", color: isError ? "var(--accent)" : "var(--muted)", fontSize: "0.9rem" }}>{done}</span>}
    </p>
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
    <span style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
      <button
        type="button"
        onClick={run}
        disabled={testing}
        style={{ padding: "0.35rem 0.75rem", fontSize: "0.9rem", background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, color: "var(--text)", cursor: testing ? "not-allowed" : "pointer" }}
      >
        {testing ? "Testing…" : "Test"}
      </button>
      {result && (
        <span className={result === "Key works." ? "status-ok" : "status-pending"} style={{ fontSize: "0.9rem" }}>
          {result}
        </span>
      )}
    </span>
  );
}

function DefaultAiSelect() {
  const [provider, setProvider] = useState("groq");
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    api.getDefaultAi().then((r) => { setProvider(r.provider); setLoading(false); });
  }, []);
  const change = (p: string) => {
    setProvider(p);
    api.setDefaultAi(p).catch(() => setProvider(provider));
  };
  if (loading) return <p style={{ color: "var(--muted)" }}>Loading…</p>;
  return (
    <select
      value={provider}
      onChange={(e) => change(e.target.value)}
      style={{ padding: "0.5rem", background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, color: "var(--text)" }}
    >
      <option value="groq">Groq</option>
      <option value="google">Google (Gemini)</option>
      <option value="claude">Claude (Anthropic)</option>
      <option value="ollama">Ollama (local)</option>
    </select>
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
      <p style={{ color: "var(--muted)", fontSize: "0.9rem" }}>
        {state.error} Then run: <code>cd services/whatsapp && npm install && npm run start</code>
      </p>
    );
  }
  if (state?.connected) {
    return <p className="status-ok">WhatsApp connected.</p>;
  }
  if (state?.qr) {
    return (
      <div>
        <p style={{ color: "var(--muted)", fontSize: "0.9rem", marginBottom: "0.5rem" }}>
          Scan with WhatsApp (Linked Devices): open WhatsApp → Settings → Linked devices → Link a device.
        </p>
        <img src={state.qr} alt="WhatsApp QR" style={{ maxWidth: 256, height: "auto", border: "1px solid var(--border)", borderRadius: 8 }} />
      </div>
    );
  }
  return <p style={{ color: "var(--muted)", fontSize: "0.9rem" }}>Loading… Start the WhatsApp bridge if you have not.</p>;
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
    <span style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
      <button
        type="button"
        onClick={run}
        disabled={testing}
        style={{ padding: "0.35rem 0.75rem", fontSize: "0.9rem", background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, color: "var(--text)", cursor: testing ? "not-allowed" : "pointer" }}
      >
        {testing ? "Testing…" : "Test credentials"}
      </button>
      {result && (
        <span className={result.ok ? "status-ok" : "status-pending"} style={{ fontSize: "0.9rem" }}>
          {result.text}
        </span>
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
        <div style={{ marginBottom: "1rem", padding: "0.75rem", background: "var(--surface)", borderRadius: 8, border: "1px solid var(--border)" }}>
          <p style={{ marginTop: 0, marginBottom: "0.5rem" }}>
            <a href={setup.dashboard_url} target="_blank" rel="noreferrer" style={{ color: "var(--accent)" }}>Spotify Developer Dashboard</a>
            {" · "}
            <a href={setup.docs_url} target="_blank" rel="noreferrer" style={{ color: "var(--accent)" }}>Web API docs</a>
          </p>
          <ol style={{ margin: 0, paddingLeft: "1.25rem", color: "var(--muted)", fontSize: "0.9rem" }}>
            {setup.steps.map((step, i) => (
              <li key={i} style={{ marginBottom: "0.35rem" }} dangerouslySetInnerHTML={{ __html: step.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>") }} />
            ))}
          </ol>
        </div>
      )}
      <div style={{ marginBottom: "0.75rem" }}>
        <label style={{ display: "block", marginBottom: "0.25rem" }}>
          Client ID
          {idSet && <span className="status-ok" style={{ marginLeft: "0.5rem" }}>· Set</span>}
        </label>
        <input
          type="password"
          placeholder={idSet ? "Leave blank to keep current" : "Paste Client ID"}
          value={clientId}
          onChange={(e) => setClientId(e.target.value)}
          style={{ width: "100%", maxWidth: 400, padding: "0.5rem", background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, color: "var(--text)" }}
        />
      </div>
      <div style={{ marginBottom: "0.75rem" }}>
        <label style={{ display: "block", marginBottom: "0.25rem" }}>
          Client secret
          {secretSet && <span className="status-ok" style={{ marginLeft: "0.5rem" }}>· Set</span>}
        </label>
        <input
          type="password"
          placeholder={secretSet ? "Leave blank to keep current" : "Paste Client secret"}
          value={clientSecret}
          onChange={(e) => setClientSecret(e.target.value)}
          style={{ width: "100%", maxWidth: 400, padding: "0.5rem", background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, color: "var(--text)" }}
        />
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", flexWrap: "wrap" }}>
        <button type="button" onClick={save} disabled={saving} style={{ padding: "0.5rem 1rem", background: "var(--accent)", color: "var(--bg)", border: "none", borderRadius: 8, cursor: "pointer" }}>
          {saving ? "Saving…" : "Save Spotify credentials"}
        </button>
        <TestSpotifyButton />
      </div>
      {msg && <p style={{ marginTop: "0.75rem", color: "var(--muted)", fontSize: "0.9rem" }}>{msg}</p>}
      <div style={{ marginTop: "1rem", paddingTop: "1rem", borderTop: "1px solid var(--border)" }}>
        <p style={{ marginBottom: "0.5rem" }}>
          {spotifyConnected === true ? (
            <span className="status-ok">Spotify connected for playback. You can say &quot;play X on Spotify&quot; in Chat and choose a device.</span>
          ) : (
            <>
              To play on your devices (phone, speaker, etc.), connect your Spotify account once:{" "}
              {setup?.connect_url ? (
                <a href={setup.connect_url} style={{ color: "var(--accent)" }}>Connect Spotify</a>
              ) : (
                <span className="muted">Load setup to get link</span>
              )}
            </>
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
      for (const provider of ["groq", "google", "claude", "ollama"]) {
        await api.setModel(provider, models[provider] ?? "");
      }
    } finally {
      setSaving(false);
    }
  };
  if (loading) return <p style={{ color: "var(--muted)" }}>Loading…</p>;
  return (
    <div>
      {(["groq", "google", "claude", "ollama"] as const).map((provider) => (
        <div key={provider} style={{ marginBottom: "0.75rem" }}>
          <label style={{ display: "block", marginBottom: "0.25rem" }}>
            {PROVIDER_LABELS[provider]}
            <span className="muted" style={{ marginLeft: "0.5rem", fontSize: "0.9rem" }}>
              default: {defaults[provider] ?? "—"}
            </span>
          </label>
          <input
            type="text"
            placeholder={defaults[provider] ?? "e.g. llama-3.3-70b-versatile"}
            value={models[provider] ?? ""}
            onChange={(e) => setModels((m) => ({ ...m, [provider]: e.target.value }))}
            style={{ width: "100%", maxWidth: 400, padding: "0.5rem", background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, color: "var(--text)" }}
          />
        </div>
      ))}
      <button type="button" onClick={save} disabled={saving} style={{ marginTop: "0.5rem", padding: "0.5rem 1rem", background: "var(--accent)", color: "var(--bg)", border: "none", borderRadius: 8, cursor: "pointer" }}>
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

      <div className="card">
        <h2>API keys</h2>
        <p style={{ color: "var(--muted)", marginBottom: "1rem" }}>
          Add your keys here to use Chat with Groq, Gemini, Claude, etc. Keys are stored in your local database (backend/asta.db) and are never committed to git.
        </p>
        <p style={{ color: "var(--muted)", fontSize: "0.9rem", marginBottom: "0.5rem" }}>
          After saving, <strong>restart the backend</strong> if you added or changed the Telegram bot token so the bot can connect. AI keys (Groq, Gemini, Claude) work right away.
        </p>
        <RestartBackendButton />
        {Object.entries(KEY_LABELS).map(([keyName, label]) => (
          <div key={keyName} style={{ marginBottom: "0.75rem" }}>
            <label style={{ display: "block", marginBottom: "0.25rem" }}>
              {label}
              {keysStatus[keyName] && <span className="status-ok" style={{ marginLeft: "0.5rem" }}>· Set</span>}
            </label>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
              <input
                type="password"
                placeholder={keysStatus[keyName] ? "Leave blank to keep current" : "Paste key"}
                value={keys[keyName] ?? ""}
                onChange={(e) => setKeys((k) => ({ ...k, [keyName]: e.target.value }))}
                style={{ width: "100%", maxWidth: 400, padding: "0.5rem", background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, color: "var(--text)" }}
              />
              {keyName === "groq_api_key" && (
                <TestGroqButton />
              )}
            </div>
          </div>
        ))}
        <button type="button" onClick={handleSaveKeys} disabled={saving} style={{ marginTop: "0.5rem", padding: "0.5rem 1rem", background: "var(--accent)", color: "var(--bg)", border: "none", borderRadius: 8, cursor: "pointer" }}>
          {saving ? "Saving…" : "Save API keys"}
        </button>
        {message && <p style={{ marginTop: "0.75rem", color: "var(--muted)" }}>{message}</p>}
      </div>

      <div className="card">
        <h2>Asta&apos;s default AI</h2>
        <p style={{ color: "var(--muted)", marginBottom: "0.5rem" }}>
          The agent Asta uses this AI for Chat, WhatsApp, and Telegram unless you pick another in Chat.
        </p>
        <DefaultAiSelect />
      </div>

      <div className="card">
        <h2>Model per provider</h2>
        <p style={{ color: "var(--muted)", marginBottom: "1rem" }}>
          Choose which model to use for each provider. Leave blank to use the built-in default (e.g. Groq: llama-3.3-70b-versatile).
        </p>
        <ModelsForm />
      </div>

      <div className="card">
        <h2>AI providers</h2>
        <p>Available for Asta: {providers.join(", ")}. Add keys above to enable each.</p>
        <p style={{ color: "var(--muted)", fontSize: "0.9rem" }}>Ollama needs no key; set OLLAMA_BASE_URL in backend/.env if not default.</p>
      </div>

      <div className="card">
        <h2>Channels</h2>
        <p style={{ color: "var(--muted)", marginBottom: "1rem" }}>
          Connect Telegram and WhatsApp so Asta can reply from the panel and on your phone.
        </p>
        <h3 style={{ fontSize: "0.95rem", marginBottom: "0.35rem" }}>Telegram</h3>
        <p style={{ color: "var(--muted)", fontSize: "0.9rem", marginBottom: "1rem" }}>
          Set your bot token above under <strong>API keys → Telegram Bot (from @BotFather)</strong>. Create a bot at <a href="https://t.me/BotFather" target="_blank" rel="noreferrer" style={{ color: "var(--accent)" }}>t.me/BotFather</a>, then paste the token and save. Restart the backend to connect.
        </p>
        <h3 style={{ fontSize: "0.95rem", marginBottom: "0.35rem" }}>WhatsApp</h3>
        <WhatsAppQr />
      </div>

      <div className="card">
        <h2>Spotify</h2>
        <p style={{ color: "var(--muted)", marginBottom: "1rem" }}>
          Set your Spotify app credentials so Asta can search songs (and later play on your devices). You can paste them here or set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in backend/.env.
        </p>
        <SpotifySetup keysStatus={keysStatus} onSaved={() => api.getSettingsKeys().then(setKeysStatus)} />
      </div>

      <div className="card">
        <h2>Audio notes</h2>
        <p style={{ color: "var(--muted)", marginBottom: "0.5rem" }}>
          Upload meetings or voice memos; Asta transcribes and formats as meeting notes or conversation summary. <strong>No API key for transcription</strong> — it runs locally (faster-whisper). Formatting uses your default AI above (Groq, Gemini, etc.).
        </p>
        <p style={{ fontSize: "0.9rem", marginBottom: "0" }}>
          Enable the skill in <strong>Skills</strong>, then use <a href="/audio-notes" style={{ color: "var(--accent)" }}>Audio notes</a> to upload and process.
        </p>
      </div>

      <div className="card">
        <h2>Run the API</h2>
        <p style={{ color: "var(--muted)", marginBottom: "0.75rem" }}>
          If the panel shows &quot;API off&quot;, start the backend in a terminal from the project root:
        </p>
        <pre style={{ background: "var(--surface)", padding: "1rem", borderRadius: 8, overflow: "auto", fontSize: "0.85rem", marginBottom: "0.5rem", whiteSpace: "pre-wrap" }}>
          {`# Linux / macOS
./asta.sh start

# Or manually:
cd backend && source .venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8000`}
        </pre>
        <p style={{ color: "var(--muted)", fontSize: "0.9rem", marginBottom: "0" }}>
          API will be at <strong>http://localhost:8000</strong>; panel at <strong>http://localhost:5173</strong>. Use <code>./asta.sh status</code> to check, <code>./asta.sh restart</code> to restart.
        </p>
      </div>

      <div className="card">
        <h2>Files</h2>
        <p>ASTA_ALLOWED_PATHS in backend/.env — comma-separated directories the AI and panel can read.</p>
      </div>
    </div>
  );
}
