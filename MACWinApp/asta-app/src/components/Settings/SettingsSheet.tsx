import { useState } from "react";
import {
  IconSettings, IconPerson, IconCpu, IconKey, IconMusic, IconPuzzle,
  IconBrain, IconLink, IconClock, IconGlobe, IconAntenna, IconHand, IconInfo, IconClose,
} from "../../lib/icons";
import TabGeneral from "./tabs/TabGeneral";
import TabPersona from "./tabs/TabPersona";
import TabModels from "./tabs/TabModels";
import TabKeys from "./tabs/TabKeys";
import TabSpotify from "./tabs/TabSpotify";
import TabSkills from "./tabs/TabSkills";
import TabKnowledge from "./tabs/TabKnowledge";
import TabChannels from "./tabs/TabChannels";
import TabCron from "./tabs/TabCron";
import TabGoogle from "./tabs/TabGoogle";
import TabNetwork from "./tabs/TabNetwork";
import TabPermissions from "./tabs/TabPermissions";
import TabAbout from "./tabs/TabAbout";

interface Props { onClose: () => void; }

const TABS = [
  { id: "general",     label: "General",     Icon: IconSettings },
  { id: "persona",     label: "Persona",     Icon: IconPerson },
  { id: "models",      label: "Models",      Icon: IconCpu },
  { id: "keys",        label: "API Keys",    Icon: IconKey },
  { id: "spotify",     label: "Spotify",     Icon: IconMusic },
  { id: "skills",      label: "Skills",      Icon: IconPuzzle },
  { id: "knowledge",   label: "Knowledge",   Icon: IconBrain },
  { id: "channels",    label: "Channels",    Icon: IconLink },
  { id: "cron",        label: "Schedule",    Icon: IconClock },
  { id: "google",      label: "Google",      Icon: IconGlobe },
  { id: "network",     label: "Connection",  Icon: IconAntenna },
  { id: "permissions", label: "Permissions", Icon: IconHand },
  { id: "about",       label: "About",       Icon: IconInfo },
] as const;
type TabId = (typeof TABS)[number]["id"];

export default function SettingsSheet({ onClose }: Props) {
  const [tab, setTab] = useState<TabId>("general");

  function renderTab() {
    switch (tab) {
      case "general":     return <TabGeneral />;
      case "persona":     return <TabPersona />;
      case "models":      return <TabModels />;
      case "keys":        return <TabKeys />;
      case "spotify":     return <TabSpotify />;
      case "skills":      return <TabSkills />;
      case "knowledge":   return <TabKnowledge />;
      case "channels":    return <TabChannels />;
      case "cron":        return <TabCron />;
      case "google":      return <TabGoogle />;
      case "network":     return <TabNetwork />;
      case "permissions": return <TabPermissions />;
      case "about":       return <TabAbout />;
    }
  }

  return (
    <div className="absolute inset-0 bg-black/60 flex items-center justify-center z-40 animate-fade-in" onClick={onClose}>
      <div className="bg-surface-raised rounded-mac shadow-modal flex overflow-hidden animate-scale-in border border-separator" style={{ width: 780, height: 580 }} onClick={e => e.stopPropagation()}>
        {/* Tab sidebar */}
        <div className="w-44 bg-surface border-r border-separator flex flex-col py-3">
          <div className="flex items-center justify-between px-4 mb-3">
            <span className="text-14 font-semibold text-label">Settings</span>
            <button onClick={onClose} className="text-label-tertiary hover:text-label-secondary p-1 rounded-mac hover:bg-white/[.06] transition-colors"><IconClose size={14} /></button>
          </div>
          <div className="flex-1 overflow-y-auto space-y-0.5 px-2 scrollbar-thin">
            {TABS.map(t => (
              <button key={t.id} onClick={() => setTab(t.id)}
                className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-mac text-left text-13 transition-all duration-150 ${
                  tab === t.id ? "bg-accent/[.12] text-accent font-medium" : "text-label-secondary hover:bg-white/[.04]"
                }`}>
                <t.Icon size={14} />
                <span className="truncate">{t.label}</span>
              </button>
            ))}
          </div>
        </div>
        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 scrollbar-thin">{renderTab()}</div>
      </div>
    </div>
  );
}
