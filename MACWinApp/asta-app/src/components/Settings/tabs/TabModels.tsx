import { useState, useEffect } from "react";
import { getModels, setModel, getAvailableModels, getUsage } from "../../../lib/api";
import ProviderLogo from "../../ProviderLogo";

const PROVIDERS = [
  { key: "anthropic", name: "Claude", default: "claude-sonnet-4-6" },
  { key: "openai", name: "OpenAI", default: "gpt-4o" },
  { key: "google", name: "Google Gemini", default: "gemini-2.0-flash" },
  { key: "groq", name: "Groq", default: "llama-3.3-70b-versatile" },
  { key: "openrouter", name: "OpenRouter", default: "" },
  { key: "ollama", name: "Ollama (Local)", default: "llama3" },
];

export default function TabModels() {
  const [models, setModels] = useState<Record<string, string>>({});
  const [available, setAvailable] = useState<Record<string, string[]>>({});
  const [saving, setSaving] = useState<string | null>(null);
  const [usage, setUsage] = useState<any>(null);

  useEffect(() => {
    getModels().then(r => setModels(r.models ?? r ?? {})).catch(()=>{});
    getAvailableModels().then(r => setAvailable(r.models ?? r ?? {})).catch(()=>{});
    getUsage(30).then(setUsage).catch(()=>{});
  }, []);

  async function save(provider: string) {
    setSaving(provider);
    await setModel(provider, models[provider] ?? "");
    setSaving(null);
  }

  const providerUsage = usage?.by_provider ?? usage?.providers ?? {};

  return (
    <div className="text-label space-y-7">
      <h2 className="text-16 font-semibold">Models</h2>

      <Section title="Provider Models">
        <div className="space-y-5">
          {PROVIDERS.map(p => {
            const opts = available[p.key] ?? [];
            return (
              <div key={p.key}>
                <label className="text-12 text-label-secondary flex items-center gap-2 mb-1.5 font-medium">
                  <ProviderLogo provider={p.key} size={16} />
                  {p.name}
                </label>
                <div className="flex gap-2">
                  {opts.length > 3 ? (
                    <select value={models[p.key] ?? ""} onChange={e => setModels({...models, [p.key]: e.target.value})}
                      className="flex-1 bg-white/[.04] border border-separator hover:border-separator-bold rounded-mac px-3 py-2.5 text-13 font-mono text-label outline-none focus:border-accent/40 transition-colors">
                      <option value="">{p.default ? `Default (${p.default})` : "Select model"}</option>
                      {opts.map(m => <option key={m} value={m}>{m}</option>)}
                    </select>
                  ) : (
                    <input type="text" value={models[p.key] ?? ""} onChange={e => setModels({...models, [p.key]: e.target.value})}
                      placeholder={p.default} list={`models-${p.key}`}
                      className="flex-1 bg-white/[.04] border border-separator hover:border-separator-bold rounded-mac px-3 py-2.5 text-13 font-mono text-label outline-none focus:border-accent/40 transition-colors" />
                  )}
                  <button onClick={() => save(p.key)} disabled={saving === p.key}
                    className="text-12 bubble-gradient disabled:opacity-50 text-white px-4 py-2 rounded-mac transition-all duration-200 active:scale-[0.97] shadow-glow-sm shrink-0">
                    {saving === p.key ? "..." : "Set"}
                  </button>
                </div>
                {opts.length > 0 && opts.length <= 3 && (
                  <datalist id={`models-${p.key}`}>
                    {opts.map(m => <option key={m} value={m} />)}
                  </datalist>
                )}
              </div>
            );
          })}
        </div>
      </Section>

      <Section title="Token Usage (Last 30 Days)">
        {usage ? (
          <div className="space-y-2">
            {Object.keys(providerUsage).length > 0 ? (
              <div className="bg-white/[.03] rounded-mac overflow-hidden border border-separator">
                <div className="grid grid-cols-4 text-10 text-label-tertiary font-bold uppercase tracking-widest px-4 py-2.5 border-b border-separator">
                  <span>Provider</span><span className="text-right">Input</span><span className="text-right">Output</span><span className="text-right">Calls</span>
                </div>
                {Object.entries(providerUsage).map(([prov, data]: [string, any]) => (
                  <div key={prov} className="grid grid-cols-4 text-13 px-4 py-2.5 border-b border-separator last:border-0 hover:bg-white/[.02] transition-colors">
                    <span className="capitalize text-label-secondary flex items-center gap-2">
                      <ProviderLogo provider={prov} size={14} />
                      {prov}
                    </span>
                    <span className="text-right tabular-nums font-mono text-label-tertiary">{fmtTokens(data.input_tokens ?? data.input ?? 0)}</span>
                    <span className="text-right tabular-nums font-mono text-label-tertiary">{fmtTokens(data.output_tokens ?? data.output ?? 0)}</span>
                    <span className="text-right tabular-nums font-mono text-label-tertiary">{data.calls ?? data.count ?? 0}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-label-tertiary text-13">No usage data available</p>
            )}
          </div>
        ) : (
          <p className="text-label-tertiary text-13">Loading usage data...</p>
        )}
      </Section>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (<section><h3 className="text-10 font-bold text-label-tertiary uppercase tracking-widest mb-2.5">{title}</h3>{children}</section>);
}

function fmtTokens(n: number) {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}
