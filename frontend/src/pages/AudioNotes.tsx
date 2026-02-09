import { useState, useRef } from "react";
import { api } from "../api/client";

const PRESET_CUSTOM = "__custom__";
const PRESETS = [
  { label: "Meeting notes (bullet points, action items)", value: "Format this as meeting notes with bullet points, action items, and key decisions." },
  { label: "Conversation between 2 people", value: "Extract and summarize the conversation between the speakers. Use clear sections or dialogue format." },
  { label: "Action items only", value: "Extract only action items and who they’re for (if clear). Use a short bullet list." },
  { label: "Free-form (type below)", value: PRESET_CUSTOM },
];

const WHISPER_OPTIONS = [
  { label: "Fast (base) — quick, good for most", value: "base" },
  { label: "Balanced (small) — more accurate", value: "small" },
  { label: "Best (medium) — most accurate, slower", value: "medium" },
];

export default function AudioNotes() {
  const [file, setFile] = useState<File | null>(null);
  const [presetValue, setPresetValue] = useState(PRESETS[0].value);
  const [customInstruction, setCustomInstruction] = useState("");
  const [whisperModel, setWhisperModel] = useState("base");
  const [loading, setLoading] = useState(false);
  const [progressStage, setProgressStage] = useState<"transcribing" | "formatting" | null>(null);
  const [result, setResult] = useState<{ transcript: string; formatted: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const effectiveInstruction =
    (presetValue === PRESET_CUSTOM ? customInstruction : presetValue).trim() || PRESETS[0].value;

  const submit = async () => {
    if (!file || loading) return;
    setError(null);
    setResult(null);
    setProgressStage(null);
    setLoading(true);
    try {
      const r = await api.processAudio(file, effectiveInstruction, "default", whisperModel);
      if ("job_id" in r && r.job_id) {
        const jobId = r.job_id;
        setProgressStage("transcribing");
        const poll = async () => {
          const status = await api.audioStatus(jobId);
          setProgressStage(status.stage === "formatting" ? "formatting" : "transcribing");
          if (status.stage === "done" && status.transcript !== undefined && status.formatted !== undefined) {
            setResult({ transcript: status.transcript, formatted: status.formatted });
            setLoading(false);
            setProgressStage(null);
            return;
          }
          if (status.stage === "error") {
            setError(status.error ?? "Unknown error");
            setLoading(false);
            setProgressStage(null);
            return;
          }
          setTimeout(poll, 1500);
        };
        poll();
        return;
      }
      if ("transcript" in r && "formatted" in r) {
        setResult({ transcript: r.transcript, formatted: r.formatted });
      }
      setLoading(false);
    } catch (e) {
      setError((e as Error).message);
      setLoading(false);
    }
  };

  return (
    <div>
      <h1 className="page-title">Audio → Notes</h1>
      <p className="page-description">
        Upload a meeting, call, or voice memo. Asta transcribes it (free, local) and formats it as meeting notes, action items, or a conversation summary. Enable the &quot;Audio notes&quot; skill in Settings → Skills.
      </p>

      <div className="card">
        <h2>Upload audio</h2>
        <p style={{ color: "var(--muted)", fontSize: "0.9rem", marginBottom: "0.75rem" }}>
          Supported: MP3, WAV, M4A, OGG, WebM, FLAC. Max 50 MB.
        </p>
        <input
          ref={inputRef}
          type="file"
          accept="audio/*,video/*,.mp3,.wav,.m4a,.ogg,.webm,.flac"
          onChange={(e) => {
            const f = e.target.files?.[0];
            setFile(f || null);
            setResult(null);
            setError(null);
          }}
          style={{ marginBottom: "1rem" }}
        />
        {file && (
          <p style={{ color: "var(--text-secondary)", marginBottom: "1rem" }}>
            Selected: <strong>{file.name}</strong> ({(file.size / 1024).toFixed(1)} KB)
          </p>
        )}

        <h3 style={{ marginBottom: "0.5rem" }}>Transcription quality</h3>
        <p style={{ color: "var(--muted)", fontSize: "0.9rem", marginBottom: "0.5rem" }}>
          More accurate models take longer. &quot;Meeting notes&quot; are saved so you can ask later: &quot;What was the last meeting about?&quot;
        </p>
        <select
          value={whisperModel}
          onChange={(e) => setWhisperModel(e.target.value)}
          style={{ width: "100%", marginBottom: "1rem", padding: "0.5rem" }}
        >
          {WHISPER_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>

        <h3 style={{ marginBottom: "0.5rem" }}>What should Asta do?</h3>
        <select
          value={presetValue}
          onChange={(e) => setPresetValue(e.target.value)}
          style={{ width: "100%", marginBottom: "0.5rem", padding: "0.5rem" }}
        >
          {PRESETS.map((p) => (
            <option key={p.label} value={p.value}>
              {p.label}
            </option>
          ))}
        </select>
        {presetValue === PRESET_CUSTOM && (
          <textarea
            placeholder="E.g. 'Make meeting notes with bullet points' or 'Extract conversation between 2 people'"
            value={customInstruction}
            onChange={(e) => setCustomInstruction(e.target.value)}
            rows={2}
            style={{ width: "100%", marginBottom: "1rem", padding: "0.5rem" }}
          />
        )}

        <button
          type="button"
          onClick={submit}
          disabled={!file || loading}
          style={{ marginRight: "0.5rem" }}
        >
          {loading ? (progressStage === "formatting" ? "Formatting…" : "Transcribing…") : "Transcribe & format"}
        </button>
        {loading && (
          <div style={{ marginTop: "1rem" }}>
            <div style={{ display: "flex", gap: "0.5rem", marginBottom: "0.35rem", fontSize: "0.9rem" }}>
              <span style={{ color: progressStage === "transcribing" ? "var(--accent)" : "var(--muted)" }}>1. Transcribing</span>
              <span style={{ color: "var(--muted)" }}>→</span>
              <span style={{ color: progressStage === "formatting" ? "var(--accent)" : "var(--muted)" }}>2. Formatting</span>
            </div>
            <div style={{ height: 6, background: "var(--surface)", borderRadius: 3, overflow: "hidden" }}>
              <div
                style={{
                  height: "100%",
                  width: progressStage === "formatting" ? "100%" : "50%",
                  background: "var(--accent)",
                  borderRadius: 3,
                  transition: "width 0.3s ease",
                }}
              />
            </div>
          </div>
        )}
        {error && <p style={{ color: "var(--error)", marginTop: "0.75rem" }}>{error}</p>}
      </div>

      {result && (
        <div className="card" style={{ marginTop: "1rem" }}>
          <h2>Transcript</h2>
          <pre
            style={{
              whiteSpace: "pre-wrap",
              wordBreak: "break-word",
              background: "var(--surface)",
              padding: "1rem",
              borderRadius: "var(--radius-sm)",
              fontSize: "0.9rem",
              maxHeight: "200px",
              overflow: "auto",
              marginBottom: "1rem",
            }}
          >
            {result.transcript}
          </pre>
          <h2>Formatted</h2>
          <div
            style={{
              whiteSpace: "pre-wrap",
              wordBreak: "break-word",
              background: "var(--surface)",
              padding: "1rem",
              borderRadius: "var(--radius-sm)",
              fontSize: "0.95rem",
              lineHeight: 1.6,
            }}
          >
            {result.formatted}
          </div>
        </div>
      )}
    </div>
  );
}
