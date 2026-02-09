import { useEffect, useState } from "react";
import type { Skill } from "../api/client";
import { api } from "../api/client";

export default function Skills() {
  const [skills, setSkills] = useState<Skill[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toggling, setToggling] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    setError(null);
    api
      .getSkills()
      .then((r) => setSkills(r.skills))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, []);

  const toggle = (skillId: string, enabled: boolean) => {
    setToggling(skillId);
    api
      .setSkillToggle(skillId, enabled)
      .then(() => load())
      .catch((e) => setError(e.message))
      .finally(() => setToggling(null));
  };

  return (
    <div>
      <h1 className="page-title">Skills</h1>
      <p className="page-description">
        Turn skills on or off to control what the AI can use. When a skill is off, Asta will not use it (e.g. no file or Drive context).
      </p>

      {error && (
        <div className="card">
          <p className="status-pending">{error}</p>
        </div>
      )}

      {loading && <p className="muted">Loading…</p>}

      {!loading && skills.length > 0 && (
        <div className="card">
          <ul className="skills-list">
            {skills.map((s) => (
              <li key={s.id} className="skill-row">
                <div className="skill-info">
                  <span className="skill-name">{s.name}</span>
                  <span className="muted skill-desc">{s.description}</span>
                  {!s.available && (
                    <span className="status-pending" style={{ fontSize: "0.85rem" }}>
                      Not configured (e.g. set allowed paths or connect Drive in Settings)
                    </span>
                  )}
                </div>
                <label className="toggle-wrap">
                  <input
                    type="checkbox"
                    checked={s.enabled}
                    disabled={toggling === s.id}
                    onChange={(e) => toggle(s.id, e.target.checked)}
                  />
                  <span className="toggle-slider" />
                </label>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
