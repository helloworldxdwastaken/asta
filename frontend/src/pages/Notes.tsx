import { useEffect, useState, useCallback, type ReactNode } from "react";
import { Link } from "react-router-dom";
import type { WorkspaceNote } from "../api/client";
import { api } from "../api/client";

type NoteSaveState = "idle" | "saving" | "saved" | "error";

const MARKDOWN_BLOCK_START = /^(#{1,3}\s+|>\s+|[-*]\s+|\d+\.\s+|```)/;

function renderInlineMarkdown(text: string): ReactNode[] {
  if (!text) return [];
  const out: ReactNode[] = [];
  const tokenPattern = /(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*)/g;
  let cursor = 0;
  let tokenIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = tokenPattern.exec(text)) !== null) {
    if (match.index > cursor) out.push(text.slice(cursor, match.index));
    const token = match[0];
    if (token.startsWith("`")) {
      out.push(<code key={`code-${tokenIndex}`} className="note-inline-code">{token.slice(1, -1)}</code>);
    } else if (token.startsWith("**")) {
      out.push(<strong key={`strong-${tokenIndex}`}>{token.slice(2, -2)}</strong>);
    } else if (token.startsWith("*")) {
      out.push(<em key={`em-${tokenIndex}`}>{token.slice(1, -1)}</em>);
    } else {
      out.push(token);
    }
    cursor = match.index + token.length;
    tokenIndex += 1;
  }
  if (cursor < text.length) out.push(text.slice(cursor));
  return out;
}

function renderMarkdownPreview(content: string): ReactNode[] {
  const normalized = content.replace(/\r\n/g, "\n");
  const lines = normalized.split("\n");
  const blocks: ReactNode[] = [];
  let i = 0;

  while (i < lines.length) {
    const trimmed = lines[i].trim();
    if (!trimmed) {
      i += 1;
      continue;
    }

    if (trimmed.startsWith("```")) {
      i += 1;
      const codeLines: string[] = [];
      while (i < lines.length && !lines[i].trim().startsWith("```")) {
        codeLines.push(lines[i]);
        i += 1;
      }
      if (i < lines.length && lines[i].trim().startsWith("```")) i += 1;
      blocks.push(
        <pre key={`code-block-${i}`} className="note-code-block">
          <code>{codeLines.join("\n")}</code>
        </pre>
      );
      continue;
    }

    const headingMatch = trimmed.match(/^(#{1,3})\s+(.+)$/);
    if (headingMatch) {
      const level = headingMatch[1].length;
      blocks.push(
        <div key={`heading-${i}`} className={`note-heading note-heading-${level}`}>
          {renderInlineMarkdown(headingMatch[2])}
        </div>
      );
      i += 1;
      continue;
    }

    if (trimmed.startsWith("> ")) {
      const quoteLines: string[] = [];
      while (i < lines.length && lines[i].trim().startsWith("> ")) {
        quoteLines.push(lines[i].trim().slice(2));
        i += 1;
      }
      blocks.push(
        <blockquote key={`quote-${i}`} className="note-blockquote">
          {quoteLines.map((line, idx) => (
            <span key={`quote-line-${idx}`}>
              {renderInlineMarkdown(line)}
              {idx < quoteLines.length - 1 ? <br /> : null}
            </span>
          ))}
        </blockquote>
      );
      continue;
    }

    if (/^[-*]\s+/.test(trimmed)) {
      const items: string[] = [];
      while (i < lines.length) {
        const itemMatch = lines[i].trim().match(/^[-*]\s+(.+)$/);
        if (!itemMatch) break;
        items.push(itemMatch[1]);
        i += 1;
      }
      blocks.push(
        <ul key={`ul-${i}`} className="note-preview-list">
          {items.map((item, idx) => <li key={`ul-item-${idx}`}>{renderInlineMarkdown(item)}</li>)}
        </ul>
      );
      continue;
    }

    if (/^\d+\.\s+/.test(trimmed)) {
      const items: string[] = [];
      while (i < lines.length) {
        const itemMatch = lines[i].trim().match(/^\d+\.\s+(.+)$/);
        if (!itemMatch) break;
        items.push(itemMatch[1]);
        i += 1;
      }
      blocks.push(
        <ol key={`ol-${i}`} className="note-preview-list note-preview-list-ordered">
          {items.map((item, idx) => <li key={`ol-item-${idx}`}>{renderInlineMarkdown(item)}</li>)}
        </ol>
      );
      continue;
    }

    const paragraph: string[] = [trimmed];
    i += 1;
    while (i < lines.length) {
      const nextTrimmed = lines[i].trim();
      if (!nextTrimmed) {
        i += 1;
        break;
      }
      if (MARKDOWN_BLOCK_START.test(nextTrimmed)) break;
      paragraph.push(nextTrimmed);
      i += 1;
    }
    blocks.push(
      <p key={`paragraph-${i}`} className="note-paragraph">
        {renderInlineMarkdown(paragraph.join(" "))}
      </p>
    );
  }

  if (blocks.length === 0) {
    return [<p key="note-empty" className="note-empty-text">Empty note.</p>];
  }
  return blocks;
}

export default function Notes() {
  const [notes, setNotes] = useState<WorkspaceNote[]>([]);
  const [activePath, setActivePath] = useState<string | null>(null);
  const [content, setContent] = useState("");
  const [originalContent, setOriginalContent] = useState("");
  const [loadingList, setLoadingList] = useState(true);
  const [loadingNote, setLoadingNote] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saveState, setSaveState] = useState<NoteSaveState>("idle");

  const isDirty = !!activePath && content !== originalContent;
  const activeNote = notes.find((n) => n.path === activePath) ?? null;

  const loadNotes = useCallback(async () => {
    setError(null);
    setLoadingList(true);
    try {
      const res = await api.getWorkspaceNotes(200);
      const next = res.notes || [];
      setNotes(next);
      setActivePath((previousPath) => {
        if (next.length === 0) return null;
        if (previousPath && next.some((n) => n.path === previousPath)) return previousPath;
        return next[0].path;
      });
      if (next.length === 0) {
        setContent("");
        setOriginalContent("");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load notes.");
    } finally {
      setLoadingList(false);
    }
  }, []);

  const loadNote = useCallback(async (path: string) => {
    setLoadingNote(true);
    setError(null);
    setSaveState("idle");
    try {
      const res = await api.filesRead(path);
      const next = res.content || "";
      setContent(next);
      setOriginalContent(next);
      setActivePath(path);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to open note.");
      setContent("");
      setOriginalContent("");
    } finally {
      setLoadingNote(false);
    }
  }, []);

  useEffect(() => {
    void loadNotes();
  }, [loadNotes]);

  useEffect(() => {
    if (!activePath) return;
    void loadNote(activePath);
  }, [activePath, loadNote]);

  useEffect(() => {
    if (saveState !== "saved") return;
    const timer = setTimeout(() => setSaveState("idle"), 1800);
    return () => clearTimeout(timer);
  }, [saveState]);

  const handleSelectNote = (path: string) => {
    if (path === activePath) return;
    if (isDirty && !confirm("Discard unsaved note changes?")) return;
    setActivePath(path);
  };

  const handleSave = async () => {
    if (!activePath || !isDirty) return;
    setSaveState("saving");
    setError(null);
    try {
      await api.filesWrite(activePath, content);
      setOriginalContent(content);
      setSaveState("saved");
      await loadNotes();
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to save.";
      setError(msg);
      setSaveState("error");
    }
  };

  const handleEditorKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "s") {
      event.preventDefault();
      void handleSave();
    }
  };

  return (
    <div className="notes-page">
      <h1 className="page-title">Notes</h1>
      <p className="page-description">
        Formatted preview + markdown editing for workspace notes. These are files under <code>notes/</code>.
      </p>

      {error && <div className="alert alert-error">{error}</div>}

      <div className="notes-layout">
        <aside className="card notes-sidebar">
          <div className="notes-sidebar-header">
            <div>
              <h2>Workspace notes</h2>
              <p>{notes.length} total</p>
            </div>
            <button type="button" className="btn btn-secondary btn-sm" onClick={() => void loadNotes()}>
              Refresh
            </button>
          </div>

          {loadingList ? (
            <div className="notes-empty">Loading notes...</div>
          ) : notes.length === 0 ? (
            <div className="notes-empty">
              No notes found. Ask Asta to take a note, or create one in <Link to="/files">Files</Link>.
            </div>
          ) : (
            <div className="notes-list" role="listbox" aria-label="Workspace notes">
              {notes.map((note) => {
                const selected = note.path === activePath;
                return (
                  <button
                    key={note.path}
                    type="button"
                    className={`note-list-item ${selected ? "active" : ""}`}
                    onClick={() => handleSelectNote(note.path)}
                    aria-selected={selected}
                  >
                    <span className="note-list-name" title={note.path}>{note.name}</span>
                    <span className="note-list-meta">
                      {new Date(note.modified_at).toLocaleDateString([], { month: "short", day: "numeric" })} · {Math.max(1, Math.round(note.size / 1024))} KB
                    </span>
                  </button>
                );
              })}
            </div>
          )}
        </aside>

        <section className="card notes-editor-card">
          <div className="notes-toolbar">
            <div className="notes-meta">
              <strong>{activeNote?.name || "Select a note"}</strong>
              <span title={activeNote?.path || ""}>{activeNote?.path || "No note selected"}</span>
            </div>
            <button
              type="button"
              className="btn btn-primary btn-sm"
              onClick={() => void handleSave()}
              disabled={!activePath || !isDirty || loadingNote || saveState === "saving"}
            >
              {saveState === "saving" ? "Saving..." : saveState === "saved" ? "Saved" : "Save"}
            </button>
          </div>

          {loadingNote ? (
            <div className="notes-empty">Loading note...</div>
          ) : activePath ? (
            <>
              <div className="note-preview">{renderMarkdownPreview(content)}</div>
              <label className="note-editor-label" htmlFor="notes-editor">Edit markdown</label>
              <textarea
                id="notes-editor"
                className="note-editor"
                value={content}
                onChange={(event) => {
                  setContent(event.target.value);
                  if (saveState !== "idle") setSaveState("idle");
                }}
                onKeyDown={handleEditorKeyDown}
              />
              <div className="note-hint">Use Cmd/Ctrl + S to save.</div>
            </>
          ) : (
            <div className="notes-empty">Select a note to preview and edit.</div>
          )}
        </section>
      </div>

      <style>{`
        .notes-page { max-width: 1500px; }
        .notes-layout {
          display: grid;
          grid-template-columns: 320px minmax(0, 1fr);
          gap: 1rem;
          align-items: start;
        }
        .notes-sidebar,
        .notes-editor-card {
          margin-bottom: 0;
        }
        .notes-sidebar-header {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          gap: 0.75rem;
          margin-bottom: 0.9rem;
        }
        .notes-sidebar-header h2 {
          margin: 0;
        }
        .notes-sidebar-header p {
          margin: 0.15rem 0 0;
          font-size: 0.85rem;
          color: var(--muted);
        }
        .notes-empty {
          color: var(--muted);
          font-size: 0.9rem;
          font-style: italic;
          padding: 0.85rem 0;
        }
        .notes-list {
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
          max-height: calc(100vh - 270px);
          overflow: auto;
          padding-right: 0.15rem;
        }
        .note-list-item {
          border: 1px solid var(--border);
          border-radius: 10px;
          background: #ffffff;
          text-align: left;
          padding: 0.6rem 0.7rem;
          cursor: pointer;
          transition: border-color 0.15s ease, box-shadow 0.15s ease, background 0.15s ease;
          display: flex;
          flex-direction: column;
          gap: 0.25rem;
        }
        .note-list-item:hover {
          border-color: var(--accent);
          background: var(--accent-soft);
        }
        .note-list-item.active {
          border-color: var(--accent);
          box-shadow: 0 0 0 2px var(--accent-dim);
          background: var(--accent-soft);
        }
        .note-list-name {
          font-size: 0.9rem;
          font-weight: 600;
          color: var(--text);
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        .note-list-meta {
          font-size: 0.74rem;
          color: var(--muted);
        }
        .notes-toolbar {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 0.8rem;
          margin-bottom: 0.8rem;
        }
        .notes-meta {
          display: flex;
          flex-direction: column;
          min-width: 0;
        }
        .notes-meta strong {
          font-size: 0.95rem;
          color: var(--text);
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        .notes-meta span {
          font-size: 0.74rem;
          color: var(--muted);
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        .note-preview {
          border: 1px solid var(--border);
          background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
          border-radius: 12px;
          padding: 0.85rem;
          max-height: 260px;
          overflow: auto;
          font-size: 0.9rem;
          line-height: 1.5;
          color: var(--text);
        }
        .note-heading { font-weight: 700; color: var(--text); margin: 0.2rem 0 0.4rem; }
        .note-heading-1 { font-size: 1.04rem; }
        .note-heading-2 { font-size: 0.98rem; }
        .note-heading-3 { font-size: 0.92rem; }
        .note-paragraph { margin: 0 0 0.6rem; }
        .note-preview-list { margin: 0 0 0.6rem; padding-left: 1.25rem; }
        .note-preview-list-ordered { list-style: decimal; }
        .note-blockquote {
          margin: 0 0 0.6rem;
          padding: 0.4rem 0.7rem;
          border-left: 3px solid #93c5fd;
          background: #eff6ff;
          color: var(--text-secondary);
        }
        .note-code-block {
          margin: 0 0 0.6rem;
          background: #0f172a;
          color: #e2e8f0;
          border-radius: 10px;
          padding: 0.7rem;
          overflow: auto;
          font-size: 0.78rem;
          line-height: 1.45;
        }
        .note-inline-code {
          font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
          background: rgba(15, 23, 42, 0.08);
          color: #0f172a;
          border-radius: 4px;
          padding: 0.03rem 0.25rem;
          font-size: 0.82em;
        }
        .note-empty-text {
          color: var(--muted);
          margin: 0;
          font-style: italic;
        }
        .note-editor-label {
          display: block;
          margin-top: 0.75rem;
          margin-bottom: 0.35rem;
          font-size: 0.74rem;
          text-transform: uppercase;
          letter-spacing: 0.04em;
          color: var(--muted);
          font-weight: 700;
        }
        .note-editor {
          width: 100%;
          min-height: 260px;
          resize: vertical;
          border: 1px solid var(--border);
          border-radius: 12px;
          padding: 0.8rem;
          font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
          font-size: 0.84rem;
          color: var(--text);
          background: #ffffff;
        }
        .note-editor:focus {
          outline: none;
          border-color: var(--accent);
          box-shadow: 0 0 0 3px var(--accent-soft);
        }
        .note-hint {
          font-size: 0.74rem;
          color: var(--muted);
          margin-top: 0.35rem;
        }
        @media (max-width: 1300px) {
          .notes-layout {
            grid-template-columns: 270px minmax(0, 1fr);
          }
        }
        @media (max-width: 1000px) {
          .notes-layout {
            grid-template-columns: 1fr;
          }
          .notes-list {
            max-height: 220px;
          }
          .note-preview {
            max-height: 210px;
          }
        }
      `}</style>
    </div>
  );
}
