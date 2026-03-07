import { useState, useEffect, useRef } from "react";
import { getBackendUrl, setBackendUrl, checkHealth, getHealth, getAuthToken, setAuthToken as setAuthTokenApi, getApiTokenStatus, setApiToken } from "../../../lib/api";
import { IconCheck, IconWarning } from "../../../lib/icons";

export default function TabNetwork() {
  const [url, setUrl] = useState(getBackendUrl());
  const [saved, setSaved] = useState(false);
  const [connected, setConnected] = useState(false);
  const [checking, setChecking] = useState(true);
  const [version, setVersion] = useState("");
  const pollRef = useRef<ReturnType<typeof setInterval> | undefined>(undefined);

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

  const isLocalUrl = url.includes("localhost") || url.includes("127.0.0.1");

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
