import { useState, useEffect } from "react";
import { getSecurityAudit } from "../../../lib/api";
import { IconWarning, IconCheck } from "../../../lib/icons";

export default function TabPermissions() {
  const [audit, setAudit] = useState<any>(null);

  useEffect(() => {
    getSecurityAudit().then(setAudit).catch(()=>{});
  }, []);

  const warnings = audit?.warnings ?? [];

  return (
    <div className="text-label space-y-5">
      <h2 className="text-15 font-semibold">Permissions</h2>
      <p className="text-13 text-label-secondary">
        Security audit of your Asta configuration. Warnings indicate potential issues.
      </p>
      {audit === null && <p className="text-13 text-label-tertiary">Loading…</p>}
      {audit && warnings.length === 0 && (
        <div className="bg-success/10 border border-success/20 rounded-mac px-4 py-3 flex items-center gap-2">
          <IconCheck size={14} className="text-success" />
          <span className="text-13 text-success">All checks passed — no warnings</span>
        </div>
      )}
      {warnings.length > 0 && (
        <div className="space-y-2">
          {warnings.map((w: any, i: number) => (
            <div key={i} className="bg-warning/10 border border-warning/20 rounded-mac px-4 py-3 flex items-start gap-2">
              <IconWarning size={14} className="text-warning shrink-0 mt-0.5" />
              <div>
                <p className="text-13 text-warning font-medium">{w.title ?? w}</p>
                {w.detail && <p className="text-12 text-label-tertiary mt-0.5">{w.detail}</p>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
