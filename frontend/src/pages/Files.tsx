import { useState, useEffect } from "react";
import { api } from "../api/client";

type Entry = { name: string; path: string; dir: boolean; size?: number };

const ROOT_LABELS: Record<string, string> = {
  "asta:knowledge": "Asta knowledge",
  "user:memories": "About you (User.md)",
};

export default function Files() {
  const [roots, setRoots] = useState<string[]>([]);
  const [entries, setEntries] = useState<Entry[]>([]);
  const [currentRoot, setCurrentRoot] = useState<string>("");
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [content, setContent] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = (dir?: string) => {
    setError(null);
    setLoading(true);
    api
      .filesList(dir)
      .then((r) => {
        if (r.roots) setRoots(r.roots);
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
        if (r.roots) setRoots(r.roots);
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
  const openFile = (path: string) => {
    setSelectedFile(path);
    setContent("");
    api.filesRead(path).then((r) => setContent(r.content)).catch((e) => setContent("Error: " + (e as Error).message));
  };

  const rootLabel = (r: string) => ROOT_LABELS[r] || r;

  const crumbs = (() => {
    if (!currentRoot) return [];
    const label = ROOT_LABELS[currentRoot] || currentRoot;
    return [{ label, path: currentRoot }];
  })();

  return (
    <div>
      <h1 className="page-title">Files</h1>
      <p className="page-description">
        Asta knowledge (docs), your memories (User.md), and allowed paths. AI uses this context when you chat.
      </p>
      {error && <div className="alert alert-error">{error}</div>}
      {roots.length === 0 && !error && (
        <div className="card">
          <p>No roots available. Add ASTA_ALLOWED_PATHS (comma-separated dirs) in backend/.env and restart.</p>
        </div>
      )}
      {roots.length > 0 && (
        <div className="card">
          <div className="field">
            <div className="label">Browse</div>
            <div className="actions">
              {roots.map((r) => (
                <button key={r} type="button" onClick={() => openDir(r)} className="btn btn-secondary">
                  {rootLabel(r)}
                </button>
              ))}
            </div>
            <p className="help">Asta knowledge = docs. About you = User.md memories. Add ASTA_ALLOWED_PATHS for more.</p>
          </div>
        </div>
      )}

      {currentRoot && roots.length > 0 && (
        <div className="file-browser">
          <div className="card">
            <div className="card-header">
              <div>
                <h2 style={{ margin: 0 }}>Browse</h2>
                <p className="help" style={{ marginTop: "0.25rem" }}>
                  Click folders to navigate, click files to preview.
                </p>
              </div>
              <button type="button" className="btn btn-quiet" onClick={refreshDir} disabled={loading}>
                {loading ? "Refreshing…" : "Refresh"}
              </button>
            </div>

            <div className="breadcrumbs" style={{ marginBottom: "0.75rem" }}>
              <span className="muted">Current:</span>
              {crumbs.map((c) => (
                <button key={c.path} type="button" className="crumb" onClick={() => openDir(c.path)}>
                  {c.label}
                </button>
              ))}
            </div>

            <ul className="file-list" style={{ margin: 0 }}>
              {entries.map((e) => (
                <li key={e.path}>
                  {e.dir ? (
                    <button type="button" onClick={() => openDir(e.path)} className="link-btn">
                      📁 {e.name}
                    </button>
                  ) : (
                    <button type="button" onClick={() => openFile(e.path)} className="link-btn">
                      📄 {e.name}{" "}
                      {e.size != null ? <span className="muted">({Math.max(1, Math.round(e.size / 1024))} KB)</span> : null}
                    </button>
                  )}
                </li>
              ))}
              {entries.length === 0 && <li className="muted">Empty directory.</li>}
            </ul>
          </div>

          <div className="card">
            <div className="card-header">
              <div>
                <h2 style={{ margin: 0 }}>Preview</h2>
                <p className="help" style={{ marginTop: "0.25rem" }}>
                  {selectedFile ? selectedFile : "Select a file to preview its contents."}
                </p>
              </div>
              {selectedFile ? (
                <button type="button" className="btn btn-secondary" onClick={() => openFile(selectedFile)}>
                  Reload
                </button>
              ) : null}
            </div>

            {selectedFile ? (
              <pre className="file-preview">{content || "Loading…"}</pre>
            ) : (
              <div className="alert">
                Tip: set <code>ASTA_ALLOWED_PATHS</code> in <code>backend/.env</code> to control what shows up here.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
