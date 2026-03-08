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

const DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const DAY_CRON   = ["1",   "2",   "3",   "4",   "5",   "6",   "0"];

const COMMON_TZ = [
  "", "America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles",
  "Europe/London", "Europe/Paris", "Europe/Lisbon", "Europe/Berlin",
  "Asia/Tokyo", "Asia/Jerusalem", "Asia/Shanghai", "Australia/Sydney",
];

/** Parse a cron expression into {minute, hour, days} or null if not simple */
function parseCron(expr: string): { minute: number; hour: number; days: number[] } | null {
  const parts = expr.trim().split(/\s+/);
  if (parts.length !== 5) return null;
  const [minP, hourP, , , dowP] = parts;
  // Must be numeric minute/hour, day-of-month=*, month=*
  if (parts[2] !== "*" || parts[3] !== "*") return null;
  const minute = parseInt(minP, 10);
  const hour = parseInt(hourP, 10);
  if (isNaN(minute) || isNaN(hour)) return null;
  let days: number[] = [];
  if (dowP === "*") {
    days = [0, 1, 2, 3, 4, 5, 6];
  } else {
    // Parse comma-separated day numbers (support ranges like 1-5)
    for (const seg of dowP.split(",")) {
      if (seg.includes("-")) {
        const [a, b] = seg.split("-").map(Number);
        if (isNaN(a) || isNaN(b)) return null;
        for (let i = a; i <= b; i++) days.push(i);
      } else {
        const d = parseInt(seg, 10);
        if (isNaN(d)) return null;
        days.push(d);
      }
    }
  }
  return { minute, hour, days };
}

/** Build a cron expression from {minute, hour, days} */
function buildCron(minute: number, hour: number, days: number[]): string {
  const sorted = [...days].sort((a, b) => a - b);
  const dowPart = sorted.length === 7 ? "*" : sorted.join(",");
  return `${minute} ${hour} * * ${dowPart}`;
}

/** Format hour:minute for display */
function fmtTime(h: number, m: number): string {
  const suffix = h >= 12 ? "PM" : "AM";
  const h12 = h === 0 ? 12 : h > 12 ? h - 12 : h;
  return `${h12}:${m.toString().padStart(2, "0")} ${suffix}`;
}

/** Describe days for display */
function fmtDays(days: number[]): string {
  const sorted = [...days].sort((a, b) => a - b);
  if (sorted.length === 7) return "Every day";
  if (sorted.length === 5 && [1,2,3,4,5].every(d => sorted.includes(d))) return "Weekdays";
  if (sorted.length === 2 && sorted.includes(0) && sorted.includes(6)) return "Weekends";
  // Map cron day numbers to labels (0=Sun, 1=Mon, ...)
  const map: Record<number, string> = { 0: "Sun", 1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri", 6: "Sat" };
  return sorted.map(d => map[d] ?? d).join(", ");
}

const inputCls = "w-full bg-white/[.06] border border-separator rounded-lg px-3 py-2 text-13 text-label outline-none focus:border-accent/50";
const labelCls = "text-11 text-label-tertiary block mb-1";

export default function TabCron() {
  const [jobs, setJobs] = useState<CronJob[]>([]);
  const [adding, setAdding] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [useAdvanced, setUseAdvanced] = useState(false);

  // Form fields
  const [name, setName] = useState("");
  const [cronExpr, setCronExpr] = useState("");
  const [message, setMessage] = useState("");
  const [tz, setTz] = useState("");
  const [channel, setChannel] = useState("web");
  const [channelTarget, setChannelTarget] = useState("");
  const [payloadKind, setPayloadKind] = useState("agentturn");
  const [tlgCall, setTlgCall] = useState(true);

  // Friendly schedule fields
  const [hour, setHour] = useState(8);
  const [minute, setMinute] = useState(0);
  const [selectedDays, setSelectedDays] = useState<number[]>([1, 2, 3, 4, 5]);

  async function load() { listCron().then(r => setJobs(r.cron_jobs ?? r.jobs ?? r ?? [])).catch(() => {}); }
  useEffect(() => { load(); }, []);

  function resetForm() {
    setName(""); setCronExpr(""); setMessage(""); setTz("");
    setChannel("web"); setChannelTarget(""); setPayloadKind("agentturn"); setTlgCall(true);
    setHour(8); setMinute(0); setSelectedDays([1, 2, 3, 4, 5]); setUseAdvanced(false);
  }

  function effectiveCron(): string {
    if (useAdvanced) return cronExpr;
    return buildCron(minute, hour, selectedDays);
  }

  async function save() {
    const expr = effectiveCron();
    if (!name.trim() || !expr.trim() || !message.trim()) return;
    const payload = {
      name, cron_expr: expr, message, tz: tz || undefined,
      channel, channel_target: channelTarget, payload_kind: payloadKind, tlg_call: tlgCall,
    };
    try {
      if (editId) await updateCron(editId, payload);
      else await createCron(payload);
      resetForm(); setAdding(false); setEditId(null); load();
    } catch (e: any) {
      alert(e?.message || "Failed to save");
    }
  }

  function startEdit(j: CronJob) {
    setEditId(j.id); setName(j.name); setCronExpr(j.cron_expr);
    setMessage(j.message ?? ""); setTz(j.tz ?? "");
    setChannel(j.channel ?? "web"); setChannelTarget(j.channel_target ?? "");
    setPayloadKind(j.payload_kind ?? "agentturn"); setTlgCall(j.tlg_call ?? true);
    // Try to parse into friendly mode
    const parsed = parseCron(j.cron_expr);
    if (parsed) {
      setHour(parsed.hour); setMinute(parsed.minute); setSelectedDays(parsed.days);
      setUseAdvanced(false);
    } else {
      setUseAdvanced(true);
    }
    setAdding(true);
  }

  function toggleDay(d: number) {
    setSelectedDays(prev => prev.includes(d) ? prev.filter(x => x !== d) : [...prev, d]);
  }

  async function toggleEnabled(j: CronJob) {
    await updateCron(j.id, { enabled: !j.enabled });
    load();
  }

  const canSave = name.trim() && message.trim() && (useAdvanced ? cronExpr.trim() : selectedDays.length > 0);

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
            className={inputCls} />

          {/* Schedule section */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <p className="text-11 font-semibold text-label-tertiary uppercase tracking-wider">When</p>
              <button onClick={() => setUseAdvanced(!useAdvanced)}
                className="text-[10px] text-accent hover:underline">
                {useAdvanced ? "Simple mode" : "Advanced (cron)"}
              </button>
            </div>

            {useAdvanced ? (
              <div>
                <input type="text" value={cronExpr} onChange={e => setCronExpr(e.target.value)} placeholder="0 8 * * 1,2,3,4,5"
                  className={`${inputCls} font-mono`} />
                <p className="text-[10px] text-label-tertiary mt-1 px-1">5-field cron: minute hour day-of-month month day-of-week</p>
              </div>
            ) : (
              <>
                {/* Day pills */}
                <div className="flex gap-1.5">
                  {DAY_LABELS.map((label, i) => {
                    const cronDay = parseInt(DAY_CRON[i], 10);
                    const active = selectedDays.includes(cronDay);
                    return (
                      <button key={label} onClick={() => toggleDay(cronDay)}
                        className={`flex-1 py-1.5 rounded-lg text-11 font-medium transition-colors ${
                          active
                            ? "bg-accent text-white"
                            : "bg-white/[.06] text-label-tertiary hover:text-label hover:bg-white/[.1]"
                        }`}>
                        {label}
                      </button>
                    );
                  })}
                </div>
                {/* Quick select */}
                <div className="flex gap-2">
                  {([
                    ["Weekdays", [1,2,3,4,5]],
                    ["Weekends", [0,6]],
                    ["Every day", [0,1,2,3,4,5,6]],
                  ] as [string, number[]][]).map(([label, days]) => (
                    <button key={label} onClick={() => setSelectedDays(days)}
                      className="text-[10px] text-label-tertiary hover:text-accent transition-colors">
                      {label}
                    </button>
                  ))}
                </div>
                {/* Time picker */}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className={labelCls}>Hour</label>
                    <select value={hour} onChange={e => setHour(parseInt(e.target.value, 10))}
                      className={inputCls}>
                      {Array.from({ length: 24 }, (_, i) => (
                        <option key={i} value={i}>
                          {i === 0 ? "12 AM" : i < 12 ? `${i} AM` : i === 12 ? "12 PM" : `${i - 12} PM`}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className={labelCls}>Minute</label>
                    <select value={minute} onChange={e => setMinute(parseInt(e.target.value, 10))}
                      className={inputCls}>
                      {[0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55].map(m => (
                        <option key={m} value={m}>{m.toString().padStart(2, "0")}</option>
                      ))}
                    </select>
                  </div>
                </div>
                {selectedDays.length === 0 && (
                  <p className="text-[10px] text-danger/70 px-1">Select at least one day</p>
                )}
              </>
            )}
          </div>

          <textarea value={message} onChange={e => setMessage(e.target.value)} placeholder="Message to send"
            rows={2} className={`${inputCls} resize-none`} />

          <div>
            <label className={labelCls}>Timezone</label>
            <select value={tz} onChange={e => setTz(e.target.value)} className={inputCls}>
              <option value="">Local (server default)</option>
              {COMMON_TZ.filter(Boolean).map(t => <option key={t} value={t}>{t.replace(/_/g, " ")}</option>)}
            </select>
          </div>

          <p className="text-11 font-semibold text-label-tertiary uppercase tracking-wider pt-2">Delivery</p>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={labelCls}>Channel</label>
              <select value={channel} onChange={e => setChannel(e.target.value)} className={inputCls}>
                <option value="web">Web (in-app)</option>
                <option value="telegram">Telegram</option>
              </select>
            </div>
            <div>
              <label className={labelCls}>Mode</label>
              <select value={payloadKind} onChange={e => setPayloadKind(e.target.value)} className={inputCls}>
                <option value="agentturn">AI response</option>
                <option value="systemevent">Notification only</option>
              </select>
            </div>
          </div>
          {channel === "telegram" && (
            <div>
              <label className={labelCls}>Telegram Chat ID</label>
              <input type="text" value={channelTarget} onChange={e => setChannelTarget(e.target.value)}
                placeholder="Chat ID" className={inputCls} />
            </div>
          )}
          <div className="flex items-center gap-4">
            <Toggle checked={tlgCall} onChange={setTlgCall} label="Voice call" />
          </div>

          {editId && (
            <div className="pt-1">
              <Toggle checked={jobs.find(j => j.id === editId)?.enabled !== false}
                onChange={() => { const j = jobs.find(j => j.id === editId); if (j) toggleEnabled(j); }}
                label="Enabled" />
            </div>
          )}

          <div className="flex gap-2 pt-1">
            <button onClick={save} disabled={!canSave}
              className="text-12 bg-accent hover:bg-accent-hover disabled:opacity-40 text-white px-4 py-1.5 rounded-lg transition-colors">
              {editId ? "Save" : "Create"}
            </button>
            <button onClick={() => { setAdding(false); setEditId(null); resetForm(); }}
              className="text-12 text-label-tertiary hover:text-label px-4 py-1.5">Cancel</button>
          </div>
        </div>
      )}

      <div className="space-y-1.5">
        {jobs.map(j => {
          const parsed = parseCron(j.cron_expr);
          return (
            <div key={j.id} className="flex items-center gap-3 bg-white/[.04] rounded-mac px-4 py-3 group">
              <div className="shrink-0">
                <Toggle checked={j.enabled !== false} onChange={() => toggleEnabled(j)} />
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-13 font-medium">{j.name}</p>
                <p className="text-11 text-label-tertiary mt-0.5 truncate">
                  {parsed
                    ? `${fmtDays(parsed.days)} at ${fmtTime(parsed.hour, parsed.minute)}`
                    : j.cron_expr
                  }
                  {j.message ? ` \u2014 ${j.message}` : ""}
                </p>
                <div className="flex items-center gap-2 mt-0.5 flex-wrap">
                  <span className="text-[10px] text-label-tertiary bg-white/[.04] px-1.5 py-0.5 rounded">{j.channel ?? "web"}</span>
                  {j.tz && <span className="text-[10px] text-label-tertiary">{j.tz?.replace(/_/g, " ")}</span>}
                  {j.next_run && <span className="text-[10px] text-label-tertiary">Next: {j.next_run}</span>}
                </div>
              </div>
              <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <button onClick={() => startEdit(j)} className="text-label-tertiary hover:text-label p-1.5"><IconEdit size={12} /></button>
                <button onClick={async () => { await deleteCron(j.id); load(); }} className="text-danger/50 hover:text-danger p-1.5"><IconTrash size={12} /></button>
              </div>
            </div>
          );
        })}
        {jobs.length === 0 && !adding && <p className="text-label-tertiary text-13">No scheduled jobs. Click + to add one.</p>}
      </div>
    </div>
  );
}
