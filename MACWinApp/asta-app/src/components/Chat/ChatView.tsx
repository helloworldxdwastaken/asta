import { useState, useEffect, useRef, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  IconSliders, IconBrain, IconBook,
  IconAttach, IconChevronDown,
} from "../../lib/icons";
import {
  loadMessages, streamChat, setThinking, setMoodSetting,
  getDefaultAI, getThinking, getMoodSetting, truncateConversation,
} from "../../lib/api";
import type { StreamChunk } from "../../lib/api";
import EmptyState from "./EmptyState";
import MessageCard from "./MessageCard";
import type { Message } from "./MessageCard";
import InputBar from "./InputBar";
import ToolIndicator from "./ToolIndicator";

const THINKING_LEVELS = ["off", "minimal", "low", "medium", "high", "xhigh"];
const MOODS = ["normal", "friendly", "serious"];

const THINKING_WORDS = [
  "thinking", "pondering", "analyzing", "fabricating", "curiosating",
  "brainstorming", "computing", "imagining", "processing", "conjuring",
  "contemplating", "synthesizing", "decoding", "inventing", "wondering",
  "crunching", "assembling", "dreaming", "crafting", "brewing",
];

interface Agent { id: string; name: string; icon?: string; enabled: boolean; }
interface PendingFile { name: string; type: "image" | "text" | "pdf"; content: string; }

interface Props {
  conversationId?: string;
  onConversationCreated: (id: string) => void;
  agents: Agent[];
  isAdmin?: boolean;
}

function ThinkingWords() {
  const [idx, setIdx] = useState(() => Math.floor(Math.random() * THINKING_WORDS.length));
  useEffect(() => {
    const t = setInterval(() => setIdx(i => (i + 1) % THINKING_WORDS.length), 2000);
    return () => clearInterval(t);
  }, []);
  return (
    <span className="inline-flex items-center gap-2 text-13 text-label-tertiary italic animate-fade-in">
      <span className="inline-flex gap-1">
        {[0, 1, 2].map(i => (
          <span key={i} className="w-1.5 h-1.5 bg-accent/50 rounded-full animate-bounce-dot"
            style={{ animationDelay: `${i * 150}ms` }} />
        ))}
      </span>
      <span key={idx} className="animate-fade-in">{THINKING_WORDS[idx]}</span>
    </span>
  );
}

export default function ChatView({ conversationId, onConversationCreated, agents, isAdmin = true }: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [streamContent, setStreamContent] = useState("");
  const [streamThinking, setStreamThinking] = useState("");
  const [activeTools, setActiveTools] = useState<string[]>([]);
  const [completedTools, setCompletedTools] = useState<string[]>([]);
  const [, setStreamProvider] = useState(""); // kept for re-render trigger
  const [input, setInput] = useState("");
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);
  const showThinking = true;
  const [webEnabled] = useState(localStorage.getItem("webEnabled") === "true");
  const [learningMode, setLearningMode] = useState(false);
  const [provider, setProvider] = useState("claude");
  const [thinkingLevel, setThinkingLevel] = useState(() => localStorage.getItem("thinkingLevel") ?? "off");
  const [mood, setMood] = useState("normal");
  const [showProviderMenu, setShowProviderMenu] = useState(false);
  const [showThinkingMenu, setShowThinkingMenu] = useState(false);
  const [showAgentMenu, setShowAgentMenu] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editText, setEditText] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const [showScrollBtn, setShowScrollBtn] = useState(false);
  const [streamStatus, setStreamStatus] = useState<string | null>(null);

  const endRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const stopRef = useRef<(() => void) | null>(null);
  const providerRef = useRef("");

  // Load settings from backend on mount + when changed in Settings
  const fetchSettings = useCallback(() => {
    getDefaultAI().then(r => setProvider(r.provider ?? r.default_ai_provider ?? "claude")).catch(() => {});
    getThinking().then(r => { const l = r.thinking_level ?? "off"; localStorage.setItem("thinkingLevel", l); setThinkingLevel(l); }).catch(() => {});
    getMoodSetting().then(r => setMood(r.mood ?? "normal")).catch(() => {});
  }, []);
  useEffect(() => {
    fetchSettings();
    window.addEventListener("settings-changed", fetchSettings);
    return () => window.removeEventListener("settings-changed", fetchSettings);
  }, [fetchSettings]);

  useEffect(() => {
    setSelectedAgent(null);
    setMessages([]);
    if (!conversationId) return;
    setLoading(true);
    loadMessages(conversationId)
      .then(r => setMessages((r.messages ?? []).map(normalizeMsg)))
      .catch(() => setMessages([]))
      .finally(() => setLoading(false));
  }, [conversationId]);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, streamContent]);

  const handleScroll = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    const fromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    setShowScrollBtn(fromBottom > 200);
  }, []);

  function scrollToBottom() {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }

  function normalizeMsg(m: any): Message {
    return {
      id: m.id ?? String(Date.now()),
      role: m.role,
      content: m.content ?? "",
      thinking: m.thinking ?? m.thinkingContent ?? undefined,
      provider: m.provider,
      activeTools: m.activeTools ?? [],
      completedTools: m.completedTools ?? [],
    };
  }

  // Drag & drop files
  const dragCounterRef = useRef(0);
  const [pendingFiles, setPendingFiles] = useState<PendingFile[]>([]);

  function handleDragEnter(e: React.DragEvent) {
    e.preventDefault();
    dragCounterRef.current++;
    if (e.dataTransfer.types.includes("Files")) setDragOver(true);
  }
  function handleDragOver(e: React.DragEvent) {
    e.preventDefault();
    e.dataTransfer.dropEffect = "copy";
  }
  function handleDragLeave(e: React.DragEvent) {
    e.preventDefault();
    dragCounterRef.current--;
    if (dragCounterRef.current === 0) setDragOver(false);
  }
  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    dragCounterRef.current = 0;
    setDragOver(false);
    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) handleFiles(files);
  }

  function handleFiles(files: File[]) {
    const textExts = [".md", ".txt", ".csv", ".json", ".ts", ".tsx", ".js", ".jsx", ".py", ".sh", ".yaml", ".yml", ".toml", ".xml", ".html", ".css"];
    files.forEach(file => {
      if (file.type.startsWith("image/")) {
        const reader = new FileReader();
        reader.onload = () => {
          setPendingFiles(prev => [...prev, { name: file.name, type: "image", content: reader.result as string }]);
        };
        reader.readAsDataURL(file);
      } else if (file.type === "application/pdf" || file.name.endsWith(".pdf")) {
        const reader = new FileReader();
        reader.onload = () => {
          setPendingFiles(prev => [...prev, { name: file.name, type: "pdf", content: reader.result as string }]);
        };
        reader.readAsDataURL(file);
      } else if (file.type.startsWith("text/") || textExts.some(ext => file.name.endsWith(ext))) {
        file.text().then(text => {
          setPendingFiles(prev => [...prev, { name: file.name, type: "text", content: text }]);
        });
      }
    });
  }

  function removeFile(index: number) {
    setPendingFiles(prev => prev.filter((_, i) => i !== index));
  }

  function buildFileContext(): string {
    if (pendingFiles.length === 0) return "";
    return pendingFiles.map(f => {
      if (f.type === "image") return `![${f.name}](${f.content})`;
      if (f.type === "pdf") return `<document name="${f.name}" type="pdf">${f.content}</document>`;
      return `<document name="${f.name}">\n${f.content}\n</document>`;
    }).join("\n");
  }

  async function send(overrideText?: string) {
    const rawText = (overrideText ?? input).trim();
    const fileCtx = buildFileContext();
    const text = fileCtx ? `${rawText}\n\n${fileCtx}` : rawText;
    if (!rawText || streaming) return;
    if (!overrideText) setInput("");
    setPendingFiles([]);
    if (inputRef.current) inputRef.current.style.height = "auto";

    const userMsg: Message = { id: Date.now().toString(), role: "user", content: rawText + (pendingFiles.length > 0 ? ` [${pendingFiles.map(f => f.name).join(", ")}]` : ""), activeTools: [], completedTools: [] };
    setMessages(prev => [...prev, userMsg]);
    setStreaming(true);
    setStreamContent("");
    setStreamThinking("");
    setActiveTools([]);
    setCompletedTools([]);
    setStreamProvider("");
    providerRef.current = "";

    let convId = conversationId;
    let accumulated = "";
    let thinkAccumulated = "";
    const doneTools: string[] = [];

    stopRef.current = streamChat(
      {
        text: selectedAgent ? `@${selectedAgent.name}: ${text}` : text,
        conversation_id: convId,
        web_enabled: webEnabled,
        provider,
      },
      (chunk: StreamChunk) => {
        if (chunk.conversation_id && !convId) {
          convId = chunk.conversation_id;
          onConversationCreated(convId!);
        }

        switch (chunk.type) {
          case "thinking": {
            let delta = chunk.delta ?? chunk.text ?? "";
            if (!thinkAccumulated && delta.startsWith("Reasoning:\n")) {
              delta = delta.slice("Reasoning:\n".length);
            }
            thinkAccumulated += delta;
            setStreamThinking(thinkAccumulated);
            break;
          }
          case "text": {
            const delta = chunk.delta ?? chunk.text ?? "";
            accumulated += delta;
            setStreamContent(accumulated);
            break;
          }
          case "assistant_final": {
            const finalText = (chunk.text ?? chunk.delta ?? "").trim();
            if (!finalText) break;
            if (finalText !== accumulated.trim()) {
              accumulated = finalText;
              setStreamContent(accumulated);
            }
            break;
          }
          case "tool_start": {
            const label = chunk.label ?? chunk.name ?? "tool";
            setActiveTools(prev => prev.includes(label) ? prev : [...prev, label]);
            accumulated = "";
            setStreamContent("");
            break;
          }
          case "tool_end": {
            const label = chunk.label ?? chunk.name ?? "tool";
            setActiveTools(prev => prev.filter(t => t !== label));
            if (!doneTools.includes(label)) doneTools.push(label);
            setCompletedTools([...doneTools]);
            break;
          }
          case "done": {
            if (!accumulated && chunk.reply) accumulated = chunk.reply.trim();
            if (chunk.provider) {
              providerRef.current = chunk.provider;
              setStreamProvider(chunk.provider);
            }
            break;
          }
          case "status": {
            const msg = chunk.text ?? chunk.delta ?? "";
            if (msg) setStreamStatus(msg);
            break;
          }
          case "error": {
            accumulated = chunk.error ?? chunk.text ?? "Server error";
            setStreamContent(accumulated);
            break;
          }
          default: break;
        }
      },
      (newConvId) => {
        if (newConvId && !convId) { convId = newConvId; onConversationCreated(convId!); }
        const msg: Message = {
          id: (Date.now() + 1).toString(), role: "assistant", content: accumulated,
          thinking: thinkAccumulated || undefined,
          provider: providerRef.current || undefined,
          activeTools: [],
          completedTools: [...doneTools],
        };
        setMessages(prev => [...prev, msg]);
        setStreamContent(""); setStreamThinking(""); setActiveTools([]); setCompletedTools([]); setStreamStatus(null); setStreaming(false);
        stopRef.current = null;
      },
      (err) => {
        const errMsg = err?.message || (typeof err === "string" ? err : String(err)) || "Unknown error";
        setMessages(prev => [...prev, {
          id: (Date.now()+1).toString(), role: "assistant", content: `Error: ${errMsg}`,
          activeTools: [], completedTools: [],
        }]);
        setStreamContent(""); setStreamStatus(null); setStreaming(false); stopRef.current = null;
      },
    );
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
  }

  function copyToClipboard(text: string, msgId: string) {
    navigator.clipboard.writeText(text).catch(() => {});
    setCopiedId(msgId);
    setTimeout(() => setCopiedId(null), 2000);
  }

  function startEdit(msg: Message) {
    setEditingId(msg.id);
    setEditText(msg.content);
  }

  async function submitEdit() {
    if (!editingId || !conversationId) return;
    if (!editText.trim()) { cancelEdit(); return; }
    if (streaming) return;
    const msgIndex = messages.findIndex(m => m.id === editingId);
    if (msgIndex < 0) return;
    const captured = editText;
    setEditingId(null);
    setEditText("");
    await truncateConversation(conversationId, msgIndex).catch(() => {});
    setMessages(prev => prev.slice(0, msgIndex));
    send(captured);
  }

  function cancelEdit() {
    setEditingId(null);
    setEditText("");
  }

  const closeMenus = () => { setShowProviderMenu(false); setShowThinkingMenu(false); setShowAgentMenu(false); };

  // Markdown components for streaming content (reuse the same renderers as MessageCard)
  const mdComponents = {
    a: ({ href, children, ...props }: any) => {
      function handleLinkClick(e: React.MouseEvent) {
        e.preventDefault();
        e.stopPropagation();
        if (!href) return;
        import("@tauri-apps/plugin-opener").then(({ openUrl }) => openUrl(href)).catch(() => {
          window.open(href, "_blank");
        });
      }
      return <a href={href} onClick={handleLinkClick} className="text-accent underline cursor-pointer" {...props}>{children}</a>;
    },
    img: ({ src, alt, ...props }: any) => (
      <img src={src} alt={alt ?? ""} {...props}
        className="max-w-full max-h-80 rounded-mac my-2 block"
        loading="lazy" />
    ),
    code: ({ className, children, ...props }: any) => {
      if (!className?.startsWith("language-")) {
        return <code className={className} {...props}>{children}</code>;
      }
      // Inline CodeBlock for streaming — same style as MessageCard's CodeBlock
      return <code className={className} {...props}>{children}</code>;
    },
    pre: ({ children }: any) => <>{children}</>,
  };

  return (
    <div className="relative flex flex-col flex-1 min-h-0 bg-surface"
      onClick={closeMenus}
      onDragEnter={handleDragEnter} onDragOver={handleDragOver} onDragLeave={handleDragLeave} onDrop={handleDrop}>

      {/* Synthwave grid + scanlines behind entire view when chat is empty */}
      {!loading && messages.length === 0 && !streaming && (
        <>
          <div className="synth-grid z-0" style={{ opacity: input.trim() ? 0 : 1 }} aria-hidden>
            <div className="synth-grid-inner" />
          </div>
          <div className="absolute inset-0 pointer-events-none z-[1]" aria-hidden
            style={{ background: "repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,0,0,0.02) 2px, rgba(0,0,0,0.02) 4px)", mixBlendMode: "multiply", opacity: input.trim() ? 0 : 1, transition: "opacity 0.5s" }} />
        </>
      )}

      {/* Drag overlay */}
      {dragOver && (
        <div className="absolute inset-0 bg-accent/[.08] border-2 border-dashed border-accent/40 rounded-2xl z-50 flex items-center justify-center backdrop-blur-sm">
          <div className="text-accent text-15 font-semibold bg-surface-raised/95 px-8 py-4 rounded-mac shadow-float flex items-center gap-3 animate-scale-in">
            <IconAttach size={18} />
            Drop files here
          </div>
        </div>
      )}

      {/* Toolbar */}
      <div className="flex items-center justify-end gap-1.5 px-4 border-b border-separator shrink-0 titlebar-drag" style={{ height: 46 }}>
        {/* Thinking + Mood chip */}
        <div className="relative">
          <button
            onClick={e => { e.stopPropagation(); setShowThinkingMenu(!showThinkingMenu); setShowProviderMenu(false); }}
            className="flex items-center gap-1.5 text-11 text-label-secondary bg-white/[.05] hover:bg-white/[.08] rounded-mac px-2.5 py-1.5 transition-all duration-200 active:scale-[0.97]"
            style={{ height: 28, minWidth: 44 }}
          >
            <IconSliders size={10} />
            <IconChevronDown size={8} className="text-label-tertiary" />
          </button>
          {showThinkingMenu && (
            <div className="absolute right-0 top-full mt-1.5 bg-surface-raised border border-separator-bold rounded-mac shadow-modal py-1.5 z-50 w-52 animate-scale-in">
              <p className="px-4 py-1.5 text-10 text-label-tertiary font-bold uppercase tracking-widest">Thinking</p>
              {THINKING_LEVELS.map(l => (
                <button key={l}
                  className={`w-full text-left px-4 py-2 text-13 transition-all duration-150 capitalize ${thinkingLevel === l ? "text-accent bg-accent/[.08]" : "text-label-secondary hover:bg-white/[.04]"}`}
                  onClick={async () => { setThinkingLevel(l); localStorage.setItem("thinkingLevel", l); await setThinking(l); }}>
                  {l}
                </button>
              ))}
              <div className="border-t border-separator mx-3 my-1.5" />
              <p className="px-4 py-1.5 text-10 text-label-tertiary font-bold uppercase tracking-widest">Mood</p>
              {MOODS.map(m => (
                <button key={m}
                  className={`w-full text-left px-4 py-2 text-13 capitalize transition-all duration-150 ${mood === m ? "text-accent bg-accent/[.08]" : "text-label-secondary hover:bg-white/[.04]"}`}
                  onClick={async () => { setMood(m); await setMoodSetting(m); }}>
                  {m}
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="w-px h-4 bg-separator mx-0.5" />

        {/* Brain indicator */}
        {thinkingLevel !== "off" && (
          <span className="flex items-center gap-1 rounded-mac px-2 py-1.5 text-11 text-violet-400 bg-violet-500/[.12]">
            <IconBrain size={12} />
          </span>
        )}

        {/* Learning mode — admin only */}
        {isAdmin && (
          <button onClick={() => setLearningMode(!learningMode)}
            className={`flex items-center gap-1 rounded-mac px-2 py-1.5 text-11 transition-all duration-200 active:scale-[0.95] ${learningMode ? "text-success bg-success/[.12]" : "text-label-tertiary bg-white/[.05] hover:bg-white/[.08]"}`}>
            <IconBook size={12} />
            {learningMode && <span className="font-medium">Learn</span>}
          </button>
        )}
      </div>

      {/* Message list */}
      <div ref={scrollRef} onScroll={handleScroll} className="flex-1 overflow-y-auto px-5 py-5 space-y-5 scrollbar-thin">
        {loading && (
          <div className="flex items-center justify-center h-full">
            <div className="flex items-center gap-2.5 text-label-tertiary text-13">
              <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
              Loading...
            </div>
          </div>
        )}

        {/* Empty state */}
        {!loading && messages.length === 0 && !streaming && (
          <EmptyState
            agents={agents}
            inputHasText={!!input.trim()}
            onAgentClick={(a) => { setSelectedAgent(a); inputRef.current?.focus(); }}
            onSuggestionClick={(s) => { setInput(s); inputRef.current?.focus(); }}
          />
        )}

        {messages.map((msg) => (
          <MessageCard
            key={msg.id}
            message={msg}
            streaming={streaming}
            copiedId={copiedId}
            editingId={editingId}
            editText={editText}
            showThinking={showThinking}
            onCopy={copyToClipboard}
            onStartEdit={startEdit}
            onEditTextChange={setEditText}
            onSubmitEdit={submitEdit}
            onCancelEdit={cancelEdit}
          />
        ))}

        {/* Streaming content */}
        {streaming && (streamContent || streamThinking || activeTools.length > 0 || completedTools.length > 0 || streamStatus) && (
          <div className="flex justify-start gap-2.5 animate-fade-in">
            <img src="/appicon-512.png" alt="" className="w-7 h-7 rounded-[8px] shrink-0 mt-0.5" />
            <div className="flex-1 min-w-0">
              {/* Thinking stream */}
              {streamThinking && showThinking && (
                <div className="mb-2.5 bg-violet-500/[.06] border border-violet-500/[.1] rounded-mac p-3.5 text-12 font-mono text-violet-400/80 whitespace-pre-wrap leading-relaxed">
                  <span className="inline-block w-2 h-2 rounded-full bg-violet-400 animate-pulse mr-2 align-middle" />
                  {streamThinking}
                </div>
              )}
              {/* Active + completed tool pills */}
              <ToolIndicator activeTools={activeTools} completedTools={completedTools} />
              {/* Status line */}
              {streamStatus && !streamContent && (
                <div className="flex items-center gap-2 text-12 text-label-tertiary italic animate-fade-in">
                  <span className="w-1.5 h-1.5 rounded-full bg-accent/50 animate-pulse shrink-0" />
                  <span className="truncate">{streamStatus}</span>
                </div>
              )}
              {/* Content stream */}
              {streamContent && (
                <div className="text-label text-14 prose prose-invert prose-sm leading-relaxed">
                  <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>{streamContent}</ReactMarkdown>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Thinking words */}
        {streaming && !streamContent && !streamThinking && activeTools.length === 0 && !streamStatus && (
          <div className="flex justify-start gap-2.5 animate-fade-in">
            <img src="/appicon-512.png" alt="" className="w-7 h-7 rounded-[8px] shrink-0 mt-0.5" />
            <div className="px-2 py-3">
              <ThinkingWords />
            </div>
          </div>
        )}

        <div ref={endRef} />
      </div>

      {/* Scroll to bottom FAB */}
      {showScrollBtn && (
        <button
          onClick={scrollToBottom}
          className="absolute bottom-24 right-6 w-9 h-9 rounded-full bg-surface-raised border border-separator-bold shadow-float flex items-center justify-center text-label-secondary hover:text-label hover:bg-surface-overlay transition-all duration-200 animate-fade-in z-20"
          title="Scroll to bottom"
        >
          <IconChevronDown size={14} />
        </button>
      )}

      {/* Input area */}
      <InputBar
        input={input}
        onInputChange={setInput}
        onSend={() => send()}
        onStop={() => stopRef.current?.()}
        onKeyDown={handleKeyDown}
        streaming={streaming}
        pendingFiles={pendingFiles}
        onRemoveFile={removeFile}
        onFilesSelected={handleFiles}
        agents={agents}
        selectedAgent={selectedAgent}
        onSelectAgent={(a) => { setSelectedAgent(a); setShowAgentMenu(false); }}
        provider={provider}
        onProviderChange={(key) => { setProvider(key); setShowProviderMenu(false); }}
        showProviderMenu={showProviderMenu}
        onToggleProviderMenu={() => { setShowProviderMenu(!showProviderMenu); setShowThinkingMenu(false); }}
        showAgentMenu={showAgentMenu}
        onToggleAgentMenu={() => { setShowAgentMenu(!showAgentMenu); setShowProviderMenu(false); setShowThinkingMenu(false); }}
        inputRef={inputRef}
      />
    </div>
  );
}
