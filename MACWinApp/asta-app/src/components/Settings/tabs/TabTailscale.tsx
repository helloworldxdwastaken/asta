import { useState } from "react";
import { getBackendUrl, setBackendUrl } from "../../../lib/api";

export default function TabTailscale() {
  const [url, setUrl] = useState(getBackendUrl());
  const [saved, setSaved] = useState(false);

  function save() {
    setBackendUrl(url);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  return (
    <div className="text-white space-y-6">
      <h2 className="text-lg font-semibold">Network / Tailscale</h2>
      <p className="text-sm text-white/50">
        Set the backend URL. Use this to connect to a Mac backend from Windows via Tailscale or LAN.
      </p>
      <div>
        <label className="text-xs text-white/40 block mb-2">Backend URL</label>
        <input
          type="text"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2.5 text-sm font-mono text-white outline-none focus:border-[#007AFF]"
        />
      </div>
      <button
        onClick={save}
        className="bg-[#007AFF] hover:bg-[#0066CC] text-white text-sm rounded-xl px-5 py-2 transition-colors"
      >
        {saved ? "✓ Saved" : "Save"}
      </button>
    </div>
  );
}
