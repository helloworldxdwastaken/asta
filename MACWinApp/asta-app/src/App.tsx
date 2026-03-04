import { useState, useEffect } from "react";
import SetupWizard from "./components/Setup/SetupWizard";
import Sidebar from "./components/Sidebar/Sidebar";
import ChatView from "./components/Chat/ChatView";
import SettingsSheet from "./components/Settings/SettingsSheet";
import UpdateToast from "./components/UpdateToast";
import AgentsSheet from "./components/Agents/AgentsSheet";
import { getSetupDone } from "./lib/store";
import { checkHealth, getDefaultAI, listAgents, autoResolveBackend } from "./lib/api";

interface Agent {
  id: string; name: string; description?: string; icon?: string;
  enabled: boolean; model_override?: string; category?: string;
}

const PROVIDER_NAMES: Record<string, string> = {
  claude: "Claude", google: "Gemini",
  openrouter: "OR", ollama: "Local",
};

export default function App() {
  const [setupDone, setSetupDone] = useState(getSetupDone());
  const [conversationId, setConversationId] = useState<string | undefined>();
  const [showSettings, setShowSettings] = useState(false);
  const [showAgents, setShowAgents] = useState(false);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [sidebarRefresh, setSidebarRefresh] = useState(0);
  const [chatKey, setChatKey] = useState(0);
  const [isOnline, setIsOnline] = useState(false);
  const [providerKey, setProviderKey] = useState("claude");

  // On mount: auto-resolve backend URL, then poll health + fetch data
  useEffect(() => {
    const fetchProvider = () => getDefaultAI().then(r => setProviderKey(r.provider ?? r.default_ai_provider ?? "claude")).catch(() => {});

    // Auto-resolve first, then start normal polling
    autoResolveBackend().then(ok => {
      setIsOnline(ok);
      if (ok) {
        fetchProvider();
        listAgents().then(r => setAgents(r.agents ?? [])).catch(() => {});
      }
    });

    const check = async () => {
      const ok = await checkHealth().catch(() => false);
      setIsOnline(ok);
    };
    const interval = setInterval(check, 15000);
    fetchProvider();
    listAgents().then(r => setAgents(r.agents ?? [])).catch(() => {});
    window.addEventListener("settings-changed", fetchProvider);
    return () => { clearInterval(interval); window.removeEventListener("settings-changed", fetchProvider); };
  }, []);

  function handleNewChat() { setConversationId(undefined); setChatKey(k => k + 1); }
  function handleConversationCreated(id: string) {
    setConversationId(id);
    setSidebarRefresh(n => n + 1);
  }

  const providerShortName = PROVIDER_NAMES[providerKey] ?? providerKey;
  const enabledAgentCount = agents.filter(a => a.enabled).length;

  if (!setupDone) {
    return <SetupWizard onComplete={() => setSetupDone(true)} />;
  }

  return (
    <div className="flex h-screen bg-surface text-label overflow-hidden select-none grain">
      {/* Sidebar — frosted glass */}
      <div className="w-60 shrink-0 border-r border-separator relative glass-subtle">
        <Sidebar
          selectedId={conversationId}
          onSelect={setConversationId}
          onNewChat={handleNewChat}
          onOpenSettings={() => setShowSettings(true)}
          onOpenAgents={() => setShowAgents(true)}
          enabledAgentCount={enabledAgentCount}
          providerShortName={providerShortName}
          isOnline={isOnline}
          refreshTrigger={sidebarRefresh}
        />
      </div>

      {/* Chat */}
      <div className="flex-1 min-w-0 relative">
        <ChatView
          key={chatKey}
          conversationId={conversationId}
          onConversationCreated={handleConversationCreated}
          agents={agents}
        />
      </div>

      {showSettings && <SettingsSheet onClose={() => setShowSettings(false)} />}
      {showAgents && <AgentsSheet onClose={() => setShowAgents(false)} onAgentsChange={setAgents} />}
      <UpdateToast />
    </div>
  );
}
