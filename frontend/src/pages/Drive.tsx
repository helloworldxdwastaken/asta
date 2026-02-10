import { useState, useEffect } from "react";
import { api } from "../api/client";

export default function Drive() {
  const [status, setStatus] = useState<{ connected: boolean; summary: string } | null>(null);
  const [list, setList] = useState<{ files: unknown[]; connected: boolean } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setError(null);
    api.driveStatus().then(setStatus).catch((e) => setError((e as Error).message));
    api.driveList().then(setList).catch(() => setList(null));
  }, []);

  return (
    <div>
      <h1 className="page-title">Google Drive</h1>
      <p className="page-description">
        Connect Drive to let the AI see your files. (OAuth flow can be added in Settings.)
      </p>
      {error && <div className="alert alert-error">{error}</div>}

      <div className="card">
        <div className="card-header">
          <h2>Status</h2>
        </div>
        {status ? (
          <div className={status.connected ? "alert alert-success" : "alert"}>
            <strong>{status.connected ? "Connected" : "Not connected"}</strong>
            {status.summary ? <span className="muted"> — {status.summary}</span> : null}
          </div>
        ) : (
          <p className="muted">Loading…</p>
        )}
        {!status?.connected && (
          <p className="help" style={{ marginTop: "0.75rem" }}>
            Drive is currently a stub in this repo. Once OAuth is implemented, this page can list and search your Drive files.
          </p>
        )}
      </div>

      {list?.connected && (
        <div className="card">
          <div className="card-header">
            <h2>Recent files (debug)</h2>
          </div>
          <pre className="file-preview" style={{ maxHeight: 320 }}>
            {JSON.stringify(list.files, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
