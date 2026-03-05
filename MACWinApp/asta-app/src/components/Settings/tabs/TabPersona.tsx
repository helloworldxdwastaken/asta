import { useState, useEffect } from "react";
import { getPersona, setPersona } from "../../../lib/api";

interface MemoryFields {
  name: string;
  location: string;
  about: string;
  preferences: string;
  notes: string;
}

const FIELD_LABELS: { key: keyof MemoryFields; label: string; placeholder: string; multiline?: boolean }[] = [
  { key: "name", label: "Name", placeholder: "Your name" },
  { key: "location", label: "Location", placeholder: "City, Country" },
  { key: "about", label: "About me", placeholder: "Occupation, interests, what you do...", multiline: true },
  { key: "preferences", label: "Preferences", placeholder: "Communication style, topics, how you want Asta to respond...", multiline: true },
  { key: "notes", label: "Notes", placeholder: "Anything else Asta should remember...", multiline: true },
];

function parseMemoryFields(md: string): MemoryFields {
  const fields: MemoryFields = { name: "", location: "", about: "", preferences: "", notes: "" };
  if (!md.trim()) return fields;
  let currentKey: keyof MemoryFields | null = null;
  const lines = md.split("\n");
  for (const line of lines) {
    const headerMatch = line.match(/^##\s+(.+)$/);
    if (headerMatch) {
      const label = headerMatch[1].trim().toLowerCase();
      const found = FIELD_LABELS.find(f => f.label.toLowerCase() === label);
      currentKey = found ? found.key : null;
      continue;
    }
    // Also parse "**Label:** value" format (legacy)
    const boldMatch = line.match(/^\*\*(.+?)\*\*:\s*(.*)$/);
    if (boldMatch) {
      const label = boldMatch[1].trim().toLowerCase();
      const found = FIELD_LABELS.find(f => f.label.toLowerCase() === label);
      if (found) {
        fields[found.key] = boldMatch[2].trim();
        currentKey = null;
        continue;
      }
    }
    if (currentKey && line.trim()) {
      fields[currentKey] = fields[currentKey] ? fields[currentKey] + "\n" + line : line;
    }
  }
  // Trim all
  for (const k of Object.keys(fields) as (keyof MemoryFields)[]) {
    fields[k] = fields[k].trim();
  }
  return fields;
}

function fieldsToMarkdown(fields: MemoryFields): string {
  const lines: string[] = [];
  for (const { key, label } of FIELD_LABELS) {
    const val = fields[key].trim();
    if (val) {
      lines.push(`## ${label}`);
      lines.push(val);
      lines.push("");
    }
  }
  return lines.join("\n");
}

export default function TabPersona({ isAdmin = true }: { isAdmin?: boolean }) {
  const [active, setActive] = useState<"SOUL.md" | "USER.md">(isAdmin ? "SOUL.md" : "USER.md");
  const [soul, setSoul] = useState("");
  const [fields, setFields] = useState<MemoryFields>({ name: "", location: "", about: "", preferences: "", notes: "" });
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    getPersona().then(r => {
      setSoul(r.soul ?? r.SOUL ?? "");
      const raw = r.user ?? r.USER ?? "";
      setFields(parseMemoryFields(raw));
    }).catch(() => {});
  }, []);

  async function save() {
    setSaving(true);
    if (active === "SOUL.md") {
      await setPersona({ soul });
    } else {
      await setPersona({ user: fieldsToMarkdown(fields) });
    }
    setSaving(false);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  function updateField(key: keyof MemoryFields, value: string) {
    setFields(prev => ({ ...prev, [key]: value }));
  }

  const inputClass = "w-full bg-white/[.04] border border-separator hover:border-separator-bold rounded-mac px-3.5 py-2.5 text-13 text-label outline-none focus:border-accent/40 transition-colors placeholder:text-label-tertiary";

  return (
    <div className="text-label flex flex-col h-full space-y-4">
      <h2 className="text-16 font-semibold">{isAdmin ? "Persona" : "Memories"}</h2>

      {isAdmin && (
        <div className="flex gap-1 bg-white/[.04] rounded-mac p-1 w-fit border border-separator">
          {(["SOUL.md", "USER.md"] as const).map(f => (
            <button key={f} onClick={() => setActive(f)}
              className={`px-4 py-1.5 rounded-[8px] text-13 font-medium transition-all duration-200 ${active === f ? "bg-white/[.1] text-label shadow-sm" : "text-label-tertiary hover:text-label-secondary"}`}>
              {f === "SOUL.md" ? "Soul" : "Memories"}
            </button>
          ))}
        </div>
      )}

      <p className="text-11 text-label-tertiary">
        {active === "SOUL.md"
          ? "Asta's personality, voice, and character."
          : "Info about you — Asta uses this to personalize responses."}
      </p>

      {active === "SOUL.md" ? (
        <textarea
          value={soul}
          onChange={e => setSoul(e.target.value)}
          className="flex-1 min-h-[300px] bg-white/[.04] border border-separator hover:border-separator-bold rounded-mac px-4 py-3 text-13 font-mono text-label/90 placeholder-label-tertiary outline-none focus:border-accent/40 resize-none transition-colors"
          placeholder="Edit SOUL.md…"
        />
      ) : (
        <div className="flex-1 overflow-y-auto space-y-4 scrollbar-thin pr-1">
          {FIELD_LABELS.map(({ key, label, placeholder, multiline }) => (
            <div key={key}>
              <label className="text-11 font-semibold text-label-tertiary uppercase tracking-widest mb-1.5 block">
                {label}
              </label>
              {multiline ? (
                <textarea
                  value={fields[key]}
                  onChange={e => updateField(key, e.target.value)}
                  placeholder={placeholder}
                  rows={3}
                  className={inputClass + " resize-none"}
                />
              ) : (
                <input
                  type="text"
                  value={fields[key]}
                  onChange={e => updateField(key, e.target.value)}
                  placeholder={placeholder}
                  className={inputClass}
                />
              )}
            </div>
          ))}
        </div>
      )}

      <button onClick={save} disabled={saving}
        className="accent-gradient disabled:opacity-50 text-white text-13 rounded-mac px-6 py-2.5 w-fit shadow-glow-sm hover:shadow-glow transition-all duration-200 active:scale-[0.97]">
        {saved ? "Saved" : saving ? "Saving..." : "Save"}
      </button>
    </div>
  );
}
