import { useState, useEffect } from "react";
import { setKeys, getKeyStatus, testKey } from "../../../lib/api";
import { openUrl } from "@tauri-apps/plugin-opener";
import ProviderLogo from "../../ProviderLogo";

// key = field name sent to PUT /api/settings/keys
// statusKey = field name returned by GET /api/settings/keys (backend uses _api_key suffix)
// key = field name matching backend ApiKeysIn model (PUT /api/settings/keys)
const FIELDS = [
  { key: "anthropic_api_key", label: "Anthropic (Claude)", ph: "sk-ant-...", prov: "claude", icon: "anthropic", url: "https://console.anthropic.com/settings/keys" },
  { key: "openai_api_key", label: "OpenAI", ph: "sk-...", prov: "openai", icon: "openai", url: "https://platform.openai.com/api-keys" },
  { key: "openrouter_api_key", label: "OpenRouter", ph: "sk-or-...", prov: "openrouter", icon: "openrouter", url: "https://openrouter.ai/keys" },
  { key: "gemini_api_key", label: "Google / Gemini", ph: "AIza...", prov: "google", icon: "google", url: "https://aistudio.google.com/app/apikey" },
  { key: "groq_api_key", label: "Groq", ph: "gsk_...", prov: "groq", icon: "groq", url: "https://console.groq.com/keys" },
  { key: "huggingface_api_key", label: "HuggingFace", ph: "hf_...", prov: null, icon: "huggingface", url: "https://huggingface.co/settings/tokens" },
  { key: "giphy_api_key", label: "Giphy", ph: "", prov: null, icon: "giphy", url: "https://developers.giphy.com/" },
  { key: "notion_api_key", label: "Notion", ph: "ntn_...", prov: null, icon: "notion", url: "https://www.notion.so/my-integrations" },
  { key: "pexels_api_key", label: "Pexels", ph: "", prov: null, icon: "pexels", url: "https://www.pexels.com/api/" },
  { key: "pixabay_api_key", label: "Pixabay", ph: "", prov: null, icon: "pixabay", url: "https://pixabay.com/api/docs/" },
  { key: "youtube_api_key", label: "YouTube", ph: "AIza...", prov: null, icon: "youtube", url: "https://console.cloud.google.com/apis/library/youtube.googleapis.com" },
  { key: "github_token", label: "GitHub", ph: "ghp_...", prov: null, icon: "github", url: "https://github.com/settings/tokens" },
];

export default function TabKeys() {
  const [keys, setKeysState] = useState<Record<string, string>>({});
  const [vis, setVis] = useState<Record<string, boolean>>({});
  const [status, setStatus] = useState<Record<string, boolean>>({});
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [testing, setTesting] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<Record<string, "ok" | "fail">>({});

  useEffect(() => { getKeyStatus().then(setStatus).catch(()=>{}); }, []);

  async function save() {
    setSaving(true);
    const toSave: Record<string, string> = {};
    for (const f of FIELDS) { if (keys[f.key]) toSave[f.key] = keys[f.key]; }
    await setKeys(toSave);
    setSaving(false); setSaved(true);
    getKeyStatus().then(setStatus).catch(()=>{});
    setTimeout(() => setSaved(false), 2000);
  }

  async function handleTest(provider: string, key: string) {
    setTesting(key);
    try {
      const r = await testKey(provider);
      setTestResult(prev => ({ ...prev, [key]: (r.ok || r.valid) ? "ok" : "fail" }));
    } catch {
      setTestResult(prev => ({ ...prev, [key]: "fail" }));
    }
    setTesting(null);
    setTimeout(() => setTestResult(prev => { const n = { ...prev }; delete n[key]; return n; }), 3000);
  }

  return (
    <div className="text-label space-y-6">
      <h2 className="text-16 font-semibold">API Keys</h2>
      <div className="space-y-5">
        {FIELDS.map(f => {
          const isSet = status[f.key];
          return (
            <div key={f.key}>
              <div className="flex items-center gap-2 mb-1.5">
                <ProviderLogo provider={f.icon} size={18} />
                <label className="text-12 text-label-secondary font-medium">{f.label}</label>
                <span className={`w-1.5 h-1.5 rounded-full ${isSet ? "bg-success" : "bg-label-tertiary/30"}`} />
                <span className={`text-11 font-mono ${isSet ? "text-success" : "text-label-tertiary"}`}>{isSet ? "Active" : "Not set"}</span>
                <div className="flex-1" />
                {f.url && <button onClick={() => openUrl(f.url!).catch(() => window.open(f.url!, "_blank"))} className="text-11 text-accent hover:underline bg-transparent border-none cursor-pointer p-0">Get key</button>}
              </div>
              <div className="flex gap-2">
                <input type={vis[f.key] ? "text" : "password"} value={keys[f.key] ?? ""}
                  onChange={e => setKeysState({...keys, [f.key]: e.target.value})}
                  placeholder={isSet ? "Leave blank to keep existing" : f.ph || "Enter key..."}
                  className="flex-1 bg-white/[.04] border border-separator hover:border-separator-bold rounded-mac px-3 py-2.5 text-13 font-mono text-label outline-none focus:border-accent/40 transition-colors" />
                <button onClick={() => setVis({...vis, [f.key]: !vis[f.key]})}
                  className="text-11 text-label-tertiary bg-white/[.05] rounded-mac px-3 hover:bg-white/[.08] transition-colors shrink-0 border border-separator">
                  {vis[f.key] ? "Hide" : "Show"}
                </button>
                {isSet && f.prov && (
                  <button onClick={() => handleTest(f.prov!, f.key)} disabled={testing === f.key}
                    className={`text-11 rounded-mac px-3 transition-all duration-200 shrink-0 border ${
                      testResult[f.key] === "ok" ? "bg-success/[.12] text-success border-success/20" :
                      testResult[f.key] === "fail" ? "bg-danger/[.12] text-danger border-danger/20" :
                      "bg-white/[.05] text-label-tertiary hover:bg-white/[.08] border-separator"
                    }`}>
                    {testing === f.key ? "..." : testResult[f.key] === "ok" ? "Valid" : testResult[f.key] === "fail" ? "Invalid" : "Test"}
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
      <button onClick={save} disabled={saving}
        className="accent-gradient disabled:opacity-50 text-white text-13 rounded-mac px-6 py-2.5 shadow-glow-sm hover:shadow-glow transition-all duration-200 active:scale-[0.97]">
        {saved ? "Saved" : saving ? "Saving..." : "Save Keys"}
      </button>
    </div>
  );
}
