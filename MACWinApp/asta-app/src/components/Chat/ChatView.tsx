import { useState, useEffect, useRef, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  IconSliders, IconBrain, IconBook, IconAgents,
  IconAttach, IconSend, IconStop, IconCopy, IconChevronDown, IconEdit, IconCheck,
  resolveAgentIcon,
} from "../../lib/icons";
import {
  loadMessages, streamChat, setDefaultAI, setThinking, setMoodSetting,
  getDefaultAI, getThinking, getMoodSetting, truncateConversation,
} from "../../lib/api";
import type { StreamChunk } from "../../lib/api";
import { downloadPdf, downloadOfficeDoc } from "../../lib/api";
import ProviderLogo from "../ProviderLogo";

const STATUS_PREFIX = "[[ASTA_STATUS]]";
const PROVIDERS = [
  { key: "claude",      name: "Claude" },
  { key: "google",      name: "Gemini" },
  { key: "openrouter",  name: "OR" },
  { key: "ollama",      name: "Local" },
];
const THINKING_LEVELS = ["off", "minimal", "low", "medium", "high", "xhigh"];
const MOODS = ["normal", "friendly", "serious"];

const FALLBACK_SUGGESTIONS = [
  "Summarize my recent notes",
  "What's on my schedule today?",
  "Write a quick email draft",
  "Search the web for latest news",
];

const THINKING_WORDS = [
  "thinking", "pondering", "analyzing", "fabricating", "curiosating",
  "brainstorming", "computing", "imagining", "processing", "conjuring",
  "contemplating", "synthesizing", "decoding", "inventing", "wondering",
  "crunching", "assembling", "dreaming", "crafting", "brewing",
];

interface Message {
  id: string; role: "user" | "assistant"; content: string;
  thinking?: string; provider?: string;
  activeTools: string[]; completedTools: string[];
}
interface Agent { id: string; name: string; icon?: string; enabled: boolean; }
interface PendingFile { name: string; type: "image" | "text" | "pdf"; content: string; }

interface Props {
  conversationId?: string;
  onConversationCreated: (id: string) => void;
  agents: Agent[];
  isAdmin?: boolean;
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
  const [showThinking, setShowThinking] = useState(localStorage.getItem("showThinking") === "true");
  const [webEnabled] = useState(localStorage.getItem("webEnabled") === "true");
  const [learningMode, setLearningMode] = useState(false);
  const [provider, setProvider] = useState("claude");
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
  const [streamStatus, setStreamStatus] = useState<string | null>(null);

  const endRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const stopRef = useRef<(() => void) | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  // Use refs to track accumulated values during streaming (avoids stale closure)
  const providerRef = useRef("");

  // Load settings from backend on mount + when changed in Settings
  const fetchSettings = useCallback(() => {
    getDefaultAI().then(r => setProvider(r.provider ?? r.default_ai_provider ?? "claude")).catch(() => {});
    getThinking().then(r => setThinkingLevel(r.thinking_level ?? "off")).catch(() => {});
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
    const rawText = (overrideText ?? input).trim();
    const fileCtx = buildFileContext();
    const text = fileCtx ? `${rawText}\n\n${fileCtx}` : rawText;
    if (!rawText || streaming) return;
    if (!overrideText) setInput("");
    setPendingFiles([]);
    // Reset textarea height
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
    if (!editText.trim()) { cancelEdit(); return; }  // don't truncate for empty text
    if (streaming) return;                            // don't truncate during active stream
    const msgIndex = messages.findIndex(m => m.id === editingId);
    if (msgIndex < 0) return;
    const captured = editText;
    // Clear edit state before async work so UI doesn't flash between states
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

  /** Extract attached file names from message content */
  function extractFiles(c: string): { name: string; type: string }[] {
    const files: { name: string; type: string }[] = [];
    const docRe = /<document\s+name="([^"]+)"[^>]*>/g;
    let m;
    while ((m = docRe.exec(c)) !== null) {
      const name = m[1];
      const ext = name.split(".").pop()?.toLowerCase() ?? "";
      files.push({ name, type: ext === "pdf" ? "pdf" : ext.match(/^(png|jpg|jpeg|gif|webp|svg)$/) ? "image" : "file" });
    }
    const imgRe = /!\[([^\]]*)\]\(data:[^)]+\)/g;
    while ((m = imgRe.exec(c)) !== null) {
      files.push({ name: m[1] || "image", type: "image" });
    }
    return files;
  }

  /** Strip embedded file attachments from message content for display */
  function cleanContent(c: string): string {
    let s = c;
    s = s.replace(/<document\s+name="([^"]+)"[^>]*>[\s\S]*?<\/document>/g, "");
    s = s.replace(/!\[([^\]]*)\]\(data:[^)]+\)/g, "");
    s = s.replace(/\n{3,}/g, "\n\n");
    return s.trim();
  }

  /** Extract generated PDF references from assistant message content (legacy path format) */
  const PDF_PATH_RE = /PDF generated:\s*(.*?[/\\]workspace[/\\]pdfs[/\\](.+?\.pdf))/gi;
  /** Extract download links emitted by generate_pdf / generate_pptx / generate_docx */
  const DOWNLOAD_LINK_RE = /Download:\s*(\/api\/files\/download-(?:pdf|office)\/([^\s\n]+))/gi;

  interface DownloadLink { url: string; name: string; }

  function extractDownloadLinks(c: string): DownloadLink[] {
    const links: DownloadLink[] = [];
    let m;
    // New format: "Download: /api/files/download-office/foo.pptx"
    const re1 = new RegExp(DOWNLOAD_LINK_RE.source, DOWNLOAD_LINK_RE.flags);
    while ((m = re1.exec(c)) !== null) {
      links.push({ url: m[1], name: decodeURIComponent(m[2]) });
    }
    // Legacy PDF path format
    const re2 = new RegExp(PDF_PATH_RE.source, PDF_PATH_RE.flags);
    while ((m = re2.exec(c)) !== null) {
      links.push({ url: `/api/files/download-pdf/${encodeURIComponent(m[2])}`, name: m[2] });
    }
    return links;
  }

  function stripDownloadPaths(c: string): string {
    return c
      .replace(DOWNLOAD_LINK_RE, "")
      .replace(PDF_PATH_RE, "")
      .replace(/\n{3,}/g, "\n\n")
      .trim();
  }

  // Keep backward-compat aliases
  const extractPdfLinks = (c: string) => extractDownloadLinks(c);
  const stripPdfPaths = (c: string) => stripDownloadPaths(c);

  function isStatus(c: string) { return c.startsWith(STATUS_PREFIX); }
  function statusText(c: string) { return c.slice(STATUS_PREFIX.length).trim(); }

  const enabledAgents = agents.filter(a => a.enabled);

  // Custom markdown renderers
  const mdComponents = {
    img: ({ src, alt, ...props }: any) => (
      <img src={src} alt={alt ?? ""} {...props}
        className="max-w-full max-h-80 rounded-mac my-2 block"
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
          <div className="flex flex-col items-center justify-center h-full gap-4 relative overflow-hidden pt-8">
            {/* 8-bit floating pixel sprites */}
            <div className="absolute inset-0 pointer-events-none transition-opacity duration-500" style={{ opacity: input.trim() ? 0 : 1 }} aria-hidden>
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
                    <button key={a.id} onClick={() => { setSelectedAgent(a); inputRef.current?.focus(); }}
                      className="flex items-center gap-2.5 bg-white/[.04] hover:bg-white/[.08] border border-separator hover:border-separator-bold rounded-xl px-3.5 py-3 transition-all duration-200 active:scale-[0.97] text-left">
                      <span className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0" style={{ background: ai.bg, color: ai.color }}>
                        <ai.Icon size={15} />
                      </span>
                      <span className="text-13 text-label-secondary font-medium truncate">{a.name}</span>
                    </button>
                  );
                })
                : FALLBACK_SUGGESTIONS.map(s => (
                  <button key={s} onClick={() => { setInput(s); inputRef.current?.focus(); }}
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
        )}

        {messages.map((msg) => {
          if (msg.role === "user") {
            if (editingId === msg.id) {
              return (
                <div key={msg.id} className="flex justify-end animate-fade-in">
                  <div className="max-w-[75%] space-y-2">
                    <textarea value={editText} onChange={e => setEditText(e.target.value)}
                      onKeyDown={e => {
                        if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submitEdit(); }
                        if (e.key === "Escape") { e.preventDefault(); cancelEdit(); }
                      }}
                      className="w-full bg-white/[.05] border border-accent/30 rounded-bubble px-4 py-3 text-14 text-label outline-none resize-none focus:border-accent/60 transition-colors"
                      rows={3} autoFocus />
                    <div className="flex justify-end gap-2">
                      <button onClick={cancelEdit} className="text-12 text-label-tertiary hover:text-label-secondary px-3 py-1.5 rounded-mac transition-colors">Cancel</button>
                      <button onClick={submitEdit} className="text-12 accent-gradient text-white px-4 py-1.5 rounded-mac shadow-glow-sm hover:shadow-glow transition-all duration-200 active:scale-[0.97]">Save & Send</button>
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
                    {!streaming && (
                      <button onClick={() => startEdit(msg)} className="text-label-tertiary hover:text-label-secondary p-1.5 rounded-mac hover:bg-white/[.06] transition-colors" title="Edit">
                        <IconEdit size={12} />
                      </button>
                    )}
                    <button onClick={() => copyToClipboard(msg.content, msg.id)} className="text-label-tertiary hover:text-label-secondary p-1.5 rounded-mac hover:bg-white/[.06] transition-colors" title="Copy">
                      {copiedId === msg.id ? <IconCheck size={12} className="text-success" /> : <IconCopy size={12} />}
                    </button>
                  </div>
                  <div className="bubble-gradient rounded-bubble px-4 py-2.5 text-14 shadow-sm space-y-1.5" style={{ color: "var(--user-bubble-text)" }}>
                    {extractFiles(msg.content).length > 0 && (
                      <div className="flex flex-wrap gap-1.5">
                        {extractFiles(msg.content).map((f, i) => (
                          <span key={i} className="inline-flex items-center gap-1.5 bg-black/[.08] dark:bg-white/[.15] rounded-lg px-2.5 py-1 text-12">
                            <span>{f.type === "pdf" ? "\u{1F4C4}" : f.type === "image" ? "\u{1F5BC}" : "\u{1F4CE}"}</span>
                            <span className="max-w-40 truncate">{f.name}</span>
                          </span>
                        ))}
                      </div>
                    )}
                    {cleanContent(msg.content) && <div className="whitespace-pre-wrap">{cleanContent(msg.content)}</div>}
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
                {/* Generated file download links (PDF, PPTX, DOCX) */}
                {extractDownloadLinks(msg.content).length > 0 && (
                  <div className="flex flex-wrap gap-2 mb-2">
                    {extractDownloadLinks(msg.content).map((file, i) => {
                      const ext = file.name.split(".").pop()?.toLowerCase() ?? "";
                      const isPdf  = ext === "pdf";
                      const isPptx = ext === "pptx";
                      const isDocx = ext === "docx";
                      const label = isPptx ? "PowerPoint" : isDocx ? "Word Doc" : "PDF";
                      function handleDownload() {
                        if (isPdf) downloadPdf(file.name).catch(() => {});
                        else downloadOfficeDoc(file.name).catch(() => {});
                      }
                      return (
                        <button key={i} onClick={handleDownload}
                          className="inline-flex items-center gap-2 bg-accent/10 hover:bg-accent/20 border border-accent/20 rounded-xl px-3 py-2 text-13 text-accent transition-colors cursor-pointer">
                          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
                            <polyline points="7 10 12 15 17 10" />
                            <line x1="12" y1="15" x2="12" y2="3" />
                          </svg>
                          <span>{label}: {file.name}</span>
                        </button>
                      );
                    })}
                  </div>
                )}
                {/* Content */}
                <div className="text-label text-14 prose prose-invert prose-sm leading-relaxed">
                  <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>{stripPdfPaths(cleanContent(msg.content))}</ReactMarkdown>
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
      <div className="px-4 py-3">
        <div className="bg-white/[.04] border border-separator hover:border-separator-bold focus-within:border-accent/30 rounded-2xl transition-all duration-200">
          {/* Pending file chips */}
          {pendingFiles.length > 0 && (
            <div className="flex flex-wrap gap-1.5 px-4 pt-3 pb-0">
              {pendingFiles.map((f, i) => (
                <span key={i} className="inline-flex items-center gap-1.5 bg-white/[.06] border border-separator rounded-lg px-2.5 py-1 text-11 text-label-secondary animate-scale-in">
                  <span>{f.type === "image" ? "\uD83D\uDDBC" : f.type === "pdf" ? "\uD83D\uDCC4" : "\uD83D\uDCCE"}</span>
                  <span className="max-w-32 truncate">{f.name}</span>
                  <button onClick={() => removeFile(i)} className="text-label-tertiary hover:text-label ml-0.5 transition-colors">&times;</button>
                </span>
              ))}
            </div>
          )}

          {/* Textarea */}
          <textarea
            ref={inputRef} rows={1} value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
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
                onChange={e => { if (e.target.files) handleFiles(Array.from(e.target.files)); e.target.value = ""; }} />

              {enabledAgents.length > 0 && (
                <div className="relative shrink-0">
                  <button
                    onClick={e => { e.stopPropagation(); setShowAgentMenu(!showAgentMenu); setShowProviderMenu(false); setShowThinkingMenu(false); }}
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
                        onClick={() => { setSelectedAgent(null); setShowAgentMenu(false); }}>
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
                            onClick={() => { setSelectedAgent(a); setShowAgentMenu(false); }}>
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
                  onClick={e => { e.stopPropagation(); setShowProviderMenu(!showProviderMenu); setShowThinkingMenu(false); }}
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
                        onClick={async () => { setProvider(p.key); setShowProviderMenu(false); await setDefaultAI(p.key); }}>
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
                onClick={streaming ? () => stopRef.current?.() : () => send()}
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
    </div>
  );
}
