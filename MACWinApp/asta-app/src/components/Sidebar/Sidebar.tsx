import { useState, useEffect, useCallback, useRef } from "react";
import { createPortal } from "react-dom";
import {
  IconNewChat, IconSettings, IconFolder, IconNewFolder,
  IconTrash, IconSearch,
} from "../../lib/icons";
import type { User } from "../../lib/auth";
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
  onOpenSettings?: () => void;
  onOpenDashboard?: () => void;
  onOpenAgents?: () => void;
  onSelectProject?: (id: string | null) => void;
  isOnline: boolean;
  refreshTrigger?: number;
  user?: User;
  onLogout?: () => void;
}

export default function Sidebar({
  selectedId, onSelect, onNewChat, onOpenSettings, onOpenDashboard: _onOpenDashboard, onOpenAgents, onSelectProject,
  isOnline, refreshTrigger,
  user, onLogout,
}: Props) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [folders, setFolders] = useState<Folder[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renamingText, setRenamingText] = useState("");
  const [droppingOn, setDroppingOn] = useState<string | null>(null);
  const [ctx, setCtx] = useState<{
    type: "conv" | "folder"; id: string; x: number; y: number; folderId?: string;
  } | null>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const [creatingFolder, setCreatingFolder] = useState(false);
  const [newFolderName, setNewFolderName] = useState("");

  const refresh = useCallback(async () => {
    try {
      const [c, f] = await Promise.all([listConversations(), listFolders()]);
      setConversations(c.conversations ?? []);
      setFolders(f.folders ?? []);
    } catch {}
    setLoading(false);
  }, []);

  useEffect(() => { refresh(); }, [refreshTrigger, refresh]);

  async function handleRename(id: string) {
    if (!renamingText.trim()) { setRenamingId(null); return; }
    await renameFolder(id, renamingText.trim());
    setRenamingId(null); refresh();
  }

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

  const q = searchQuery.trim().toLowerCase();
  const allFiltered = q ? conversations.filter(c => c.title?.toLowerCase().includes(q)) : conversations;
  const inFolder = (fid: string) => allFiltered.filter(c => c.folder_id === fid);
  const unfiled = allFiltered.filter(c => !c.folder_id);

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

      {/* ── Top actions ── */}
      <div className="px-3 pt-4 pb-1 space-y-0.5 titlebar-drag shrink-0">
        <button
          onClick={onNewChat}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-mac hover:bg-white/[.07] text-label text-13 font-medium transition-all duration-200 active:scale-[0.98] group"
        >
          <IconNewChat size={14} className="text-label-secondary" />
          <span>New chat</span>
        </button>
        {onOpenAgents && (
          <button
            onClick={onOpenAgents}
            className="w-full flex items-center gap-3 px-3 py-2 rounded-mac hover:bg-white/[.07] text-label-secondary text-13 font-medium transition-all duration-200 active:scale-[0.98] group"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-label-secondary">
              <circle cx="12" cy="12" r="3"/><path d="M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4M4.22 19.78l2.83-2.83M16.95 7.05l2.83-2.83"/>
            </svg>
            <span>Agents</span>
          </button>
        )}

      </div>

      <div className="h-px bg-separator mx-3 my-1 shrink-0" />

      {/* ── Projects ── */}
      <div className="px-3 py-0.5 space-y-0.5 shrink-0">
        <div className="flex items-center justify-between px-3 pt-1.5 pb-0.5">
          <p className="text-[10px] font-semibold text-label-tertiary uppercase tracking-widest">Projects</p>
          <div className="flex items-center gap-2">
            <button onClick={() => { setCreatingFolder(true); setNewFolderName(""); }}
              className="text-label-tertiary hover:text-accent transition-colors" title="New project">
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
              </svg>
            </button>
            {onSelectProject && (
              <button onClick={() => onSelectProject(null)} className="text-[10px] text-label-tertiary hover:text-accent transition-colors">View all</button>
            )}
          </div>
        </div>
        {creatingFolder && (
          <div className="flex items-center gap-2 px-3 py-1.5">
            <IconNewFolder size={13} className="text-accent shrink-0" />
            <input autoFocus value={newFolderName}
              onChange={e => setNewFolderName(e.target.value)}
              onKeyDown={async e => {
                if (e.key === "Enter" && newFolderName.trim()) {
                  await createFolder(newFolderName.trim());
                  setCreatingFolder(false); setNewFolderName(""); refresh();
                }
                if (e.key === "Escape") { setCreatingFolder(false); setNewFolderName(""); }
              }}
              onBlur={() => { setCreatingFolder(false); setNewFolderName(""); }}
              placeholder="Project name..."
              className="flex-1 bg-transparent text-12 font-semibold text-label outline-none border-b border-accent placeholder:text-label-tertiary"
            />
          </div>
        )}
        {folders.length === 0 && !creatingFolder && onSelectProject && (
          <button onClick={() => { setCreatingFolder(true); setNewFolderName(""); }}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-mac hover:bg-white/[.05] text-label-tertiary text-12 transition-colors">
            <IconNewFolder size={12} />
            <span>Create a project</span>
          </button>
        )}
        {folders.map(folder => {
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
                className={`flex items-center gap-2 px-3 py-1.5 rounded-mac cursor-pointer transition-colors ${
                  dropping ? "bg-accent/10 border border-accent/30" : "hover:bg-white/[.05] border border-transparent"
                }`}
                onClick={() => onSelectProject?.(folder.id)}
                onContextMenu={(e) => { e.preventDefault(); setCtx({ type: "folder", id: folder.id, x: e.clientX, y: e.clientY }); }}
              >
                <IconFolder size={13} style={folder.color ? { color: folder.color } : undefined} className={folder.color ? "" : "text-label-tertiary"} />
                {renamingId === folder.id ? (
                  <input autoFocus value={renamingText}
                    onChange={e => setRenamingText(e.target.value)}
                    onKeyDown={e => { if (e.key === "Enter") handleRename(folder.id); if (e.key === "Escape") setRenamingId(null); }}
                    onBlur={() => handleRename(folder.id)}
                    onClick={e => e.stopPropagation()}
                    className="flex-1 bg-transparent text-12 font-semibold text-label outline-none border-b border-accent"
                  />
                ) : (
                  <span className="text-13 text-label-secondary flex-1 truncate">{folder.name}</span>
                )}
                <span className="text-11 text-label-tertiary">{children.length || ""}</span>
              </div>
            </div>
            );
          })}
      </div>

      <div className="h-px bg-separator mx-3 my-1 shrink-0" />

      {/* ── Search + Recents ── */}
      <div className="flex-1 min-h-0 flex flex-col overflow-hidden">
        {/* Search bar */}
        <div className="px-3 pt-1.5 pb-1 shrink-0">
          {!searching ? (
            <button
              onClick={() => { setSearching(true); setTimeout(() => searchRef.current?.focus(), 0); }}
              className="w-full flex items-center gap-2 px-3 py-1.5 rounded-mac hover:bg-white/[.06] text-label-tertiary text-12 transition-colors"
            >
              <IconSearch size={12} />
              <span>Search chats</span>
            </button>
          ) : (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-mac bg-white/[.06] border border-separator">
              <IconSearch size={12} className="text-label-tertiary shrink-0" />
              <input
                ref={searchRef}
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                onKeyDown={e => { if (e.key === "Escape") { setSearchQuery(""); setSearching(false); } }}
                onBlur={() => { if (!searchQuery) setSearching(false); }}
                placeholder="Search..."
                className="flex-1 bg-transparent text-12 text-label outline-none placeholder:text-label-tertiary"
              />
              {searchQuery && (
                <button onClick={() => { setSearchQuery(""); searchRef.current?.focus(); }} className="text-label-tertiary hover:text-label-secondary shrink-0">
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                </button>
              )}
            </div>
          )}
        </div>

        {/* Recents label */}
        {!q && unfiled.length > 0 && (
          <p className="text-[10px] font-semibold text-label-tertiary px-4 pt-1.5 pb-1 uppercase tracking-widest shrink-0">
            Recents
          </p>
        )}
        {q && allFiltered.length === 0 && (
          <p className="text-center text-label-tertiary text-13 py-8 shrink-0">No results</p>
        )}

        {/* Conversation list */}
        <div className="flex-1 overflow-y-auto px-2 pb-2 space-y-px scrollbar-thin">
          {loading && conversations.length === 0 && (
            <div className="flex items-center justify-center py-10">
              <div className="w-5 h-5 border-2 border-accent/40 border-t-accent rounded-full animate-spin" />
            </div>
          )}
          {unfiled.map(c => <ConvRow key={c.id} c={c} />)}
          {!loading && conversations.length === 0 && (
            <p className="text-center text-label-tertiary text-13 py-10">No conversations yet</p>
          )}
        </div>
      </div>

      {/* ── Bottom bar ── */}
      <div className="shrink-0 border-t border-separator px-3 py-3">
        <div className="flex items-center gap-2.5">
          {/* Status dot */}
          <div className="relative shrink-0">
            <div className={`w-2.5 h-2.5 rounded-full ${isOnline ? "bg-success" : "bg-danger"}`} />
            {isOnline && <div className="absolute inset-0 w-2.5 h-2.5 rounded-full bg-success animate-ping opacity-40" />}
          </div>

          {/* User info */}
          <div className="flex-1 min-w-0">
            {user ? (
              <div className="flex items-center gap-2">
                <span className="text-12 text-label font-medium truncate">{user.username}</span>
                <span className="text-[10px] text-label-tertiary bg-white/[.08] px-1.5 py-0.5 rounded-full uppercase tracking-wider font-semibold shrink-0">{user.role}</span>
              </div>
            ) : (
              <span className="text-12 text-label-secondary font-medium">{isOnline ? "Connected" : "Offline"}</span>
            )}
          </div>

          {/* Actions */}
          <div className="flex items-center gap-1 shrink-0">
            {onOpenSettings && (
              <button onClick={onOpenSettings} className="w-7 h-7 flex items-center justify-center rounded-mac hover:bg-white/[.08] text-label-tertiary hover:text-label-secondary transition-colors" title="Customize">
                <IconSettings size={13} />
              </button>
            )}
            {onLogout && (
              <button onClick={onLogout} className="w-7 h-7 flex items-center justify-center rounded-mac hover:bg-white/[.08] text-label-tertiary hover:text-danger transition-colors" title="Sign out">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Context menu */}
      {ctx && createPortal(
        <div className="fixed inset-0 z-[9999]" onClick={() => setCtx(null)}>
          <div className="fixed bg-surface-raised border border-separator-bold rounded-xl shadow-modal py-1.5 w-52 animate-scale-in" style={{ left: ctx.x, top: ctx.y }} onClick={e => e.stopPropagation()}>
            {ctx.type === "conv" && (
              <>
                {folders.length > 0 && (
                  <>
                    <p className="px-3.5 py-1 text-11 text-label-tertiary font-medium uppercase tracking-wider">Move to project</p>
                    {folders.filter(f => f.id !== ctx.folderId).map(f => (
                      <button key={f.id} className="w-full text-left px-4 py-1.5 text-13 text-label-secondary hover:bg-white/[.05] rounded-lg mx-1 transition-colors" style={{ width: "calc(100% - 8px)" }}
                        onClick={async () => { await assignConversationFolder(ctx.id, f.id); setCtx(null); refresh(); }}>
                        <IconFolder size={11} className="inline mr-2 -mt-px" />{f.name}
                      </button>
                    ))}
                    {ctx.folderId && (
                      <button className="w-full text-left px-4 py-1.5 text-13 text-label-secondary hover:bg-white/[.05] transition-colors"
                        onClick={async () => { await assignConversationFolder(ctx.id, null); setCtx(null); refresh(); }}>
                        Remove from project
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
