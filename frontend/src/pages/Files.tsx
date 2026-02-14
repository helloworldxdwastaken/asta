import { useState, useEffect, useCallback } from "react";
import { api } from "../api/client";

const USER_MD_PATH = "user:memories/User.md";
type Entry = { name: string; path: string; dir: boolean; size?: number };

const ROOT_LABELS: Record<string, string> = {
  "asta:knowledge": "Asta knowledge",
};

function rootLabel(r: string): string {
  if (ROOT_LABELS[r]) return ROOT_LABELS[r];
  // Show last path segment for allowed paths
  const parts = r.split(/[/\\]/).filter(Boolean);
  return parts.length ? parts[parts.length - 1] : r;
}

export default function Files() {
  const [roots, setRoots] = useState<string[]>([]);
  const [entries, setEntries] = useState<Entry[]>([]);
  const [currentRoot, setCurrentRoot] = useState<string>("");
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [content, setContent] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [pathAccessRequest, setPathAccessRequest] = useState<string | null>(null);

  // —— About you (User.md) — always visible, load on mount
  const [userMdContent, setUserMdContent] = useState<string>("");
  const [userMdEdit, setUserMdEdit] = useState<string>("");
  const [userMdSaving, setUserMdSaving] = useState(false);
  const [userMdLoaded, setUserMdLoaded] = useState(false);
  const [userMdError, setUserMdError] = useState<string | null>(null);

  const loadUserMd = useCallback(() => {
    setUserMdError(null);
    api
      .filesReadWithAccess(USER_MD_PATH)
      .then((result) => {
        if ("content" in result) {
          setUserMdContent(result.content);
          setUserMdEdit(result.content);
          setUserMdLoaded(true);
        } else if ("code" in result && result.code === "PATH_ACCESS_REQUEST") {
          setUserMdError("Could not load. Grant access in Settings → Allowed paths.");
        }
      })
      .catch((e) => setUserMdError((e as Error).message));
  }, []);

  useEffect(() => {
    loadUserMd();
  }, [loadUserMd]);

  const saveUserMd = () => {
    setUserMdSaving(true);
    setUserMdError(null);
    api
      .filesWrite(USER_MD_PATH, userMdEdit)
      .then(() => {
        setUserMdContent(userMdEdit);
        setUserMdSaving(false);
      })
      .catch((e) => {
        setUserMdError((e as Error).message);
        setUserMdSaving(false);
      });
  };

  const isUserMdDirty = userMdLoaded && userMdEdit !== userMdContent;

  // —— File browser
  const load = (dir?: string) => {
    setError(null);
    setLoading(true);
    api
      .filesList(dir)
      .then((r) => {
        if (r.roots) setRoots((r.roots as string[]).filter((x) => x !== "user:memories"));
        if (r.root) setCurrentRoot(r.root);
        setEntries(r.entries || []);
        setSelectedFile(null);
        setContent("");
      })
      .catch((e) => setError((e as Error).message))
      .finally(() => setLoading(false));
  };

  const refreshDir = () => {
    if (!currentRoot) return;
    setError(null);
    setLoading(true);
    api
      .filesList(currentRoot)
      .then((r) => {
        if (r.roots) setRoots((r.roots as string[]).filter((x) => x !== "user:memories"));
        if (r.root) setCurrentRoot(r.root);
        setEntries(r.entries || []);
      })
      .catch((e) => setError((e as Error).message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, []);

  const openDir = (path: string) => load(path);
  const openFile = async (path: string) => {
    setSelectedFile(path);
    setContent("Loading…");
    setPathAccessRequest(null);
    setError(null);
    try {
      const result = await api.filesReadWithAccess(path);
      if ("code" in result && result.code === "PATH_ACCESS_REQUEST") {
        setPathAccessRequest(result.requested_path);
        setContent("");
        setError(result.error || "Path not in allowed list. Grant access below.");
        return;
      }
      if ("content" in result) {
        setContent(result.content);
      }
    } catch (e) {
      const msg = (e as Error).message;
      setError(msg);
      setContent("Error: " + msg);
    }
  };

  const grantAccessAndRetry = async () => {
    if (!pathAccessRequest || !selectedFile) return;
    setError(null);
    try {
      await api.filesAllowPath(pathAccessRequest);
      setPathAccessRequest(null);
      await openFile(selectedFile);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const crumbs = currentRoot ? [{ label: rootLabel(currentRoot), path: currentRoot }] : [];

  return (
    <div className="files-page">
      <header className="files-page-header">
        <h1 className="page-title">Files & context</h1>
        <p className="page-description">
          Edit who you are (About you) and browse Asta knowledge or allowed paths. The AI uses your context when you chat.
        </p>
      </header>

      {error && <div className="alert alert-error">{error}</div>}
      {pathAccessRequest && (
        <div className="card files-grant-card">
          <p><strong>Path not allowed.</strong> Requested:</p>
          <code className="files-grant-path">{pathAccessRequest}</code>
          <p className="help">Granting adds this path to your allowlist. You can revoke in Settings → Allowed paths.</p>
          <div className="actions">
            <button type="button" className="btn btn-primary" onClick={grantAccessAndRetry}>Grant access</button>
            <button type="button" className="btn btn-secondary" onClick={() => { setPathAccessRequest(null); setError(null); setContent(""); }}>Dismiss</button>
          </div>
        </div>
      )}

      {/* —— About you (User.md) — editable card */}
      <section className="files-about-you card">
        <div className="card-header">
          <div>
            <h2 className="files-section-title">About you</h2>
            <p className="help files-section-desc">Location, preferred name, important facts. Asta uses this when you chat (workspace/USER.md).</p>
          </div>
          <div className="files-about-actions">
            {userMdError && <span className="files-error-text">{userMdError}</span>}
            <button type="button" className="btn btn-primary" onClick={saveUserMd} disabled={userMdSaving || !isUserMdDirty}>
              {userMdSaving ? "Saving…" : isUserMdDirty ? "Save" : "Saved"}
            </button>
          </div>
        </div>
        <textarea
          className="files-user-textarea"
          value={userMdEdit}
          onChange={(e) => setUserMdEdit(e.target.value)}
          placeholder="# USER.md - About You\n\n- **Name:**\n- **What to call you:**\n- **Location:** (e.g. City, Country)\n- **Timezone:** (optional)\n- **Notes:**\n\n## Context\n\n(Projects, preferences, things that matter.)"
          spellCheck="false"
        />
      </section>

      {/* —— File browser */}
      <section className="files-browser-section">
        <h2 className="files-section-title">Knowledge & allowed paths</h2>
        <p className="help files-section-desc">Browse docs and granted paths. Click a file to preview.</p>

        {roots.length === 0 && !error && (
          <div className="card">
            <p>No roots available. Add allowed paths in Settings → Files, or set <code>ASTA_ALLOWED_PATHS</code> in backend/.env and restart.</p>
          </div>
        )}

        {roots.length > 0 && (
          <div className="files-browser">
            <div className="card files-browser-tree">
              <div className="files-browser-tree-header">
                <span>Roots</span>
                <button type="button" className="btn btn-quiet btn-sm" onClick={refreshDir} disabled={loading}>
                  {loading ? "…" : "Refresh"}
                </button>
              </div>
              <div className="files-roots">
                {roots.map((r) => (
                  <button key={r} type="button" onClick={() => openDir(r)} className="files-root-btn" data-active={currentRoot === r || undefined}>
                    {rootLabel(r)}
                  </button>
                ))}
              </div>
              {currentRoot && (
                <>
                  <div className="files-breadcrumbs">
                    {crumbs.map((c) => (
                      <button key={c.path} type="button" className="crumb" onClick={() => openDir(c.path)}>{c.label}</button>
                    ))}
                  </div>
                  <ul className="files-list">
                    {entries.map((e) => (
                      <li key={e.path}>
                        {e.dir ? (
                          <button type="button" onClick={() => openDir(e.path)} className="files-list-item files-list-dir">
                            <span className="files-list-icon">📁</span>
                            <span>{e.name}</span>
                          </button>
                        ) : (
                          <button type="button" onClick={() => openFile(e.path)} className="files-list-item" data-selected={selectedFile === e.path || undefined}>
                            <span className="files-list-icon">📄</span>
                            <span>{e.name}</span>
                            {e.size != null && <span className="files-list-size">{Math.max(1, Math.round(e.size / 1024))} KB</span>}
                          </button>
                        )}
                      </li>
                    ))}
                    {entries.length === 0 && <li className="files-list-empty">Empty directory.</li>}
                  </ul>
                </>
              )}
            </div>

            <div className="card files-preview-card">
              <div className="card-header">
                <div>
                  <h2 style={{ margin: 0 }}>{selectedFile ? "Preview" : "File"}</h2>
                  <p className="help" style={{ marginTop: "0.25rem" }}>{selectedFile ? selectedFile : "Select a file."}</p>
                </div>
                {selectedFile && (
                  <button type="button" className="btn btn-secondary btn-sm" onClick={() => openFile(selectedFile)}>Reload</button>
                )}
              </div>
              {selectedFile ? (
                <pre className="files-preview-content">{content || "Loading…"}</pre>
              ) : (
                <div className="files-preview-empty">Select a file from the list to preview.</div>
              )}
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
