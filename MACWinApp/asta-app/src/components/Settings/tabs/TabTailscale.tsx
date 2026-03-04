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
    <div className="text-label space-y-6">
      <h2 className="text-16 font-semibold">Network / Tailscale</h2>
      <p className="text-13 text-label-secondary">
        Set the backend URL. Use this to connect to a Mac backend from Windows via Tailscale or LAN.
      </p>
      <div>
        <label className="text-11 text-label-tertiary block mb-2">Backend URL</label>
        <input
          type="text"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          className="w-full bg-white/[.04] border border-separator rounded-mac px-4 py-2.5 text-13 font-mono text-label outline-none focus:border-accent/50 transition-colors"
        />
      </div>
      <button
        onClick={save}
        className="accent-gradient hover:opacity-90 text-white text-13 font-medium rounded-mac px-5 py-2.5 shadow-glow-sm hover:shadow-glow transition-all duration-200 active:scale-[0.97]"
      >
        {saved ? "Saved" : "Save"}
      </button>
    </div>
  );
}
