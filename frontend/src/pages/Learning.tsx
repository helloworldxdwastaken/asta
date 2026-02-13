import { useState, useEffect, useCallback } from "react";
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
  const [ragStatus, setRagStatus] = useState<{ ok: boolean; message: string; provider: string | null; detail?: string | null; ollama_url?: string | null; ollama_reason?: string; ollama_ok?: boolean; store_error?: boolean } | null>(null);
  const [ollamaUrl, setOllamaUrl] = useState("http://localhost:11434");
  const [ollamaCheck, setOllamaCheck] = useState<{ ok: boolean; detail: string | null; ollama_url: string; ollama_reason?: string } | null>(null);
  const [ollamaChecking, setOllamaChecking] = useState(false);
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

  const fetchRagStatus = useCallback(() => {
    api.ragStatus()
      .then((s) => {
        setRagStatus(s);
        if (s?.ollama_url) setOllamaUrl(s.ollama_url);
      })
      .catch(() => setRagStatus({ ok: false, message: "Could not check RAG status.", provider: null, detail: null }));
  }, []);

  useEffect(() => {
    fetchRagStatus();
  }, [fetchRagStatus]);

  const checkOllama = () => {
    setOllamaChecking(true);
    setOllamaCheck(null);
    api.ragCheckOllama(ollamaUrl)
      .then((r) => setOllamaCheck(r))
      .catch((e) => setOllamaCheck({ ok: false, detail: (e as Error).message, ollama_url: ollamaUrl }))
      .finally(() => setOllamaChecking(false));
  };

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
      <h1 className="page-title">RAG</h1>
      <p className="page-description">
        Add knowledge by topic. The AI will use it when you ask related questions. Uses Ollama for embeddings (run
        <code> ollama pull nomic-embed-text</code>).
      </p>

      {ragStatus !== null && (
        <>
          {/* Single clear status banner */}
          <div
            className="card"
            style={{
              marginBottom: "1rem",
              backgroundColor: ragStatus.ok
                ? "var(--success-dim)"
                : ragStatus.store_error && ragStatus.ollama_ok
                  ? "var(--warning-dim, rgba(220, 160, 0, 0.12))"
                  : "var(--error-dim)",
              borderLeft: `4px solid ${ragStatus.ok ? "var(--success)" : ragStatus.store_error && ragStatus.ollama_ok ? "var(--warning, #d4a000)" : "var(--error)"}`,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "0.5rem" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
                <span
                  style={{
                    fontWeight: 700,
                    color: ragStatus.ok
                      ? "var(--success)"
                      : ragStatus.store_error && ragStatus.ollama_ok
                        ? "var(--warning, #b8860b)"
                        : "var(--error)",
                  }}
                >
                  {ragStatus.ok
                    ? "✓ RAG ready"
                    : ragStatus.store_error && ragStatus.ollama_ok
                      ? "⚠ Ollama connected; RAG store unavailable"
                      : "✗ RAG not available"}
                </span>
                {ragStatus.ok && ragStatus.provider && (
                  <span className="muted" style={{ fontSize: "0.9rem" }}>(using {ragStatus.provider})</span>
                )}
              </div>
              {!ragStatus.ok && (
                <button type="button" onClick={fetchRagStatus} className="button" style={{ fontSize: "0.85rem" }}>
                  Refresh status
                </button>
              )}
            </div>
            <p style={{ margin: "0.35rem 0 0 0", fontSize: "0.95rem", color: "var(--text-secondary)" }}>
              {ragStatus.ok
                ? ragStatus.message
                : ragStatus.store_error && ragStatus.ollama_ok
                  ? "Ollama and the embed model work. The RAG store (ChromaDB) failed to start — see how to fix below."
                  : ragStatus.message}
            </p>

            {/* Case 1: Store failed but Ollama is OK — only show ChromaDB fix */}
            {!ragStatus.ok && ragStatus.store_error && ragStatus.ollama_ok && (
              <div className="help" style={{ marginTop: "1rem" }}>
                <p style={{ fontWeight: 600, marginBottom: "0.5rem" }}>Fix the RAG store (ChromaDB)</p>
                <p style={{ marginBottom: "0.5rem" }}>
                  The RAG store (ChromaDB) needs <strong>Python 3.12 or 3.13</strong>. Python 3.14 is not yet supported (pydantic-core/PyO3). Use a venv with 3.12 or 3.13:
                </p>
                <p style={{ margin: "0 0 0.25rem 0" }}><code>cd backend</code></p>
                <p style={{ margin: "0 0 0.25rem 0" }}>If needed: <code>brew install python@3.12</code></p>
                <p style={{ margin: "0 0 0.25rem 0" }}><code>python3.12 -m venv .venv</code> (or <code>python3.13 -m venv .venv</code>)</p>
                <p style={{ margin: "0 0 0.25rem 0" }}><code>source .venv/bin/activate</code></p>
                <p style={{ margin: "0 0 0.5rem 0" }}><code>pip install -r requirements.txt</code></p>
                <p style={{ marginBottom: 0 }}>Then <strong>restart the backend</strong> with this venv active and click Refresh status above.</p>
                <p className="muted" style={{ marginTop: "0.5rem", marginBottom: 0, fontSize: "0.85rem" }}>
                  Ollama is verified at <code>{ragStatus.ollama_url}</code>. No need to change it unless you use a different URL.
                </p>
              </div>
            )}

            {/* Case 2: Ollama not OK — show Ollama guidance + address box */}
            {!ragStatus.ok && !ragStatus.ollama_ok && (() => {
              const reason = ragStatus.ollama_reason || "unknown";
              return (
                <>
                  <div className="help" style={{ marginTop: "1rem" }}>
                    {reason === "not_running" && (
                      <>
                        <p style={{ fontWeight: 600, marginBottom: "0.5rem" }}>Ollama isn’t running or not installed</p>
                        <p style={{ marginBottom: "0.35rem" }}><strong>Install:</strong> <code>curl -fsSL https://ollama.com/install.sh | sh</code></p>
                        <p style={{ marginBottom: "0.35rem" }}>Then: <code>ollama pull nomic-embed-text</code></p>
                        <p style={{ marginBottom: "0.35rem" }}><strong>Start:</strong> <code>ollama serve</code> or open the Ollama app.</p>
                        <p style={{ marginTop: "0.5rem", marginBottom: 0 }}>If it’s already running, the backend may be using the wrong address — use the box below to test; if Check works, set <code>OLLAMA_BASE_URL</code> in <code>backend/.env</code> and restart the backend.</p>
                      </>
                    )}
                    {reason === "model_missing" && (
                      <>
                        <p style={{ fontWeight: 600, marginBottom: "0.5rem" }}>Ollama is running but the embed model isn’t loaded</p>
                        <p style={{ margin: "0 0 0.5rem 0" }}><code>ollama pull nomic-embed-text</code></p>
                        <p style={{ marginBottom: 0 }}>Then refresh this page or click Refresh status.</p>
                      </>
                    )}
                    {reason === "wrong_config" && (
                      <>
                        <p style={{ fontWeight: 600, marginBottom: "0.5rem" }}>Embed model not set up correctly</p>
                        <p style={{ margin: "0 0 0.5rem 0" }}><code>ollama pull nomic-embed-text</code></p>
                        <p style={{ marginBottom: 0 }}>Keep Ollama running, then refresh or click Refresh status.</p>
                      </>
                    )}
                    {(reason === "unknown" || !reason) && (
                      <>
                        <p style={{ fontWeight: 600, marginBottom: "0.5rem" }}>Asta can’t reach Ollama</p>
                        <p style={{ marginBottom: 0 }}>Test the address below. If Ollama runs on this machine, set <code>OLLAMA_BASE_URL</code> in <code>backend/.env</code> and restart the backend.</p>
                      </>
                    )}
                  </div>
                  <div style={{ marginTop: "1rem", padding: "1rem", backgroundColor: "var(--bg)", borderRadius: "8px", border: "1px solid var(--border)" }}>
                    <label style={{ display: "block", fontWeight: 600, marginBottom: "0.5rem", fontSize: "0.9rem" }}>Ollama address</label>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem", alignItems: "center" }}>
                      <input
                        type="url"
                        value={ollamaUrl}
                        onChange={(e) => setOllamaUrl(e.target.value)}
                        placeholder="http://localhost:11434"
                        style={{ flex: "1 1 200px", minWidth: "200px", padding: "0.5rem 0.6rem", borderRadius: "6px", border: "1px solid var(--border)", background: "var(--bg-secondary)", color: "var(--text)" }}
                      />
                      <button type="button" onClick={checkOllama} disabled={ollamaChecking} className="button primary">
                        {ollamaChecking ? "Checking…" : "Check connection"}
                      </button>
                    </div>
                    {ollamaCheck !== null && (
                      <div style={{ marginTop: "0.75rem", fontSize: "0.9rem", color: ollamaCheck.ok ? "var(--success)" : "var(--error)" }}>
                        {ollamaCheck.ok ? "✓ Ollama is reachable and nomic-embed-text works." : `✗ ${ollamaCheck.detail || "Connection failed."}`}
                      </div>
                    )}
                    {ollamaCheck?.ok && (
                      <p className="muted" style={{ marginTop: "0.5rem", marginBottom: 0, fontSize: "0.85rem" }}>
                        Set <code>OLLAMA_BASE_URL={ollamaCheck.ollama_url}</code> in <code>backend/.env</code> and restart the backend, then click Refresh status.
                      </p>
                    )}
                  </div>
                </>
              );
            })()}
          </div>
        </>
      )}

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
          Replace [TOPIC] with your subject, paste the result into "Learn now" below.
        </p>
      </div>

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
