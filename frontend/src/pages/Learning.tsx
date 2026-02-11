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
  const [expandedTopic, setExpandedTopic] = useState<string | null>(null);
  const [topicContent, setTopicContent] = useState<string>("");
  const [editingTopic, setEditingTopic] = useState<string | null>(null);
  const [editContent, setEditContent] = useState<string>("");

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
            <ul style={{ margin: 0, paddingLeft: 0, listStyle: "none" }}>
              {learned.topics.map((t) => {
                const isExpanded = expandedTopic === t.topic;
                const isEditing = editingTopic === t.topic;

                return (
                  <li key={t.topic} style={{ marginBottom: "0.75rem", border: "1px solid var(--border-color)", borderRadius: "4px", overflow: "hidden" }}>
                    <div style={{ padding: "0.75rem", display: "flex", alignItems: "center", justifyContent: "space-between", backgroundColor: "var(--card-bg)" }}>
                      <div>
                        <strong>{t.topic}</strong>
                        {t.chunks_count > 0 && (
                          <span className="muted" style={{ marginLeft: "0.5rem" }}>
                            ({t.chunks_count} chunk{t.chunks_count !== 1 ? "s" : ""})
                          </span>
                        )}
                      </div>
                      <div style={{ display: "flex", gap: "0.5rem" }}>
                        <button
                          type="button"
                          className="btn btn-secondary"
                          style={{ fontSize: "0.85rem", padding: "0.25rem 0.75rem" }}
                          onClick={() => {
                            if (isExpanded) {
                              setExpandedTopic(null);
                              setEditingTopic(null);
                            } else {
                              setExpandedTopic(t.topic);
                              setEditingTopic(null);
                              api.ragGetTopic(t.topic)
                                .then((r) => setTopicContent(r.content))
                                .catch((e) => setResult("Error loading: " + (e as Error).message));
                            }
                          }}
                        >
                          {isExpanded ? "Hide" : "View"}
                        </button>
                        <button
                          type="button"
                          className="btn btn-secondary"
                          style={{ fontSize: "0.85rem", padding: "0.25rem 0.75rem" }}
                          onClick={() => {
                            if (confirm(`Delete all content for topic "${t.topic}"?`)) {
                              api.ragDeleteTopic(t.topic)
                                .then(() => {
                                  setResult(`Deleted topic "${t.topic}"`);
                                  setExpandedTopic(null);
                                  setEditingTopic(null);
                                  fetchLearned();
                                })
                                .catch((e) => setResult("Error: " + (e as Error).message));
                            }
                          }}
                        >
                          Delete
                        </button>
                      </div>
                    </div>

                    {isExpanded && (
                      <div style={{ padding: "0.75rem", borderTop: "1px solid var(--border-color)", backgroundColor: "var(--bg-secondary)" }}>
                        {isEditing ? (
                          <>
                            <textarea
                              className="textarea"
                              value={editContent}
                              onChange={(e) => setEditContent(e.target.value)}
                              rows={12}
                              style={{ marginBottom: "0.5rem", fontFamily: "monospace", fontSize: "0.9rem" }}
                            />
                            <div style={{ display: "flex", gap: "0.5rem" }}>
                              <button
                                type="button"
                                className="btn btn-primary"
                                onClick={() => {
                                  api.ragUpdateTopic(t.topic, editContent)
                                    .then(() => {
                                      setResult(`Updated topic "${t.topic}"`);
                                      setTopicContent(editContent);
                                      setEditingTopic(null);
                                      fetchLearned();
                                    })
                                    .catch((e) => setResult("Error: " + (e as Error).message));
                                }}
                              >
                                Save
                              </button>
                              <button
                                type="button"
                                className="btn btn-secondary"
                                onClick={() => {
                                  setEditingTopic(null);
                                  setEditContent("");
                                }}
                              >
                                Cancel
                              </button>
                            </div>
                          </>
                        ) : (
                          <>
                            <pre style={{
                              whiteSpace: "pre-wrap",
                              wordWrap: "break-word",
                              backgroundColor: "var(--bg)",
                              padding: "0.75rem",
                              borderRadius: "4px",
                              fontSize: "0.9rem",
                              maxHeight: "400px",
                              overflow: "auto",
                              margin: "0 0 0.5rem 0"
                            }}>
                              {topicContent || "Loading..."}
                            </pre>
                            <button
                              type="button"
                              className="btn btn-secondary"
                              onClick={() => {
                                setEditingTopic(t.topic);
                                setEditContent(topicContent);
                              }}
                            >
                              Edit
                            </button>
                          </>
                        )}
                      </div>
                    )}
                  </li>
                );
              })}
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

      <div className="card" style={{ backgroundColor: "var(--bg-secondary)", borderLeft: "3px solid var(--primary)" }}>
        <h3 style={{ marginTop: 0 }}>💡 Tip: Prepare content with AI</h3>
        <p className="help" style={{ marginBottom: "0.75rem" }}>
          You can use ChatGPT or other AIs to research and format content for learning. Copy this prompt:
        </p>
        <div style={{ position: "relative" }}>
          <pre style={{
            backgroundColor: "var(--bg)",
            padding: "0.75rem",
            borderRadius: "4px",
            fontSize: "0.85rem",
            overflow: "auto",
            margin: "0 0 0.5rem 0"
          }}>
            {`Research and summarize information about [TOPIC].
Format the output as a comprehensive reference document.
Include key concepts, definitions, examples, and important details.
Keep it well-structured and informative.`}
          </pre>
          <button
            type="button"
            className="btn btn-secondary"
            style={{ fontSize: "0.85rem" }}
            onClick={() => {
              navigator.clipboard.writeText(
                `Research and summarize information about [TOPIC].\nFormat the output as a comprehensive reference document.\nInclude key concepts, definitions, examples, and important details.\nKeep it well-structured and informative.`
              );
              setResult("Prompt copied to clipboard!");
            }}
          >
            Copy Prompt
          </button>
        </div>
        <p className="help" style={{ marginTop: "0.75rem", marginBottom: 0 }}>
          Replace [TOPIC] with your subject, paste the result into "Learn now" above.
        </p>
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
