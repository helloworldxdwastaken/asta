import { useState, useEffect, useRef } from "react";
import { spotifyStatus, spotifyDisconnect, spotifyConnectUrl, spotifyDevices } from "../../../lib/api";
// IconMusic removed — using ProviderLogo instead
import ProviderLogo from "../../ProviderLogo";

export default function TabSpotify() {
  const [connected, setConnected] = useState(false);
  const [account, setAccount] = useState("");
  const [devices, setDevices] = useState<any[]>([]);
  const [connecting, setConnecting] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | undefined>(undefined);

  async function loadStatus() {
    const r = await spotifyStatus().catch(() => ({ connected: false }));
    setConnected(r.connected ?? false);
    setAccount(r.account ?? r.display_name ?? "");
    if (r.connected) spotifyDevices().then(r => setDevices(r.devices ?? [])).catch(()=>{});
    return r.connected ?? false;
  }

  useEffect(() => {
    loadStatus();
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, []);

  function startConnect() {
    window.open(spotifyConnectUrl(), "_blank");
    setConnecting(true);
    pollRef.current = setInterval(async () => {
      const ok = await loadStatus();
      if (ok) { setConnecting(false); if (pollRef.current) clearInterval(pollRef.current); }
    }, 3000);
    setTimeout(() => { setConnecting(false); if (pollRef.current) clearInterval(pollRef.current); }, 120000);
  }

  async function disconnect() {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = undefined; }
    await spotifyDisconnect();
    setConnected(false); setConnecting(false); setAccount(""); setDevices([]);
  }

  return (
    <div className="text-label space-y-7">
      <div className="flex items-center gap-2.5">
        <ProviderLogo provider="spotify" size={24} />
        <h2 className="text-16 font-semibold">Spotify</h2>
      </div>

      {/* Status card */}
      <div className="bg-white/[.03] border border-separator rounded-mac p-4 flex items-center gap-3">
        <div className={`w-10 h-10 rounded-mac flex items-center justify-center ${connected ? "bg-success/[.12]" : "bg-label-tertiary/[.08]"}`}>
          <ProviderLogo provider="spotify" size={20} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full ${connected ? "bg-success" : "bg-label-tertiary/30"}`} />
            <span className="text-13 font-medium">{connected ? "Connected" : connecting ? "Waiting for authorization..." : "Not connected"}</span>
          </div>
          {account && <p className="text-12 text-label-tertiary mt-0.5 truncate">{account}</p>}
        </div>
        {connected ? (
          <button onClick={disconnect} className="text-12 bg-danger/[.12] text-danger hover:bg-danger/[.2] border border-danger/20 px-4 py-2 rounded-mac transition-all duration-200 active:scale-[0.97] shrink-0">Disconnect</button>
        ) : (
          <button onClick={startConnect} disabled={connecting}
            className="text-12 bg-success/[.12] text-success hover:bg-success/[.2] border border-success/20 disabled:opacity-50 px-4 py-2 rounded-mac transition-all duration-200 active:scale-[0.97] shrink-0">
            {connecting ? "Connecting..." : "Connect"}
          </button>
        )}
      </div>

      {/* Instructions */}
      {!connected && !connecting && (
        <div className="bg-white/[.03] border border-separator rounded-mac p-4 space-y-2">
          <p className="text-12 text-label-secondary font-medium">Setup</p>
          <ol className="text-11 text-label-tertiary space-y-1.5 list-decimal pl-4 leading-relaxed">
            <li>Make sure the Asta backend is running</li>
            <li>Click "Connect" to open the Spotify authorization page</li>
            <li>Log in and authorize Asta to control your Spotify</li>
            <li>Return here - the status will update automatically</li>
          </ol>
          <p className="text-11 text-label-tertiary mt-2">Spotify Premium is required for playback control.</p>
        </div>
      )}

      {connecting && (
        <div className="flex items-center gap-2.5 text-13 text-label-secondary">
          <div className="w-4 h-4 border-2 border-accent/40 border-t-accent rounded-full animate-spin" />
          Waiting for Spotify authorization...
        </div>
      )}

      {/* Devices */}
      {connected && (
        <section>
          <div className="flex items-center justify-between mb-2.5">
            <h3 className="text-10 font-bold text-label-tertiary uppercase tracking-widest">Devices</h3>
            <button onClick={() => spotifyDevices().then(r => setDevices(r.devices ?? [])).catch(()=>{})}
              className="text-11 text-accent hover:underline transition-colors">Refresh</button>
          </div>
          <div className="space-y-1.5">
            {devices.map((d: any, i: number) => (
              <div key={i} className="bg-white/[.03] border border-separator rounded-mac px-4 py-3 flex items-center justify-between hover:bg-white/[.05] transition-colors">
                <span className="text-13">{d.name}</span>
                <span className={`text-11 px-2.5 py-0.5 rounded-full ${d.is_active ? "bg-success/[.12] text-success border border-success/20" : "bg-white/[.04] text-label-tertiary"}`}>
                  {d.is_active ? "Active" : d.type ?? "Inactive"}
                </span>
              </div>
            ))}
            {devices.length === 0 && <p className="text-label-tertiary text-13">No devices found. Open Spotify on a device.</p>}
          </div>
        </section>
      )}
    </div>
  );
}
