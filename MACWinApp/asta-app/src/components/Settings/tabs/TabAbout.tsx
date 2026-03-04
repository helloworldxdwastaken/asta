import { useState, useEffect } from "react";
import { getHealth, checkUpdate, triggerUpdate, getServerStatus, getUsage } from "../../../lib/api";
import { getVersion } from "@tauri-apps/api/app";
import { invoke } from "@tauri-apps/api/core";
import { IconCpu, IconMemory, IconClock } from "../../../lib/icons";

interface UpdateInfo {
  has_update: boolean;
  latest_version: string;
  current_version: string;
  release_url: string;
  download_url?: string;
}

export default function TabAbout() {
  const [appVersion, setAppVersion] = useState("–");
  const [backendVersion, setBackendVersion] = useState("–");
  const [serverStatus, setServerStatus] = useState<any>(null);
  const [usage, setUsage] = useState<any>(null);
  const [updateAvail, setUpdateAvail] = useState(false);
  const [updating, setUpdating] = useState(false);
  const [checking, setChecking] = useState(false);
  const [updateInfo, setUpdateInfo] = useState<UpdateInfo | null>(null);
  const [checkDone, setCheckDone] = useState(false);

  useEffect(() => {
    getVersion().then(setAppVersion).catch(() => {});
    getHealth().then(r => setBackendVersion(r.version ?? "–")).catch(()=>{});
    getServerStatus().then(setServerStatus).catch(()=>{});
    getUsage(7).then(setUsage).catch(()=>{});
    checkUpdate().then(r => setUpdateAvail(r.available ?? r.update_available ?? false)).catch(()=>{});
  }, []);

  async function doUpdate() {
    setUpdating(true);
    await triggerUpdate().catch(()=>{});
    setUpdating(false);
  }

  async function manualCheck() {
    setChecking(true);
    setCheckDone(false);
    setUpdateInfo(null);
    try {
      const ver = await getVersion();
      const result = await invoke<UpdateInfo>("check_app_update", { currentVersion: ver });
      setUpdateInfo(result);
      if (result.has_update) setUpdateAvail(true);
    } catch { /* ignore */ }
    setChecking(false);
    setCheckDone(true);
  }

  // Format server-status fields (backend returns cpu_percent, ram object, uptime_str)
  const cpu = serverStatus
    ? `${serverStatus.cpu_percent ?? serverStatus.cpu ?? "–"}%`
    : "–";
  const ram = serverStatus?.ram
    ? (typeof serverStatus.ram === "object"
        ? `${serverStatus.ram.used_gb?.toFixed(1) ?? "?"}/${serverStatus.ram.total_gb?.toFixed(0) ?? "?"} GB`
        : String(serverStatus.ram))
    : "–";
  const uptime = serverStatus
    ? (serverStatus.uptime_str ?? serverStatus.uptime ?? "–")
    : "–";

  // Usage: backend returns { usage: [...], days: 7 }
  const usageList = usage?.usage ?? [];
  const totalMessages = Array.isArray(usageList)
    ? usageList.reduce((s: number, u: any) => s + (u.calls ?? u.count ?? 0), 0)
    : (usage?.messages ?? 0);
  const totalTokens = Array.isArray(usageList)
    ? usageList.reduce((s: number, u: any) => s + ((u.input_tokens ?? 0) + (u.output_tokens ?? 0)), 0)
    : (usage?.tokens ?? 0);

  return (
    <div className="text-label space-y-5">
      <h2 className="text-15 font-semibold">About</h2>
      <div className="grid grid-cols-2 gap-3">
        <div className="bg-white/[.04] rounded-mac px-4 py-3">
          <p className="text-11 text-label-tertiary mb-0.5">App version</p>
          <p className="text-14 font-mono">{appVersion}</p>
        </div>
        <div className="bg-white/[.04] rounded-mac px-4 py-3">
          <p className="text-11 text-label-tertiary mb-0.5">Backend</p>
          <p className="text-14 font-mono">{backendVersion}</p>
        </div>
      </div>

      {serverStatus && (
        <div className="bg-white/[.04] rounded-mac p-4 space-y-2">
          <p className="text-11 font-semibold text-label-tertiary uppercase tracking-wider">Server</p>
          <div className="grid grid-cols-3 gap-3">
            {([
              { icon: <IconCpu size={16} />, label: "CPU", value: cpu },
              { icon: <IconMemory size={16} />, label: "RAM", value: ram },
              { icon: <IconClock size={16} />, label: "Uptime", value: uptime },
            ] as const).map(({ icon, label, value }) => (
              <div key={label} className="flex flex-col items-center gap-1.5">
                <span className="text-label-tertiary">{icon}</span>
                <p className="text-xl font-semibold tabular-nums">{value}</p>
                <p className="text-11 text-label-tertiary">{label}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {usage && (
        <div className="bg-white/[.04] rounded-mac p-4">
          <p className="text-11 font-semibold text-label-tertiary uppercase tracking-wider mb-2">Usage (7 days)</p>
          <p className="text-13 text-label-secondary">
            Messages: <span className="text-label tabular-nums">{totalMessages}</span>
            {totalTokens > 0 && <> · Tokens: <span className="text-label tabular-nums">{fmtTokens(totalTokens)}</span></>}
          </p>
        </div>
      )}

      <div className="flex items-center gap-3">
        <button onClick={manualCheck} disabled={checking}
          className="bg-white/[.06] hover:bg-white/[.10] disabled:opacity-50 text-label text-13 rounded-mac px-4 py-2 border border-separator transition-colors">
          {checking ? "Checking…" : "Check for updates"}
        </button>
        {checkDone && !updateInfo?.has_update && (
          <span className="text-12 text-label-tertiary">You're on the latest version</span>
        )}
      </div>

      {(updateAvail || updateInfo?.has_update) && (
        <div className="bg-white/[.04] rounded-mac p-4 flex items-center justify-between">
          <div>
            <p className="text-13 font-semibold text-label">Update available</p>
            <p className="text-11 text-label-tertiary">v{updateInfo?.latest_version ?? "new"}</p>
          </div>
          <button onClick={() => {
            if (updateInfo?.release_url) window.open(updateInfo.release_url, "_blank");
          }}
            className="bg-accent hover:bg-accent-hover text-white text-13 rounded-mac px-5 py-2 transition-colors">
            View release
          </button>
        </div>
      )}
    </div>
  );
}

function fmtTokens(n: number) {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}
