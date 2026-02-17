import { useEffect, useState } from "react";
import type { CronJob } from "../api/client";
import { api } from "../api/client";

function formatCreatedAt(created_at: string) {
  if (!created_at) return "—";
  try {
    const d = new Date(created_at);
    return d.toLocaleString(undefined, { dateStyle: "short", timeStyle: "short" });
  } catch {
    return created_at;
  }
}

function CronJobRow({ job, onDelete, onUpdate }: { job: CronJob; onDelete: (id: number) => void; onUpdate: () => void }) {
  const [deleting, setDeleting] = useState(false);
  const [toggling, setToggling] = useState(false);

  const handleDelete = async () => {
    if (!window.confirm(`Are you sure you want to remove "${job.name}"?`)) return;
    setDeleting(true);
    try {
      await api.deleteCronJob(job.id);
      onDelete(job.id);
    } catch (e) {
      alert((e as Error).message);
      setDeleting(false);
    }
  };

  const toggleTelegram = async () => {
    setToggling(true);
    const newChannel = job.channel === "telegram" ? "web" : "telegram";
    try {
      await api.updateCronJob(job.id, { channel: newChannel });
      onUpdate();
    } catch (e) {
      alert("Failed to toggle channel: " + (e as Error).message);
    } finally {
      setToggling(false);
    }
  };

  const toggleEnabled = async () => {
    setToggling(true);
    try {
      await api.updateCronJob(job.id, { enabled: !job.enabled });
      onUpdate();
    } catch (e) {
      alert("Failed to toggle status: " + (e as Error).message);
    } finally {
      setToggling(false);
    }
  };

  const toggleMode = async () => {
    setToggling(true);
    const newKind = job.payload_kind === "agentturn" ? "systemevent" : "agentturn";
    try {
      await api.updateCronJob(job.id, { payload_kind: newKind });
      onUpdate();
    } catch (e) {
      alert("Failed to toggle mode: " + (e as Error).message);
    } finally {
      setToggling(false);
    }
  };

  const toggleCall = async () => {
    setToggling(true);
    try {
      await api.updateCronJob(job.id, { tlg_call: !job.tlg_call });
      onUpdate();
    } catch (e) {
      alert("Failed to toggle call: " + (e as Error).message);
    } finally {
      setToggling(false);
    }
  };

  return (
    <tr>
      <td className="cron-name">{job.name}</td>
      <td className="cron-expr">
        {job.cron_expr.startsWith("@at ") ? (
          <span className="badge badge-info" title={job.cron_expr}>One-Shot</span>
        ) : (
          <code>{job.cron_expr}</code>
        )}
      </td>
      <td className="cron-tz">{job.tz || "—"}</td>
      <td className="cron-message" title={job.message}>
        {job.message.length > 60 ? job.message.slice(0, 60) + "…" : job.message}
      </td>
      <td className="cron-channel">
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <button
            className={`btn btn-sm ${job.channel === "telegram" ? "btn-primary" : "btn-secondary"}`}
            onClick={(e) => {
              e.stopPropagation();
              toggleTelegram();
            }}
            disabled={toggling}
          >
            {toggling ? "..." : (job.channel === "telegram" ? "Telegram" : "Web")}
          </button>
          {job.channel_target && job.channel !== "web" && (
            <span style={{ opacity: 0.7, fontSize: "0.8em" }}>{job.channel_target}</span>
          )}
        </div>
      </td>
      <td className="cron-mode">
        <button
          className={`btn btn-sm ${job.payload_kind === "agentturn" ? "btn-primary" : "btn-secondary"}`}
          onClick={(e) => {
            e.stopPropagation();
            toggleMode();
          }}
          disabled={toggling}
          title={job.payload_kind === "agentturn" ? "Calls AI to process the message" : "Directly sends the message as a notification"}
        >
          {job.payload_kind === "agentturn" ? "Call AI" : "Notify"}
        </button>
      </td>
      <td className="cron-call">
        <button
          className={`btn btn-sm ${job.tlg_call ? "btn-primary" : "btn-secondary"}`}
          onClick={(e) => {
            e.stopPropagation();
            toggleCall();
          }}
          disabled={toggling}
          title="Trigger an automated voice call when job runs (requires phone number in channel target)"
        >
          {job.tlg_call ? "Call" : "No Call"}
        </button>
      </td>
      <td className="cron-created">{formatCreatedAt(job.created_at)}</td>
      <td className="cron-status">
        <button
          className={`btn btn-sm ${job.enabled ? "btn-success" : "btn-outline"}`}
          onClick={(e) => {
            e.stopPropagation();
            toggleEnabled();
          }}
          disabled={toggling}
        >
          {job.enabled ? "On" : "Off"}
        </button>
      </td>
      <td>
        <button
          type="button"
          className="btn btn-danger btn-sm"
          onClick={handleDelete}
          disabled={deleting}
          aria-label={`Remove ${job.name}`}
        >
          {deleting ? "Removing…" : "Remove"}
        </button>
      </td>
    </tr>
  );
}

export default function Cron() {
  const [jobs, setJobs] = useState<CronJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    setError(null);
    api
      .getCronJobs()
      .then((r) => setJobs(r.cron_jobs || []))
      .catch((e) => setError((e as Error).message))
      .finally(() => setLoading(false));
  };

  const [showForm, setShowForm] = useState(false);
  const [creating, setCreating] = useState(false);

  // Form fields
  const [newName, setNewName] = useState("");
  const [newCron, setNewCron] = useState("");
  const [newTz, setNewTz] = useState("");
  const [newMessage, setNewMessage] = useState("");
  const [newChannel, setNewChannel] = useState("web");
  const [newTarget, setNewTarget] = useState("");
  const [newKind, setNewKind] = useState("agentturn");
  const [newTlgCall, setNewTlgCall] = useState(false);

  const handleCreate = async () => {
    if (!newName || !newCron || !newMessage) {
      alert("Please fill in Name, Schedule, and Message.");
      return;
    }

    setCreating(true);
    try {
      await api.addCronJob({
        name: newName,
        cron_expr: newCron,
        message: newMessage,
        tz: newTz,
        channel: newChannel,
        channel_target: newTarget,
        payload_kind: newKind,
        tlg_call: newTlgCall
      });
      // Refresh list
      await load();
      // Reset form
      setNewName("");
      setNewCron("");
      setNewMessage("");
      setNewTlgCall(false);
      setShowForm(false);
    } catch (e) {
      alert("Failed to create job: " + (e as Error).message);
    } finally {
      setCreating(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const removeFromList = (id: number) => {
    setJobs((prev) => prev.filter((j) => j.id !== id));
  };

  return (
    <div className="cron-page">
      <div className="page-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h1 className="page-title" style={{ margin: 0 }}>Cron</h1>
        <button
          className="btn btn-primary"
          onClick={() => setShowForm(!showForm)}
        >
          {showForm ? "Cancel" : "New Job"}
        </button>
      </div>

      <p className="help" style={{ marginBottom: "1rem" }}>
        Recurring jobs and one-shot reminders scheduled by the AI or via the API.
        When a job runs, its message is sent to the AI (Agent Turn) or delivered directly as a notification.
        One-shot reminders are shown with <code>@at</code> followed by their scheduled time.
      </p>

      {error && (
        <div className="alert alert-error" style={{ marginBottom: "1rem" }}>
          {error}
        </div>
      )}

      {showForm && (
        <div className="card" style={{ marginBottom: "2rem", padding: "1.5rem" }}>
          <h3 style={{ marginTop: 0 }}>Create New Job</h3>
          <form onSubmit={(e) => { e.preventDefault(); handleCreate(); }}>
            <div className="field">
              <label className="label">Name</label>
              <input
                className="input"
                value={newName}
                onChange={e => setNewName(e.target.value)}
                placeholder="Morning Routine"
                required
              />
            </div>

            <div className="field-row">
              <div className="field" style={{ flex: 1 }}>
                <label className="label">Schedule (Cron)</label>
                <input
                  className="input"
                  value={newCron}
                  onChange={e => setNewCron(e.target.value)}
                  placeholder="0 8 * * *"
                  required
                />
              </div>
              <div className="field" style={{ flex: 1 }}>
                <label className="label">Timezone (Optional)</label>
                <input
                  className="input"
                  value={newTz}
                  onChange={e => setNewTz(e.target.value)}
                  placeholder="America/New_York"
                />
              </div>
            </div>

            <div className="field">
              <label className="label">Instructions / Message</label>
              <textarea
                className="input"
                value={newMessage}
                onChange={e => setNewMessage(e.target.value)}
                placeholder="Check my calendar and tell me the agenda."
                rows={3}
                required
              />
            </div>

            <div className="field-row">
              <div className="field" style={{ flex: 1 }}>
                <label className="label">Channel</label>
                <select
                  className="select"
                  value={newChannel}
                  onChange={e => setNewChannel(e.target.value)}
                >
                  <option value="web">Web (Notification)</option>
                  <option value="telegram">Telegram</option>
                  <option value="whatsapp">WhatsApp</option>
                </select>
              </div>

              <div className="field" style={{ flex: 1 }}>
                <label className="label">Mode</label>
                <select
                  className="select"
                  value={newKind}
                  onChange={e => setNewKind(e.target.value)}
                >
                  <option value="agentturn">Call AI (Agent Turn)</option>
                  <option value="systemevent">Notify Only (Direct)</option>
                </select>
              </div>

              <div className="field" style={{ flex: 1, display: "flex", alignItems: "flex-end" }}>
                <label style={{ display: "inline-flex", alignItems: "center", gap: "0.5rem", cursor: "pointer" }}>
                  <input
                    type="checkbox"
                    checked={newTlgCall}
                    onChange={(e) => setNewTlgCall(e.target.checked)}
                  />
                  Voice Call (Pingram/Phone)
                </label>
              </div>
            </div>

            {newChannel !== "web" && (
              <div className="field">
                <label className="label">Target (Chat ID / Number)</label>
                <input
                  className="input"
                  value={newTarget}
                  onChange={e => setNewTarget(e.target.value)}
                  placeholder={newChannel === "telegram" ? "123456789" : "+1234567890"}
                  required
                />
              </div>
            )}

            {newChannel === "telegram" && !newTarget && (
              <p className="help">
                To get your ID, message the bot on Telegram.
              </p>
            )}

            <div className="actions">
              <button type="submit" className="btn btn-primary" disabled={creating}>
                {creating ? "Creating..." : "Create Job"}
              </button>
            </div>
          </form>
        </div>
      )}

      {loading ? (
        <p>Loading scheduled tasks…</p>
      ) : jobs.length === 0 ? (
        <div className="cron-empty">
          <p>No cron jobs scheduled.</p>
          <p className="help">You can ask Asta to schedule one (e.g. “Remind me every day at 9am”) or use the New Job button above.</p>
        </div>
      ) : (
        <div className="table-wrap">
          <table className="cron-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Schedule</th>
                <th>Timezone</th>
                <th>Message</th>
                <th>Channel</th>
                <th>Mode</th>
                <th>Call</th>
                <th>Created</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((job) => (
                <CronJobRow key={job.id} job={job} onDelete={removeFromList} onUpdate={load} />
              ))}
            </tbody>
            <style>{`
        .badge {
            font-size: 0.7rem;
            padding: 2px 6px;
            border-radius: 4px;
            font-weight: 700;
            text-transform: uppercase;
        }
        .badge-info {
            background: rgba(var(--rgb-accent), 0.15);
            color: var(--accent);
            border: 1px solid rgba(var(--rgb-accent), 0.2);
        }
      `}</style>
          </table>
        </div>
      )}
    </div>
  );
}
