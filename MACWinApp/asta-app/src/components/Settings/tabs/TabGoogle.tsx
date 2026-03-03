import { useState, useEffect } from "react";
import { getKeyStatus, setKeys } from "../../../lib/api";

export default function TabGoogle() {
  const [key, setKey] = useState("");
  const [hasKey, setHasKey] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    getKeyStatus().then(r => setHasKey(!!r.google_key)).catch(()=>{});
  }, []);

  async function save() {
    if (!key.trim()) return;
    setSaving(true);
    await setKeys({ google_key: key });
    setSaving(false); setSaved(true); setHasKey(true);
    setTimeout(() => setSaved(false), 2000);
  }

  return (
    <div className="text-label space-y-5">
      <h2 className="text-15 font-semibold">Google</h2>
      <p className="text-13 text-label-secondary">Google Gemini API key for the Google provider.</p>
      <div>
        <div className="flex items-center gap-2 mb-1">
          <label className="text-11 text-label-tertiary">API Key</label>
          <span className={`text-11 ${hasKey ? "text-success" : "text-label-tertiary"}`}>
            {hasKey ? "● set" : "○ not set"}
          </span>
        </div>
        <div className="flex gap-2">
          <input type="password" value={key} onChange={e => setKey(e.target.value)}
            placeholder="Leave blank to keep existing"
            className="flex-1 bg-white/[.04] border border-separator rounded-mac px-3 py-2 text-13 font-mono text-label outline-none focus:border-accent/50" />
          <button onClick={save} disabled={saving || !key.trim()}
            className="text-12 bg-accent hover:bg-accent-hover disabled:opacity-40 text-white px-4 py-1.5 rounded-lg transition-colors">
            {saved ? "✓ Saved" : saving ? "…" : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}
