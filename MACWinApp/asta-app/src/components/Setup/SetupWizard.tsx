import { useState, useEffect } from "react";
import { getKeyStatus, setKeys } from "../../lib/api";
import { setSetupDone } from "../../lib/store";
import { IconCheck } from "../../lib/icons";

interface Props {
  onComplete: () => void;
}

const STEPS = [
  { id: 1, title: "Welcome to Asta" },
  { id: 2, title: "API Keys" },
  { id: 3, title: "You're ready!" },
];

export default function SetupWizard({ onComplete }: Props) {
  const [step, setStep] = useState(0);

  // Key entry state
  const [anthropicKey, setAnthropicKey] = useState("");
  const [openaiKey, setOpenaiKey] = useState("");
  const [keyStatus, setKeyStatus] = useState<Record<string, boolean>>({});
  const [savingKeys, setSavingKeys] = useState(false);
  const [keysSaved, setKeysSaved] = useState(false);

  // Load key status when entering step 1
  useEffect(() => {
    if (step === 1) {
      getKeyStatus().then(setKeyStatus).catch(() => {});
    }
  }, [step]);

  async function saveApiKeys() {
    const keys: Record<string, string> = {};
    if (anthropicKey.trim()) keys.anthropic_api_key = anthropicKey.trim();
    if (openaiKey.trim()) keys.openai_api_key = openaiKey.trim();
    if (Object.keys(keys).length === 0) {
      setStep(2);
      return;
    }
    setSavingKeys(true);
    await setKeys(keys).catch(() => {});
    setSavingKeys(false);
    setKeysSaved(true);
    setTimeout(() => setStep(2), 600);
  }

  function finish() {
    setSetupDone();
    onComplete();
  }

  const current = STEPS[step];

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
              Asta is your AI assistant. Let's get you set up with your API keys.
            </p>
            <button onClick={() => setStep(1)}
              className="w-full bg-accent hover:bg-accent-hover text-white rounded-mac py-3 text-14 font-medium transition-colors">
              Get Started
            </button>
          </div>
        )}

        {/* ── Step 1: API Keys ── */}
        {step === 1 && (
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

        {/* ── Step 2: Done ── */}
        {step === 2 && (
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
