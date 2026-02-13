import { useEffect, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import type { Skill } from "../api/client";
import { api } from "../api/client";

function SkillCard({
  skill,
  toggling,
  onToggle,
}: {
  skill: Skill;
  toggling: string | null;
  onToggle: (id: string, enabled: boolean) => void;
}) {
  const needsAction = !skill.available && skill.action_hint;
  return (
    <div className="skill-card">
      <div className="skill-card-header">
        <span className="skill-card-name">{skill.name}</span>
        <label className="toggle-wrap">
          <input
            type="checkbox"
            checked={skill.enabled}
            disabled={toggling === skill.id}
            onChange={(e) => onToggle(skill.id, e.target.checked)}
          />
          <span className="toggle-slider" />
        </label>
      </div>
      <p className="skill-card-desc">{skill.description}</p>
      <div className="skill-card-footer">
        {skill.available ? (
          <span className="skill-pill skill-pill-ready">Ready</span>
        ) : needsAction ? (
          <Link to="/settings" className="skill-pill skill-pill-action">
            {skill.action_hint}
          </Link>
        ) : (
          <span className="skill-pill skill-pill-pending">Not configured</span>
        )}
      </div>
    </div>
  );
}

export default function Skills() {
  const [skills, setSkills] = useState<Skill[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toggling, setToggling] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

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

  const handleZip = useCallback(
    (file: File) => {
      if (!file.name.toLowerCase().endsWith(".zip")) {
        setUploadError("Please drop a .zip file.");
        return;
      }
      setUploadError(null);
      setUploading(true);
      api
        .skillsUploadZip(file)
        .then(() => {
          load();
        })
        .catch((e) => setUploadError((e as Error).message))
        .finally(() => setUploading(false));
    },
    []
  );

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const f = e.dataTransfer.files[0];
      if (f) handleZip(f);
    },
    [handleZip]
  );

  return (
    <div className="skills-page">
      <h1 className="page-title">Skills</h1>
      <p className="page-description">
        Turn skills on or off. When a skill is off, Asta will not use it. Some skills need to be connected or configured in Settings.
      </p>

      <div
        className="card skills-upload-zone"
        style={{
          border: dragOver ? "2px dashed var(--accent)" : "2px dashed var(--border)",
          background: dragOver ? "var(--accent-soft)" : undefined,
        }}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
      >
        <div className="field">
          <div className="label">Add skill from zip (OpenClaw-style)</div>
          <p className="help" style={{ marginTop: "0.25rem" }}>
            Drag and drop a .zip here, or choose a file. The zip must contain <code>SKILL.md</code> at the root or inside a single top-level folder.
          </p>
          <input
            type="file"
            accept=".zip"
            disabled={uploading}
            style={{ marginTop: "0.5rem" }}
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) handleZip(f);
              e.target.value = "";
            }}
          />
          {uploading && <p className="muted" style={{ marginTop: "0.5rem" }}>Uploading…</p>}
          {uploadError && <p className="status-pending" style={{ marginTop: "0.5rem" }}>{uploadError}</p>}
        </div>
      </div>

      {error && (
        <div className="card">
          <p className="status-pending">{error}</p>
        </div>
      )}

      {loading && <p className="muted">Loading…</p>}

      {!loading && skills.length > 0 && (
        <div className="skills-grid">
          {skills.map((s) => (
            <SkillCard key={s.id} skill={s} toggling={toggling} onToggle={toggle} />
          ))}
        </div>
      )}
    </div>
  );
}
