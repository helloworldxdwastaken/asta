import { useState, useEffect, useCallback } from "react";
import { BrowserRouter, Routes, Route, Link, NavLink } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import Chat from "./pages/Chat";
import Files from "./pages/Files";
import Drive from "./pages/Drive";
import Learning from "./pages/Learning";
import AudioNotes from "./pages/AudioNotes";
import Skills from "./pages/Skills";
import Settings from "./pages/Settings";
import { api } from "./api/client";
import "./index.css";

const ICONS = {
  dashboard: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="7" height="9" rx="1" />
      <rect x="14" y="3" width="7" height="5" rx="1" />
      <rect x="14" y="12" width="7" height="9" rx="1" />
      <rect x="3" y="16" width="7" height="5" rx="1" />
    </svg>
  ),
  chat: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>
  ),
  files: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
    </svg>
  ),
  drive: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
      <line x1="12" y1="11" x2="12" y2="17" />
    </svg>
  ),
  learning: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
      <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
    </svg>
  ),
  audio: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
      <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
      <line x1="12" y1="19" x2="12" y2="23" />
      <line x1="8" y1="23" x2="16" y2="23" />
    </svg>
  ),
  skills: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 2L2 7l10 5 10-5-10-5z" />
      <path d="M2 17l10 5 10-5" />
    </svg>
  ),
  settings: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  ),
};

function BackendIndicator() {
  const [connected, setConnected] = useState<boolean | null>(null);
  const check = useCallback(() => {
    api.health().then(() => setConnected(true)).catch(() => setConnected(false));
  }, []);
  useEffect(() => {
    check();
    const t = setInterval(check, 8000);
    return () => clearInterval(t);
  }, [check]);
  if (connected === null) return <span className="nav-api-status loading" title="Checking…">●</span>;
  return (
    <span
      className={"nav-api-status " + (connected ? "ok" : "off")}
      title={
        connected
          ? "Backend connected"
          : "Backend not reachable. Open this app at http://localhost:5173 and run ./asta.sh start (backend on port 8010)."
      }
    >
      ● {connected ? "API" : "API off"}
    </span>
  );
}

export default function App() {
  const [navOpen, setNavOpen] = useState(false);

  return (
    <BrowserRouter>
      <div className="app">
        <aside className={"sidebar " + (navOpen ? "open" : "")}>
          <div className="sidebar-header">
            <div className="sidebar-brand-row">
              <Link to="/" className="brand" onClick={() => setNavOpen(false)}>
                <span className="brand-icon">{ICONS.dashboard}</span>
                <span className="brand-text">Asta</span>
              </Link>
              <BackendIndicator />
            </div>
            <button
              type="button"
              className="sidebar-toggle"
              aria-label={navOpen ? "Close menu" : "Open menu"}
              aria-expanded={navOpen}
              onClick={() => setNavOpen((v) => !v)}
            >
              <span className="sidebar-toggle-bars" aria-hidden />
            </button>
          </div>
          <nav className="sidebar-nav">
            <NavLink to="/" end onClick={() => setNavOpen(false)}>
              <span className="nav-icon">{ICONS.dashboard}</span>
              <span className="nav-label">Dashboard</span>
            </NavLink>
            <NavLink to="/chat" onClick={() => setNavOpen(false)}>
              <span className="nav-icon">{ICONS.chat}</span>
              <span className="nav-label">Chat</span>
            </NavLink>
            <NavLink to="/files" onClick={() => setNavOpen(false)}>
              <span className="nav-icon">{ICONS.files}</span>
              <span className="nav-label">Files</span>
            </NavLink>
            <NavLink to="/drive" onClick={() => setNavOpen(false)}>
              <span className="nav-icon">{ICONS.drive}</span>
              <span className="nav-label">Drive</span>
            </NavLink>
            <NavLink to="/learning" onClick={() => setNavOpen(false)}>
              <span className="nav-icon">{ICONS.learning}</span>
              <span className="nav-label">Learning</span>
            </NavLink>
            <NavLink to="/audio-notes" onClick={() => setNavOpen(false)}>
              <span className="nav-icon">{ICONS.audio}</span>
              <span className="nav-label">Audio notes</span>
            </NavLink>
            <span className="nav-divider" aria-hidden />
            <NavLink to="/skills" onClick={() => setNavOpen(false)}>
              <span className="nav-icon">{ICONS.skills}</span>
              <span className="nav-label">Skills</span>
            </NavLink>
            <NavLink to="/settings" onClick={() => setNavOpen(false)}>
              <span className="nav-icon">{ICONS.settings}</span>
              <span className="nav-label">Settings</span>
            </NavLink>
          </nav>
        </aside>
        <main className="main">
          <div className="main-inner">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/chat" element={<Chat />} />
            <Route path="/files" element={<Files />} />
            <Route path="/drive" element={<Drive />} />
            <Route path="/learning" element={<Learning />} />
            <Route path="/audio-notes" element={<AudioNotes />} />
            <Route path="/skills" element={<Skills />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
          </div>
        </main>
      </div>
    </BrowserRouter>
  );
}
