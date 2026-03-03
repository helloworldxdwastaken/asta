import { useState, useEffect } from "react";
import { ragStatus, ragLearned, ragDeleteTopic, getMemoryHealth } from "../../../lib/api";
import { IconTrash } from "../../../lib/icons";

interface RagTopic { topic: string; chunks_count?: number; }

export default function TabKnowledge() {
  const [status, setStatus] = useState<any>(null);
  const [topics, setTopics] = useState<RagTopic[]>([]);
  const [health, setHealth] = useState<any>(null);
  const [deleting, setDeleting] = useState<string | null>(null);

  async function load() {
    const [s, t] = await Promise.all([ragStatus(), ragLearned()]);
    setStatus(s);
    // API may return [{topic, chunks_count}] or just string[]
    const raw = t.topics ?? t.learned ?? [];
    setTopics(raw.map((x: any) => typeof x === "string" ? { topic: x } : x));
    getMemoryHealth(true).then(setHealth).catch(()=>{});
  }
  useEffect(() => { load(); }, []);

  async function del(topicName: string) {
    setDeleting(topicName);
    await ragDeleteTopic(topicName);
    setTopics(prev => prev.filter(t => t.topic !== topicName));
    setDeleting(null);
  }

  return (
    <div className="text-label space-y-6">
      <div>
        <h2 className="text-16 font-semibold">Knowledge Base</h2>
        <p className="text-12 text-label-tertiary mt-1">
          Asta can learn from documents and conversations using RAG (Retrieval-Augmented Generation).
        </p>
      </div>

      {/* Status */}
      <div className="bg-white/[.03] border border-separator rounded-mac p-4 space-y-2">
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${status?.ok ? "bg-success" : "bg-warning"}`} />
          <span className="text-13 font-medium">{status?.ok ? "Active" : "Inactive"}</span>
          {status?.provider && <span className="text-11 text-label-tertiary font-mono ml-1">({status.provider})</span>}
        </div>
        {status?.store_error && status.detail && (
          <p className="text-12 text-warning">{status.detail}</p>
        )}
      </div>

      {/* Memory Health */}
      {health && (
        <Section title="Memory Health">
          <div className="grid grid-cols-3 gap-3">
            {[
              ["Vectors", health.vector_count],
              ["Chunks", health.chunk_count],
              ["Size", health.store_size_mb != null ? `${Number(health.store_size_mb).toFixed(1)} MB` : "\u2014"],
            ].map(([label, val]) => (
              <div key={label as string} className="bg-white/[.03] border border-separator rounded-mac px-4 py-3.5 text-center">
                <p className="text-18 font-semibold tabular-nums text-gradient">{val ?? 0}</p>
                <p className="text-11 text-label-tertiary mt-1">{label as string}</p>
              </div>
            ))}
          </div>
          {health.error && <p className="text-12 text-warning mt-2">{health.error}</p>}
        </Section>
      )}

      {/* Learned Topics */}
      <Section title="Learned Topics">
        <div className="space-y-2">
          {topics.map(t => (
            <div key={t.topic} className="flex items-center justify-between bg-white/[.03] border border-separator rounded-mac px-4 py-3 hover:bg-white/[.05] transition-colors">
              <div className="min-w-0">
                <span className="text-13 font-medium truncate block">{t.topic}</span>
                {t.chunks_count != null && (
                  <span className="text-11 text-label-tertiary font-mono">{t.chunks_count} chunks</span>
                )}
              </div>
              <button onClick={() => del(t.topic)} disabled={deleting === t.topic}
                className="text-danger/50 hover:text-danger hover:bg-danger/[.08] disabled:opacity-50 p-1.5 rounded-mac transition-all duration-200 shrink-0 ml-2">
                {deleting === t.topic
                  ? <div className="w-3 h-3 border-2 border-danger/40 border-t-danger rounded-full animate-spin" />
                  : <IconTrash size={13} />}
              </button>
            </div>
          ))}
          {topics.length === 0 && (
            <p className="text-label-tertiary text-13">
              No learned topics yet. Use learning mode in chat to teach Asta new information.
            </p>
          )}
        </div>
      </Section>

      {/* Instructions */}
      <Section title="How to Use">
        <div className="bg-white/[.03] border border-separator rounded-mac p-4">
          <ol className="text-12 text-label-tertiary space-y-1.5 list-decimal pl-4 leading-relaxed">
            <li>Toggle learning mode on in the chat toolbar</li>
            <li>Send a message — Asta will save it to memory</li>
            <li>Toggle learning mode off to return to normal chat</li>
            <li>Asta will automatically retrieve relevant knowledge when answering questions</li>
          </ol>
        </div>
      </Section>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h3 className="text-10 font-bold text-label-tertiary uppercase tracking-widest mb-2.5">{title}</h3>
      {children}
    </section>
  );
}
