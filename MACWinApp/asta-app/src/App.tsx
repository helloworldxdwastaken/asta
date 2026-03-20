import { useState, useEffect } from "react";
import SetupWizard from "./components/Setup/SetupWizard";
import LoginPage from "./components/Login/LoginPage";
import Sidebar from "./components/Sidebar/Sidebar";
import ChatView from "./components/Chat/ChatView";
import ProjectView from "./components/Projects/ProjectView";
import SettingsSheet from "./components/Settings/SettingsSheet";
import UpdateToast from "./components/UpdateToast";
import AgentsSheet from "./components/Agents/AgentsSheet";
import AutomationDashboard from "./components/Dashboard/AutomationDashboard";
import StudioView from "./components/Studio/StudioView";
import { getSetupDone } from "./lib/store";
import { checkHealth, listAgents, autoResolveBackend, getMe } from "./lib/api";
import { getJwt, getStoredUser, setAuth, clearAuth, User } from "./lib/auth";
import { getVersion } from "@tauri-apps/api/app";

interface Agent {
  id: string; name: string; description?: string; icon?: string;
  enabled: boolean; model_override?: string; category?: string;
}


export default function App() {
  const [setupDone, setSetupDone] = useState(getSetupDone());
  const [conversationId, setConversationId] = useState<string | undefined>();
  const [activeProjectId, setActiveProjectId] = useState<string | null>(null);
  const [showSettings, setShowSettings] = useState(false);
  const [showAgents, setShowAgents] = useState(false);
  const [activeView, setActiveView] = useState<"chat" | "automations" | "studio">("chat");
  const [agents, setAgents] = useState<Agent[]>([]);
  const [sidebarRefresh, setSidebarRefresh] = useState(0);
  const [chatKey, setChatKey] = useState(0);
  const [isOnline, setIsOnline] = useState(false);
  // Auth state: null = still checking, false = no multi-user (skip login), User = logged in
  const [user, setUser] = useState<User | false | null>(null);
  const [needsLogin, setNeedsLogin] = useState(false);

  // Check auth on mount
  useEffect(() => {
    (async () => {
      // Clear auth on app update so user must re-login
      try {
        const v = await getVersion();
        const prev = localStorage.getItem("asta_app_version");
        if (prev && prev !== v) clearAuth();
        localStorage.setItem("asta_app_version", v);
      } catch {}

      const ok = await autoResolveBackend().catch(() => false);
      setIsOnline(ok);
      // Try to validate existing JWT
      const jwt = getJwt();
      if (!ok) {
        // Backend unreachable: trust stored JWT if present, else show login
        if (jwt) {
          const stored = getStoredUser();
          setUser(stored || false);
        } else {
          setNeedsLogin(true);
        }
        return;
      }
      if (jwt) {
        try {
          const me = await getMe();
          const u: User = { id: me.id, username: me.username, role: me.role as "admin" | "user" };
          setAuth(jwt, u);
          setUser(u);
          return;
        } catch {
          clearAuth();
        }
      }
      // No JWT — check if backend is in multi-user mode by trying /api/auth/me
      // If 401 → needs login; if any other response → single-user mode
      try {
        await getMe();
        // Succeeded without JWT = single-user mode (no auth needed)
        setUser(false);
      } catch (err: any) {
        if (err?.message?.includes("401")) {
          setNeedsLogin(true);
        } else {
          // Backend unreachable or other error — assume single-user
          setUser(false);
        }
      }
    })();

    // Listen for auth expiry from api.ts
    const onExpired = () => { setUser(null); setNeedsLogin(true); };
    window.addEventListener("auth-expired", onExpired);
    return () => window.removeEventListener("auth-expired", onExpired);
  }, []);

  // Once authenticated (or single-user), load data
  useEffect(() => {
    if (user === null && !needsLogin) return; // still loading
    if (needsLogin) return; // waiting for login
    listAgents().then(r => setAgents(r.agents ?? [])).catch(() => {});

    const check = async () => {
      const ok = await checkHealth().catch(() => false);
      setIsOnline(ok);
    };
    const interval = setInterval(check, 15000);
    return () => { clearInterval(interval); };
  }, [user, needsLogin]);

  function handleLogin() {
    const u = getStoredUser();
    setUser(u || false);
    setNeedsLogin(false);
  }

  function handleLogout() {
    clearAuth();
    setUser(null);
    setNeedsLogin(true);
    setConversationId(undefined);
    setChatKey(k => k + 1);
  }

  function handleNewChat() { setConversationId(undefined); setActiveProjectId(null); setChatKey(k => k + 1); }
  function handleConversationCreated(id: string) {
    setConversationId(id);
    setSidebarRefresh(n => n + 1);
  }

  const userIsAdmin = user ? user.role === "admin" : true; // single-user = admin

  // Show login page if multi-user and not logged in
  if (needsLogin) {
    return <LoginPage onLogin={handleLogin} />;
  }

  // Still checking auth
  if (user === null) {
    return (
      <div className="flex items-center justify-center h-screen bg-surface grain">
        <div className="w-6 h-6 border-2 border-accent/40 border-t-accent rounded-full animate-spin" />
      </div>
    );
  }

  if (!setupDone && userIsAdmin) {
    return <SetupWizard onComplete={() => setSetupDone(true)} />;
  }

  return (
    <div className={`flex h-screen bg-surface text-label overflow-hidden select-none grain ${activeView === "studio" ? "studio-env" : ""}`}>
      {/* Sidebar — frosted glass (hidden in studio, which has its own nav) */}
      {activeView !== "studio" && (
        <div className="w-60 shrink-0 border-r border-separator relative glass-subtle">
          <Sidebar
            selectedId={conversationId}
            onSelect={(id) => { setConversationId(id); setActiveProjectId(null); }}
            onNewChat={handleNewChat}
            onOpenSettings={userIsAdmin ? () => setShowSettings(true) : undefined}
            onOpenDashboard={userIsAdmin ? () => setActiveView("automations") : undefined}
            onOpenAgents={userIsAdmin ? () => setShowAgents(true) : undefined}
            onSelectProject={(id) => { setActiveProjectId(id); setConversationId(undefined); }}
            isOnline={isOnline}
            refreshTrigger={sidebarRefresh}
            user={user || undefined}
            onLogout={user ? handleLogout : undefined}
          />
        </div>
      )}

      {/* Main content */}
      <div className="flex-1 min-w-0 relative flex flex-col">
        {/* Floating tab selector — overlays content, no banner */}
        {activeProjectId === null && (
          <div className="absolute top-2 left-1/2 -translate-x-1/2 z-20 pointer-events-none"
               style={{ WebkitAppRegion: "drag" } as React.CSSProperties}>
            <div className="flex bg-white/[.06] backdrop-blur-md rounded-lg p-0.5 shadow-lg pointer-events-auto"
                 style={{ WebkitAppRegion: "no-drag" } as React.CSSProperties}>
              {(["chat", ...(userIsAdmin ? ["automations", "studio"] as const : [])] as const).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveView(tab as any)}
                  className={`px-4 py-1 text-12 font-medium rounded-md transition-all ${
                    activeView === tab
                      ? "bg-white/[.10] text-label shadow-sm"
                      : "text-label-secondary hover:text-label"
                  }`}
                >
                  {tab === "chat" ? "Chat" : tab === "automations" ? "Automations" : "Studio"}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* View content */}
        {activeProjectId !== null ? (
          <ProjectView
            folderId={activeProjectId}
            onSelectChat={(id) => { setConversationId(id); setActiveProjectId(null); }}
            onBack={() => setActiveProjectId(null)}
          />
        ) : activeView === "studio" ? (
          <StudioView />
        ) : activeView === "automations" ? (
          <AutomationDashboard onClose={() => setActiveView("chat")} />
        ) : (
          <ChatView
            key={chatKey}
            conversationId={conversationId}
            onConversationCreated={handleConversationCreated}
            agents={agents}
            isAdmin={userIsAdmin}
          />
        )}
      </div>

      {showSettings && <SettingsSheet onClose={() => setShowSettings(false)} />}
      {showAgents && <AgentsSheet onClose={() => setShowAgents(false)} onAgentsChange={setAgents} />}
      <UpdateToast />
    </div>
  );
}
