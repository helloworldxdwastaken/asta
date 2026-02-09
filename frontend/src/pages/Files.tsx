import { useState, useEffect } from "react";
import { api } from "../api/client";

type Entry = { name: string; path: string; dir: boolean; size?: number };

export default function Files() {
  const [roots, setRoots] = useState<string[]>([]);
  const [entries, setEntries] = useState<Entry[]>([]);
  const [currentRoot, setCurrentRoot] = useState<string>("");
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [content, setContent] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  const load = (dir?: string) => {
    setError(null);
    api
      .filesList(dir)
      .then((r) => {
        if (r.roots) setRoots(r.roots);
        if (r.root) setCurrentRoot(r.root);
        setEntries(r.entries || []);
      })
      .catch((e) => setError((e as Error).message));
  };

  useEffect(() => {
    load();
  }, []);

  const openDir = (path: string) => load(path);
  const openFile = (path: string) => {
    setSelectedFile(path);
    api.filesRead(path).then((r) => setContent(r.content)).catch((e) => setContent("Error: " + (e as Error).message));
  };

  return (
    <div>
      <h1 className="page-title">Files</h1>
      <p className="page-description">
        Browse allowed paths (set ASTA_ALLOWED_PATHS in .env). AI can use this context when you chat.
      </p>
      {error && <div className="card" style={{ color: "var(--accent)" }}>{error}</div>}
      {roots.length === 0 && !error && (
        <div className="card">
          <p>No allowed paths configured. Add ASTA_ALLOWED_PATHS (comma-separated dirs) and restart.</p>
        </div>
      )}
      {roots.length > 0 && (
        <>
          <div className="card">
            <strong>Roots:</strong>{" "}
            {roots.map((r) => (
              <button key={r} type="button" onClick={() => openDir(r)} className="link-btn">
                {r}
              </button>
            ))}
          </div>
          {currentRoot && (
            <div className="card">
              <p>
                <strong>Current:</strong> {currentRoot}
              </p>
              <ul className="file-list">
                {entries.map((e) => (
                  <li key={e.path}>
                    {e.dir ? (
                      <button type="button" onClick={() => openDir(e.path)} className="link-btn">
                        📁 {e.name}
                      </button>
                    ) : (
                      <button type="button" onClick={() => openFile(e.path)} className="link-btn">
                        📄 {e.name} {e.size != null && `(${Math.round(e.size / 1024)} KB)`}
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
      {selectedFile && (
        <div className="card">
          <h3>{selectedFile}</h3>
          <pre style={{ whiteSpace: "pre-wrap", maxHeight: 400, overflow: "auto" }}>{content}</pre>
        </div>
      )}
    </div>
  );
}
