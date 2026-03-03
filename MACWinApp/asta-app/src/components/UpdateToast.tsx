import { useState, useEffect } from "react";
import { invoke } from "@tauri-apps/api/core";

const APP_VERSION = "0.1.0"; // Should match tauri.conf.json
const CHECK_INTERVAL = 60 * 60 * 1000; // 1 hour

interface UpdateInfo {
  has_update: boolean;
  latest_version: string;
  release_url: string;
  download_url?: string;
  release_notes?: string;
}

export default function UpdateToast() {
  const [update, setUpdate] = useState<UpdateInfo | null>(null);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    checkForUpdate();
    const interval = setInterval(checkForUpdate, CHECK_INTERVAL);
    return () => clearInterval(interval);
  }, []);

  async function checkForUpdate() {
    try {
      const result = await invoke<UpdateInfo>("check_app_update", {
        currentVersion: APP_VERSION,
      });
      if (result.has_update) {
        // Only show again if it's a new version (not the one we dismissed)
        const dismissedVersion = localStorage.getItem("dismissedAppUpdate");
        if (dismissedVersion !== result.latest_version) {
          setUpdate(result);
          setDismissed(false);
        }
      }
    } catch {
      // Silently fail — not critical
    }
  }

  function dismiss() {
    setDismissed(true);
    if (update) localStorage.setItem("dismissedAppUpdate", update.latest_version);
  }

  function openDownload() {
    const url = update?.download_url || update?.release_url;
    if (url) window.open(url, "_blank");
  }

  if (!update || dismissed) return null;

  return (
    <div className="fixed bottom-5 right-5 z-[9999] max-w-xs animate-slide-up">
      <div className="bg-surface-raised border border-separator rounded-2xl shadow-2xl p-4 space-y-2">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-xl bg-accent/15 flex items-center justify-center shrink-0">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-accent">
                <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
                <polyline points="7 10 12 15 17 10" />
                <line x1="12" y1="15" x2="12" y2="3" />
              </svg>
            </div>
            <div>
              <p className="text-13 font-semibold text-label">Update available</p>
              <p className="text-11 text-label-tertiary">v{update.latest_version}</p>
            </div>
          </div>
          <button onClick={dismiss} className="text-label-tertiary hover:text-label-secondary p-0.5 -mt-0.5 -mr-0.5">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>
        <button onClick={openDownload}
          className="w-full text-12 font-medium bg-accent hover:bg-accent-hover text-white py-2 rounded-xl transition-colors">
          Download update
        </button>
      </div>
    </div>
  );
}
