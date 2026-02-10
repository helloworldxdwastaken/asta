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
        <nav className="nav">
          <div className="nav-left">
            <button
              type="button"
              className="nav-toggle"
              aria-label={navOpen ? "Close navigation menu" : "Open navigation menu"}
              aria-expanded={navOpen}
              onClick={() => setNavOpen((v) => !v)}
            >
              <span className="nav-toggle-bars" aria-hidden />
            </button>

            <Link to="/" className="brand" onClick={() => setNavOpen(false)}>
              Asta
            </Link>
          </div>

          <div className={"nav-links " + (navOpen ? "open" : "")}>
            <NavLink to="/" end onClick={() => setNavOpen(false)}>
              Dashboard
            </NavLink>
            <NavLink to="/chat" onClick={() => setNavOpen(false)}>
              Chat
            </NavLink>
            <NavLink to="/files" onClick={() => setNavOpen(false)}>
              Files
            </NavLink>
            <NavLink to="/drive" onClick={() => setNavOpen(false)}>
              Drive
            </NavLink>
            <NavLink to="/learning" onClick={() => setNavOpen(false)}>
              Learning
            </NavLink>
            <NavLink to="/audio-notes" onClick={() => setNavOpen(false)}>
              Audio notes
            </NavLink>
            <span className="nav-divider" aria-hidden />
            <NavLink to="/skills" onClick={() => setNavOpen(false)}>
              Skills
            </NavLink>
            <NavLink to="/settings" onClick={() => setNavOpen(false)}>
              Settings
            </NavLink>
          </div>

          <BackendIndicator />
        </nav>
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
