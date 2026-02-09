import { useState, useEffect } from "react";
import { api } from "../api/client";

export default function Drive() {
  const [status, setStatus] = useState<{ connected: boolean; summary: string } | null>(null);
  const [list, setList] = useState<{ files: unknown[]; connected: boolean } | null>(null);

  useEffect(() => {
    api.driveStatus().then(setStatus);
    api.driveList().then(setList);
  }, []);

  return (
    <div>
      <h1 className="page-title">Google Drive</h1>
      <p className="page-description">
        Connect Drive to let the AI see your files. (OAuth flow can be added in Settings.)
      </p>
      <div className="card">
        <h2>Status</h2>
        {status && (
          <p className={status.connected ? "status-ok" : "status-pending"}>
            {status.connected ? "Connected" : "Not connected"} — {status.summary}
          </p>
        )}
      </div>
      {list && list.connected && (
        <div className="card">
          <h2>Recent files</h2>
          <pre>{JSON.stringify(list.files, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}
