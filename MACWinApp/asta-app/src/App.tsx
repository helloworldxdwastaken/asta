import { useState, useEffect } from "react";
import SetupWizard from "./components/Setup/SetupWizard";
import Sidebar from "./components/Sidebar/Sidebar";
import ChatView from "./components/Chat/ChatView";
import SettingsSheet from "./components/Settings/SettingsSheet";
import UpdateToast from "./components/UpdateToast";
import AgentsSheet from "./components/Agents/AgentsSheet";
import { getSetupDone } from "./lib/store";
import { checkHealth, getDefaultAI } from "./lib/api";

interface Agent {
  id: string; name: string; description?: string; icon?: string;
  enabled: boolean; model_override?: string; category?: string;
}

const PROVIDER_NAMES: Record<string, string> = {
  anthropic: "Claude", openai: "GPT", google: "Gemini",
  groq: "Groq", openrouter: "OR", ollama: "Local",
};

export default function App() {
  const [setupDone, setSetupDone] = useState(getSetupDone());
  const [conversationId, setConversationId] = useState<string | undefined>();
  const [showSettings, setShowSettings] = useState(false);
  const [showAgents, setShowAgents] = useState(false);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [sidebarRefresh, setSidebarRefresh] = useState(0);
  const [isOnline, setIsOnline] = useState(false);
  const [providerKey, setProviderKey] = useState("anthropic");

  // Poll health + fetch provider
  useEffect(() => {
    const check = async () => {
      const ok = await checkHealth().catch(() => false);
      setIsOnline(ok);
    };
    check();
    const interval = setInterval(check, 15000);
    getDefaultAI().then(r => setProviderKey(r.provider ?? r.default_ai_provider ?? "anthropic")).catch(() => {});
    return () => clearInterval(interval);
  }, []);

  function handleNewChat() { setConversationId(undefined); }
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
