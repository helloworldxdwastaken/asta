import { useState, useEffect } from "react";
import { getPersona, setPersona } from "../../../lib/api";

export default function TabPersona() {
  const [active, setActive] = useState<"SOUL.md" | "USER.md">("SOUL.md");
  const [soul, setSoul] = useState(""); const [user, setUser] = useState("");
  const [saving, setSaving] = useState(false); const [saved, setSaved] = useState(false);

  useEffect(() => {
    getPersona().then(r => { setSoul(r.soul ?? r.SOUL ?? ""); setUser(r.user ?? r.USER ?? ""); }).catch(()=>{});
  }, []);

  async function save() {
    setSaving(true);
    await setPersona(active === "SOUL.md" ? { soul } : { user });
    setSaving(false); setSaved(true); setTimeout(() => setSaved(false), 2000);
  }

  return (
    <div className="text-label flex flex-col h-full space-y-4">
      <h2 className="text-16 font-semibold">Persona</h2>
      <div className="flex gap-1 bg-white/[.04] rounded-mac p-1 w-fit border border-separator">
        {(["SOUL.md", "USER.md"] as const).map(f => (
          <button key={f} onClick={() => setActive(f)}
            className={`px-4 py-1.5 rounded-[8px] text-13 font-medium transition-all duration-200 ${active === f ? "bg-white/[.1] text-label shadow-sm" : "text-label-tertiary hover:text-label-secondary"}`}>
            {f === "SOUL.md" ? "Soul" : "You"}
          </button>
        ))}
      </div>
      <p className="text-11 text-label-tertiary">
        {active === "SOUL.md" ? "Asta's personality, voice, and character." : "Facts about you — name, preferences, context."}
      </p>
      <textarea value={active === "SOUL.md" ? soul : user}
        onChange={e => active === "SOUL.md" ? setSoul(e.target.value) : setUser(e.target.value)}
        className="flex-1 min-h-[300px] bg-white/[.04] border border-separator hover:border-separator-bold rounded-mac px-4 py-3 text-13 font-mono text-label/90 placeholder-label-tertiary outline-none focus:border-accent/40 resize-none transition-colors"
        placeholder={`Edit ${active}…`} />
      <button onClick={save} disabled={saving}
        className="accent-gradient disabled:opacity-50 text-white text-13 rounded-mac px-6 py-2.5 w-fit shadow-glow-sm hover:shadow-glow transition-all duration-200 active:scale-[0.97]">
        {saved ? "Saved" : saving ? "Saving..." : "Save"}
      </button>
    </div>
  );
}
