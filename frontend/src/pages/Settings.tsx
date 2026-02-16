import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import type { CronJob, VisionSettings } from "../api/client";
import { api } from "../api/client";

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

const PROVIDER_IDS = ["groq", "google", "claude", "ollama", "openai", "openrouter"] as const;
type ProviderId = (typeof PROVIDER_IDS)[number];

const CLAUDE_CUSTOM_MODEL = "__custom__";
const CLAUDE_MODEL_PRESETS: Array<{ label: string; value: string }> = [
  { label: "Use provider default", value: "" },
  { label: "Claude 3.5 Sonnet (stable)", value: "claude-3-5-sonnet-20241022" },
  { label: "Claude 3.5 Haiku (fast)", value: "claude-3-5-haiku-20241022" },
];
const OLLAMA_DEFAULT_MODEL = "__provider_default__";
const OLLAMA_CUSTOM_MODEL = "__custom_model__";

function resolveOllamaSelectValue(model: string, ollamaList: string[]): string {
  const trimmed = model.trim();
  if (!trimmed) return OLLAMA_DEFAULT_MODEL;
  const matched = ollamaList.find((name) => name === trimmed || name.startsWith(trimmed + ":"));
  return matched ?? OLLAMA_CUSTOM_MODEL;
}

function DefaultAiSelect() {
  const [provider, setProvider] = useState("");
  const [model, setModel] = useState("");
  const [thinkingLevel, setThinkingLevel] = useState<"off" | "minimal" | "low" | "medium" | "high" | "xhigh">("off");
  const [reasoningMode, setReasoningMode] = useState<"off" | "on" | "stream">("off");
  const [visionSettings, setVisionSettings] = useState<VisionSettings>({
    preprocess: true,
    provider_order: "openrouter,claude,openai",
    openrouter_model: "nvidia/nemotron-nano-12b-v2-vl:free",
  });
  const [availableModels, setAvailableModels] = useState<{ ollama: string[] }>({ ollama: [] });
  const [defaults, setDefaults] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [savingModel, setSavingModel] = useState(false);
  const [savingThinking, setSavingThinking] = useState(false);
  const [savingReasoning, setSavingReasoning] = useState(false);
  const [savingVision, setSavingVision] = useState(false);
  const [visionMsg, setVisionMsg] = useState<string | null>(null);
  const [connected, setConnected] = useState<Record<string, boolean>>({});
  useEffect(() => {
    Promise.all([
      api.getDefaultAi(),
      api.status(),
      api.getModels(),
      api.getThinking(),
      api.getReasoning(),
      api.getVisionSettings(),
    ]).then(([r, status, modelsResp, thinkingResp, reasoningResp, visionResp]) => {
      setConnected(status.apis ?? {});
      setDefaults(modelsResp.defaults ?? {});
      setModel((modelsResp.models ?? {})[r.provider] ?? "");
      setThinkingLevel(thinkingResp.thinking_level ?? "off");
      setReasoningMode(reasoningResp.reasoning_mode ?? "off");
      setVisionSettings({
        preprocess: !!visionResp.preprocess,
        provider_order: visionResp.provider_order || "openrouter,claude,openai",
        openrouter_model: visionResp.openrouter_model || "nvidia/nemotron-nano-12b-v2-vl:free",
      });
      setLoading(false);
      setProvider(r.provider);
    });
    api.getAvailableModels().then(setAvailableModels).catch(() => setAvailableModels({ ollama: [] }));
  }, []);
  useEffect(() => {
    if (loading || !provider || Object.keys(connected).length === 0) return;
    const connectedIds = PROVIDER_IDS.filter(
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
  const saveThinking = (level: "off" | "minimal" | "low" | "medium" | "high" | "xhigh") => {
    setThinkingLevel(level);
    setSavingThinking(true);
    api.setThinking(level).finally(() => setSavingThinking(false));
  };
  const saveReasoning = (mode: "off" | "on" | "stream") => {
    setReasoningMode(mode);
    setSavingReasoning(true);
    api.setReasoning(mode).finally(() => setSavingReasoning(false));
  };
  const saveVision = async () => {
    setSavingVision(true);
    setVisionMsg(null);
    try {
      const saved = await api.setVisionSettings({
        preprocess: !!visionSettings.preprocess,
        provider_order: (visionSettings.provider_order || "").trim(),
        openrouter_model: (visionSettings.openrouter_model || "").trim(),
      });
      setVisionSettings(saved);
      setVisionMsg("Vision settings saved.");
    } catch (e) {
      setVisionMsg("Error: " + ((e as Error).message || "Failed to save"));
    } finally {
      setSavingVision(false);
    }
  };
  const connectedProviders = PROVIDER_IDS.filter(
    (id) => connected[PROVIDER_STATUS_KEYS[id]]
  );
  if (loading) return <p style={{ color: "var(--muted)" }}>Loading…</p>;
  if (connectedProviders.length === 0) {
    return (
      <p className="help">
        No API connected yet. Add at least one key above (Groq, OpenRouter, etc.), save, then choose your default AI and model here.
      </p>
    );
  }
  const value = connectedProviders.includes(provider as typeof connectedProviders[number]) ? provider : connectedProviders[0];
  const defaultModel = defaults[provider] ?? "";
  const isClaudeProvider = provider === "claude";
  const ollamaList = availableModels.ollama || [];
  const isOllamaProvider = provider === "ollama";
  const ollamaSelectValue = resolveOllamaSelectValue(model, ollamaList);
  const isKnownClaudePreset = CLAUDE_MODEL_PRESETS.some((p) => p.value === model);
  const claudePresetValue = isKnownClaudePreset ? model : (model.trim() ? CLAUDE_CUSTOM_MODEL : "");
  const pickClaudeModel = (picked: string) => {
    if (picked === CLAUDE_CUSTOM_MODEL) return;
    setModel(picked);
    setSavingModel(true);
    api.setModel("claude", picked.trim()).finally(() => setSavingModel(false));
  };
  const pickOllamaModel = (picked: string) => {
    if (picked === OLLAMA_CUSTOM_MODEL) return;
    const nextModel = picked === OLLAMA_DEFAULT_MODEL ? "" : picked;
    setModel(nextModel);
    setSavingModel(true);
    api.setModel("ollama", nextModel.trim()).finally(() => setSavingModel(false));
  };
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
          <label className="label" htmlFor="thinking-level-select">Thinking level</label>
          <span className="help">Used across chat + channels</span>
        </div>
        <div className="actions" style={{ gap: "0.5rem", alignItems: "center" }}>
          <select
            id="thinking-level-select"
            value={thinkingLevel}
            onChange={(e) => saveThinking(e.target.value as "off" | "minimal" | "low" | "medium" | "high" | "xhigh")}
            className="select"
            style={{ maxWidth: 220 }}
          >
            <option value="off">Off</option>
            <option value="minimal">Minimal</option>
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
            <option value="xhigh">XHigh</option>
          </select>
          {savingThinking && <span className="help">Saving…</span>}
        </div>
        <p className="help" style={{ marginTop: "0.35rem" }}>
          Higher levels spend more effort before replying, especially for tool-heavy tasks. `minimal` is a lightweight nudge; `xhigh` is the deepest mode.
        </p>
      </div>
      <div className="field">
        <div className="field-row">
          <label className="label" htmlFor="reasoning-mode-select">Reasoning visibility</label>
          <span className="help">Off by default</span>
        </div>
        <div className="actions" style={{ gap: "0.5rem", alignItems: "center" }}>
          <select
            id="reasoning-mode-select"
            value={reasoningMode}
            onChange={(e) => saveReasoning(e.target.value as "off" | "on" | "stream")}
            className="select"
            style={{ maxWidth: 220 }}
          >
            <option value="off">Off</option>
            <option value="on">On</option>
            <option value="stream">Stream</option>
          </select>
          {savingReasoning && <span className="help">Saving…</span>}
        </div>
        <p className="help" style={{ marginTop: "0.35rem" }}>
          Shows a short “Reasoning:” section when available. Stream mode sends reasoning as live status updates.
        </p>
      </div>
      <div className="field">
        <div className="field-row">
          <label className="label" htmlFor="default-ai-model">Model (optional)</label>
          {defaultModel && <span className="help">default: {defaultModel}</span>}
        </div>
        {isClaudeProvider && (
          <div style={{ marginBottom: "0.5rem", maxWidth: 420 }}>
            <select
              id="default-ai-claude-preset"
              value={claudePresetValue}
              onChange={(e) => pickClaudeModel(e.target.value)}
              className="select"
              style={{ width: "100%" }}
            >
              {CLAUDE_MODEL_PRESETS.map((preset) => (
                <option key={preset.value || "__default__"} value={preset.value}>
                  {preset.label}
                </option>
              ))}
              <option value={CLAUDE_CUSTOM_MODEL}>Custom model ID (manual input below)</option>
            </select>
          </div>
        )}
        {isOllamaProvider && ollamaList.length > 0 && (
          <div style={{ marginBottom: "0.5rem", maxWidth: 420 }}>
            <select
              id="default-ai-ollama-select"
              value={ollamaSelectValue}
              onChange={(e) => pickOllamaModel(e.target.value)}
              className="select"
              style={{ width: "100%" }}
            >
              <option value={OLLAMA_DEFAULT_MODEL}>Use provider default</option>
              {ollamaList.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
              <option value={OLLAMA_CUSTOM_MODEL}>Custom model/tag (manual input below)</option>
            </select>
          </div>
        )}
        <div className="actions" style={{ flexWrap: "wrap", gap: "0.5rem" }}>
          <input
            id="default-ai-model"
            type="text"
            placeholder={
              provider === "openrouter"
                ? "e.g. anthropic/claude-3.5-sonnet or model,fallback (comma-separated)"
                : provider === "ollama"
                  ? "Custom Ollama model/tag (optional)"
                : provider === "claude"
                  ? "e.g. claude-haiku-4-5-20251001"
                  : (defaultModel || "e.g. llama-3.3-70b-versatile")
            }
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
        {provider === "ollama" && ollamaList.length > 0 && (
          <p className="help" style={{ marginTop: "0.35rem" }}>
            Pick from installed models using the dropdown, or type a custom tag manually.
          </p>
        )}
        <p className="help" style={{ marginTop: "0.35rem" }}>
          Leave blank to use the provider default. For OpenRouter, use a model ID from{" "}
          <a href="https://openrouter.ai/models" target="_blank" rel="noreferrer" className="link">openrouter.ai/models</a>.
          {provider === "claude" ? " You can also pick a Claude preset above, then override with a custom model ID." : ""}
          {provider === "ollama" ? " You can pick from local models using the dropdown above, or type any Ollama model/tag manually." : ""}
        </p>
      </div>
      <div className="field">
        <div className="field-row">
          <label className="label" htmlFor="vision-preprocess-toggle">Vision controls</label>
          <span className="help">Image analysis path</span>
        </div>
        <label style={{ display: "inline-flex", gap: "0.5rem", alignItems: "center", marginBottom: "0.5rem" }}>
          <input
            id="vision-preprocess-toggle"
            type="checkbox"
            checked={!!visionSettings.preprocess}
            onChange={(e) => setVisionSettings((v) => ({ ...v, preprocess: e.target.checked }))}
          />
          <span>Preprocess screenshots before vision analysis</span>
        </label>
        <div className="field" style={{ marginBottom: "0.5rem" }}>
          <label className="label" htmlFor="vision-provider-order">Provider order</label>
          <input
            id="vision-provider-order"
            type="text"
            className="input"
            value={visionSettings.provider_order}
            onChange={(e) => setVisionSettings((v) => ({ ...v, provider_order: e.target.value }))}
            placeholder="openrouter,claude,openai"
            style={{ maxWidth: 420 }}
          />
          <p className="help" style={{ marginTop: "0.35rem" }}>
            Comma-separated order: <code>openrouter</code>, <code>claude</code>, <code>openai</code>.
          </p>
        </div>
        <div className="field" style={{ marginBottom: "0.5rem" }}>
          <label className="label" htmlFor="vision-openrouter-model">OpenRouter vision model</label>
          <input
            id="vision-openrouter-model"
            type="text"
            className="input"
            value={visionSettings.openrouter_model}
            onChange={(e) => setVisionSettings((v) => ({ ...v, openrouter_model: e.target.value }))}
            placeholder="nvidia/nemotron-nano-12b-v2-vl:free"
            style={{ maxWidth: 420 }}
          />
        </div>
        <div className="actions" style={{ gap: "0.5rem", alignItems: "center" }}>
          <button type="button" onClick={saveVision} disabled={savingVision} className="btn btn-secondary">
            {savingVision ? "Saving…" : "Save vision settings"}
          </button>
          {visionMsg && <span className={visionMsg.startsWith("Error:") ? "status-pending" : "status-ok"}>{visionMsg}</span>}
        </div>
      </div>
    </div>
  );
}

function FallbackProviderSelect() {
  const [fallbackCsv, setFallbackCsv] = useState("");
  const [defaultProvider, setDefaultProvider] = useState("");
  const [connected, setConnected] = useState<Record<string, boolean>>({});
  const [models, setModels] = useState<Record<string, string>>({});
  const [defaults, setDefaults] = useState<Record<string, string>>({});
  const [availableModels, setAvailableModels] = useState<{ ollama: string[] }>({ ollama: [] });
  const [loading, setLoading] = useState(true);
  const [savingOrder, setSavingOrder] = useState(false);
  const [savingModelFor, setSavingModelFor] = useState<ProviderId | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      api.getFallbackProviders(),
      api.getDefaultAi(),
      api.status(),
      api.getModels(),
      api.getAvailableModels(),
    ]).then(([fb, ai, status, modelsResp, availableResp]) => {
      setFallbackCsv(fb.providers || "");
      setDefaultProvider(ai.provider);
      setConnected(status.apis ?? {});
      setModels(modelsResp.models ?? {});
      setDefaults(modelsResp.defaults ?? {});
      setAvailableModels(availableResp ?? { ollama: [] });
      setLoading(false);
    });
  }, []);

  const connectedProviders: ProviderId[] = PROVIDER_IDS.filter(
    (id) => connected[PROVIDER_STATUS_KEYS[id]] && id !== defaultProvider
  );

  const selected: ProviderId[] = fallbackCsv
    .split(",")
    .map((s) => s.trim())
    .filter((s): s is ProviderId => !!s && connectedProviders.includes(s as ProviderId));

  const saveOrder = async (next: ProviderId[]) => {
    const csv = next.join(",");
    setFallbackCsv(csv);
    setSavingOrder(true);
    setMsg(null);
    try {
      await api.setFallbackProviders(csv);
      setMsg(next.length ? `Fallback order: ${next.map((p) => DEFAULT_AI_LABELS[p]).join(" -> ")}` : "Auto-detect (all available keys)");
    } catch {
      setMsg("Failed to save fallback order.");
    } finally {
      setSavingOrder(false);
    }
  };

  const toggle = (provider: ProviderId) => {
    let next: string[];
    if (selected.includes(provider)) {
      next = selected.filter((p) => p !== provider);
    } else {
      next = [...selected, provider];
    }
    void saveOrder(next as ProviderId[]);
  };

  const saveProviderModel = async (provider: ProviderId, overrideModel?: string) => {
    const rawValue = overrideModel ?? models[provider] ?? "";
    const value = rawValue.trim();
    if (overrideModel !== undefined) {
      setModels((m) => ({ ...m, [provider]: rawValue }));
    }
    setSavingModelFor(provider);
    setMsg(null);
    try {
      await api.setModel(provider, value);
      setMsg(`${DEFAULT_AI_LABELS[provider]} model saved.`);
    } catch {
      setMsg(`Failed to save ${DEFAULT_AI_LABELS[provider]} model.`);
    } finally {
      setSavingModelFor(null);
    }
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
              disabled={savingOrder || !!savingModelFor}
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
      {selected.length > 0 && (
        <div style={{ marginTop: "1rem" }}>
          <h4 style={{ margin: "0 0 0.4rem 0" }}>Fallback model per provider</h4>
          <p className="help" style={{ marginBottom: "0.5rem" }}>
            Each fallback provider can use its own model.
          </p>
          {selected.map((id) => (
            <div key={"fallback-model-" + id} className="field">
              <div className="field-row">
                <label className="label" htmlFor={"fallback-model-" + id}>
                  {DEFAULT_AI_LABELS[id]}
                </label>
                <span className="help">default: {defaults[id] ?? "—"}</span>
              </div>
              <div className="actions" style={{ flexWrap: "wrap", gap: "0.5rem" }}>
                {id === "ollama" && availableModels.ollama.length > 0 && (
                  <select
                    id={"fallback-model-select-" + id}
                    value={resolveOllamaSelectValue(models[id] ?? "", availableModels.ollama)}
                    onChange={(e) => {
                      const picked = e.target.value;
                      if (picked === OLLAMA_CUSTOM_MODEL) return;
                      const next = picked === OLLAMA_DEFAULT_MODEL ? "" : picked;
                      void saveProviderModel(id, next);
                    }}
                    className="select"
                    style={{ maxWidth: 420, flex: "1 1 220px" }}
                  >
                    <option value={OLLAMA_DEFAULT_MODEL}>Use provider default</option>
                    {availableModels.ollama.map((name) => (
                      <option key={name} value={name}>
                        {name}
                      </option>
                    ))}
                    <option value={OLLAMA_CUSTOM_MODEL}>Custom model/tag (manual input below)</option>
                  </select>
                )}
                <input
                  id={"fallback-model-" + id}
                  type="text"
                  placeholder={
                    id === "openrouter"
                      ? "main-model, fallback1, fallback2 (comma-separated)"
                      : id === "ollama"
                        ? "Custom Ollama model/tag (optional)"
                      : (defaults[id] ?? "Optional model override")
                  }
                  value={models[id] ?? ""}
                  onChange={(e) => setModels((m) => ({ ...m, [id]: e.target.value }))}
                  onBlur={() => void saveProviderModel(id)}
                  className="input"
                  style={{ maxWidth: 420, flex: "1 1 220px" }}
                />
                <button
                  type="button"
                  onClick={() => void saveProviderModel(id)}
                  disabled={!!savingModelFor}
                  className="btn btn-secondary"
                >
                  {savingModelFor === id ? "Saving…" : "Save model"}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
      {msg && (
        <p
          className="help"
          style={{ marginTop: "0.5rem", color: msg.startsWith("Failed") ? "var(--error)" : "var(--success)" }}
        >
          {msg}
        </p>
      )}
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
      <p className="help" style={{ marginBottom: "1rem" }}>
        Organized by setup phase so you can do first-time setup quickly, then tune integrations and maintenance settings.
      </p>

      <div className="settings-jump-links">
        <a href="#settings-core" className="settings-jump-link">1. Core setup</a>
        <a href="#settings-integrations" className="settings-jump-link">2. Integrations</a>
        <a href="#settings-system" className="settings-jump-link">3. System help</a>
      </div>

      <div className="settings-group" id="settings-core">
        <div className="settings-group-head">
          <h2 className="settings-group-title">1. Core setup</h2>
          <p className="help">Connect providers and choose how Asta thinks across chat and channels.</p>
        </div>
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
        </div>
      </div>

      <div className="settings-group" id="settings-integrations">
        <div className="settings-group-head">
          <h2 className="settings-group-title">2. Integrations</h2>
          <p className="help">Connect optional services and automation flows.</p>
        </div>
        <div className="accordion">
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
        </div>
      </div>

      <div className="settings-group" id="settings-system">
        <div className="settings-group-head">
          <h2 className="settings-group-title">3. System help</h2>
          <p className="help">Troubleshooting and quick reference.</p>
        </div>
        <div className="accordion">
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
    </div>
  );
}
