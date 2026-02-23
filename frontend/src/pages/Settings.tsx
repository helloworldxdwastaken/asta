import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import type { CronJob, ProviderFlow } from "../api/client";
import { api } from "../api/client";

/** Logo URL or fallback initial for provider cards */
const PROVIDER_LOGOS: Record<string, { url: string; initial: string }> = {
  groq: { url: "https://groq.com/favicon.ico", initial: "G" },
  google: { url: "https://www.google.com/favicon.ico", initial: "G" },
  claude: { url: "https://anthropic.com/favicon.ico", initial: "C" },
  openai: { url: "https://openai.com/favicon.ico", initial: "O" },
  openrouter: { url: "https://openrouter.ai/favicon.ico", initial: "R" },
  ollama: { url: "https://ollama.com/favicon.ico", initial: "O" },
  giphy: { url: "https://giphy.com/favicon.ico", initial: "G" },
  notion: { url: "https://www.notion.so/images/favicon.ico", initial: "N" },
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
  { id: "notion", name: "Notion", key: "notion_api_key", logoKey: "notion", getKeyUrl: "https://notion.so/my-integrations" },
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
        <div className={isError ? "alert alert-error settings-alert-top" : "alert settings-alert-top"}>
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
            className="input settings-input-sm"
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
            className="input settings-input-md"
          />
        </div>
        <div className="actions">
          <button type="button" onClick={handleSave} disabled={saving} className="btn btn-primary">
            {saving ? "Saving…" : "Save schedule"}
          </button>
        </div>
        {message && <div className={message.startsWith("Error") ? "alert alert-error settings-alert-top" : "alert settings-alert-top"}>{message}</div>}
        <p className="help settings-help-gap-sm">
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

const MAIN_PROVIDER_IDS = ["claude", "ollama", "openrouter"] as const;
type MainProviderId = (typeof MAIN_PROVIDER_IDS)[number];
const MAIN_PROVIDER_LABELS: Record<MainProviderId, string> = {
  claude: "Claude",
  ollama: "Ollama",
  openrouter: "OpenRouter",
};

const CLAUDE_CUSTOM_MODEL = "__custom__";
const CLAUDE_MODEL_PRESETS: Array<{ label: string; value: string }> = [
  { label: "Use provider default", value: "" },
  { label: "Claude 3.5 Sonnet (stable)", value: "claude-3-5-sonnet-20241022" },
  { label: "Claude 3.5 Haiku (fast)", value: "claude-3-5-haiku-20241022" },
];
const OLLAMA_DEFAULT_MODEL = "__provider_default__";
const OLLAMA_CUSTOM_MODEL = "__custom_model__";
const OPENROUTER_CUSTOM_MODEL = "__custom_openrouter__";
const FIXED_VISION_MODEL = "nvidia/nemotron-nano-12b-v2-vl:free";
const OPENROUTER_MODEL_PRESETS: Array<{ label: string; value: string }> = [
  { label: "Kimi K2.5 (tools)", value: "moonshotai/kimi-k2.5" },
  { label: "Kimi K2 Thinking (tools)", value: "moonshotai/kimi-k2-thinking" },
  { label: "Trinity Large Preview (free)", value: "arcee-ai/trinity-large-preview:free" },
  { label: "Kimi -> Trinity fallback", value: "moonshotai/kimi-k2.5,arcee-ai/trinity-large-preview:free" },
];

function resolveOllamaSelectValue(model: string, ollamaList: string[]): string {
  const trimmed = model.trim();
  if (!trimmed) return OLLAMA_DEFAULT_MODEL;
  const matched = ollamaList.find((name) => name === trimmed || name.startsWith(trimmed + ":"));
  return matched ?? OLLAMA_CUSTOM_MODEL;
}

function resolveOpenRouterSelectValue(model: string, presets: string[]): string {
  const trimmed = model.trim();
  if (!trimmed) return presets[0] ?? OPENROUTER_CUSTOM_MODEL;
  return presets.includes(trimmed) ? trimmed : OPENROUTER_CUSTOM_MODEL;
}

function formatProviderDisableReason(reason: string): string {
  const key = (reason || "").trim().toLowerCase();
  if (key === "billing") return "Auto-disabled: billing / credits issue";
  if (key === "auth") return "Auto-disabled: auth/key issue";
  if (!key) return "Auto-disabled";
  return `Auto-disabled: ${key}`;
}

function DefaultAiSelect() {
  const [provider, setProvider] = useState<MainProviderId>("claude");
  const [model, setModel] = useState("");
  const [models, setModels] = useState<Record<string, string>>({});
  const [thinkingLevel, setThinkingLevel] = useState<"off" | "minimal" | "low" | "medium" | "high" | "xhigh">("off");
  const [reasoningMode, setReasoningMode] = useState<"off" | "on" | "stream">("off");
  const [finalMode, setFinalMode] = useState<"off" | "strict">("off");
  const [visionPreprocess, setVisionPreprocess] = useState(true);
  const [providerFlow, setProviderFlow] = useState<ProviderFlow | null>(null);
  const [availableModels, setAvailableModels] = useState<{ ollama: string[]; openrouter?: string[] }>({ ollama: [] });
  const [defaults, setDefaults] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [savingModel, setSavingModel] = useState(false);
  const [savingThinking, setSavingThinking] = useState(false);
  const [savingReasoning, setSavingReasoning] = useState(false);
  const [savingFinalMode, setSavingFinalMode] = useState(false);
  const [savingVision, setSavingVision] = useState(false);
  const [visionMsg, setVisionMsg] = useState<string | null>(null);
  const refresh = async () => {
    const [
      defaultResp,
      modelsResp,
      thinkingResp,
      reasoningResp,
      finalModeResp,
      visionResp,
      flowResp,
      availableResp,
    ] = await Promise.allSettled([
      api.getDefaultAi(),
      api.getModels(),
      api.getThinking(),
      api.getReasoning(),
      api.getFinalMode(),
      api.getVisionSettings(),
      api.getProviderFlow(),
      api.getAvailableModels(),
    ]);
    if (defaultResp.status !== "fulfilled") {
      throw new Error("Default AI provider settings unavailable");
    }
    const nextProvider = (defaultResp.value.provider || "claude") as MainProviderId;
    setProvider(nextProvider);
    const nextModels = modelsResp.status === "fulfilled" ? (modelsResp.value.models ?? {}) : {};
    const nextDefaults = modelsResp.status === "fulfilled" ? (modelsResp.value.defaults ?? {}) : {};
    setModels(nextModels);
    setDefaults(nextDefaults);
    setModel(nextModels[nextProvider] ?? "");
    setThinkingLevel(thinkingResp.status === "fulfilled" ? (thinkingResp.value.thinking_level ?? "off") : "off");
    setReasoningMode(reasoningResp.status === "fulfilled" ? (reasoningResp.value.reasoning_mode ?? "off") : "off");
    setFinalMode(finalModeResp.status === "fulfilled" ? (finalModeResp.value.final_mode ?? "off") : "off");
    setVisionPreprocess(visionResp.status === "fulfilled" ? !!visionResp.value.preprocess : true);
    setProviderFlow(flowResp.status === "fulfilled" ? flowResp.value : null);
    setAvailableModels(availableResp.status === "fulfilled" ? (availableResp.value ?? { ollama: [] }) : { ollama: [] });
  };
  useEffect(() => {
    refresh()
      .catch(() => {
        setProviderFlow(null);
      })
      .finally(() => setLoading(false));
  }, []);
  useEffect(() => {
    setModel(models[provider] ?? "");
  }, [provider, models]);
  useEffect(() => {
    if (!providerFlow) return;
    const active = providerFlow.providers.filter((p) => p.active).map((p) => p.provider as MainProviderId);
    const connected = providerFlow.providers
      .filter((p) => p.connected && p.enabled)
      .map((p) => p.provider as MainProviderId);
    const options: MainProviderId[] =
      active.length > 0
        ? active
        : connected.length > 0
          ? connected
          : providerFlow.providers.map((p) => p.provider as MainProviderId);
    if (options.length === 0 || options.includes(provider)) return;
    const fallback = options[0];
    setProvider(fallback);
    api.setDefaultAi(fallback).catch(() => { });
  }, [providerFlow, provider]);
  const change = (p: MainProviderId) => {
    const previous = provider;
    setProvider(p);
    api.setDefaultAi(p).catch(() => setProvider(previous));
  };
  const saveModel = () => {
    if (!provider) return;
    const trimmed = model.trim();
    setSavingModel(true);
    api.setModel(provider, trimmed).then(() => {
      setModels((prev) => ({ ...prev, [provider]: trimmed }));
    }).finally(() => setSavingModel(false));
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
  const saveFinalMode = (mode: "off" | "strict") => {
    setFinalMode(mode);
    setSavingFinalMode(true);
    api.setFinalMode(mode).finally(() => setSavingFinalMode(false));
  };
  const saveVision = async () => {
    setSavingVision(true);
    setVisionMsg(null);
    try {
      await api.setVisionSettings({
        preprocess: !!visionPreprocess,
        provider_order: "openrouter,claude,openai",
        openrouter_model: FIXED_VISION_MODEL,
      });
      setVisionMsg("Vision settings saved.");
    } catch (e) {
      setVisionMsg("Error: " + ((e as Error).message || "Failed to save"));
    } finally {
      setSavingVision(false);
    }
  };
  if (loading) return <p className="settings-loading">Loading…</p>;
  const flowProviders = providerFlow?.providers ?? [];
  const activeOptions = flowProviders.filter((p) => p.active).map((p) => p.provider as MainProviderId);
  const connectedEnabledOptions = flowProviders
    .filter((p) => p.connected && p.enabled)
    .map((p) => p.provider as MainProviderId);
  const selectableProviders: MainProviderId[] =
    activeOptions.length > 0
      ? activeOptions
      : connectedEnabledOptions.length > 0
        ? connectedEnabledOptions
        : flowProviders.map((p) => p.provider as MainProviderId);
  if (selectableProviders.length === 0) {
    return (
      <p className="help">
        No main AI provider is connected yet. Set up Claude, Ollama, or OpenRouter first.
      </p>
    );
  }
  const value = selectableProviders.includes(provider) ? provider : selectableProviders[0];
  const defaultModel = defaults[provider] ?? "";
  const isClaudeProvider = provider === "claude";
  const ollamaList = availableModels.ollama || [];
  const openrouterList = (availableModels.openrouter && availableModels.openrouter.length > 0)
    ? availableModels.openrouter
    : OPENROUTER_MODEL_PRESETS.map((p) => p.value);
  const isOllamaProvider = provider === "ollama";
  const isOpenRouterProvider = provider === "openrouter";
  const ollamaSelectValue = resolveOllamaSelectValue(model, ollamaList);
  const openrouterSelectValue = resolveOpenRouterSelectValue(model, openrouterList);
  const isKnownClaudePreset = CLAUDE_MODEL_PRESETS.some((p) => p.value === model);
  const claudePresetValue = isKnownClaudePreset ? model : (model.trim() ? CLAUDE_CUSTOM_MODEL : "");
  const pickClaudeModel = (picked: string) => {
    if (picked === CLAUDE_CUSTOM_MODEL) return;
    const trimmed = picked.trim();
    setModel(picked);
    setSavingModel(true);
    api.setModel("claude", trimmed).then(() => {
      setModels((prev) => ({ ...prev, claude: trimmed }));
    }).finally(() => setSavingModel(false));
  };
  const pickOllamaModel = (picked: string) => {
    if (picked === OLLAMA_CUSTOM_MODEL) return;
    const nextModel = picked === OLLAMA_DEFAULT_MODEL ? "" : picked;
    const trimmed = nextModel.trim();
    setModel(nextModel);
    setSavingModel(true);
    api.setModel("ollama", trimmed).then(() => {
      setModels((prev) => ({ ...prev, ollama: trimmed }));
    }).finally(() => setSavingModel(false));
  };
  const pickOpenRouterModel = (picked: string) => {
    if (picked === OPENROUTER_CUSTOM_MODEL) return;
    const trimmed = picked.trim();
    setModel(picked);
    setSavingModel(true);
    api.setModel("openrouter", trimmed).then(() => {
      setModels((prev) => ({ ...prev, openrouter: trimmed }));
    }).finally(() => setSavingModel(false));
  };
  return (
    <div>
      <div className="field">
        <label className="label" htmlFor="default-ai-select">Default AI provider</label>
        <select
          id="default-ai-select"
          value={value}
          onChange={(e) => change(e.target.value as MainProviderId)}
          className="select settings-input-provider"
        >
          {selectableProviders.map((id) => (
            <option key={id} value={id}>
              {MAIN_PROVIDER_LABELS[id]}
            </option>
          ))}
        </select>
        <p className="help settings-help-gap-xs">Fallback order is fixed for now: Claude -&gt; Ollama -&gt; OpenRouter.</p>
      </div>
      <div className="field">
        <div className="field-row">
          <label className="label" htmlFor="thinking-level-select">Thinking level</label>
          <span className="help">Used across chat + channels</span>
        </div>
        <div className="actions settings-inline-controls">
          <select
            id="thinking-level-select"
            value={thinkingLevel}
            onChange={(e) => saveThinking(e.target.value as "off" | "minimal" | "low" | "medium" | "high" | "xhigh")}
            className="select settings-input-sm"
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
        <p className="help settings-help-gap-xs">
          Higher levels spend more effort before replying, especially for tool-heavy tasks. `minimal` is a lightweight nudge; `xhigh` is the deepest mode.
        </p>
      </div>
      <div className="field">
        <div className="field-row">
          <label className="label" htmlFor="reasoning-mode-select">Reasoning visibility</label>
          <span className="help">Off by default</span>
        </div>
        <div className="actions settings-inline-controls">
          <select
            id="reasoning-mode-select"
            value={reasoningMode}
            onChange={(e) => saveReasoning(e.target.value as "off" | "on" | "stream")}
            className="select settings-input-sm"
          >
            <option value="off">Off</option>
            <option value="on">On</option>
            <option value="stream">Stream</option>
          </select>
          {savingReasoning && <span className="help">Saving…</span>}
        </div>
        <p className="help settings-help-gap-xs">
          Shows a short “Reasoning:” section when available. Stream mode sends reasoning as live status updates.
        </p>
      </div>
      <div className="field">
        <div className="field-row">
          <label className="label" htmlFor="final-mode-select">Final tag mode</label>
          <span className="help">OpenClaw strict mode</span>
        </div>
        <div className="actions settings-inline-controls">
          <select
            id="final-mode-select"
            value={finalMode}
            onChange={(e) => saveFinalMode(e.target.value as "off" | "strict")}
            className="select settings-input-sm"
          >
            <option value="off">Off</option>
            <option value="strict">Strict</option>
          </select>
          {savingFinalMode && <span className="help">Saving…</span>}
        </div>
        <p className="help settings-help-gap-xs">
          Strict mode only shows text inside <code>&lt;final&gt;...&lt;/final&gt;</code>. Text outside final tags is suppressed.
        </p>
      </div>
      <div className="field">
        <div className="field-row">
          <label className="label" htmlFor="default-ai-model">Model (optional)</label>
          {defaultModel && <span className="help">default: {defaultModel}</span>}
        </div>
        {isClaudeProvider && (
          <div className="settings-input-block settings-input-lg">
            <select
              id="default-ai-claude-preset"
              value={claudePresetValue}
              onChange={(e) => pickClaudeModel(e.target.value)}
              className="select settings-full-width"
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
          <div className="settings-input-block settings-input-lg">
            <select
              id="default-ai-ollama-select"
              value={ollamaSelectValue}
              onChange={(e) => pickOllamaModel(e.target.value)}
              className="select settings-full-width"
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
        {isOpenRouterProvider && openrouterList.length > 0 && (
          <div className="settings-input-block settings-input-lg">
            <select
              id="default-ai-openrouter-select"
              value={openrouterSelectValue}
              onChange={(e) => pickOpenRouterModel(e.target.value)}
              className="select settings-full-width"
            >
              {OPENROUTER_MODEL_PRESETS.map((preset) => (
                <option key={preset.value} value={preset.value}>
                  {preset.label}
                </option>
              ))}
              {openrouterList
                .filter((value) => !OPENROUTER_MODEL_PRESETS.some((preset) => preset.value === value))
                .map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              <option value={OPENROUTER_CUSTOM_MODEL}>Custom model ID (advanced)</option>
            </select>
          </div>
        )}
        <div className="actions settings-inline-controls settings-actions-wrap">
          <input
            id="default-ai-model"
            type="text"
            placeholder={
              provider === "openrouter"
                ? "Kimi/Trinity only (comma-separated fallback allowed)"
                : provider === "ollama"
                  ? "Custom Ollama model/tag (optional)"
                  : provider === "claude"
                    ? "e.g. claude-haiku-4-5-20251001"
                    : (defaultModel || "e.g. llama-3.3-70b-versatile")
            }
            value={model}
            onChange={(e) => setModel(e.target.value)}
            onBlur={saveModel}
            className="input settings-input-lg settings-input-flex"
          />
          <button type="button" onClick={saveModel} disabled={savingModel} className="btn btn-secondary">
            {savingModel ? "Saving…" : "Save model"}
          </button>
        </div>
        {provider === "ollama" && ollamaList.length > 0 && (
          <p className="help settings-help-gap-xs">
            Pick from installed models using the dropdown, or type a custom tag manually.
          </p>
        )}
        <p className="help settings-help-gap-xs">
          Leave blank to use the provider default.
          {provider === "openrouter" ? " OpenRouter is restricted to Kimi/Trinity models for tool reliability." : ""}
          {provider !== "openrouter" && (
            <>
              {" "}For OpenRouter, use a model ID from{" "}
              <a href="https://openrouter.ai/models" target="_blank" rel="noreferrer" className="link">openrouter.ai/models</a>.
            </>
          )}
          {provider === "claude" ? " You can also pick a Claude preset above, then override with a custom model ID." : ""}
          {provider === "ollama" ? " You can pick from local models using the dropdown above, or type any Ollama model/tag manually." : ""}
        </p>
      </div>
      <div className="field">
        <div className="field-row">
          <label className="label" htmlFor="vision-preprocess-toggle">Vision (fixed model)</label>
          <span className="help">{FIXED_VISION_MODEL}</span>
        </div>
        <label className="settings-checkbox-row">
          <input
            id="vision-preprocess-toggle"
            type="checkbox"
            checked={!!visionPreprocess}
            onChange={(e) => setVisionPreprocess(e.target.checked)}
          />
          <span>Preprocess screenshots before vision analysis</span>
        </label>
        <div className="actions settings-inline-controls">
          <button type="button" onClick={saveVision} disabled={savingVision} className="btn btn-secondary">
            {savingVision ? "Saving…" : "Save vision settings"}
          </button>
          {visionMsg && <span className={visionMsg.startsWith("Error:") ? "status-pending" : "status-ok"}>{visionMsg}</span>}
        </div>
      </div>
    </div>
  );
}

const MAIN_PROVIDER_GET_KEY_URL: Record<MainProviderId, string> = {
  claude: "https://console.anthropic.com/settings/keys",
  ollama: "",
  openrouter: "https://openrouter.ai/keys",
};

function FallbackProviderSelect({
  keys = {},
  setKeys,
  keysStatus = {},
}: {
  keys?: Record<string, string>;
  setKeys?: React.Dispatch<React.SetStateAction<Record<string, string>>>;
  keysStatus?: Record<string, boolean>;
} = {}) {
  const [flow, setFlow] = useState<ProviderFlow | null>(null);
  const [models, setModels] = useState<Record<string, string>>({});
  const [defaults, setDefaults] = useState<Record<string, string>>({});
  const [availableModels, setAvailableModels] = useState<{ ollama: string[]; openrouter?: string[] }>({ ollama: [] });
  const [loading, setLoading] = useState(true);
  const [savingProvider, setSavingProvider] = useState<MainProviderId | null>(null);
  const [savingModelFor, setSavingModelFor] = useState<MainProviderId | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const keyFieldByProvider: Partial<Record<MainProviderId, string>> = { claude: "anthropic_api_key", openrouter: "openrouter_api_key" };

  const load = async () => {
    const [flowResp, modelsResp, availableResp] = await Promise.allSettled([
      api.getProviderFlow(),
      api.getModels(),
      api.getAvailableModels(),
    ]);
    if (flowResp.status !== "fulfilled") {
      throw flowResp.reason;
    }
    setFlow(flowResp.value);
    setModels(modelsResp.status === "fulfilled" ? (modelsResp.value.models ?? {}) : {});
    setDefaults(modelsResp.status === "fulfilled" ? (modelsResp.value.defaults ?? {}) : {});
    setAvailableModels(availableResp.status === "fulfilled" ? (availableResp.value ?? { ollama: [] }) : { ollama: [] });
  };

  useEffect(() => {
    load()
      .catch(() => {
        setFlow(null);
      })
      .finally(() => setLoading(false));
  }, []);

  const toggleProvider = async (provider: MainProviderId, enabled: boolean) => {
    setSavingProvider(provider);
    setMsg(null);
    try {
      await api.setProviderEnabled(provider, enabled);
      await load();
      setMsg(`${MAIN_PROVIDER_LABELS[provider]} ${enabled ? "enabled" : "disabled"}.`);
    } catch {
      setMsg(`Failed to update ${MAIN_PROVIDER_LABELS[provider]}.`);
    } finally {
      setSavingProvider(null);
    }
  };

  const saveProviderModel = async (provider: MainProviderId, overrideModel?: string) => {
    const rawValue = overrideModel ?? models[provider] ?? "";
    const value = rawValue.trim();
    if (overrideModel !== undefined) {
      setModels((m) => ({ ...m, [provider]: rawValue }));
    }
    setSavingModelFor(provider);
    setMsg(null);
    try {
      await api.setModel(provider, value);
      setMsg(`${MAIN_PROVIDER_LABELS[provider]} model saved.`);
    } catch {
      setMsg(`Failed to save ${MAIN_PROVIDER_LABELS[provider]} model.`);
    } finally {
      setSavingModelFor(null);
    }
  };

  if (loading) return <p className="settings-loading">Loading…</p>;
  if (!flow || flow.providers.length === 0) {
    return (
      <p className="help settings-help-gap-sm">
        Provider flow is unavailable right now.
      </p>
    );
  }

  return (
    <div className="settings-block-top">
      <div className="provider-cards">
        {flow.providers.map((entry) => {
          const id = entry.provider as MainProviderId;
          const isKnownClaudePreset = CLAUDE_MODEL_PRESETS.some((p) => p.value === (models[id] ?? ""));
          const claudePresetValue = isKnownClaudePreset
            ? (models[id] ?? "")
            : ((models[id] ?? "").trim() ? CLAUDE_CUSTOM_MODEL : "");
          const keyField = keyFieldByProvider[id];
          const keySet = keyField ? keysStatus[keyField] : false;
          return (
            <div key={"flow-provider-" + id} className="provider-card">
              <div className="provider-card-header">
                <ProviderLogo logoKey={id} size={36} />
                <div className="provider-card-title-wrap">
                  <span className="provider-card-title">
                    {entry.position}. {entry.label}
                  </span>
                  {entry.connected ? <span className="status-ok">Connected</span> : keySet ? <span className="status-ok">Key set</span> : <span className="status-pending">Not connected</span>}
                </div>
              </div>
              {keyField && setKeys && (
                <div className="provider-card-fields" style={{ marginBottom: "0.75rem" }}>
                  <div className="field">
                    <div className="field-row">
                      <label className="label" htmlFor={"flow-key-" + id}>API key</label>
                      {keysStatus[keyField] && <span className="status-ok">Set</span>}
                    </div>
                    <div className="actions settings-inline-controls settings-actions-wrap">
                      <input
                        id={"flow-key-" + id}
                        type="password"
                        placeholder={keysStatus[keyField] ? "Leave blank to keep current" : "Paste key"}
                        value={keys[keyField] ?? ""}
                        onChange={(e) => setKeys((k) => ({ ...k, [keyField]: e.target.value }))}
                        className="input settings-input-flex"
                      />
                    </div>
                    <p className="help provider-card-get-key">
                      Get your API key: <a href={MAIN_PROVIDER_GET_KEY_URL[id]} target="_blank" rel="noreferrer" className="link">{MAIN_PROVIDER_GET_KEY_URL[id]}</a>
                    </p>
                  </div>
                </div>
              )}
              <div className="field-row">
                <span className="help">
                  {entry.auto_disabled
                    ? formatProviderDisableReason(entry.disabled_reason)
                    : entry.enabled
                      ? "Enabled"
                      : "Disabled"}
                </span>
                <button
                  type="button"
                  onClick={() => void toggleProvider(id, !entry.enabled || entry.auto_disabled)}
                  disabled={!!savingProvider || !entry.connected}
                  className="btn btn-secondary"
                >
                  {savingProvider === id
                    ? "Saving…"
                    : (!entry.enabled || entry.auto_disabled)
                      ? "Enable"
                      : "Disable"}
                </button>
              </div>
              <div className="field">
                <div className="field-row">
                  <label className="label" htmlFor={"flow-model-" + id}>Model</label>
                  <span className="help">default: {defaults[id] ?? entry.default_model ?? "—"}</span>
                </div>
                <div className="actions settings-inline-controls settings-actions-wrap">
                  {id === "claude" && (
                    <select
                      id={"flow-claude-select-" + id}
                      value={claudePresetValue}
                      onChange={(e) => {
                        const picked = e.target.value;
                        if (picked === CLAUDE_CUSTOM_MODEL) return;
                        void saveProviderModel(id, picked);
                      }}
                      className="select settings-input-lg settings-input-flex-wide"
                    >
                      {CLAUDE_MODEL_PRESETS.map((preset) => (
                        <option key={preset.value || "__default__"} value={preset.value}>
                          {preset.label}
                        </option>
                      ))}
                      <option value={CLAUDE_CUSTOM_MODEL}>Custom model ID (manual input below)</option>
                    </select>
                  )}
                  {id === "ollama" && availableModels.ollama.length > 0 && (
                    <select
                      id={"flow-ollama-select-" + id}
                      value={resolveOllamaSelectValue(models[id] ?? "", availableModels.ollama)}
                      onChange={(e) => {
                        const picked = e.target.value;
                        if (picked === OLLAMA_CUSTOM_MODEL) return;
                        const next = picked === OLLAMA_DEFAULT_MODEL ? "" : picked;
                        void saveProviderModel(id, next);
                      }}
                      className="select settings-input-lg settings-input-flex-wide"
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
                  {id === "openrouter" && (
                    <select
                      id={"flow-openrouter-select-" + id}
                      value={resolveOpenRouterSelectValue(models[id] ?? "", OPENROUTER_MODEL_PRESETS.map((p) => p.value))}
                      onChange={(e) => {
                        const picked = e.target.value;
                        if (picked === OPENROUTER_CUSTOM_MODEL) return;
                        void saveProviderModel(id, picked);
                      }}
                      className="select settings-input-lg settings-input-flex-wide"
                    >
                      {OPENROUTER_MODEL_PRESETS.map((preset) => (
                        <option key={preset.value} value={preset.value}>
                          {preset.label}
                        </option>
                      ))}
                      <option value={OPENROUTER_CUSTOM_MODEL}>Custom model ID (advanced)</option>
                    </select>
                  )}
                  <input
                    id={"flow-model-" + id}
                    type="text"
                    placeholder={
                      id === "openrouter"
                        ? "Kimi/Trinity only (comma-separated)"
                        : id === "ollama"
                          ? "Custom Ollama model/tag (optional)"
                          : (defaults[id] ?? "Optional model override")
                    }
                    value={models[id] ?? ""}
                    onChange={(e) => setModels((m) => ({ ...m, [id]: e.target.value }))}
                    onBlur={() => void saveProviderModel(id)}
                    className="input settings-input-lg settings-input-flex-wide"
                  />
                  <button
                    type="button"
                    onClick={() => void saveProviderModel(id)}
                    disabled={!!savingModelFor || !entry.connected}
                    className="btn btn-secondary"
                  >
                    {savingModelFor === id ? "Saving…" : "Save model"}
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>
      {msg && (
        <p className={msg.startsWith("Failed") ? "help settings-help-gap-sm settings-status-error" : "help settings-help-gap-sm settings-status-success"}>
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
        <div className="alert settings-alert-bottom">
          <p className="settings-inline-links">
            <a href={setup.dashboard_url} target="_blank" rel="noreferrer" className="link">Spotify Developer Dashboard</a>
            {" · "}
            <a href={setup.docs_url} target="_blank" rel="noreferrer" className="link">Web API docs</a>
          </p>
          <ol className="help settings-steps-list">
            {setup.steps.map((step, i) => (
              <li
                key={i}
                className="settings-steps-item"
                dangerouslySetInnerHTML={{ __html: step.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>") }}
              />
            ))}
            {spotifyConnected !== true && setup.connect_url && (
              <li className="settings-steps-item">
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
          className="input settings-input-lg"
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
          className="input settings-input-lg"
        />
      </div>
      <div className="actions">
        <button type="button" onClick={save} disabled={saving} className="btn btn-primary">
          {saving ? "Saving…" : "Save Spotify credentials"}
        </button>
        <TestSpotifyButton />
      </div>
      {msg && <div className="alert settings-alert-top">{msg}</div>}
      <div className="settings-block-top">
        <p className="help settings-help-bottom-sm">
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
    <div className="settings-page">
      <h1 className="page-title">Settings</h1>
      <p className="help settings-page-intro">
        Organized by setup phase so you can do first-time setup quickly, then tune integrations and maintenance settings.
      </p>

      <div className="settings-layout">
        <aside className="settings-sidebar">
          <div className="settings-nav-card">
            <p className="settings-nav-title">Jump to section</p>
            <div className="settings-jump-links">
              <a href="#settings-core" className="settings-jump-link">1. Core setup</a>
              <a href="#settings-integrations" className="settings-jump-link">2. Integrations</a>
              <a href="#settings-system" className="settings-jump-link">3. System help</a>
            </div>
          </div>
        </aside>

        <div className="settings-main">
          <div className="settings-group" id="settings-core">
            <div className="settings-group-head">
              <h2 className="settings-group-title">1. Core setup</h2>
              <p className="help">Connect providers and choose how Asta thinks across chat and channels.</p>
            </div>
            <div className="accordion">
              <details open>
                <summary>
                  <span>API keys & default AI</span>
                  <span className="acc-meta">Connect services and choose who answers</span>
                </summary>
                <div className="acc-body">
                  <p className="help settings-help-bottom">
                    API keys let Asta use each service (Claude, OpenAI, etc.). Pick a <strong>default AI</strong> for chat and channels, then add keys and turn providers on or off. Keys are stored locally (<code>backend/asta.db</code>). Restart the backend if you change the Telegram token.
                  </p>
                  <RestartBackendButton />

                  <h3 className="settings-section-title">Default AI</h3>
                  <p className="help settings-help-bottom-sm">Which AI answers by default in Chat, WhatsApp, and Telegram.</p>
                  <DefaultAiSelect />

                  <h3 className="settings-section-title settings-subhead-gap">Main AI providers (Claude, Ollama, OpenRouter)</h3>
                  <p className="help settings-help-bottom-sm">
                    Order is fixed. Add your API key for each, then enable or disable. Ollama needs no key (runs locally).
                  </p>
                  <FallbackProviderSelect keys={keys} setKeys={setKeys} keysStatus={keysStatus} />

                  <h3 className="settings-section-title">More AI services (Groq, Google, OpenAI)</h3>
                  <div className="provider-cards">
                    {AI_PROVIDER_ENTRIES.filter((e) => e.id !== "claude" && e.id !== "openrouter").map((entry) => (
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
                              <div className="actions settings-inline-controls settings-actions-wrap">
                                <input
                                  id={keyName}
                                  type="password"
                                  placeholder={keysStatus[keyName] ? "Leave blank to keep current" : "Paste key"}
                                  value={keys[keyName] ?? ""}
                                  onChange={(e) => setKeys((k) => ({ ...k, [keyName]: e.target.value }))}
                                  className="input settings-input-flex"
                                />
                                {entry.testKey === keyName && <TestGroqButton />}
                              </div>
                            </div>
                          ))}
                        </div>
                        <div className="actions settings-actions-top-sm">
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

                  <h3 className="settings-section-title">Channels & other (Telegram, Giphy, Notion…)</h3>
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
                          />
                        </div>
                        <div className="actions settings-actions-top-sm">
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

                  <div className="actions settings-actions-top">
                    <button type="button" onClick={handleSaveKeys} disabled={saving} className="btn btn-primary">
                      {saving ? "Saving…" : "Save all API keys"}
                    </button>
                  </div>
                  {message && <div className={message.startsWith("Error:") ? "alert alert-error settings-alert-top" : "alert settings-alert-top"}>{message}</div>}
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
                  <pre className="file-preview settings-command-block">
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
                  <h3 className="settings-subhead settings-subhead-first">AI providers</h3>
                  <p className="help">
                    Available for Asta: {providers.join(", ")}. Ollama needs no key; set <code>OLLAMA_BASE_URL</code> in <code>backend/.env</code> if needed.
                  </p>

                  <h3 className="settings-subhead">Files</h3>
                  <p className="help">
                    <code>ASTA_ALLOWED_PATHS</code> in <code>backend/.env</code> controls which directories the panel/AI can read.
                  </p>

                  <h3 className="settings-subhead">Audio notes</h3>
                  <p className="help">Transcription runs locally (faster-whisper). Formatting uses your default AI.</p>
                </div>
              </details>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
