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

function CronJobRow({ job, onDelete }: { job: CronJob; onDelete: (id: number) => void }) {
  const [deleting, setDeleting] = useState(false);
  const handleDelete = () => {
    if (!confirm(`Remove cron job "${job.name}"?`)) return;
    setDeleting(true);
    api
      .deleteCronJob(job.id)
      .then(() => onDelete(job.id))
      .catch((e) => alert((e as Error).message))
      .finally(() => setDeleting(false));
  };
  return (
    <tr>
      <td className="cron-name">{job.name}</td>
      <td className="cron-expr">
        <code>{job.cron_expr}</code>
      </td>
      <td className="cron-tz">{job.tz || "—"}</td>
      <td className="cron-message" title={job.message}>
        {job.message.length > 60 ? job.message.slice(0, 60) + "…" : job.message}
      </td>
      <td className="cron-created">{formatCreatedAt(job.created_at)}</td>
      <td className="cron-enabled">{job.enabled ? "On" : "Off"}</td>
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

  useEffect(() => {
    load();
  }, []);

  const removeFromList = (id: number) => {
    setJobs((prev) => prev.filter((j) => j.id !== id));
  };

  return (
    <div className="cron-page">
      <h1 className="page-title">Cron</h1>
      <p className="help" style={{ marginBottom: "1rem" }}>
        Recurring jobs scheduled by the AI or via the API. When a job runs, its message is sent to the AI and the reply is delivered to you (web, Telegram, or WhatsApp). Use 5-field cron: <code>minute hour day month day_of_week</code> (e.g. <code>0 8 * * *</code> = daily at 8:00).
      </p>

      {error && (
        <div className="alert alert-error" style={{ marginBottom: "1rem" }}>
          {error}
        </div>
      )}

      {loading ? (
        <p>Loading scheduled tasks…</p>
      ) : jobs.length === 0 ? (
        <div className="cron-empty">
          <p>No cron jobs scheduled.</p>
          <p className="help">You can ask Asta to schedule one (e.g. “Remind me every day at 9am”) or add one via the API.</p>
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
                <th>Created</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((job) => (
                <CronJobRow key={job.id} job={job} onDelete={removeFromList} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
