import { resolveAgentIcon } from "../../lib/icons";

interface Agent { id: string; name: string; icon?: string; enabled: boolean; }

const FALLBACK_SUGGESTIONS = [
  "Summarize my recent notes",
  "What's on my schedule today?",
  "Write a quick email draft",
  "Search the web for latest news",
];

interface EmptyStateProps {
  agents: Agent[];
  inputHasText: boolean;
  onAgentClick: (agent: Agent) => void;
  onSuggestionClick: (text: string) => void;
}

export default function EmptyState({ agents, inputHasText, onAgentClick, onSuggestionClick }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-4 relative overflow-hidden pt-8">
      {/* 8-bit floating pixel sprites */}
      <div className="absolute inset-0 pointer-events-none transition-opacity duration-500" style={{ opacity: inputHasText ? 0 : 1 }} aria-hidden>
        {/* Left side sprites */}
        <div className="pixel-block absolute left-[6%] top-[12%]" style={{ animationDelay: "0s", animationDuration: "7s" }}>
          <svg width="20" height="20" viewBox="0 0 5 5" style={{ imageRendering: "pixelated" }}>
            <rect x="2" y="0" width="1" height="1" fill="var(--accent)" /><rect x="0" y="2" width="1" height="1" fill="var(--accent)" />
            <rect x="1" y="1" width="1" height="1" fill="var(--accent)" /><rect x="2" y="2" width="1" height="1" fill="var(--accent)" />
            <rect x="3" y="1" width="1" height="1" fill="var(--accent)" /><rect x="4" y="2" width="1" height="1" fill="var(--accent)" />
            <rect x="2" y="4" width="1" height="1" fill="var(--accent)" /><rect x="1" y="3" width="1" height="1" fill="var(--accent)" />
            <rect x="3" y="3" width="1" height="1" fill="var(--accent)" />
          </svg>
        </div>
        <div className="pixel-block absolute left-[14%] top-[38%]" style={{ animationDelay: "1.2s", animationDuration: "8s" }}>
          <svg width="15" height="15" viewBox="0 0 5 5" style={{ imageRendering: "pixelated" }}>
            <rect x="2" y="0" width="1" height="1" fill="#a78bfa" /><rect x="1" y="1" width="1" height="1" fill="#a78bfa" />
            <rect x="3" y="1" width="1" height="1" fill="#a78bfa" /><rect x="0" y="2" width="1" height="1" fill="#a78bfa" />
            <rect x="4" y="2" width="1" height="1" fill="#a78bfa" /><rect x="1" y="3" width="1" height="1" fill="#a78bfa" />
            <rect x="3" y="3" width="1" height="1" fill="#a78bfa" /><rect x="2" y="4" width="1" height="1" fill="#a78bfa" />
          </svg>
        </div>
        <div className="pixel-block absolute left-[4%] top-[60%]" style={{ animationDelay: "2.4s", animationDuration: "9s" }}>
          <svg width="21" height="18" viewBox="0 0 7 6" style={{ imageRendering: "pixelated" }}>
            <rect x="1" y="0" width="2" height="1" fill="var(--accent-end, #FF3D7F)" />
            <rect x="4" y="0" width="2" height="1" fill="var(--accent-end, #FF3D7F)" />
            <rect x="0" y="1" width="7" height="1" fill="var(--accent-end, #FF3D7F)" />
            <rect x="0" y="2" width="7" height="1" fill="var(--accent-end, #FF3D7F)" />
            <rect x="1" y="3" width="5" height="1" fill="var(--accent-end, #FF3D7F)" />
            <rect x="2" y="4" width="3" height="1" fill="var(--accent-end, #FF3D7F)" />
            <rect x="3" y="5" width="1" height="1" fill="var(--accent-end, #FF3D7F)" />
          </svg>
        </div>
        <div className="pixel-block absolute left-[10%] top-[78%]" style={{ animationDelay: "0.8s", animationDuration: "6.5s" }}>
          <svg width="20" height="20" viewBox="0 0 5 5" style={{ imageRendering: "pixelated" }}>
            <rect x="2" y="0" width="1" height="1" fill="#FFD700" /><rect x="0" y="2" width="5" height="1" fill="#FFD700" />
            <rect x="2" y="1" width="1" height="1" fill="#FFD700" /><rect x="1" y="1" width="1" height="1" fill="#FFD700" opacity="0.5" />
            <rect x="3" y="1" width="1" height="1" fill="#FFD700" opacity="0.5" /><rect x="2" y="3" width="1" height="1" fill="#FFD700" />
            <rect x="1" y="4" width="1" height="1" fill="#FFD700" /><rect x="3" y="4" width="1" height="1" fill="#FFD700" />
          </svg>
        </div>
        <div className="pixel-block absolute left-[20%] top-[25%]" style={{ animationDelay: "3.5s", animationDuration: "8.5s" }}>
          <svg width="12" height="12" viewBox="0 0 3 3" style={{ imageRendering: "pixelated" }}>
            <rect width="3" height="3" fill="var(--accent)" /><rect x="0" y="0" width="1" height="1" fill="white" opacity="0.3" />
          </svg>
        </div>
        {/* Right side sprites */}
        <div className="pixel-block absolute right-[8%] top-[15%]" style={{ animationDelay: "0.5s", animationDuration: "7.5s" }}>
          <svg width="18" height="18" viewBox="0 0 7 6" style={{ imageRendering: "pixelated" }}>
            <rect x="1" y="0" width="2" height="1" fill="var(--accent)" />
            <rect x="4" y="0" width="2" height="1" fill="var(--accent)" />
            <rect x="0" y="1" width="7" height="1" fill="var(--accent)" />
            <rect x="0" y="2" width="7" height="1" fill="var(--accent)" />
            <rect x="1" y="3" width="5" height="1" fill="var(--accent)" />
            <rect x="2" y="4" width="3" height="1" fill="var(--accent)" />
            <rect x="3" y="5" width="1" height="1" fill="var(--accent)" />
          </svg>
        </div>
        <div className="pixel-block absolute right-[5%] top-[35%]" style={{ animationDelay: "1.8s", animationDuration: "6s" }}>
          <svg width="15" height="15" viewBox="0 0 5 5" style={{ imageRendering: "pixelated" }}>
            <rect x="2" y="0" width="1" height="1" fill="var(--accent-end, #FF3D7F)" />
            <rect x="1" y="1" width="3" height="1" fill="var(--accent-end, #FF3D7F)" />
            <rect x="0" y="2" width="5" height="1" fill="var(--accent-end, #FF3D7F)" />
            <rect x="2" y="3" width="1" height="1" fill="var(--accent-end, #FF3D7F)" />
            <rect x="2" y="4" width="1" height="1" fill="var(--accent-end, #FF3D7F)" />
          </svg>
        </div>
        <div className="pixel-block absolute right-[12%] top-[55%]" style={{ animationDelay: "3s", animationDuration: "7.2s" }}>
          <svg width="16" height="16" viewBox="0 0 5 5" style={{ imageRendering: "pixelated" }}>
            <rect x="2" y="0" width="1" height="1" fill="#FFD700" /><rect x="0" y="2" width="5" height="1" fill="#FFD700" />
            <rect x="2" y="1" width="1" height="1" fill="#FFD700" /><rect x="1" y="1" width="1" height="1" fill="#FFD700" opacity="0.5" />
            <rect x="3" y="1" width="1" height="1" fill="#FFD700" opacity="0.5" /><rect x="2" y="3" width="1" height="1" fill="#FFD700" />
            <rect x="1" y="4" width="1" height="1" fill="#FFD700" /><rect x="3" y="4" width="1" height="1" fill="#FFD700" />
          </svg>
        </div>
        <div className="pixel-block absolute right-[3%] top-[72%]" style={{ animationDelay: "2s", animationDuration: "8.2s" }}>
          <svg width="20" height="20" viewBox="0 0 5 5" style={{ imageRendering: "pixelated" }}>
            <rect x="2" y="0" width="1" height="1" fill="#a78bfa" /><rect x="1" y="1" width="1" height="1" fill="#a78bfa" />
            <rect x="3" y="1" width="1" height="1" fill="#a78bfa" /><rect x="0" y="2" width="1" height="1" fill="#a78bfa" />
            <rect x="4" y="2" width="1" height="1" fill="#a78bfa" /><rect x="1" y="3" width="1" height="1" fill="#a78bfa" />
            <rect x="3" y="3" width="1" height="1" fill="#a78bfa" /><rect x="2" y="4" width="1" height="1" fill="#a78bfa" />
          </svg>
        </div>
        <div className="pixel-block absolute right-[18%] top-[85%]" style={{ animationDelay: "0.3s", animationDuration: "6.8s" }}>
          <svg width="12" height="12" viewBox="0 0 3 3" style={{ imageRendering: "pixelated" }}>
            <rect width="3" height="3" fill="var(--accent-end, #FF3D7F)" /><rect x="0" y="0" width="1" height="1" fill="white" opacity="0.3" />
          </svg>
        </div>
        {/* Ambient glow orbs */}
        <div className="absolute w-48 h-48 rounded-full opacity-[0.03] pointer-events-none"
          style={{ background: "radial-gradient(circle, var(--accent), transparent 70%)", top: "8%", left: "-3%", animation: "orb-float 12s ease-in-out infinite" }} />
        <div className="absolute w-36 h-36 rounded-full opacity-[0.025] pointer-events-none"
          style={{ background: "radial-gradient(circle, var(--accent-end, #FF3D7F), transparent 70%)", bottom: "5%", right: "-2%", animation: "orb-float 15s ease-in-out infinite reverse" }} />
      </div>

      <div className="relative w-20 h-20 z-10 hero-enter" style={{ animationDelay: "0s" }}>
        <div className="absolute inset-0 rounded-full bg-[var(--user-bubble)] opacity-20 blur-xl animate-[orb-float_8s_ease-in-out_infinite]" />
        <img src="/appicon-512.png" alt="Asta" className="relative w-20 h-20 rounded-2xl"
          style={{ boxShadow: "0 8px 32px rgba(255,107,44,0.12), 0 0 0 1px rgba(255,255,255,0.06)" }} />
      </div>
      <div className="text-center z-10 hero-enter" style={{ animationDelay: "0.12s" }}>
        <p className="text-label text-[28px] font-bold tracking-tight leading-tight">What can I help with?</p>
        <p className="text-label-tertiary text-13 mt-2 font-medium">Ask anything, or try a suggestion below</p>
      </div>
      <div className="grid grid-cols-2 gap-2.5 max-w-sm w-full mt-2 z-10 hero-enter" style={{ animationDelay: "0.24s" }}>
        {(agents.filter(a => a.enabled).slice(0, 4).length > 0
          ? agents.filter(a => a.enabled).slice(0, 4).map(a => {
            const ai = resolveAgentIcon(a as any);
            return (
              <button key={a.id} onClick={() => onAgentClick(a)}
                className="flex items-center gap-2.5 bg-white/[.04] hover:bg-white/[.08] border border-separator hover:border-separator-bold rounded-xl px-3.5 py-3 transition-all duration-200 active:scale-[0.97] text-left">
                <span className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0" style={{ background: ai.bg, color: ai.color }}>
                  <ai.Icon size={15} />
                </span>
                <span className="text-13 text-label-secondary font-medium truncate">{a.name}</span>
              </button>
            );
          })
          : FALLBACK_SUGGESTIONS.map(s => (
            <button key={s} onClick={() => onSuggestionClick(s)}
              className="flex items-center gap-2.5 bg-white/[.04] hover:bg-white/[.08] border border-separator hover:border-separator-bold rounded-xl px-3.5 py-3 transition-all duration-200 active:scale-[0.97] text-left">
              <span className="text-13 text-label-secondary truncate">{s}</span>
            </button>
          ))
        )}
      </div>
      {/* Category cards */}
      <div className="flex gap-4 mt-4 z-10 hero-enter" style={{ animationDelay: "0.36s" }}>
        {[
          { img: "/cat-office.jpeg", label: "Office" },
          { img: "/cat-finance.jpeg", label: "Finance" },
          { img: "/cat-coding.jpeg", label: "Coding" },
        ].map(cat => (
          <button key={cat.label}
            className="group flex flex-col items-center gap-2 transition-all duration-300 hover:scale-[1.05] active:scale-[0.98] cursor-default">
            <div className="relative w-36 h-24 rounded-2xl overflow-hidden border border-white/[.08] group-hover:border-white/[.2] group-hover:shadow-lg transition-all duration-300">
              <img src={cat.img} alt={cat.label} className="absolute inset-0 w-full h-full object-cover" />
            </div>
            <span className="text-12 text-label-tertiary group-hover:text-label-secondary font-medium transition-colors">{cat.label}</span>
          </button>
        ))}
      </div>
      <p className="text-label-tertiary text-11 tracking-wide mt-4 opacity-40 z-10 hero-enter text-center" style={{ animationDelay: "0.48s" }}>
        Enter to send · Shift+Enter for new line
      </p>
    </div>
  );
}
