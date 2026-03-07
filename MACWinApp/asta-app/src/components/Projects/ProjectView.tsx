import { useState, useEffect, useCallback } from "react";
import { IconFolder, IconNewFolder } from "../../lib/icons";
import {
  listConversations, listFolders, createFolder,
  assignConversationFolder, renameFolder,
} from "../../lib/api";

interface Conversation {
  id: string; title: string; folder_id?: string | null;
  approx_tokens?: number; last_active?: string;
}
interface Folder { id: string; name: string; color?: string; }

interface Props {
  folderId: string | null;          // null = show all projects overview
  onSelectChat: (id: string) => void;
  onBack: () => void;
}

export default function ProjectView({ folderId, onSelectChat, onBack }: Props) {
  const [folders, setFolders] = useState<Folder[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [newName, setNewName] = useState("");
  const [creating, setCreating] = useState(false);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameText, setRenameText] = useState("");

  const refresh = useCallback(async () => {
    try {
      const [c, f] = await Promise.all([listConversations(), listFolders()]);
      setConversations(c.conversations ?? []);
      setFolders(f.folders ?? []);
    } catch {}
    setLoading(false);
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const folder = folderId ? folders.find(f => f.id === folderId) : null;
  const chatsInFolder = folderId
    ? conversations.filter(c => c.folder_id === folderId)
    : [];
  const unfiledChats = conversations.filter(c => !c.folder_id);

  async function handleCreate() {
    if (!newName.trim()) return;
    await createFolder(newName.trim());
    setNewName(""); setCreating(false); refresh();
  }

  async function handleRename(id: string) {
    if (!renameText.trim()) { setRenamingId(null); return; }
    await renameFolder(id, renameText.trim());
    setRenamingId(null); refresh();
  }

  function fmtTime(ts?: string) {
    if (!ts) return "";
    const d = new Date(ts);
    if (isNaN(d.getTime())) return "";
    const ms = Date.now() - d.getTime();
    const h = ms / 3600000;
    if (h < 1) return "just now";
    if (h < 24) return `${Math.round(h)}h ago`;
    const days = h / 24;
    if (days < 7) return `${Math.round(days)}d ago`;
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full bg-surface">
        <div className="w-6 h-6 border-2 border-accent/40 border-t-accent rounded-full animate-spin" />
      </div>
    );
  }

  // ── Single project detail view ──
  if (folderId && folder) {
    return (
      <div className="flex flex-col h-full bg-surface">
        {/* Header */}
        <div className="flex items-center gap-3 px-6 border-b border-separator titlebar-drag" style={{ height: 52 }}>
          <button onClick={onBack} className="text-label-tertiary hover:text-label transition-colors">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="15 18 9 12 15 6"/></svg>
          </button>
          <IconFolder size={16} style={folder.color ? { color: folder.color } : undefined} className={folder.color ? "" : "text-accent"} />
          {renamingId === folder.id ? (
            <input autoFocus value={renameText}
              onChange={e => setRenameText(e.target.value)}
              onKeyDown={e => { if (e.key === "Enter") handleRename(folder.id); if (e.key === "Escape") setRenamingId(null); }}
              onBlur={() => handleRename(folder.id)}
              className="text-17 font-semibold text-label bg-transparent outline-none border-b border-accent"
            />
          ) : (
            <h1 className="text-17 font-semibold text-label cursor-pointer hover:text-accent transition-colors"
              onClick={() => { setRenamingId(folder.id); setRenameText(folder.name); }}>
              {folder.name}
            </h1>
          )}
          <span className="text-12 text-label-tertiary ml-1">{chatsInFolder.length} chats</span>
        </div>

        {/* Chats in project */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {chatsInFolder.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-center">
              <IconFolder size={40} className="text-label-tertiary mb-4 opacity-40" />
              <p className="text-15 text-label-secondary font-medium mb-2">No chats in this project</p>
              <p className="text-13 text-label-tertiary mb-6 max-w-xs">Drag chats from your sidebar into this project, or right-click a chat and select "Move to project".</p>
            </div>
          ) : (
            <div className="space-y-1">
              {chatsInFolder.map(c => (
                <button key={c.id} onClick={() => onSelectChat(c.id)}
                  className="w-full text-left flex items-center gap-3 px-4 py-3 rounded-xl hover:bg-white/[.05] transition-colors group">
                  <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center shrink-0">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-accent"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-13 text-label font-medium truncate">{c.title || "Untitled"}</p>
                    <p className="text-11 text-label-tertiary">{fmtTime(c.last_active)}</p>
                  </div>
                </button>
              ))}
            </div>
          )}

          {/* Quick-add unfiled chats */}
          {unfiledChats.length > 0 && (
            <>
              <div className="h-px bg-separator my-5" />
              <p className="text-[10px] font-semibold text-label-tertiary uppercase tracking-widest mb-2">Add chats to this project</p>
              <div className="space-y-0.5">
                {unfiledChats.slice(0, 10).map(c => (
                  <button key={c.id}
                    onClick={async () => { await assignConversationFolder(c.id, folderId); refresh(); }}
                    className="w-full text-left flex items-center gap-3 px-3 py-2 rounded-mac hover:bg-white/[.05] transition-colors text-label-secondary hover:text-label">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                    <span className="text-12 truncate">{c.title || "Untitled"}</span>
                  </button>
                ))}
                {unfiledChats.length > 10 && (
                  <p className="text-11 text-label-tertiary px-3 py-1">+{unfiledChats.length - 10} more in sidebar</p>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    );
  }

  // ── All projects overview ──
  return (
    <div className="flex flex-col h-full bg-surface">
      {/* Header */}
      <div className="flex items-center justify-between px-6 border-b border-separator titlebar-drag" style={{ height: 52 }}>
        <div className="flex items-center gap-3">
          <button onClick={onBack} className="text-label-tertiary hover:text-label transition-colors">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="15 18 9 12 15 6"/></svg>
          </button>
          <h1 className="text-17 font-semibold text-label">Projects</h1>
        </div>
        <button
          onClick={() => setCreating(true)}
          className="flex items-center gap-2 px-3 py-1.5 text-12 text-accent hover:bg-accent/10 rounded-mac transition-colors font-medium"
        >
          <IconNewFolder size={13} />
          New project
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-4">
        {folders.length === 0 && !creating ? (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <div className="w-16 h-16 rounded-2xl bg-accent/10 flex items-center justify-center mb-5">
              <IconFolder size={28} className="text-accent" />
            </div>
            <p className="text-16 text-label font-semibold mb-2">No projects yet</p>
            <p className="text-13 text-label-tertiary mb-6 max-w-xs">Projects help you organize your chats by topic. Create one to get started.</p>
            <button onClick={() => setCreating(true)}
              className="px-5 py-2.5 accent-gradient text-white text-13 font-medium rounded-mac transition-all hover:opacity-90 active:scale-[0.97]">
              Create your first project
            </button>
          </div>
        ) : (
          <div className="grid gap-3" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))" }}>
            {folders.map(f => {
              const count = conversations.filter(c => c.folder_id === f.id).length;
              return (
                <button key={f.id} onClick={() => onSelectChat(f.id)}
                  className="text-left p-4 rounded-xl border border-separator hover:border-accent/30 hover:bg-white/[.04] transition-all group">
                  <IconFolder size={20} style={f.color ? { color: f.color } : undefined} className={f.color ? "mb-2" : "text-accent mb-2"} />
                  <p className="text-13 text-label font-medium truncate">{f.name}</p>
                  <p className="text-11 text-label-tertiary mt-0.5">{count} {count === 1 ? "chat" : "chats"}</p>
                </button>
              );
            })}
          </div>
        )}

        {/* Create inline */}
        {creating && (
          <div className="mt-4 flex items-center gap-2">
            <input autoFocus value={newName}
              onChange={e => setNewName(e.target.value)}
              onKeyDown={e => { if (e.key === "Enter") handleCreate(); if (e.key === "Escape") { setCreating(false); setNewName(""); } }}
              placeholder="Project name..."
              className="flex-1 bg-white/[.04] border border-separator rounded-mac px-3 py-2 text-13 text-label outline-none focus:border-accent/50 transition-colors"
            />
            <button onClick={handleCreate} disabled={!newName.trim()}
              className="px-4 py-2 text-13 accent-gradient disabled:opacity-40 text-white rounded-mac font-medium">Create</button>
            <button onClick={() => { setCreating(false); setNewName(""); }}
              className="px-3 py-2 text-13 text-label-secondary hover:text-label rounded-mac">Cancel</button>
          </div>
        )}
      </div>
    </div>
  );
}
