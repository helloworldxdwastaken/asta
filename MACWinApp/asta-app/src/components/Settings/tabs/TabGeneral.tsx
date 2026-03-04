import { useState, useEffect } from "react";
import { getDefaultAI, setDefaultAI, getThinking, setThinking, getMoodSetting, setMoodSetting, getReasoning, setReasoning, getFinalMode, setFinalMode, getVision, setVision } from "../../../lib/api";
import { getThemeMode, setThemeMode, type ThemeMode } from "../../../lib/theme";
import { IconSun, IconMoon, IconMonitor } from "../../../lib/icons";

const PROVIDERS = [
  { key: "claude", name: "Claude" }, { key: "google", name: "Gemini" },
  { key: "openrouter", name: "OpenRouter" }, { key: "ollama", name: "Local (Ollama)" },
];
const notifySettingsChanged = () => window.dispatchEvent(new Event("settings-changed"));
const THINKING = ["off", "minimal", "low", "medium", "high", "xhigh"];
const MOODS = ["normal", "friendly", "serious"];

const THEME_MODES: { mode: ThemeMode; label: string; Icon: React.FC<{ size?: number }> }[] = [
  { mode: "system", label: "System", Icon: IconMonitor },
  { mode: "light", label: "Light", Icon: IconSun },
  { mode: "dark", label: "Dark", Icon: IconMoon },
];

export default function TabGeneral() {
  const [provider, setProvider] = useState("claude");
  const [thinking, setThinkingState] = useState("off");
  const [reasoning, setReasoningState] = useState("off");
  const [mood, setMoodState] = useState("normal");
  const [finalMode, setFinalModeState] = useState("off");
  const [vision, setVisionState] = useState(true);
  const [theme, setTheme] = useState<ThemeMode>(getThemeMode());

  useEffect(() => {
    getDefaultAI().then(r => setProvider(r.provider ?? r.default_ai_provider ?? "claude")).catch(()=>{});
    getThinking().then(r => setThinkingState(r.thinking_level ?? "off")).catch(()=>{});
    getReasoning().then(r => setReasoningState(r.reasoning_mode ?? r.reasoning_budget ?? "off")).catch(()=>{});
    getMoodSetting().then(r => setMoodState(r.mood ?? "normal")).catch(()=>{});
    getFinalMode().then(r => setFinalModeState(r.final_mode ?? "off")).catch(()=>{});
    getVision().then(r => setVisionState(r.preprocess ?? true)).catch(()=>{});
  }, []);

  return (
    <div className="text-label space-y-7">
      <h2 className="text-16 font-semibold">General</h2>

      <Section title="Appearance">
        <div className="flex gap-2">
          {THEME_MODES.map(({ mode, label, Icon }) => (
            <button key={mode} onClick={() => { setTheme(mode); setThemeMode(mode); }}
              className={`flex items-center gap-2 px-4 py-2.5 rounded-mac text-13 font-medium transition-all duration-200 active:scale-[0.97] ${
                theme === mode
                  ? "accent-gradient text-white shadow-glow-sm"
                  : "bg-white/[.05] text-label-secondary hover:bg-white/[.08] border border-separator"
              }`}>
              <Icon size={14} />
              {label}
            </button>
          ))}
        </div>
        <p className="text-11 text-label-tertiary mt-1.5">
          {theme === "system" ? "Follows your operating system setting" : theme === "light" ? "Always use light mode" : "Always use dark mode"}
        </p>
      </Section>

      <Section title="AI Provider">
        {PROVIDERS.map(p => (
          <Radio key={p.key} label={p.name} checked={provider === p.key}
            onChange={async () => { setProvider(p.key); await setDefaultAI(p.key); notifySettingsChanged(); }} />
        ))}
      </Section>

      <Section title="Thinking Level">
        <div className="flex flex-wrap gap-2">
          {THINKING.map(l => (
            <Chip key={l} label={l} active={thinking === l}
              onClick={async () => { setThinkingState(l); await setThinking(l); notifySettingsChanged(); }} />
          ))}
        </div>
      </Section>

      <Section title="Reasoning Mode">
        <div className="flex gap-2">
          {["off", "on", "stream"].map(m => (
            <Chip key={m} label={m} active={reasoning === m}
              onClick={async () => { setReasoningState(m); await setReasoning(m); }} />
          ))}
        </div>
      </Section>

      <Section title="Mood">
        <div className="flex gap-3">
          {MOODS.map(m => (
            <Radio key={m} label={m} checked={mood === m} capitalize
              onChange={async () => { setMoodState(m); await setMoodSetting(m); notifySettingsChanged(); }} />
          ))}
        </div>
        <p className="text-11 text-label-tertiary mt-1.5">Changes the tone of AI replies</p>
      </Section>

      <Section title="Final Mode">
        <div className="flex gap-2">
          {["off", "strict"].map(m => (
            <Chip key={m} label={m} active={finalMode === m}
              onClick={async () => { setFinalModeState(m); await setFinalMode(m); }} />
          ))}
        </div>
        <p className="text-11 text-label-tertiary mt-1.5">Strips thinking tags from output</p>
      </Section>

      <Section title="Vision">
        <Toggle checked={vision} onChange={async v => { setVisionState(v); try { await setVision(v); } catch { setVisionState(!v); } }} label="Enable image understanding" />
      </Section>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h3 className="text-10 font-bold text-label-tertiary uppercase tracking-widest mb-2.5">{title}</h3>
      {children}
    </section>
  );
}
function Radio({ label, checked, onChange, capitalize }: { label: string; checked: boolean; onChange: () => void; capitalize?: boolean }) {
  return (
    <label className="flex items-center gap-2.5 cursor-pointer py-1 group">
      <span className={`w-4 h-4 rounded-full border-2 flex items-center justify-center transition-colors ${checked ? "border-accent" : "border-label-tertiary/40 group-hover:border-label-tertiary"}`}>
        {checked && <span className="w-2 h-2 rounded-full bg-accent" />}
      </span>
      <input type="radio" checked={checked} onChange={onChange} className="sr-only" />
      <span className={`text-13 transition-colors ${checked ? "text-label" : "text-label-secondary"} ${capitalize ? "capitalize" : ""}`}>{label}</span>
    </label>
  );
}
function Chip({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button onClick={onClick}
      className={`px-3.5 py-1.5 rounded-mac text-12 font-medium capitalize transition-all duration-200 active:scale-[0.96] ${active ? "accent-gradient text-white shadow-glow-sm" : "bg-white/[.05] text-label-secondary hover:bg-white/[.08] border border-separator"}`}>
      {label}
    </button>
  );
}
export function Toggle({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label?: string }) {
  return (
    <label className="flex items-center gap-3 cursor-pointer">
      <button type="button" role="switch" aria-checked={checked} onClick={() => onChange(!checked)}
        className={`toggle-track relative inline-flex w-[42px] h-[26px] rounded-full transition-all duration-200 ${checked ? "bg-accent shadow-glow-sm" : "toggle-off"}`}>
        <span className={`absolute top-[3px] left-[3px] w-5 h-5 rounded-full shadow-sm transition-transform duration-200 ${checked ? "translate-x-4 bg-white" : "translate-x-0 toggle-knob"}`} />
      </button>
      {label && <span className="text-13 text-label-secondary">{label}</span>}
    </label>
  );
}
