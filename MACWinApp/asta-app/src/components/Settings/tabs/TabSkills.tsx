import { useState, useEffect, useRef } from "react";
import { getSkills, toggleSkill, uploadSkill } from "../../../lib/api";
import { IconPuzzle } from "../../../lib/icons";
import { Toggle } from "./TabGeneral";

interface Skill { id: string; name: string; description?: string; enabled: boolean; path?: string; }

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
    setSkills(prev => prev.map(s => s.id === id ? {...s, enabled: newEnabled} : s));
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
      <div className="space-y-2">
        {skills.map(s => (
          <div key={s.id} className="flex items-center justify-between bg-white/[.03] border border-separator rounded-mac px-4 py-3 hover:bg-white/[.05] transition-colors">
            <div className="min-w-0">
              <p className="text-13 font-medium truncate">{s.name}</p>
              {s.description && <p className="text-11 text-label-tertiary truncate mt-0.5">{s.description}</p>}
            </div>
            <div className="shrink-0 ml-3">
              <Toggle checked={s.enabled} onChange={() => toggle(s.id)} />
            </div>
          </div>
        ))}
        {skills.length === 0 && <p className="text-label-tertiary text-13">No skills found</p>}
      </div>
    </div>
  );
}
