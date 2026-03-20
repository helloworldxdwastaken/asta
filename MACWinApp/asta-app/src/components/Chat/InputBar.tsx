import React, { useRef } from "react";
import {
  IconAttach, IconSend, IconStop, IconCheck, IconChevronDown, IconAgents,
  resolveAgentIcon,
} from "../../lib/icons";
import { setDefaultAI } from "../../lib/api";
import ProviderLogo from "../ProviderLogo";

interface Agent { id: string; name: string; icon?: string; enabled: boolean; }
interface PendingFile { name: string; type: "image" | "text" | "pdf"; content: string; }

const PROVIDERS = [
  { key: "claude",      name: "Claude" },
  { key: "google",      name: "Gemini" },
  { key: "openrouter",  name: "OR" },
  { key: "ollama",      name: "Local" },
];

interface InputBarProps {
  input: string;
  onInputChange: (val: string) => void;
  onSend: () => void;
  onStop: () => void;
  onKeyDown: (e: React.KeyboardEvent<HTMLTextAreaElement>) => void;
  streaming: boolean;
  pendingFiles: PendingFile[];
  onRemoveFile: (index: number) => void;
  onFilesSelected: (files: File[]) => void;
  agents: Agent[];
  selectedAgent: Agent | null;
  onSelectAgent: (agent: Agent | null) => void;
  provider: string;
  onProviderChange: (key: string) => void;
  showProviderMenu: boolean;
  onToggleProviderMenu: () => void;
  showAgentMenu: boolean;
  onToggleAgentMenu: () => void;
  inputRef: React.RefObject<HTMLTextAreaElement | null>;
}

export default function InputBar({
  input, onInputChange, onSend, onStop, onKeyDown,
  streaming, pendingFiles, onRemoveFile, onFilesSelected,
  agents, selectedAgent, onSelectAgent,
  provider, onProviderChange,
  showProviderMenu, onToggleProviderMenu,
  showAgentMenu, onToggleAgentMenu,
  inputRef,
}: InputBarProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const enabledAgents = agents.filter(a => a.enabled);
  const providerName = PROVIDERS.find(p => p.key === provider)?.name ?? provider;

  return (
    <div className="px-4 py-3">
      <div className="bg-white/[.04] border border-separator hover:border-separator-bold focus-within:border-accent/30 rounded-2xl transition-all duration-200">
        {/* Pending file chips */}
        {pendingFiles.length > 0 && (
          <div className="flex flex-wrap gap-1.5 px-4 pt-3 pb-0">
            {pendingFiles.map((f, i) => (
              <span key={i} className="inline-flex items-center gap-1.5 bg-white/[.06] border border-separator rounded-lg px-2.5 py-1 text-11 text-label-secondary animate-scale-in">
                <span>{f.type === "image" ? "\uD83D\uDDBC" : f.type === "pdf" ? "\uD83D\uDCC4" : "\uD83D\uDCCE"}</span>
                <span className="max-w-32 truncate">{f.name}</span>
                <button onClick={() => onRemoveFile(i)} className="text-label-tertiary hover:text-label ml-0.5 transition-colors">&times;</button>
              </span>
            ))}
          </div>
        )}

        {/* Textarea */}
        <textarea
          ref={inputRef} rows={1} value={input}
          onChange={e => onInputChange(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder={selectedAgent ? `Message @${selectedAgent.name}...` : "Ask anything..."}
          className="w-full bg-transparent px-4 pt-3 pb-2 text-14 text-label placeholder-label-tertiary outline-none resize-none"
          style={{ minHeight: 40, maxHeight: 200, lineHeight: "20px" }}
          onInput={e => { const el = e.currentTarget; el.style.height = "auto"; el.style.height = Math.min(el.scrollHeight, 200) + "px"; }}
        />

        {/* Bottom toolbar */}
        <div className="flex items-center justify-between px-2 pb-2 pt-0.5">
          {/* Left: attach + agent icon */}
          <div className="flex items-center gap-0.5">
            <button onClick={() => fileInputRef.current?.click()}
              className="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-white/[.06] text-label-tertiary hover:text-label-secondary shrink-0 transition-colors" title="Attach file">
              <IconAttach size={16} />
            </button>
            <input ref={fileInputRef} type="file" multiple accept="image/*,.pdf,.txt,.md,.csv,.json,.ts,.tsx,.js,.jsx,.py,.sh,.yaml,.yml,.toml,.xml,.html,.css" className="hidden"
              onChange={e => { if (e.target.files) onFilesSelected(Array.from(e.target.files)); e.target.value = ""; }} />

            {enabledAgents.length > 0 && (
              <div className="relative shrink-0">
                <button
                  onClick={e => { e.stopPropagation(); onToggleAgentMenu(); }}
                  className={`w-8 h-8 flex items-center justify-center rounded-lg transition-all duration-200 active:scale-[0.95] ${
                    selectedAgent
                      ? "text-accent bg-accent/[.12]"
                      : "text-label-tertiary hover:text-label-secondary hover:bg-white/[.06]"
                  }`}
                  title={selectedAgent ? selectedAgent.name : "Select agent"}>
                  <IconAgents size={16} />
                </button>
                {showAgentMenu && (
                  <div className="absolute left-0 bottom-full mb-1.5 bg-surface-raised border border-separator-bold rounded-xl shadow-modal py-1.5 z-50 w-56 max-h-64 overflow-y-auto scrollbar-thin animate-scale-in">
                    <button
                      className={`w-full text-left px-4 py-2.5 text-13 transition-all duration-150 ${!selectedAgent ? "text-accent bg-accent/[.08]" : "text-label-secondary hover:bg-white/[.04]"}`}
                      onClick={() => { onSelectAgent(null); }}>
                      No agent (default)
                    </button>
                    <div className="border-t border-separator mx-3 my-1" />
                    {enabledAgents.map(a => {
                      const ai = resolveAgentIcon(a as any);
                      return (
                        <button key={a.id}
                          className={`w-full text-left px-4 py-2.5 text-13 transition-all duration-150 flex items-center gap-2.5 ${
                            selectedAgent?.id === a.id ? "text-accent bg-accent/[.08]" : "text-label-secondary hover:bg-white/[.04]"
                          }`}
                          onClick={() => { onSelectAgent(a); }}>
                          <span className="w-5 h-5 rounded-md flex items-center justify-center shrink-0" style={{ background: ai.bg, color: ai.color }}>
                            <ai.Icon size={12} />
                          </span>
                          <span className="truncate">{a.name}</span>
                          {selectedAgent?.id === a.id && <IconCheck size={12} className="ml-auto text-accent shrink-0" />}
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Right: provider + send */}
          <div className="flex items-center gap-1.5">
            {/* Provider chip */}
            <div className="relative">
              <button
                onClick={e => { e.stopPropagation(); onToggleProviderMenu(); }}
                className="flex items-center gap-1.5 text-11 text-label-tertiary hover:text-label-secondary rounded-lg px-2 h-8 transition-all duration-200 active:scale-[0.97]"
              >
                <ProviderLogo provider={provider} size={14} />
                <span>{providerName}</span>
                <IconChevronDown size={8} />
              </button>
              {showProviderMenu && (
                <div className="absolute right-0 bottom-full mb-1.5 bg-surface-raised border border-separator-bold rounded-mac shadow-modal py-1.5 z-50 w-52 animate-scale-in">
                  {PROVIDERS.map(p => (
                    <button key={p.key}
                      className={`w-full text-left px-4 py-2.5 text-13 transition-all duration-150 flex items-center gap-3 ${provider === p.key ? "text-accent bg-accent/[.08]" : "text-label-secondary hover:bg-white/[.04]"}`}
                      onClick={async () => { onProviderChange(p.key); await setDefaultAI(p.key); }}>
                      <ProviderLogo provider={p.key} size={18} />
                      {p.name}
                      {provider === p.key && <IconCheck size={12} className="ml-auto text-accent" />}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Send / Stop */}
            <button
              onClick={streaming ? onStop : onSend}
              disabled={!streaming && !input.trim()}
              className={`w-8 h-8 flex items-center justify-center rounded-[10px] shrink-0 transition-all duration-200 active:scale-[0.93] ${
                streaming
                  ? "bg-danger/20 text-danger hover:bg-danger/30"
                  : input.trim()
                    ? "accent-gradient text-white shadow-glow-sm hover:shadow-glow"
                    : "bg-white/[.06] text-label-tertiary"
              }`}
            >
              {streaming ? <IconStop size={14} /> : <IconSend size={14} />}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
