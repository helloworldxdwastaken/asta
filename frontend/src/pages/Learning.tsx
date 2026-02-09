import { useState } from "react";
import { api } from "../api/client";

export default function Learning() {
  const [topic, setTopic] = useState("");
  const [text, setText] = useState("");
  const [duration, setDuration] = useState(60);
  const [sources, setSources] = useState("");
  const [result, setResult] = useState<string | null>(null);

  const learnNow = () => {
    if (!topic.trim() || !text.trim()) return;
    setResult(null);
    api
      .ragLearn(topic.trim(), text.trim())
      .then((r) => setResult(`Learned "${r.topic}". Ask about it in Chat.`))
      .catch((e) => setResult("Error: " + (e as Error).message));
  };

  const scheduleLearn = () => {
    if (!topic.trim()) return;
    const srcList = sources.split("\n").map((s) => s.trim()).filter(Boolean);
    setResult(null);
    api
      .tasksLearn(topic.trim(), duration, srcList)
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
        <h2>Learn now (paste text)</h2>
        <input
          type="text"
          placeholder="Topic (e.g. Next.js)"
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          style={{ width: "100%", marginBottom: "0.5rem" }}
        />
        <textarea
          placeholder="Paste text to learn..."
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={6}
          style={{ width: "100%", marginBottom: "0.5rem" }}
        />
        <button type="button" onClick={learnNow} disabled={!topic.trim() || !text.trim()}>
          Learn this
        </button>
      </div>

      <div className="card">
        <h2>Schedule learning job</h2>
        <input
          type="text"
          placeholder="Topic"
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          style={{ width: "100%", marginBottom: "0.5rem" }}
        />
        <label>
          Duration (minutes): <input type="number" value={duration} onChange={(e) => setDuration(parseInt(e.target.value, 10) || 60)} min={1} />
        </label>
        <textarea
          placeholder="Sources (one per line: URLs or text snippets)"
          value={sources}
          onChange={(e) => setSources(e.target.value)}
          rows={3}
          style={{ width: "100%", marginTop: "0.5rem" }}
        />
        <button type="button" onClick={scheduleLearn} disabled={!topic.trim()} style={{ marginTop: "0.5rem" }}>
          Start job
        </button>
      </div>

      {result && <div className="card status-ok">{result}</div>}
    </div>
  );
}
