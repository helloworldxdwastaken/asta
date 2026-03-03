import { useState, useEffect, useRef, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  IconSliders, IconBrain, IconBook, IconGlobe,
  IconAttach, IconSend, IconStop, IconCopy, IconChevronDown, IconEdit, IconCheck,
} from "../../lib/icons";
import {
  loadMessages, streamChat, setDefaultAI, setThinking, setMoodSetting,
  getDefaultAI, getThinking, getMoodSetting, truncateConversation,
} from "../../lib/api";
import type { StreamChunk } from "../../lib/api";
import ProviderLogo from "../ProviderLogo";

const STATUS_PREFIX = "[[ASTA_STATUS]]";
const PROVIDERS = [
  { key: "anthropic", name: "Claude" },
  { key: "openai",    name: "GPT" },
  { key: "google",    name: "Gemini" },
  { key: "groq",      name: "Groq" },
  { key: "openrouter", name: "OR" },
  { key: "ollama",    name: "Local" },
];
const THINKING_LEVELS = ["off", "minimal", "low", "medium", "high", "xhigh"];
const MOODS = ["normal", "friendly", "serious"];

const SUGGESTIONS = [
  "Summarize my recent notes",
  "What's on my schedule today?",
  "Write a quick email draft",
  "Search the web for latest news",
];

interface Message {
  id: string; role: "user" | "assistant"; content: string;
  thinking?: string; provider?: string;
  activeTools: string[]; completedTools: string[];
}
interface Agent { id: string; name: string; icon?: string; enabled: boolean; }

interface Props {
  conversationId?: string;
  onConversationCreated: (id: string) => void;
  agents: Agent[];
}

/* ── Code block with copy button ─────────────────────────────────────────── */
function CodeBlock({ className, children }: { className?: string; children?: React.ReactNode }) {
  const [copied, setCopied] = useState(false);
  const lang = className?.replace("language-", "") ?? "";
  const code = String(children ?? "").replace(/\n$/, "");

  function copy() {
    navigator.clipboard.writeText(code).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className="relative group/code my-3">
      {lang && (
        <div className="flex items-center justify-between px-4 py-1.5 border-b border-[var(--code-border)] text-11 text-label-tertiary font-mono">
          <span>{lang}</span>
        </div>
      )}
      <button
        onClick={copy}
        className="absolute top-2 right-2 opacity-0 group-hover/code:opacity-100 transition-opacity text-label-tertiary hover:text-label-secondary bg-surface-raised/80 backdrop-blur-sm rounded-md px-2 py-1 text-11 flex items-center gap-1.5 border border-separator z-10"
      >
        {copied ? <><IconCheck size={10} className="text-success" /> Copied</> : <><IconCopy size={10} /> Copy</>}
      </button>
      <pre className="!my-0 !rounded-none last:!rounded-b-mac first:!rounded-mac" style={lang ? { borderTopLeftRadius: 0, borderTopRightRadius: 0 } : undefined}>
        <code className={className}>{code}</code>
      </pre>
    </div>
  );
}

export default function ChatView({ conversationId, onConversationCreated, agents }: Props) {
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
  const [showThinking, setShowThinking] = useState(localStorage.getItem("showThinking") === "true");
  const [webEnabled, setWebEnabled] = useState(localStorage.getItem("webEnabled") === "true");
  const [learningMode, setLearningMode] = useState(false);
  const [provider, setProvider] = useState("anthropic");
  const [thinkingLevel, setThinkingLevel] = useState("off");
  const [mood, setMood] = useState("normal");
  const [showProviderMenu, setShowProviderMenu] = useState(false);
  const [showThinkingMenu, setShowThinkingMenu] = useState(false);
  const [showAgentMenu, setShowAgentMenu] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editText, setEditText] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const [showScrollBtn, setShowScrollBtn] = useState(false);

  const endRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const stopRef = useRef<(() => void) | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  // Use refs to track accumulated values during streaming (avoids stale closure)
  const providerRef = useRef("");

  // Load settings from backend on mount
  useEffect(() => {
    getDefaultAI().then(r => setProvider(r.provider ?? r.default_ai_provider ?? "anthropic")).catch(() => {});
    getThinking().then(r => setThinkingLevel(r.thinking_level ?? "off")).catch(() => {});
    getMoodSetting().then(r => setMood(r.mood ?? "normal")).catch(() => {});
  }, []);

  useEffect(() => {
    if (!conversationId) { setMessages([]); return; }
    setLoading(true);
    loadMessages(conversationId)
      .then(r => setMessages((r.messages ?? []).map(normalizeMsg)))
      .catch(() => setMessages([]))
      .finally(() => setLoading(false));
  }, [conversationId]);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, streamContent]);

  // Scroll-to-bottom detection
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

  const providerName = PROVIDERS.find(p => p.key === provider)?.name ?? provider;

  async function send(overrideText?: string) {
    const text = (overrideText ?? input).trim();
    if (!text || streaming) return;
    if (!overrideText) setInput("");
    // Reset textarea height
    if (inputRef.current) inputRef.current.style.height = "auto";

    const userMsg: Message = { id: Date.now().toString(), role: "user", content: text, activeTools: [], completedTools: [] };
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
          case "tool_start": {
            const label = chunk.label ?? chunk.name ?? "tool";
            setActiveTools(prev => prev.includes(label) ? prev : [...prev, label]);
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
        setStreamContent(""); setStreamThinking(""); setActiveTools([]); setCompletedTools([]); setStreaming(false);
        stopRef.current = null;
      },
      (err) => {
        setMessages(prev => [...prev, {
          id: (Date.now()+1).toString(), role: "assistant", content: `Error: ${err.message}`,
          activeTools: [], completedTools: [],
        }]);
        setStreamContent(""); setStreaming(false); stopRef.current = null;
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
    const msgIndex = messages.findIndex(m => m.id === editingId);
    if (msgIndex < 0) return;
    await truncateConversation(conversationId, msgIndex).catch(() => {});
    setMessages(prev => prev.slice(0, msgIndex));
    setEditingId(null);
    send(editText);
  }

  function cancelEdit() {
    setEditingId(null);
    setEditText("");
  }

  // Drag & drop files
  const dragCounterRef = useRef(0);
  const [attachedFiles, setAttachedFiles] = useState<string[]>([]);

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
    const names: string[] = [];
    const imageFiles = files.filter(f => f.type.startsWith("image/"));
    if (imageFiles.length > 0) {
      imageFiles.forEach(file => {
        names.push(file.name);
        const reader = new FileReader();
        reader.onload = () => {
          const base64 = reader.result as string;
          setInput(prev => prev + (prev ? "\n" : "") + `![${file.name}](${base64})`);
        };
        reader.readAsDataURL(file);
      });
    }
    const textExts = [".md", ".txt", ".csv", ".json", ".ts", ".tsx", ".js", ".jsx", ".py", ".sh", ".yaml", ".yml", ".toml", ".xml", ".html", ".css"];
    const textFiles = files.filter(f => f.type.startsWith("text/") || textExts.some(ext => f.name.endsWith(ext)));
    textFiles.forEach(file => {
      names.push(file.name);
      file.text().then(text => {
        setInput(prev => prev + (prev ? "\n" : "") + "```" + file.name + "\n" + text + "\n```");
      });
    });
    if (names.length > 0) {
      setAttachedFiles(names);
      setTimeout(() => setAttachedFiles([]), 3000);
    }
  }

  function isStatus(c: string) { return c.startsWith(STATUS_PREFIX); }
  function statusText(c: string) { return c.slice(STATUS_PREFIX.length).trim(); }

  const enabledAgents = agents.filter(a => a.enabled);

  // Custom markdown renderers
  const mdComponents = {
    img: ({ src, alt, ...props }: any) => (
      <img src={src} alt={alt ?? ""} {...props}
        className="max-w-full max-h-80 rounded-mac my-1"
        style={{ display: "inline-block" }}
        loading="lazy" />
    ),
    code: ({ className, children, ...props }: any) => {
      // Inline code (no language class, short content)
      const isBlock = className?.startsWith("language-");
      if (!isBlock) {
        return <code className={className} {...props}>{children}</code>;
      }
      return <CodeBlock className={className}>{children}</CodeBlock>;
    },
    pre: ({ children }: any) => {
      // If the child is already our CodeBlock, just pass through
      return <>{children}</>;
    },
  };

  const closeMenus = () => { setShowProviderMenu(false); setShowThinkingMenu(false); setShowAgentMenu(false); };

  return (
    <div className="relative flex flex-col h-full bg-surface"
      onClick={closeMenus}
      onDragEnter={handleDragEnter} onDragOver={handleDragOver} onDragLeave={handleDragLeave} onDrop={handleDrop}>

      {/* Drag overlay */}
      {dragOver && (
        <div className="absolute inset-0 bg-accent/[.08] border-2 border-dashed border-accent/40 rounded-2xl z-50 flex items-center justify-center backdrop-blur-sm">
          <div className="text-accent text-15 font-semibold bg-surface-raised/95 px-8 py-4 rounded-mac shadow-float flex items-center gap-3 animate-scale-in">
            <IconAttach size={18} />
            Drop files here
          </div>
        </div>
      )}

      {/* Attached file toast */}
      {attachedFiles.length > 0 && (
        <div className="absolute top-14 left-1/2 -translate-x-1/2 z-50 bg-success text-white text-12 font-medium px-5 py-2.5 rounded-mac shadow-float animate-slide-up">
          Attached: {attachedFiles.join(", ")}
        </div>
      )}

      {/* Toolbar */}
      <div className="flex items-center justify-end gap-1.5 px-4 border-b border-separator shrink-0 titlebar-drag" style={{ height: 46 }}>
        {/* Provider chip */}
        <div className="relative">
          <button
            onClick={e => { e.stopPropagation(); setShowProviderMenu(!showProviderMenu); setShowThinkingMenu(false); setShowAgentMenu(false); }}
            className="flex items-center gap-1.5 text-11 font-semibold text-label-secondary bg-white/[.05] hover:bg-white/[.08] rounded-mac px-2.5 py-1.5 transition-all duration-200 active:scale-[0.97]"
          >
            <ProviderLogo provider={provider} size={14} />
            <span>{providerName}</span>
            <IconChevronDown size={8} className="text-label-tertiary" />
          </button>
          {showProviderMenu && (
            <div className="absolute right-0 top-full mt-1.5 bg-surface-raised border border-separator-bold rounded-mac shadow-modal py-1.5 z-50 w-52 animate-scale-in">
              {PROVIDERS.map(p => (
                <button key={p.key}
                  className={`w-full text-left px-4 py-2.5 text-13 transition-all duration-150 flex items-center gap-3 ${provider === p.key ? "text-accent bg-accent/[.08]" : "text-label-secondary hover:bg-white/[.04]"}`}
                  onClick={async () => { setProvider(p.key); setShowProviderMenu(false); await setDefaultAI(p.key); }}>
                  <ProviderLogo provider={p.key} size={18} />
                  {p.name}
                  {provider === p.key && <IconCheck size={12} className="ml-auto text-accent" />}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Thinking + Mood chip */}
        <div className="relative">
          <button
            onClick={e => { e.stopPropagation(); setShowThinkingMenu(!showThinkingMenu); setShowProviderMenu(false); setShowAgentMenu(false); }}
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
                  onClick={async () => { setThinkingLevel(l); await setThinking(l); }}>
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

        {/* Brain toggle */}
        {thinkingLevel !== "off" && (
          <button onClick={() => { const v = !showThinking; setShowThinking(v); localStorage.setItem("showThinking", String(v)); }}
            className={`flex items-center gap-1 rounded-mac px-2 py-1.5 text-11 transition-all duration-200 active:scale-[0.95] ${showThinking ? "text-violet-400 bg-violet-500/[.12]" : "text-label-tertiary bg-white/[.05] hover:bg-white/[.08]"}`}>
            <IconBrain size={12} />
          </button>
        )}

        {/* Learning mode */}
        <button onClick={() => setLearningMode(!learningMode)}
          className={`flex items-center gap-1 rounded-mac px-2 py-1.5 text-11 transition-all duration-200 active:scale-[0.95] ${learningMode ? "text-success bg-success/[.12]" : "text-label-tertiary bg-white/[.05] hover:bg-white/[.08]"}`}>
          <IconBook size={12} />
          {learningMode && <span className="font-medium">Learn</span>}
        </button>

        {/* Web toggle */}
        <button onClick={() => { const v = !webEnabled; setWebEnabled(v); localStorage.setItem("webEnabled", String(v)); }}
          className={`flex items-center gap-1 rounded-mac px-2 py-1.5 text-11 transition-all duration-200 active:scale-[0.95] ${webEnabled ? "text-accent bg-accent/[.12]" : "text-label-tertiary bg-white/[.05] hover:bg-white/[.08]"}`}>
          <IconGlobe size={12} />
        </button>
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
          <div className="flex flex-col items-center justify-center h-full gap-4">
            <div className="relative w-20 h-20">
              <div className="absolute inset-0 rounded-full bg-gradient-to-br from-[var(--user-bubble)] to-[var(--user-bubble-end)] opacity-20 blur-xl animate-[orb-float_8s_ease-in-out_infinite]" />
              <img src="/appicon-512.png" alt="Asta" className="relative w-20 h-20 rounded-2xl" />
            </div>
            <div className="text-center">
              <p className="text-label text-16 font-semibold">What can I help with?</p>
              <p className="text-label-tertiary text-12 mt-1">Ask anything, or try a suggestion below</p>
            </div>
            <div className="flex flex-wrap justify-center gap-2 max-w-md mt-2">
              {SUGGESTIONS.map(s => (
                <button key={s} onClick={() => { setInput(s); inputRef.current?.focus(); }}
                  className="text-13 text-label-secondary bg-white/[.04] hover:bg-white/[.08] border border-separator hover:border-separator-bold rounded-full px-4 py-2 transition-all duration-200 active:scale-[0.97]">
                  {s}
                </button>
              ))}
            </div>
            <p className="text-label-tertiary text-11 font-mono tracking-wide mt-3 opacity-50">Cmd+Alt+Space to toggle</p>
          </div>
        )}

        {messages.map((msg) => {
          if (msg.role === "user") {
            if (editingId === msg.id) {
              return (
                <div key={msg.id} className="flex justify-end animate-fade-in">
                  <div className="max-w-[75%] space-y-2">
                    <textarea value={editText} onChange={e => setEditText(e.target.value)}
                      className="w-full bg-white/[.05] border border-accent/30 rounded-bubble px-4 py-3 text-14 text-label outline-none resize-none focus:border-accent/60 transition-colors"
                      rows={3} autoFocus />
                    <div className="flex justify-end gap-2">
                      <button onClick={cancelEdit} className="text-12 text-label-tertiary hover:text-label-secondary px-3 py-1.5 rounded-mac transition-colors">Cancel</button>
                      <button onClick={submitEdit} className="text-12 bubble-gradient text-white px-4 py-1.5 rounded-mac shadow-glow-sm hover:shadow-glow transition-all duration-200 active:scale-[0.97]">Save & Send</button>
                    </div>
                  </div>
                </div>
              );
            }

            return (
              <div key={msg.id} className="flex justify-end group">
                <div className="relative max-w-[75%] flex items-start gap-2">
                  {/* Actions — left of bubble */}
                  <div className="flex gap-0.5 pt-2 shrink-0 opacity-0 group-hover:opacity-100 transition-all duration-200">
                    <button onClick={() => startEdit(msg)} className="text-label-tertiary hover:text-label-secondary p-1.5 rounded-mac hover:bg-white/[.06] transition-colors" title="Edit">
                      <IconEdit size={12} />
                    </button>
                    <button onClick={() => copyToClipboard(msg.content, msg.id)} className="text-label-tertiary hover:text-label-secondary p-1.5 rounded-mac hover:bg-white/[.06] transition-colors" title="Copy">
                      {copiedId === msg.id ? <IconCheck size={12} className="text-success" /> : <IconCopy size={12} />}
                    </button>
                  </div>
                  <div className="bubble-gradient text-white rounded-bubble px-4 py-2.5 text-14 whitespace-pre-wrap shadow-sm">
                    {msg.content}
                  </div>
                </div>
              </div>
            );
          }

          if (isStatus(msg.content)) return (
            <div key={msg.id} className="text-11 text-label-tertiary italic pl-10 py-0.5">{statusText(msg.content)}</div>
          );

          return (
            <div key={msg.id} className="flex justify-start gap-2.5 group">
              <img src="/appicon-512.png" alt="" className="w-7 h-7 rounded-[8px] shrink-0 mt-0.5" />
              <div className="flex-1 min-w-0">
                {/* Thinking block */}
                {msg.thinking && showThinking && (
                  <details className="mb-2.5">
                    <summary className="text-11 text-violet-400 cursor-pointer hover:text-violet-300 flex items-center gap-1.5 transition-colors">
                      <IconBrain size={11} /> Thought
                    </summary>
                    <div className="mt-1.5 bg-violet-500/[.06] border border-violet-500/[.1] rounded-mac p-3.5 text-12 font-mono text-violet-400/80 whitespace-pre-wrap leading-relaxed">
                      {msg.thinking}
                    </div>
                  </details>
                )}
                {/* Completed tool pills */}
                {msg.completedTools.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 mb-2.5">
                    {msg.completedTools.map(tool => (
                      <span key={tool} className="inline-flex items-center gap-1.5 rounded-full bg-white/[.04] border border-separator px-2.5 py-1 text-11 text-label-secondary">
                        <IconCheck size={10} className="text-success" />
                        {tool}
                      </span>
                    ))}
                  </div>
                )}
                {/* Content */}
                <div className="text-label text-14 prose prose-invert prose-sm leading-relaxed">
                  <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>{msg.content}</ReactMarkdown>
                </div>
                {/* Provider badge + actions */}
                <div className="flex items-center gap-3 mt-1.5">
                  {msg.provider && (
                    <div className="flex items-center gap-1.5">
                      <ProviderLogo provider={msg.provider} size={10} />
                      <span className="text-10 text-label-tertiary font-mono">{msg.provider}</span>
                    </div>
                  )}
                  <div className="flex gap-0.5 opacity-0 group-hover:opacity-100 transition-all duration-200">
                    <button onClick={() => copyToClipboard(msg.content, msg.id)}
                      className="text-label-tertiary hover:text-label-secondary p-1.5 rounded-mac hover:bg-white/[.06] flex items-center gap-1 text-11 transition-colors" title="Copy">
                      {copiedId === msg.id ? <><IconCheck size={12} className="text-success" /> Copied</> : <><IconCopy size={12} /> Copy</>}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          );
        })}

        {/* Streaming content */}
        {streaming && (streamContent || streamThinking || activeTools.length > 0 || completedTools.length > 0) && (
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
              {/* Active tool pills (animated) */}
              {activeTools.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mb-2.5">
                  {activeTools.map(tool => (
                    <span key={tool} className="inline-flex items-center gap-1.5 rounded-full bg-accent/[.1] border border-accent/[.15] px-3 py-1 text-11 font-medium text-accent animate-fade-in">
                      <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
                      {tool}
                    </span>
                  ))}
                </div>
              )}
              {/* Completed tool pills */}
              {completedTools.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mb-2.5">
                  {completedTools.map(tool => (
                    <span key={tool} className="inline-flex items-center gap-1.5 rounded-full bg-white/[.04] border border-separator px-2.5 py-1 text-11 text-label-secondary">
                      <IconCheck size={10} className="text-success" />
                      {tool}
                    </span>
                  ))}
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

        {/* Bounce dots */}
        {streaming && !streamContent && !streamThinking && activeTools.length === 0 && (
          <div className="flex justify-start gap-2.5 animate-fade-in">
            <img src="/appicon-512.png" alt="" className="w-7 h-7 rounded-[8px] shrink-0" />
            <div className="flex items-center gap-1.5 px-2 py-3">
              {[0, 1, 2].map(i => (
                <span key={i} className="w-1.5 h-1.5 bg-accent/50 rounded-full animate-bounce-dot"
                  style={{ animationDelay: `${i * 150}ms` }} />
              ))}
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
      <div className="border-t border-separator px-4 py-3">
        <div className="flex items-end gap-2">
          {/* Attach button */}
          <button onClick={() => fileInputRef.current?.click()}
            className="w-9 h-9 flex items-center justify-center rounded-mac hover:bg-white/[.06] text-label-tertiary hover:text-label-secondary shrink-0 transition-colors" title="Attach file">
            <IconAttach size={18} />
          </button>
          <input ref={fileInputRef} type="file" multiple accept="image/*,.txt,.md,.csv,.json" className="hidden"
            onChange={e => { if (e.target.files) handleFiles(Array.from(e.target.files)); e.target.value = ""; }} />

          {/* Agent picker */}
          {enabledAgents.length > 0 && (
            <div className="relative shrink-0">
              <button
                onClick={e => { e.stopPropagation(); setShowAgentMenu(!showAgentMenu); setShowProviderMenu(false); setShowThinkingMenu(false); }}
                className={`flex items-center gap-1.5 text-11 rounded-mac px-2.5 py-2 transition-all duration-200 active:scale-[0.97] ${
                  selectedAgent ? "bg-accent/[.12] text-accent font-semibold border border-accent/20" : "bg-white/[.05] text-label-secondary hover:bg-white/[.08] border border-transparent"
                }`}>
                {selectedAgent ? (
                  <>
                    {selectedAgent.icon ? (
                      <img src={selectedAgent.icon} alt="" className="w-4 h-4 rounded-full" />
                    ) : (
                      <span className="w-4 h-4 rounded-full bg-accent/30 text-[8px] font-bold flex items-center justify-center text-white">{selectedAgent.name[0]}</span>
                    )}
                    <span className="max-w-20 truncate">{selectedAgent.name}</span>
                  </>
                ) : (
                  <span>Agent</span>
                )}
                <IconChevronDown size={8} className="text-label-tertiary" />
              </button>
              {showAgentMenu && (
                <div className="absolute left-0 bottom-full mb-1.5 bg-surface-raised border border-separator-bold rounded-mac shadow-modal py-1.5 z-50 w-56 max-h-64 overflow-y-auto scrollbar-thin animate-scale-in">
                  <button
                    className={`w-full text-left px-4 py-2.5 text-13 transition-all duration-150 ${!selectedAgent ? "text-accent bg-accent/[.08]" : "text-label-secondary hover:bg-white/[.04]"}`}
                    onClick={() => { setSelectedAgent(null); setShowAgentMenu(false); }}>
                    No agent
                  </button>
                  <div className="border-t border-separator mx-3 my-1" />
                  {enabledAgents.map(a => (
                    <button key={a.id}
                      className={`w-full text-left px-4 py-2.5 text-13 transition-all duration-150 flex items-center gap-2.5 ${
                        selectedAgent?.id === a.id ? "text-accent bg-accent/[.08]" : "text-label-secondary hover:bg-white/[.04]"
                      }`}
                      onClick={() => { setSelectedAgent(a); setShowAgentMenu(false); }}>
                      {a.icon ? (
                        <img src={a.icon} alt="" className="w-5 h-5 rounded-full shrink-0" />
                      ) : (
                        <span className="w-5 h-5 rounded-full bg-accent/20 text-accent text-[10px] font-bold flex items-center justify-center shrink-0">{a.name[0]}</span>
                      )}
                      <span className="truncate">{a.name}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          <textarea
            ref={inputRef} rows={1} value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={selectedAgent ? `Message @${selectedAgent.name}...` : "Type a message..."}
            className="flex-1 bg-white/[.04] border border-separator hover:border-separator-bold rounded-[14px] px-4 py-2.5 text-14 text-label placeholder-label-tertiary outline-none focus:border-accent/40 focus:bg-white/[.06] resize-none transition-all duration-200"
            style={{ minHeight: 42, maxHeight: 200, lineHeight: "20px" }}
            onInput={e => { const el = e.currentTarget; el.style.height = "auto"; el.style.height = Math.min(el.scrollHeight, 200) + "px"; }}
          />

          <button
            onClick={streaming ? () => stopRef.current?.() : () => send()}
            disabled={!streaming && !input.trim()}
            className={`w-9 h-9 flex items-center justify-center rounded-mac shrink-0 transition-all duration-200 active:scale-[0.93] ${
              streaming
                ? "bg-danger/20 text-danger hover:bg-danger/30"
                : input.trim()
                  ? "bubble-gradient text-white shadow-glow-sm hover:shadow-glow"
                  : "bg-white/[.05] text-label-tertiary"
            }`}
          >
            {streaming ? <IconStop size={14} /> : <IconSend size={14} />}
          </button>
        </div>
        {/* Keyboard hint */}
        <div className="flex justify-end mt-1 pr-11">
          <span className="text-10 text-label-tertiary/40 font-mono">
            {streaming ? "Click stop to cancel" : "Enter to send · Shift+Enter for newline"}
          </span>
        </div>
      </div>
    </div>
  );
}
