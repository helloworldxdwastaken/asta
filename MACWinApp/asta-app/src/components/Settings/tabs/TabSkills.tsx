import { useState, useEffect, useRef } from "react";
import { getSkills, toggleSkill, uploadSkill } from "../../../lib/api";
import { IconPuzzle } from "../../../lib/icons";
import { Toggle } from "./TabGeneral";

interface Skill { id: string; name: string; description?: string; enabled: boolean; path?: string; }

/* Map skill id → icon file in /skills/ folder, or fallback to /providers/ for known brands */
const SKILL_ICON_MAP: Record<string, { src: string; bg?: string }> = {
  "after-effects-assistant": { src: "/skills/after-effects.svg", bg: "#00005b" },
  "apple-notes":    { src: "/skills/apple-notes.svg", bg: "#f5c518" },
  "competitor":     { src: "/skills/competitor.svg", bg: "#e74c3c" },
  "docx":           { src: "/skills/docx.svg", bg: "#2b579a" },
  "esimo-copywriter": { src: "/skills/esimo-copywriter.svg", bg: "#8e44ad" },
  "index-crawl":    { src: "/skills/index-crawl.svg", bg: "#27ae60" },
  "index-manager":  { src: "/skills/index-manager.svg", bg: "#2980b9" },
  "index-status":   { src: "/skills/index-status.svg", bg: "#16a085" },
  "index-submit":   { src: "/skills/index-submit.svg", bg: "#e67e22" },
  "knowledge-curator": { src: "/skills/knowledge-curator.svg", bg: "#9b59b6" },
  "librarian":      { src: "/skills/librarian.svg", bg: "#8d6e63" },
  "math":           { src: "/skills/math.svg", bg: "#3498db" },
  "notes":          { src: "/skills/notes.svg", bg: "#f39c12" },
  "notion":         { src: "/providers/Notion-logo.svg", bg: "#000" },
  "notion-operator": { src: "/providers/Notion-logo.svg", bg: "#1a1a2e" },
  "pdf":            { src: "/skills/pdf.svg", bg: "#c0392b" },
  "pptx":           { src: "/skills/pptx.svg", bg: "#d04423" },
  "seo-strategist": { src: "/skills/seo-strategist.svg", bg: "#2ecc71" },
  "skill-creator":  { src: "/skills/skill-creator.svg", bg: "#7f8c8d" },
  "things-mac":     { src: "/skills/things-mac.svg", bg: "#4a90d9" },
  "xlsx":           { src: "/skills/xlsx.svg", bg: "#217346" },
  "youtube-creator": { src: "/providers/youtube.svg", bg: "#c4302b" },
  "youtube-edit":   { src: "/skills/youtube-edit.svg", bg: "#c4302b" },
  "youtube-script": { src: "/skills/youtube-script.svg", bg: "#c4302b" },
  "youtube-source": { src: "/skills/youtube-source.svg", bg: "#c4302b" },
  "youtube-trends": { src: "/skills/youtube-trends.svg", bg: "#c4302b" },
  "youtube-upload": { src: "/skills/youtube-upload.svg", bg: "#c4302b" },
};

function hashColor(name: string): string {
  let h = 0;
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) | 0;
  return `hsl(${Math.abs(h) % 360}, 45%, 40%)`;
}

function SkillIcon({ id, size = 32 }: { id: string; size?: number }) {
  const icon = SKILL_ICON_MAP[id];
  if (icon) {
    return (
      <div className="flex items-center justify-center rounded-lg shrink-0"
        style={{ width: size, height: size, backgroundColor: icon.bg || "#333" }}>
        <img src={icon.src} alt="" width={size * 0.6} height={size * 0.6}
          className="object-contain" draggable={false} />
      </div>
    );
  }
  const letter = id.charAt(0).toUpperCase();
  return (
    <div className="flex items-center justify-center rounded-lg shrink-0 text-white font-bold"
      style={{ width: size, height: size, backgroundColor: hashColor(id), fontSize: size * 0.4 }}>
      {letter}
    </div>
  );
}

export default function TabSkills() {
  const [skills, setSkills] = useState<Skill[]>([]);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const load = () => getSkills().then(r => setSkills(r.skills ?? [])).catch(() => {});
    load();
    const interval = setInterval(load, 5000);
    return () => clearInterval(interval);
  }, []);

  async function toggle(id: string) {
    const skill = skills.find(s => s.id === id);
    if (!skill) return;
    const newEnabled = !skill.enabled;
    await toggleSkill(id, newEnabled);
    setSkills(prev => prev.map(s => s.id === id ? { ...s, enabled: newEnabled } : s));
  }

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    await uploadSkill(file);
    getSkills().then(r => setSkills(r.skills ?? []));
  }

  return (
    <div className="text-label space-y-5">
      <div className="flex items-center justify-between">
        <h2 className="text-16 font-semibold">Skills</h2>
        <button onClick={() => fileRef.current?.click()}
          className="text-12 accent-gradient text-white px-4 py-2 rounded-mac flex items-center gap-1.5 shadow-glow-sm hover:shadow-glow transition-all duration-200 active:scale-[0.97]">
          <IconPuzzle size={12} /> Upload
        </button>
        <input ref={fileRef} type="file" accept=".zip" onChange={handleUpload} className="hidden" />
      </div>
      <div className="grid grid-cols-2 gap-2.5">
        {skills.map(s => (
          <div key={s.id}
            className={`flex items-center gap-3 bg-white/[.03] border rounded-xl px-3.5 py-3 hover:bg-white/[.05] transition-all duration-150 ${
              s.enabled ? "border-accent/20" : "border-separator"
            }`}>
            <SkillIcon id={s.id} size={34} />
            <div className="min-w-0 flex-1">
              <p className="text-12 font-medium truncate leading-tight">{s.name}</p>
              {s.description && (
                <p className="text-[10px] text-label-tertiary truncate mt-0.5 leading-tight">{s.description}</p>
              )}
            </div>
            <div className="shrink-0">
              <Toggle checked={s.enabled} onChange={() => toggle(s.id)} />
            </div>
          </div>
        ))}
        {skills.length === 0 && (
          <p className="text-label-tertiary text-13 col-span-2">No skills found</p>
        )}
      </div>
    </div>
  );
}
