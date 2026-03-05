import { useState, useEffect, useRef } from "react";
import { getBackendUrl, setBackendUrl, checkHealth, getHealth, getAuthToken, setAuthToken as setAuthTokenApi, getApiTokenStatus, setApiToken } from "../../../lib/api";
import { IconCheck, IconWarning, IconAntenna } from "../../../lib/icons";
import { invoke as tauriInvoke } from "@tauri-apps/api/core";

// Tauri invoke — use proper @tauri-apps/api import
const invoke: ((cmd: string, args?: any) => Promise<any>) | null = (() => {
  try { return tauriInvoke; } catch { return null; }
})();

type TsStatus = "not_installed" | "not_logged_in" | "disconnected" | "connecting" | "connected";

export default function TabNetwork() {
  const [url, setUrl] = useState(getBackendUrl());
  const [saved, setSaved] = useState(false);
  const [connected, setConnected] = useState(false);
  const [checking, setChecking] = useState(true);
  const [version, setVersion] = useState("");
  const pollRef = useRef<ReturnType<typeof setInterval> | undefined>(undefined);

  // Tailscale state
  const [tsStatus, setTsStatus] = useState<TsStatus>("not_installed");
  const [tsIp, setTsIp] = useState("");
  const [tsDns, setTsDns] = useState("");
  const [tsServeEnabled, setTsServeEnabled] = useState(false);
  const [tsLoading, setTsLoading] = useState(false);
  const [tsServeLoading, setTsServeLoading] = useState(false);
  const [copied, setCopied] = useState<string | null>(null);

  // Auth token state
  const [authToken, setAuthTokenState] = useState(getAuthToken());
  const [tokenVisible, setTokenVisible] = useState(false);
  const [tokenSaved, setTokenSaved] = useState(false);
  const [tokenConfigured, setTokenConfigured] = useState(false);
  const [generatingToken, setGeneratingToken] = useState(false);

  // Auto-detect backend on mount + poll every 10s
  useEffect(() => {
    testConnection(getBackendUrl(), true);
    pollRef.current = setInterval(() => testConnection(getBackendUrl(), true), 10000);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, []);

  // Check if API token is configured on backend
  useEffect(() => {
    getApiTokenStatus().then(r => setTokenConfigured(r.configured)).catch(() => {});
  }, []);

  // Load Tailscale status
  useEffect(() => {
    refreshTailscale();
    const interval = setInterval(refreshTailscale, 20000);
    return () => clearInterval(interval);
  }, []);

  async function testConnection(testUrl: string, silent = false) {
    if (!silent) setChecking(true);
    try {
      setBackendUrl(testUrl);
      const ok = await checkHealth();
      setConnected(ok);
      if (ok) {
        const health = await getHealth().catch(() => null);
        setVersion(health?.version ?? "");
      }
    } catch {
      setConnected(false);
    }
    setChecking(false);
  }

  async function refreshTailscale() {
    if (!invoke) return;
    try {
      const r = await invoke("tailscale_status");
      setTsStatus(r.status ?? "not_installed");
      setTsIp(r.ip ?? "");
      setTsDns(r.dns_name ?? "");

      if (r.status === "connected") {
        const serve = await invoke("tailscale_serve_status").catch(() => ({ enabled: false }));
        setTsServeEnabled(serve.enabled ?? false);
      }
    } catch {
      setTsStatus("not_installed");
    }
  }

  function saveToken() {
    setAuthTokenApi(authToken);
    setTokenSaved(true);
    testConnection(url);
    setTimeout(() => setTokenSaved(false), 2000);
  }

  async function generateToken() {
    setGeneratingToken(true);
    try {
      const r = await setApiToken("generate");
      if (r.token) {
        setAuthTokenState(r.token);
        setAuthTokenApi(r.token);
        setTokenConfigured(true);
        setTokenSaved(true);
        setTimeout(() => setTokenSaved(false), 2000);
      }
    } catch {}
    setGeneratingToken(false);
  }

  function clearToken() {
    setAuthTokenState("");
    setAuthTokenApi("");
    setApiToken("clear").then(() => setTokenConfigured(false)).catch(() => {});
  }

  function save() {
    setBackendUrl(url);
    setSaved(true);
    testConnection(url);
    setTimeout(() => setSaved(false), 2000);
  }

  function reconnect() {
    testConnection(url);
  }

  async function handleTsConnect() {
    if (!invoke) return;
    setTsLoading(true);
    await invoke("tailscale_connect").catch(() => {});
    await refreshTailscale();
    setTsLoading(false);
  }

  async function handleTsDisconnect() {
    if (!invoke) return;
    setTsLoading(true);
    await invoke("tailscale_disconnect").catch(() => {});
    await refreshTailscale();
    setTsLoading(false);
  }

  async function handleTsLogin() {
    if (!invoke) return;
    setTsLoading(true);
    try {
      const r = await invoke("tailscale_login");
      if (r.login_url) window.open(r.login_url, "_blank");
    } catch {}
    setTimeout(refreshTailscale, 3000);
    setTimeout(refreshTailscale, 8000);
    setTsLoading(false);
  }

  async function handleEnableServe() {
    if (!invoke) return;
    setTsServeLoading(true);
    const port = parseInt(new URL(url || "http://localhost:8010").port || "8010", 10);
    await invoke("tailscale_serve_enable", { port });
    await refreshTailscale();
    setTsServeLoading(false);
  }

  async function handleDisableServe() {
    if (!invoke) return;
    setTsServeLoading(true);
    await invoke("tailscale_serve_disable");
    await refreshTailscale();
    setTsServeLoading(false);
  }

  function copyLink(link: string) {
    navigator.clipboard.writeText(link);
    setCopied(link);
    setTimeout(() => setCopied(null), 2000);
  }

  function useHere(link: string) {
    setUrl(link);
    setBackendUrl(link);
    testConnection(link);
  }

  const isLocalUrl = url.includes("localhost") || url.includes("127.0.0.1");
  const backendPort = (() => { try { return new URL(url || "http://localhost:8010").port || "8010"; } catch { return "8010"; } })();
  const httpsLink = tsServeEnabled && tsDns ? `https://${tsDns}` : null;
  const httpLink = tsIp ? `http://${tsIp}:${backendPort}` : null;

  const tsStatusLabel: Record<TsStatus, string> = {
    not_installed: "Tailscale not installed",
    not_logged_in: "Not logged in",
    disconnected: "Disconnected",
    connecting: "Connecting...",
    connected: tsIp ? `Connected · ${tsIp}` : "Connected",
  };

  return (
    <div className="text-label space-y-6">
      <h2 className="text-15 font-semibold">Connection</h2>

      {/* ── Backend section ── */}
      <Section title="Backend">
        <div className="space-y-3">
          <div>
            <label className="text-11 text-label-tertiary block mb-1">Backend URL</label>
            <input type="text" value={url}
              onChange={e => { setUrl(e.target.value); setConnected(false); }}
              className="w-full bg-white/[.04] border border-separator rounded-mac px-3 py-2.5 text-13 font-mono text-label outline-none focus:border-accent/50 transition-colors"
              placeholder="http://localhost:8010" />
          </div>

          <div className="flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full shrink-0 ${connected ? "bg-success shadow-[0_0_6px_rgba(52,199,89,0.5)]" : "bg-danger"}`} />
            <span className="text-13 text-label-secondary">
              {checking ? "Checking..." : connected ? "Connected" : "Not reachable"}
            </span>
            {connected && version && (
              <span className="text-11 text-label-tertiary">v{version}</span>
            )}
            <div className="flex-1" />
            <button onClick={reconnect}
              className="text-12 text-accent hover:text-accent-hover transition-colors">
              Reconnect
            </button>
          </div>

          <div className="flex gap-2">
            <button onClick={save}
              className="text-12 bg-accent hover:bg-accent-hover text-white px-4 py-1.5 rounded-lg transition-colors">
              {saved ? "Saved" : "Save"}
            </button>
          </div>

          {!connected && !checking && (
            <div className="bg-danger/10 border border-danger/20 rounded-mac p-3">
              <div className="flex items-start gap-2">
                <IconWarning size={13} className="text-danger shrink-0 mt-0.5" />
                <div>
                  <p className="text-12 text-danger">Cannot reach backend</p>
                  {isLocalUrl && (
                    <div className="mt-2">
                      <p className="text-11 text-label-tertiary mb-1">Start the backend:</p>
                      <div className="bg-white/[.04] rounded-lg px-3 py-2 font-mono text-11 text-label-secondary select-all">
                        cd ~/asta && ./asta.sh start
                      </div>
                    </div>
                  )}
                  {!isLocalUrl && (
                    <p className="text-11 text-label-tertiary mt-1">
                      Make sure the remote backend is running and accessible.
                    </p>
                  )}
                </div>
              </div>
            </div>
          )}

          {connected && (
            <div className="bg-success/10 border border-success/20 rounded-mac p-3 flex items-center gap-2">
              <IconCheck size={13} className="text-success shrink-0" />
              <span className="text-12 text-success font-medium">
                Backend connected{version ? ` (v${version})` : ""}
              </span>
            </div>
          )}

          <p className="text-11 text-label-tertiary">
            Where the Asta backend is running. Default: http://localhost:8010
          </p>
        </div>
      </Section>

      {/* ── Auth Token ── */}
      <Section title="Auth Token">
        <div className="space-y-3">
          <div>
            <label className="text-11 text-label-tertiary block mb-1">Bearer Token</label>
            <div className="flex gap-2">
              <input type={tokenVisible ? "text" : "password"} value={authToken}
                onChange={e => setAuthTokenState(e.target.value)}
                className="flex-1 bg-white/[.04] border border-separator rounded-mac px-3 py-2.5 text-13 font-mono text-label outline-none focus:border-accent/50 transition-colors"
                placeholder="Leave empty for local-only access" />
              <button onClick={() => setTokenVisible(!tokenVisible)}
                className="text-11 bg-white/[.05] rounded-mac px-3 hover:bg-white/[.08] transition-colors shrink-0 border border-separator">
                {tokenVisible ? "Hide" : "Show"}
              </button>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button onClick={saveToken}
              className="text-12 bg-accent hover:bg-accent-hover text-white px-4 py-1.5 rounded-lg transition-colors">
              {tokenSaved ? "Saved" : "Save"}
            </button>
            <button onClick={generateToken} disabled={generatingToken}
              className="text-12 bg-white/[.08] hover:bg-white/[.12] disabled:opacity-50 px-3 py-1.5 rounded-lg transition-colors">
              {generatingToken ? "..." : "Generate"}
            </button>
            <button onClick={clearToken}
              className="text-12 bg-white/[.08] hover:bg-white/[.12] px-3 py-1.5 rounded-lg transition-colors">
              Clear
            </button>
            <div className="flex-1" />
            {tokenConfigured && (
              <span className="text-11 text-success flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-success" />
                Active on server
              </span>
            )}
          </div>

          <p className="text-11 text-label-tertiary">
            Required for remote access via Cloudflare Tunnel. Not needed for localhost.
            Click Generate to create a token on the server and save it here.
          </p>
        </div>
      </Section>

      {/* ── Remote Access (Tailscale) ── */}
      <Section title="Remote Access (Tailscale)">
        <div className="space-y-3">
          {/* Tailscale status row */}
          <div className="flex items-center gap-3">
            <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${
              tsStatus === "connected" ? "bg-success/20" :
              tsStatus === "connecting" || tsStatus === "not_logged_in" ? "bg-warning/20" :
              "bg-label-tertiary/10"
            }`}>
              {tsStatus === "connecting" ? (
                <div className="w-4 h-4 border-2 border-accent/40 border-t-accent rounded-full animate-spin" />
              ) : (
                <IconAntenna size={14} className={
                  tsStatus === "connected" ? "text-success" :
                  tsStatus === "not_logged_in" ? "text-warning" :
                  "text-label-tertiary"
                } />
              )}
            </div>
            <div className="flex-1 min-w-0">
              <span className="text-13 font-medium">{tsStatusLabel[tsStatus]}</span>
            </div>

            {tsStatus === "not_logged_in" && (
              <button onClick={handleTsLogin} disabled={tsLoading}
                className="text-12 bg-accent hover:bg-accent-hover disabled:opacity-50 text-white px-4 py-1.5 rounded-lg transition-colors shrink-0">
                {tsLoading ? "..." : "Log in"}
              </button>
            )}
            {tsStatus === "disconnected" && (
              <button onClick={handleTsConnect} disabled={tsLoading}
                className="text-12 bg-accent hover:bg-accent-hover disabled:opacity-50 text-white px-4 py-1.5 rounded-lg transition-colors shrink-0">
                {tsLoading ? "..." : "Connect"}
              </button>
            )}
            {tsStatus === "connected" && (
              <button onClick={handleTsDisconnect} disabled={tsLoading}
                className="text-12 bg-danger/15 text-danger hover:bg-danger/25 disabled:opacity-50 px-4 py-1.5 rounded-lg transition-colors shrink-0">
                {tsLoading ? "..." : "Disconnect"}
              </button>
            )}
          </div>

          {/* HTTPS link */}
          {tsStatus === "connected" && httpsLink && (
            <LinkBox
              link={httpsLink}
              badge="HTTPS"
              badgeColor="success"
              copied={copied === httpsLink}
              onCopy={() => copyLink(httpsLink)}
              onUseHere={() => useHere(httpsLink)}
            />
          )}

          {/* Enable/disable HTTPS tunnel */}
          {tsStatus === "connected" && !tsServeEnabled && (
            <div className="bg-white/[.04] rounded-mac p-3">
              <p className="text-12 text-label-secondary mb-2">
                Enable HTTPS tunnel to access Asta remotely via a secure link.
              </p>
              <button onClick={handleEnableServe} disabled={tsServeLoading}
                className="text-12 bg-accent hover:bg-accent-hover disabled:opacity-50 text-white px-4 py-1.5 rounded-lg transition-colors">
                {tsServeLoading ? "Enabling..." : "Enable HTTPS Tunnel"}
              </button>
            </div>
          )}
          {tsStatus === "connected" && tsServeEnabled && (
            <button onClick={handleDisableServe} disabled={tsServeLoading}
              className="text-12 bg-danger/10 text-danger hover:bg-danger/20 disabled:opacity-50 px-4 py-1.5 rounded-lg transition-colors">
              {tsServeLoading ? "Disabling..." : "Disable HTTPS Tunnel"}
            </button>
          )}

          {/* HTTP fallback link */}
          {tsStatus === "connected" && httpLink && (
            <LinkBox
              link={httpLink}
              badge="HTTP (fallback)"
              badgeColor="warning"
              copied={copied === httpLink}
              onCopy={() => copyLink(httpLink)}
              onUseHere={() => useHere(httpLink)}
            />
          )}

          {/* Not installed */}
          {tsStatus === "not_installed" && (
            <div className="bg-white/[.04] rounded-mac p-4 space-y-2">
              <p className="text-12 text-label-secondary font-medium">Tailscale not found</p>
              <p className="text-11 text-label-tertiary">
                Install Tailscale to securely access your Asta backend from any device.
              </p>
              <a href="https://tailscale.com/download" target="_blank" rel="noreferrer"
                className="inline-block text-12 bg-accent hover:bg-accent-hover text-white px-4 py-1.5 rounded-lg transition-colors">
                Download Tailscale
              </a>
            </div>
          )}

          {/* Refresh button */}
          {invoke && (
            <button onClick={refreshTailscale}
              className="text-11 text-accent hover:text-accent-hover transition-colors">
              Refresh status
            </button>
          )}

          {/* Fallback instructions for non-Tauri env */}
          {!invoke && (
            <div className="bg-white/[.04] rounded-mac p-3 space-y-2">
              <p className="text-12 text-label-secondary font-medium">Setup instructions:</p>
              <ol className="text-11 text-label-tertiary space-y-1.5 list-decimal pl-4">
                <li>Install <a href="https://tailscale.com/download" target="_blank" rel="noreferrer" className="text-accent hover:underline">Tailscale</a> on both machines</li>
                <li>Sign in on both devices with the same account</li>
                <li>
                  On the backend machine, run:
                  <div className="bg-white/[.04] rounded px-2 py-1 font-mono text-11 text-label-secondary mt-1 select-all">
                    tailscale serve --bg http://localhost:8010
                  </div>
                </li>
                <li>Copy your Tailscale HTTPS URL and paste it above as the Backend URL</li>
              </ol>
            </div>
          )}

          <p className="text-11 text-label-tertiary">
            Enable HTTPS Tunnel on this Mac, then copy the link to use Asta from your phone or another computer.
          </p>
        </div>
      </Section>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h3 className="text-11 font-semibold text-label-tertiary uppercase tracking-wider mb-2">{title}</h3>
      {children}
    </section>
  );
}

function LinkBox({ link, badge, badgeColor, copied, onCopy, onUseHere }: {
  link: string; badge: string; badgeColor: "success" | "warning";
  copied: boolean; onCopy: () => void; onUseHere: () => void;
}) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center gap-2">
        <span className="text-11 font-semibold text-label-tertiary">Your remote link</span>
        <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded-full ${
          badgeColor === "success" ? "bg-success/15 text-success" : "bg-warning/15 text-warning"
        }`}>{badge}</span>
      </div>
      <div className="flex items-center gap-2 bg-accent/[.07] rounded-mac px-3 py-2.5">
        <span className="text-13 font-mono text-label flex-1 truncate select-all">{link}</span>
        <button onClick={onCopy}
          className="text-11 bg-white/[.08] hover:bg-white/[.12] px-2.5 py-1 rounded-lg transition-colors shrink-0">
          {copied ? "Copied!" : "Copy"}
        </button>
        <button onClick={onUseHere}
          className="text-11 bg-white/[.08] hover:bg-white/[.12] px-2.5 py-1 rounded-lg transition-colors shrink-0">
          Use here
        </button>
      </div>
    </div>
  );
}
