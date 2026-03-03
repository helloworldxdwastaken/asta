import { useState, useEffect } from "react";
import { listCron, createCron, updateCron, deleteCron } from "../../../lib/api";
import { IconPlus, IconTrash, IconEdit } from "../../../lib/icons";
import { Toggle } from "./TabGeneral";

interface CronJob {
  id: string; name: string; cron_expr: string; message?: string;
  next_run?: string; enabled?: boolean; tz?: string;
  channel?: string; channel_target?: string;
  payload_kind?: string; tlg_call?: boolean;
}

export default function TabCron() {
  const [jobs, setJobs] = useState<CronJob[]>([]);
  const [adding, setAdding] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);

  // Form fields
  const [name, setName] = useState("");
  const [cronExpr, setCronExpr] = useState("");
  const [message, setMessage] = useState("");
  const [tz, setTz] = useState("");
  const [channel, setChannel] = useState("web");
  const [channelTarget, setChannelTarget] = useState("");
  const [payloadKind, setPayloadKind] = useState("agentturn");
  const [tlgCall, setTlgCall] = useState(true);

  async function load() { listCron().then(r => setJobs(r.cron_jobs ?? r.jobs ?? r ?? [])).catch(()=>{}); }
  useEffect(() => { load(); }, []);

  function resetForm() {
    setName(""); setCronExpr(""); setMessage(""); setTz("");
    setChannel("web"); setChannelTarget(""); setPayloadKind("agentturn"); setTlgCall(true);
  }

  async function save() {
    if (!name.trim() || !cronExpr.trim() || !message.trim()) return;
    const payload = {
      name, cron_expr: cronExpr, message, tz: tz || undefined,
      channel, channel_target: channelTarget, payload_kind: payloadKind, tlg_call: tlgCall,
    };
    if (editId) await updateCron(editId, payload);
    else await createCron(payload);
    resetForm(); setAdding(false); setEditId(null); load();
  }

  function startEdit(j: CronJob) {
    setEditId(j.id); setName(j.name); setCronExpr(j.cron_expr);
    setMessage(j.message ?? ""); setTz(j.tz ?? "");
    setChannel(j.channel ?? "web"); setChannelTarget(j.channel_target ?? "");
    setPayloadKind(j.payload_kind ?? "agentturn"); setTlgCall(j.tlg_call ?? true);
    setAdding(true);
  }

  async function toggleEnabled(j: CronJob) {
    await updateCron(j.id, { enabled: !j.enabled });
    load();
  }

  return (
    <div className="text-label space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-15 font-semibold">Schedule</h2>
        <button onClick={() => { setAdding(!adding); setEditId(null); resetForm(); }}
          className="text-12 bg-accent hover:bg-accent-hover text-white px-3 py-1.5 rounded-lg flex items-center gap-1">
          <IconPlus size={12} /> Add
        </button>
      </div>

      {adding && (
        <div className="bg-white/[.04] rounded-mac p-4 space-y-3">
          <p className="text-11 font-semibold text-label-tertiary uppercase tracking-wider">Job</p>
          <input type="text" value={name} onChange={e => setName(e.target.value)} placeholder="Job name"
            className="w-full bg-white/[.06] border border-separator rounded-lg px-3 py-2 text-13 text-label outline-none focus:border-accent/50" />
          <div>
            <input type="text" value={cronExpr} onChange={e => setCronExpr(e.target.value)} placeholder="Cron expression"
              className="w-full bg-white/[.06] border border-separator rounded-lg px-3 py-2 text-13 font-mono text-label outline-none focus:border-accent/50" />
            <p className="text-[10px] text-label-tertiary mt-1 px-1">e.g. 0 8 * * * = 8am daily</p>
          </div>
          <textarea value={message} onChange={e => setMessage(e.target.value)} placeholder="Message to send"
            rows={2} className="w-full bg-white/[.06] border border-separator rounded-lg px-3 py-2 text-13 text-label outline-none focus:border-accent/50 resize-none" />
          <input type="text" value={tz} onChange={e => setTz(e.target.value)} placeholder="Timezone (e.g. America/New_York)"
            className="w-full bg-white/[.06] border border-separator rounded-lg px-3 py-2 text-13 text-label outline-none focus:border-accent/50" />

          <p className="text-11 font-semibold text-label-tertiary uppercase tracking-wider pt-2">Delivery</p>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-11 text-label-tertiary block mb-1">Channel</label>
              <select value={channel} onChange={e => setChannel(e.target.value)}
                className="w-full bg-white/[.06] border border-separator rounded-lg px-3 py-2 text-13 text-label outline-none focus:border-accent/50">
                <option value="web">Web (in-app)</option>
                <option value="telegram">Telegram</option>
              </select>
            </div>
            <div>
              <label className="text-11 text-label-tertiary block mb-1">Channel Target</label>
              <input type="text" value={channelTarget} onChange={e => setChannelTarget(e.target.value)}
                placeholder={channel === "telegram" ? "Chat ID" : ""}
                className="w-full bg-white/[.06] border border-separator rounded-lg px-3 py-2 text-13 text-label outline-none focus:border-accent/50" />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-11 text-label-tertiary block mb-1">Mode</label>
              <select value={payloadKind} onChange={e => setPayloadKind(e.target.value)}
                className="w-full bg-white/[.06] border border-separator rounded-lg px-3 py-2 text-13 text-label outline-none focus:border-accent/50">
                <option value="agentturn">Call AI (agentturn)</option>
                <option value="systemevent">Notify only (systemevent)</option>
              </select>
            </div>
            <div className="flex items-end pb-1">
              <Toggle checked={tlgCall} onChange={setTlgCall} label="Voice call" />
            </div>
          </div>

          {editId && (
            <div className="pt-1">
              <Toggle checked={jobs.find(j => j.id === editId)?.enabled !== false}
                onChange={() => { const j = jobs.find(j => j.id === editId); if (j) toggleEnabled(j); }}
                label="Enabled" />
            </div>
          )}

          <div className="flex gap-2 pt-1">
            <button onClick={save} disabled={!name.trim() || !cronExpr.trim() || !message.trim()}
              className="text-12 bg-accent hover:bg-accent-hover disabled:opacity-40 text-white px-4 py-1.5 rounded-lg transition-colors">
              {editId ? "Save" : "Create"}
            </button>
            <button onClick={() => { setAdding(false); setEditId(null); resetForm(); }}
              className="text-12 text-label-tertiary hover:text-label px-4 py-1.5">Cancel</button>
          </div>
        </div>
      )}

      <div className="space-y-1.5">
        {jobs.map(j => (
          <div key={j.id} className="flex items-center gap-3 bg-white/[.04] rounded-mac px-4 py-3 group">
            <div className="shrink-0">
              <Toggle checked={j.enabled !== false} onChange={() => toggleEnabled(j)} />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-13 font-medium">{j.name}</p>
              <p className="text-11 text-label-tertiary font-mono mt-0.5 truncate">
                {j.cron_expr}{j.message ? ` — ${j.message}` : ""}
              </p>
              <div className="flex items-center gap-2 mt-0.5">
                <span className="text-[10px] text-label-tertiary bg-white/[.04] px-1.5 py-0.5 rounded">{j.channel ?? "web"}</span>
                {j.tz && <span className="text-[10px] text-label-tertiary">{j.tz}</span>}
                {j.next_run && <span className="text-[10px] text-label-tertiary">Next: {j.next_run}</span>}
              </div>
            </div>
            <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
              <button onClick={() => startEdit(j)} className="text-label-tertiary hover:text-label p-1.5"><IconEdit size={12} /></button>
              <button onClick={async () => { await deleteCron(j.id); load(); }} className="text-danger/50 hover:text-danger p-1.5"><IconTrash size={12} /></button>
            </div>
          </div>
        ))}
        {jobs.length === 0 && !adding && <p className="text-label-tertiary text-13">No scheduled jobs. Click + to add one.</p>}
      </div>
    </div>
  );
}
