import { useState, useEffect, useRef } from "react";
import { setBackendUrl, checkHealth, getHealth, getKeyStatus, setKeys } from "../../lib/api";
import { setSetupDone } from "../../lib/store";
import { IconCheck, IconWarning } from "../../lib/icons";

interface Props {
  onComplete: () => void;
}

const STEPS = [
  { id: 1, title: "Welcome to Asta" },
  { id: 2, title: "Connect to Backend" },
  { id: 3, title: "API Keys" },
  { id: 4, title: "You're ready!" },
];

export default function SetupWizard({ onComplete }: Props) {
  const [step, setStep] = useState(0);
  const [url, setUrl] = useState("https://asta.noxamusic.com");
  const [checking, setChecking] = useState(false);
  const [connected, setConnected] = useState(false);
  const [backendVersion, setBackendVersion] = useState("");
  const [failMsg, setFailMsg] = useState("");

  // Key entry state
  const [anthropicKey, setAnthropicKey] = useState("");
  const [openaiKey, setOpenaiKey] = useState("");
  const [keyStatus, setKeyStatus] = useState<Record<string, boolean>>({});
  const [savingKeys, setSavingKeys] = useState(false);
  const [keysSaved, setKeysSaved] = useState(false);

  // Auto-test connection on mount (maybe backend is already running)
  const autoTested = useRef(false);
  useEffect(() => {
    if (autoTested.current) return;
    autoTested.current = true;
    testBackend("https://asta.noxamusic.com", true);
  }, []);

  async function testBackend(testUrl: string, silent = false) {
    setChecking(true);
    setFailMsg("");
    setConnected(false);
    setBackendUrl(testUrl);

    try {
      const ok = await checkHealth();
      if (ok) {
        const health = await getHealth().catch(() => null);
        setBackendVersion(health?.version ?? "");
        setConnected(true);
        // Auto-advance if we were on the backend step
        if (step === 1) {
          setTimeout(() => setStep(2), 800);
        }
      } else {
        if (!silent) setFailMsg("Backend returned an error. Is it running?");
      }
    } catch {
      if (!silent) setFailMsg("Could not connect. Check the URL and make sure the backend is running.");
    }
    setChecking(false);
  }

  // Load key status when entering step 2
  useEffect(() => {
    if (step === 2 && connected) {
      getKeyStatus().then(setKeyStatus).catch(() => {});
    }
  }, [step, connected]);

  async function saveApiKeys() {
    const keys: Record<string, string> = {};
    if (anthropicKey.trim()) keys.anthropic_api_key = anthropicKey.trim();
    if (openaiKey.trim()) keys.openai_api_key = openaiKey.trim();
    if (Object.keys(keys).length === 0) {
      setStep(3);
      return;
    }
    setSavingKeys(true);
    await setKeys(keys).catch(() => {});
    setSavingKeys(false);
    setKeysSaved(true);
    setTimeout(() => setStep(3), 600);
  }

  function finish() {
    setSetupDone();
    onComplete();
  }

  const current = STEPS[step];
  const isLocalUrl = url.includes("localhost") || url.includes("127.0.0.1");

  return (
    <div className="flex flex-col items-center justify-center h-screen bg-surface text-label">
      {/* Progress dots */}
      <div className="flex gap-2 mb-8">
        {STEPS.map((s, i) => (
          <div key={s.id}
            className={`w-2 h-2 rounded-full transition-colors ${
              i === step ? "bg-accent" : i < step ? "bg-label-secondary" : "bg-label-tertiary"
            }`} />
        ))}
      </div>

      <div className="w-full max-w-sm px-6">
        <h1 className="text-xl font-semibold mb-2 text-center">{current.title}</h1>

        {/* ── Step 0: Welcome ── */}
        {step === 0 && (
          <div className="text-center">
            <img src="/appicon-512.png" alt="Asta" className="w-16 h-16 mb-6 rounded-2xl mx-auto" />
            <p className="text-label-secondary mb-8 text-13 leading-relaxed">
              Asta is your AI assistant that runs locally.
              Let's connect to your backend and get you set up.
            </p>
            {/* If already connected, show status */}
            {connected && (
              <div className="flex items-center justify-center gap-2 mb-4 text-success text-13">
                <IconCheck size={14} />
                <span>Backend already connected{backendVersion ? ` (v${backendVersion})` : ""}</span>
              </div>
            )}
            <button onClick={() => setStep(connected ? 2 : 1)}
              className="w-full bg-accent hover:bg-accent-hover text-white rounded-mac py-3 text-14 font-medium transition-colors">
              {connected ? "Continue" : "Get Started"}
            </button>
          </div>
        )}

        {/* ── Step 1: Backend Connection ── */}
        {step === 1 && (
          <div>
            <p className="text-label-secondary text-13 mb-4 leading-relaxed">
              Enter the URL where your Asta backend is running.
            </p>

            {/* URL input */}
            <input type="text" value={url}
              onChange={e => { setUrl(e.target.value); setConnected(false); setFailMsg(""); }}
              className="w-full bg-white/[.06] border border-separator rounded-mac px-4 py-2.5 text-13 font-mono text-label placeholder-label-tertiary outline-none focus:border-accent/50 transition-colors mb-3"
              placeholder="http://localhost:8010" />

            {/* Connection status */}
            {checking && (
              <div className="flex items-center gap-2 mb-3 text-label-secondary text-13">
                <div className="w-4 h-4 border-2 border-accent/40 border-t-accent rounded-full animate-spin" />
                Checking connection...
              </div>
            )}

            {connected && !checking && (
              <div className="bg-success/10 border border-success/20 rounded-mac px-4 py-3 mb-3 flex items-center gap-2">
                <IconCheck size={14} className="text-success shrink-0" />
                <div>
                  <p className="text-13 text-success font-medium">Backend connected!</p>
                  {backendVersion && <p className="text-11 text-success/70 mt-0.5">Version {backendVersion}</p>}
                </div>
              </div>
            )}

            {failMsg && !checking && (
              <div className="bg-danger/10 border border-danger/20 rounded-mac px-4 py-3 mb-3">
                <div className="flex items-start gap-2">
                  <IconWarning size={14} className="text-danger shrink-0 mt-0.5" />
                  <div>
                    <p className="text-13 text-danger">{failMsg}</p>
                    {isLocalUrl && (
                      <div className="mt-2">
                        <p className="text-11 text-label-tertiary mb-1">Start the backend manually:</p>
                        <div className="bg-white/[.04] rounded-lg px-3 py-2 font-mono text-11 text-label-secondary select-all">
                          cd ~/asta && ./asta.sh start
                        </div>
                        <button onClick={() => testBackend(url)}
                          className="mt-2 text-12 text-accent hover:text-accent-hover transition-colors">
                          Retry connection
                        </button>
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

            {/* Test button */}
            {!connected && (
              <button onClick={() => testBackend(url)} disabled={checking}
                className="w-full bg-accent hover:bg-accent-hover disabled:opacity-50 text-white rounded-mac py-3 text-14 font-medium transition-colors">
                {checking ? "Testing..." : "Test Connection"}
              </button>
            )}

            {connected && (
              <button onClick={() => setStep(2)}
                className="w-full bg-accent hover:bg-accent-hover text-white rounded-mac py-3 text-14 font-medium transition-colors">
                Continue
              </button>
            )}

            <button onClick={() => setStep(2)}
              className="w-full mt-2 text-label-tertiary hover:text-label-secondary text-13 py-2 transition-colors">
              Skip for now
            </button>
          </div>
        )}

        {/* ── Step 2: API Keys ── */}
        {step === 2 && (
          <div>
            <p className="text-label-secondary text-13 mb-4 leading-relaxed">
              Add at least one API key to start chatting. You can add more later in Settings.
            </p>

            {/* Anthropic key */}
            <div className="mb-3">
              <div className="flex items-center gap-2 mb-1">
                <label className="text-11 text-label-tertiary">Anthropic (Claude)</label>
                {keyStatus.anthropic_key && (
                  <span className="text-11 text-success">already set</span>
                )}
              </div>
              <input type="password" value={anthropicKey}
                onChange={e => setAnthropicKey(e.target.value)}
                placeholder={keyStatus.anthropic_key ? "Leave blank to keep existing" : "sk-ant-..."}
                className="w-full bg-white/[.06] border border-separator rounded-mac px-4 py-2.5 text-13 font-mono text-label placeholder-label-tertiary outline-none focus:border-accent/50" />
            </div>

            {/* OpenAI key */}
            <div className="mb-3">
              <div className="flex items-center gap-2 mb-1">
                <label className="text-11 text-label-tertiary">OpenAI (GPT)</label>
                {keyStatus.openai_key && (
                  <span className="text-11 text-success">already set</span>
                )}
              </div>
              <input type="password" value={openaiKey}
                onChange={e => setOpenaiKey(e.target.value)}
                placeholder={keyStatus.openai_key ? "Leave blank to keep existing" : "sk-..."}
                className="w-full bg-white/[.06] border border-separator rounded-mac px-4 py-2.5 text-13 font-mono text-label placeholder-label-tertiary outline-none focus:border-accent/50" />
            </div>

            {/* Other providers note */}
            <div className="bg-white/[.03] rounded-mac p-3 mb-4">
              <p className="text-11 text-label-tertiary leading-relaxed">
                Other providers (Google Gemini, Groq, OpenRouter, Brave Search) can be configured in Settings after setup.
              </p>
            </div>

            {keysSaved && (
              <div className="flex items-center gap-2 mb-3 text-success text-13">
                <IconCheck size={14} />
                Keys saved!
              </div>
            )}

            <button onClick={saveApiKeys} disabled={savingKeys}
              className="w-full bg-accent hover:bg-accent-hover disabled:opacity-50 text-white rounded-mac py-3 text-14 font-medium transition-colors">
              {savingKeys ? "Saving..." : (anthropicKey || openaiKey) ? "Save & Continue" : "Skip"}
            </button>
          </div>
        )}

        {/* ── Step 3: Done ── */}
        {step === 3 && (
          <div className="text-center">
            <img src="/appicon-512.png" alt="Asta" className="w-14 h-14 mb-4 rounded-2xl mx-auto" />
            <p className="text-label-secondary text-13 mb-3 leading-relaxed">
              Asta lives in your menu bar. Use the global shortcut to show and hide it anytime.
            </p>
            <div className="bg-white/[.04] rounded-mac px-4 py-3 mb-6">
              <div className="flex items-center justify-center">
                <kbd className="bg-white/[.08] rounded px-2 py-1 font-mono text-12 text-label-secondary">Alt + Space</kbd>
              </div>
            </div>

            {connected && (
              <div className="flex items-center justify-center gap-2 mb-4 text-success text-13">
                <div className="w-2 h-2 rounded-full bg-success" />
                Connected to backend{backendVersion ? ` v${backendVersion}` : ""}
              </div>
            )}

            <button onClick={finish}
              className="w-full bg-accent hover:bg-accent-hover text-white rounded-mac py-3 text-14 font-medium transition-colors">
              Open Asta
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
