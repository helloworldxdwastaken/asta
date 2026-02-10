import { useState, useEffect } from "react";
import { api } from "../api/client";

type LearnedTopic = { topic: string; chunks_count: number };

export default function Learning() {
  const [topicNow, setTopicNow] = useState("");
  const [textNow, setTextNow] = useState("");
  const [duration, setDuration] = useState(60);
  const [sources, setSources] = useState("");
  const [result, setResult] = useState<string | null>(null);
  const [learned, setLearned] = useState<{ has_learned: boolean; topics: LearnedTopic[] } | null>(null);
  const [learnedError, setLearnedError] = useState<string | null>(null);
  const [topicJob, setTopicJob] = useState("");

  const fetchLearned = () => {
    setLearnedError(null);
    setLearned(null);
    api
      .ragLearned()
      .then((r) => {
        setLearned(r);
        setLearnedError(null);
      })
      .catch((e) => {
        setLearned({ has_learned: false, topics: [] });
        setLearnedError((e as Error).message || "Could not load learned topics");
      });
  };

  useEffect(() => {
    fetchLearned();
  }, [result]);

  const learnNow = () => {
    if (!topicNow.trim() || !textNow.trim()) return;
    setResult(null);
    api
      .ragLearn(topicNow.trim(), textNow.trim())
      .then((r) => setResult(`Learned "${r.topic}". Ask about it in Chat.`))
      .catch((e) => setResult("Error: " + (e as Error).message));
  };

  const scheduleLearn = () => {
    if (!topicJob.trim()) return;
    const srcList = sources.split("\n").map((s) => s.trim()).filter(Boolean);
    setResult(null);
    api
      .tasksLearn(topicJob.trim(), duration, srcList)
      .then((r) => setResult(`Job ${r.job_id} started for "${r.topic}".`))
      .catch((e) => setResult("Error: " + (e as Error).message));
  };

  return (
    <div>
      <h1 className="page-title">Learning / RAG</h1>
      <p className="page-description">
        Add knowledge by topic. The AI will use it when you ask related questions. Uses Ollama for embeddings (run
        <code> ollama pull nomic-embed-text</code>).
      </p>

      <div className="card">
        <div className="card-header">
          <div>
            <h2 style={{ margin: 0 }}>What the AI has learned</h2>
            <p className="help" style={{ marginTop: "0.25rem" }}>
              Topics that were ingested into the RAG store.
            </p>
          </div>
          <button type="button" onClick={fetchLearned} className="btn btn-secondary">
            Refresh
          </button>
        </div>
        {learnedError && (
          <div className="alert alert-error" style={{ marginBottom: "0.75rem" }}>
            {learnedError} — Check that the backend is running and RAG is set up (Ollama with <code>nomic-embed-text</code>).
          </div>
        )}
        {learned === null && !learnedError ? (
          <p className="muted">Loading…</p>
        ) : learned?.has_learned ? (
          <>
            <p className="help" style={{ marginBottom: "0.75rem" }}>
              Topics and chunk counts:
            </p>
            <ul style={{ margin: 0, paddingLeft: "1.25rem" }}>
              {learned.topics.map((t) => (
                <li key={t.topic} style={{ marginBottom: "0.35rem" }}>
                  <strong>{t.topic}</strong>
                  {t.chunks_count > 0 && (
                    <span className="muted" style={{ marginLeft: "0.5rem" }}>
                      ({t.chunks_count} chunk{t.chunks_count !== 1 ? "s" : ""})
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </>
        ) : !learnedError ? (
          <p className="muted">Nothing learned yet. Add content below or run a learning job.</p>
        ) : null}
      </div>

      <div className="card">
        <h2>Learn now (paste text)</h2>
        <div className="field">
          <label className="label" htmlFor="topic-now">Topic</label>
          <input
            id="topic-now"
            className="input"
            type="text"
            placeholder="e.g. Next.js"
            value={topicNow}
            onChange={(e) => setTopicNow(e.target.value)}
          />
          <p className="help">Keep topics consistent so retrieval works well later.</p>
        </div>
        <div className="field">
          <label className="label" htmlFor="text-now">Text to learn</label>
          <textarea
            id="text-now"
            className="textarea"
            placeholder="Paste text to learn…"
            value={textNow}
            onChange={(e) => setTextNow(e.target.value)}
            rows={6}
          />
        </div>
        <div className="actions">
          <button type="button" className="btn btn-primary" onClick={learnNow} disabled={!topicNow.trim() || !textNow.trim()}>
            Learn this
          </button>
        </div>
      </div>

      <div className="card">
        <h2>Schedule learning job</h2>
        <div className="field">
          <label className="label" htmlFor="topic-job">Topic</label>
          <input
            id="topic-job"
            className="input"
            type="text"
            placeholder="e.g. Postgres indexing"
            value={topicJob}
            onChange={(e) => setTopicJob(e.target.value)}
          />
        </div>
        <div className="field">
          <label className="label" htmlFor="duration">Duration (minutes)</label>
          <input
            id="duration"
            className="input"
            type="number"
            value={duration}
            onChange={(e) => setDuration(parseInt(e.target.value, 10) || 60)}
            min={1}
            style={{ maxWidth: 160 }}
          />
          <p className="help">This starts an async job on the backend (sources ingestion is still evolving).</p>
        </div>
        <div className="field">
          <label className="label" htmlFor="sources">Sources</label>
          <textarea
            id="sources"
            className="textarea"
            placeholder="One per line: URLs or notes/snippets"
            value={sources}
            onChange={(e) => setSources(e.target.value)}
            rows={4}
          />
        </div>
        <div className="actions">
          <button type="button" className="btn btn-primary" onClick={scheduleLearn} disabled={!topicJob.trim()}>
            Start job
          </button>
        </div>
      </div>

      {result && (
        <div className={result.startsWith("Error:") ? "alert alert-error" : "alert alert-success"}>
          {result}
        </div>
      )}
    </div>
  );
}
