import { useState, useEffect, useCallback } from "react";
import { createPortal } from "react-dom";
import {
  IconNewChat, IconAgents, IconSettings, IconFolder, IconNewFolder,
  IconChevronRight, IconChevronDown, IconTrash,
} from "../../lib/icons";
import {
  listConversations, listFolders, createFolder, renameFolder,
  deleteFolder, deleteConversation, assignConversationFolder,
  truncateConversation,
} from "../../lib/api";

interface Conversation {
  id: string; title: string; folder_id?: string | null;
  approx_tokens?: number; last_active?: string;
}
interface Folder { id: string; name: string; color?: string; }

interface Props {
  selectedId?: string;
  onSelect: (id: string) => void;
  onNewChat: () => void;
  onOpenSettings: () => void;
  onOpenAgents: () => void;
  enabledAgentCount: number;
  providerShortName: string;
  isOnline: boolean;
  refreshTrigger?: number;
}

export default function Sidebar({
  selectedId, onSelect, onNewChat, onOpenSettings, onOpenAgents,
  enabledAgentCount, providerShortName, isOnline, refreshTrigger,
}: Props) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [folders, setFolders] = useState<Folder[]>([]);
  const [loading, setLoading] = useState(true);
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const [showNewFolder, setShowNewFolder] = useState(false);
  const [newFolderName, setNewFolderName] = useState("");
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renamingText, setRenamingText] = useState("");
  const [droppingOn, setDroppingOn] = useState<string | null>(null);
  const [ctx, setCtx] = useState<{
    type: "conv" | "folder"; id: string; x: number; y: number; folderId?: string;
  } | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [c, f] = await Promise.all([listConversations(), listFolders()]);
      setConversations(c.conversations ?? []);
      setFolders(f.folders ?? []);
    } catch {}
    setLoading(false);
  }, []);

  useEffect(() => { refresh(); }, [refreshTrigger, refresh]);

  function toggleFolder(id: string) {
    setCollapsed(prev => { const s = new Set(prev); s.has(id) ? s.delete(id) : s.add(id); return s; });
  }

  async function handleCreateFolder() {
    if (!newFolderName.trim()) return;
    await createFolder(newFolderName.trim());
    setNewFolderName(""); setShowNewFolder(false); refresh();
  }

  async function handleRename(id: string) {
    if (!renamingText.trim()) { setRenamingId(null); return; }
    await renameFolder(id, renamingText.trim());
    setRenamingId(null); refresh();
  }

  // Optimistic delete: remove from list immediately, then call API
  async function handleDeleteConv(id: string) {
    setConversations(prev => prev.filter(c => c.id !== id));
    setCtx(null);
    await deleteConversation(id).catch(() => refresh());
    refresh();
  }

  function fmtTokens(n?: number) {
    if (!n) return "";
    if (n >= 10_000) return `${Math.round(n / 1000)}k`;
    if (n >= 1_000) return `${(n / 1000).toFixed(1)}k`;
    return `${n}`;
  }

  function fmtTime(ts?: string) {
    if (!ts) return "";
    const d = new Date(ts);
    if (isNaN(d.getTime())) return "";
    const ms = Date.now() - d.getTime();
    const sec = ms / 1000;
    if (sec < 60) return "just now";
    const min = sec / 60;
    if (min < 60) return `${Math.round(min)}m ago`;
    const h = min / 60;
    if (h < 24) return `${Math.round(h)}h ago`;
    const days = h / 24;
    if (days < 7) return `${Math.round(days)}d ago`;
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  }

  const inFolder = (fid: string) => conversations.filter(c => c.folder_id === fid);
  const unfiled = conversations.filter(c => !c.folder_id);

  function ConvRow({ c }: { c: Conversation }) {
    const sel = selectedId === c.id;
    return (
      <div
        className={`flex flex-col px-3 py-2 rounded-mac cursor-pointer select-none transition-all duration-200 ${
          sel
            ? "bg-accent/[.12] text-label shadow-glow-sm"
            : "text-label hover:bg-white/[.05] hover:translate-x-0.5"
        }`}
        onClick={() => onSelect(c.id)}
        onContextMenu={(e) => {
          e.preventDefault();
          setCtx({ type: "conv", id: c.id, x: e.clientX, y: e.clientY, folderId: c.folder_id ?? undefined });
        }}
        draggable
        onDragStart={(e) => e.dataTransfer.setData("conv-id", c.id)}
      >
        <span className={`text-13 truncate ${sel ? "font-medium" : "font-normal"}`}>{c.title || "New Chat"}</span>
        <span className="text-11 text-label-tertiary tabular-nums mt-0.5 font-mono">
          {fmtTokens(c.approx_tokens)}{c.approx_tokens && c.last_active ? " · " : ""}{fmtTime(c.last_active)}
        </span>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full select-none" onClick={() => setCtx(null)}>
      {/* Top buttons */}
      <div className="px-3 pt-3 pb-1.5 space-y-1.5 titlebar-drag">
        <button
          onClick={onNewChat}
          className="w-full flex items-center justify-between px-3 py-2.5 rounded-mac bg-white/[.06] hover:bg-white/[.10] text-label text-13 font-medium transition-all duration-200 border border-separator active:scale-[0.98]"
        >
          <span className="flex items-center gap-2.5">
            <IconNewChat size={14} className="text-label-secondary" />
            <span>New chat</span>
          </span>
          <span className="text-11 text-label-tertiary bg-white/[.08] px-2 py-0.5 rounded-full font-mono">
            {providerShortName}
          </span>
        </button>
        <button
          onClick={onOpenAgents}
          className="w-full flex items-center justify-between px-3 py-2 rounded-mac bg-white/[.04] hover:bg-white/[.08] text-label text-13 font-medium transition-all duration-200 border border-separator active:scale-[0.98]"
        >
          <span className="flex items-center gap-2.5">
            <IconAgents size={14} className="text-label-secondary" />
            <span>Agents</span>
          </span>
          {enabledAgentCount > 0 && (
            <span className="text-11 text-label-secondary bg-white/[.08] px-2 py-0.5 rounded-full tabular-nums font-semibold">
              {enabledAgentCount}
            </span>
          )}
        </button>
      </div>

      <div className="h-px bg-separator mx-3 my-1.5" />

      {/* Conversation list */}
      <div className="flex-1 overflow-y-auto px-2 space-y-0.5 scrollbar-thin">
        {loading && conversations.length === 0 && folders.length === 0 && (
          <div className="flex items-center justify-center py-10">
            <div className="w-5 h-5 border-2 border-accent/40 border-t-accent rounded-full animate-spin" />
          </div>
        )}

        {folders.map((folder) => {
          const isCollapsed = collapsed.has(folder.id);
          const children = inFolder(folder.id);
          const dropping = droppingOn === folder.id;
          return (
            <div
              key={folder.id}
              onDragOver={(e) => { e.preventDefault(); setDroppingOn(folder.id); }}
              onDragLeave={() => setDroppingOn(null)}
              onDrop={async (e) => {
                setDroppingOn(null);
                const cid = e.dataTransfer.getData("conv-id");
                if (cid) { await assignConversationFolder(cid, folder.id); refresh(); }
              }}
            >
              <div
                className={`flex items-center gap-1.5 px-2 py-1 rounded-lg cursor-pointer group transition-colors ${
                  dropping ? "bg-accent/10 border border-accent/30" : "hover:bg-white/[.05] border border-transparent"
                }`}
                onClick={() => toggleFolder(folder.id)}
                onContextMenu={(e) => {
                  e.preventDefault();
                  setCtx({ type: "folder", id: folder.id, x: e.clientX, y: e.clientY });
                }}
              >
                <span className="text-label-tertiary">{isCollapsed ? <IconChevronRight size={9} /> : <IconChevronDown size={9} />}</span>
                <IconFolder size={11} style={folder.color ? { color: folder.color } : undefined} className={folder.color ? "" : "text-label-secondary"} />
                {renamingId === folder.id ? (
                  <input
                    autoFocus
                    value={renamingText}
                    onChange={e => setRenamingText(e.target.value)}
                    onKeyDown={e => { if (e.key === "Enter") handleRename(folder.id); if (e.key === "Escape") setRenamingId(null); }}
                    onBlur={() => handleRename(folder.id)}
                    onClick={e => e.stopPropagation()}
                    className="flex-1 bg-transparent text-12 font-semibold text-label outline-none border-b border-accent"
                  />
                ) : (
                  <span className="text-12 font-semibold text-label-secondary flex-1 truncate">{folder.name}</span>
                )}
                <span className="text-11 text-label-tertiary">{children.length || ""}</span>
              </div>
              {!isCollapsed && (
                <div className="ml-3.5 space-y-px">
                  {children.length === 0 && (
                    <p className="text-11 text-label-tertiary px-2 py-1 italic">Drop chats here</p>
                  )}
                  {children.map(c => <ConvRow key={c.id} c={c} />)}
                </div>
              )}
            </div>
          );
        })}

        {/* Unfiled label */}
        {folders.length > 0 && unfiled.length > 0 && (
          <p className="text-[10px] font-semibold text-label-tertiary px-2 pt-3 pb-1 uppercase tracking-widest">
            Chats
          </p>
        )}
        {unfiled.map(c => <ConvRow key={c.id} c={c} />)}

        {!loading && conversations.length === 0 && (
          <p className="text-center text-label-tertiary text-13 py-10">No conversations yet</p>
        )}
      </div>

      {/* Bottom bar */}
      <div className="flex items-center justify-between px-3 border-t border-separator" style={{ height: 48 }}>
        <div className="flex items-center gap-2">
          <div className="relative">
            <div className={`w-2 h-2 rounded-full ${isOnline ? "bg-success" : "bg-danger"}`} />
            {isOnline && <div className="absolute inset-0 w-2 h-2 rounded-full bg-success animate-ping opacity-40" />}
          </div>
          <span className="text-11 text-label-tertiary font-medium">{isOnline ? "Connected" : "Offline"}</span>
        </div>
        <div className="flex gap-0.5">
          <button onClick={() => setShowNewFolder(true)} className="w-8 h-8 flex items-center justify-center rounded-mac hover:bg-white/[.06] text-label-tertiary hover:text-label-secondary transition-all duration-200" title="New folder">
            <IconNewFolder size={14} />
          </button>
          <button onClick={onOpenSettings} className="w-8 h-8 flex items-center justify-center rounded-mac hover:bg-white/[.06] text-label-tertiary hover:text-label-secondary transition-all duration-200" title="Settings">
            <IconSettings size={15} />
          </button>
        </div>
      </div>

      {/* New Folder modal */}
      {showNewFolder && (
        <div className="absolute inset-0 bg-black/50 flex items-center justify-center z-50 animate-fade-in" onClick={() => setShowNewFolder(false)}>
          <div className="bg-surface-raised rounded-2xl p-6 w-72 shadow-modal border border-separator animate-scale-in" onClick={e => e.stopPropagation()}>
            <h3 className="text-label text-15 font-semibold mb-4">New Folder</h3>
            <input
              autoFocus type="text" value={newFolderName}
              onChange={e => setNewFolderName(e.target.value)}
              onKeyDown={e => { if (e.key === "Enter") handleCreateFolder(); if (e.key === "Escape") setShowNewFolder(false); }}
              placeholder="Folder name"
              className="w-full bg-white/[.04] border border-separator rounded-mac px-3.5 py-2.5 text-13 text-label outline-none focus:border-accent/50 transition-colors mb-4"
            />
            <div className="flex gap-2 justify-end">
              <button onClick={() => setShowNewFolder(false)} className="px-4 py-2 text-13 text-label-secondary hover:text-label rounded-mac transition-colors">Cancel</button>
              <button onClick={handleCreateFolder} disabled={!newFolderName.trim()} className="px-5 py-2 text-13 accent-gradient disabled:opacity-40 text-white rounded-mac font-medium transition-all hover:opacity-90 active:scale-[0.97]">Create</button>
            </div>
          </div>
        </div>
      )}

      {/* Context menu — rendered via portal to escape sidebar stacking context */}
      {ctx && createPortal(
        <div className="fixed inset-0 z-[9999]" onClick={() => setCtx(null)}>
          <div className="fixed bg-surface-raised border border-separator-bold rounded-xl shadow-modal py-1.5 w-52 animate-scale-in" style={{ left: ctx.x, top: ctx.y }} onClick={e => e.stopPropagation()}>
            {ctx.type === "conv" && (
              <>
                {folders.length > 0 && (
                  <>
                    <p className="px-3.5 py-1 text-11 text-label-tertiary font-medium uppercase tracking-wider">Move to</p>
                    {folders.filter(f => f.id !== ctx.folderId).map(f => (
                      <button key={f.id} className="w-full text-left px-4 py-1.5 text-13 text-label-secondary hover:bg-white/[.05] rounded-lg mx-1 transition-colors" style={{ width: "calc(100% - 8px)" }}
                        onClick={async () => { await assignConversationFolder(ctx.id, f.id); setCtx(null); refresh(); }}>
                        <IconFolder size={11} className="inline mr-2 -mt-px" />{f.name}
                      </button>
                    ))}
                    {ctx.folderId && (
                      <button className="w-full text-left px-4 py-1.5 text-13 text-label-secondary hover:bg-white/[.05] transition-colors"
                        onClick={async () => { await assignConversationFolder(ctx.id, null); setCtx(null); refresh(); }}>
                        Remove from folder
                      </button>
                    )}
                    <div className="border-t border-separator my-1.5 mx-2" />
                  </>
                )}
                <button className="w-full text-left px-4 py-1.5 text-13 text-label-secondary hover:bg-white/[.05] transition-colors"
                  onClick={async () => { await truncateConversation(ctx.id, 10); setCtx(null); }}>
                  Keep last 10 messages
                </button>
                <button className="w-full text-left px-4 py-1.5 text-13 text-danger hover:bg-danger/10 flex items-center gap-2 transition-colors"
                  onClick={() => handleDeleteConv(ctx.id)}>
                  <IconTrash size={12} /> Delete
                </button>
              </>
            )}
            {ctx.type === "folder" && (
              <>
                <button className="w-full text-left px-4 py-1.5 text-13 text-label-secondary hover:bg-white/[.05] transition-colors"
                  onClick={() => { const f = folders.find(x => x.id === ctx.id); if (f) { setRenamingId(f.id); setRenamingText(f.name); } setCtx(null); }}>
                  Rename
                </button>
                <button className="w-full text-left px-4 py-1.5 text-13 text-danger hover:bg-danger/10 flex items-center gap-2 transition-colors"
                  onClick={async () => { await deleteFolder(ctx.id); setCtx(null); refresh(); }}>
                  <IconTrash size={12} /> Delete
                </button>
              </>
            )}
          </div>
        </div>,
        document.body
      )}
    </div>
  );
}
