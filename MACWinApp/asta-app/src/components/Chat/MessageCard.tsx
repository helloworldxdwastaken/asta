import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { IconBrain, IconCopy, IconCheck, IconEdit } from "../../lib/icons";
import { downloadPdf, downloadOfficeDoc, downloadVideo } from "../../lib/api";
import ProviderLogo from "../ProviderLogo";
import ToolIndicator from "./ToolIndicator";

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

/* ── Helpers ────────────────────────────────────────────────────────────── */

const STATUS_PREFIX = "[[ASTA_STATUS]]";

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
  if (/\[Image:\s*image\/\w+\]/.test(c)) {
    files.push({ name: "image", type: "image" });
  }
  return files;
}

/** Strip embedded file attachments from message content for display */
function cleanContent(c: string): string {
  let s = c;
  s = s.replace(/<document\s+name="([^"]+)"[^>]*>[\s\S]*?<\/document>/g, "");
  s = s.replace(/!\[([^\]]*)\]\(data:[^)]+\)/g, "");
  s = s.replace(/\s*\[Image:\s*image\/\w+\]\s*/g, " ");
  s = s.replace(/\n{3,}/g, "\n\n");
  return s.trim();
}

/** Extract generated PDF references from assistant message content (legacy path format) */
const PDF_PATH_RE = /PDF generated:\s*(.*?[/\\]workspace[/\\]pdfs[/\\](.+?\.pdf))/gi;
/** Extract download links emitted by generate_pdf / generate_pptx / generate_docx */
const DOWNLOAD_LINK_RE = /Download:\s*(\/api\/files\/download-(?:pdf|office|video)\/([^\s\n]+))/gi;

interface DownloadLink { url: string; name: string; }

function extractDownloadLinks(c: string): DownloadLink[] {
  const links: DownloadLink[] = [];
  let m;
  const re1 = new RegExp(DOWNLOAD_LINK_RE.source, DOWNLOAD_LINK_RE.flags);
  while ((m = re1.exec(c)) !== null) {
    links.push({ url: m[1], name: decodeURIComponent(m[2]) });
  }
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

function isStatus(c: string) { return c.startsWith(STATUS_PREFIX); }
function statusText(c: string) { return c.slice(STATUS_PREFIX.length).trim(); }

/* ── Types ──────────────────────────────────────────────────────────────── */

export interface Message {
  id: string; role: "user" | "assistant"; content: string;
  thinking?: string; provider?: string;
  activeTools: string[]; completedTools: string[];
}

interface MessageCardProps {
  message: Message;
  streaming: boolean;
  copiedId: string | null;
  editingId: string | null;
  editText: string;
  showThinking: boolean;
  onCopy: (text: string, msgId: string) => void;
  onStartEdit: (msg: Message) => void;
  onEditTextChange: (text: string) => void;
  onSubmitEdit: () => void;
  onCancelEdit: () => void;
}

/* ── Markdown renderers ─────────────────────────────────────────────────── */

const mdComponents = {
  a: ({ href, children, ...props }: any) => {
    function handleLinkClick(e: React.MouseEvent) {
      e.preventDefault();
      e.stopPropagation();
      if (!href) return;
      if (href.includes("/api/files/download-pdf/") || href.includes("/api/files/download-office/") || href.includes("/api/files/download-video/")) {
        if (href.includes("/download-video/")) {
          const videoPath = decodeURIComponent(href.replace(/.*\/api\/files\/download-video\//, ""));
          downloadVideo(videoPath).catch(err => alert(`Download failed: ${err?.message ?? err}`));
        } else {
          const filename = decodeURIComponent(href.split("/").pop() ?? "download");
          const fn = href.includes("/download-pdf/") ? downloadPdf : downloadOfficeDoc;
          fn(filename).catch(err => alert(`Download failed: ${err?.message ?? err}`));
        }
      } else {
        import("@tauri-apps/plugin-opener").then(({ openUrl }) => openUrl(href)).catch(() => {
          window.open(href, "_blank");
        });
      }
    }
    return <a href={href} onClick={handleLinkClick} className="text-accent underline cursor-pointer" {...props}>{children}</a>;
  },
  img: ({ src, alt, ...props }: any) => (
    <img src={src} alt={alt ?? ""} {...props}
      className="max-w-full max-h-80 rounded-mac my-2 block"
      loading="lazy" />
  ),
  code: ({ className, children, ...props }: any) => {
    const isBlock = className?.startsWith("language-");
    if (!isBlock) {
      return <code className={className} {...props}>{children}</code>;
    }
    return <CodeBlock className={className}>{children}</CodeBlock>;
  },
  pre: ({ children }: any) => {
    return <>{children}</>;
  },
};

/* ── Component ──────────────────────────────────────────────────────────── */

export default function MessageCard({
  message: msg, streaming, copiedId, editingId, editText, showThinking,
  onCopy, onStartEdit, onEditTextChange, onSubmitEdit, onCancelEdit,
}: MessageCardProps) {

  /* ---- User message (editing) ---- */
  if (msg.role === "user" && editingId === msg.id) {
    return (
      <div className="flex justify-end animate-fade-in">
        <div className="max-w-[75%] space-y-2">
          <textarea value={editText} onChange={e => onEditTextChange(e.target.value)}
            onKeyDown={e => {
              if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); onSubmitEdit(); }
              if (e.key === "Escape") { e.preventDefault(); onCancelEdit(); }
            }}
            className="w-full bg-white/[.05] border border-accent/30 rounded-bubble px-4 py-3 text-14 text-label outline-none resize-none focus:border-accent/60 transition-colors"
            rows={3} autoFocus />
          <div className="flex justify-end gap-2">
            <button onClick={onCancelEdit} className="text-12 text-label-tertiary hover:text-label-secondary px-3 py-1.5 rounded-mac transition-colors">Cancel</button>
            <button onClick={onSubmitEdit} className="text-12 accent-gradient text-white px-4 py-1.5 rounded-mac shadow-glow-sm hover:shadow-glow transition-all duration-200 active:scale-[0.97]">Save & Send</button>
          </div>
        </div>
      </div>
    );
  }

  /* ---- User message (display) ---- */
  if (msg.role === "user") {
    return (
      <div className="flex justify-end group">
        <div className="relative max-w-[75%] flex items-start gap-2">
          <div className="flex gap-0.5 pt-2 shrink-0 opacity-0 group-hover:opacity-100 transition-all duration-200">
            {!streaming && (
              <button onClick={() => onStartEdit(msg)} className="text-label-tertiary hover:text-label-secondary p-1.5 rounded-mac hover:bg-white/[.06] transition-colors" title="Edit">
                <IconEdit size={12} />
              </button>
            )}
            <button onClick={() => onCopy(msg.content, msg.id)} className="text-label-tertiary hover:text-label-secondary p-1.5 rounded-mac hover:bg-white/[.06] transition-colors" title="Copy">
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

  /* ---- Status message ---- */
  if (isStatus(msg.content)) {
    return (
      <div className="text-11 text-label-tertiary italic pl-10 py-0.5">{statusText(msg.content)}</div>
    );
  }

  /* ---- Assistant message ---- */
  return (
    <div className="flex justify-start gap-2.5 group">
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
        <ToolIndicator activeTools={[]} completedTools={msg.completedTools} />
        {/* Generated file download links */}
        {extractDownloadLinks(msg.content).length > 0 && (
          <div className="flex flex-wrap gap-2 mb-2">
            {extractDownloadLinks(msg.content).map((file, i) => {
              const ext = file.name.split(".").pop()?.toLowerCase() ?? "";
              const isPdf  = ext === "pdf";
              const isPptx = ext === "pptx";
              const isDocx = ext === "docx";
              const isXlsx = ext === "xlsx";
              const isCsv  = ext === "csv";
              const label = isPptx ? "PowerPoint" : isDocx ? "Word Doc" : isXlsx ? "Excel" : isCsv ? "CSV" : "PDF";
              void isCsv; void isXlsx; void isDocx; void isPptx; // suppress unused warnings handled by label
              function handleDownload(e: React.MouseEvent) {
                e.stopPropagation();
                const fn = isPdf ? downloadPdf : downloadOfficeDoc;
                fn(file.name).catch((err) => {
                  alert(`Download failed: ${err?.message ?? err ?? "unknown error"}`);
                });
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
          <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>{stripDownloadPaths(cleanContent(msg.content))}</ReactMarkdown>
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
            <button onClick={() => onCopy(msg.content, msg.id)}
              className="text-label-tertiary hover:text-label-secondary p-1.5 rounded-mac hover:bg-white/[.06] flex items-center gap-1 text-11 transition-colors" title="Copy">
              {copiedId === msg.id ? <><IconCheck size={12} className="text-success" /> Copied</> : <><IconCopy size={12} /> Copy</>}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
