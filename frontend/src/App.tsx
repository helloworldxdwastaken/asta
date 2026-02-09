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
      title={connected ? "Backend connected" : "Backend disconnected — start it in your terminal"}
    >
      ● {connected ? "API" : "API off"}
    </span>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="app">
        <nav className="nav">
          <Link to="/" className="brand">
            Asta
          </Link>
          <NavLink to="/" end>Dashboard</NavLink>
          <NavLink to="/chat">Chat</NavLink>
          <NavLink to="/files">Files</NavLink>
          <NavLink to="/drive">Drive</NavLink>
          <NavLink to="/learning">Learning</NavLink>
          <NavLink to="/audio-notes">Audio notes</NavLink>
          <NavLink to="/skills">Skills</NavLink>
          <NavLink to="/settings">Settings</NavLink>
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
