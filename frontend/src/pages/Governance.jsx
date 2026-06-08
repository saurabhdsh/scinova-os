import { useEffect, useState, useCallback } from 'react';
import { Shield, AlertTriangle, CheckCircle, XCircle, Clock } from 'lucide-react';
import GlassPanel from '../components/ui/GlassPanel';
import {
  getAuditEvents, getRiskAlerts, getApprovals, processApproval, getGxpCheck, acknowledgeRiskAlert,
} from '../api/client';

export default function Governance() {
  const [audit, setAudit] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [approvals, setApprovals] = useState([]);
  const [gxp, setGxp] = useState(null);

  const load = useCallback(() => {
    getAuditEvents().then((r) => setAudit(r.data)).catch(console.error);
    getRiskAlerts().then((r) => setAlerts(r.data)).catch(console.error);
    getApprovals().then((r) => setApprovals(r.data)).catch(console.error);
    getGxpCheck().then((r) => setGxp(r.data)).catch(console.error);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleApproval = async (id, decision) => {
    await processApproval({ approval_id: id, decision });
    load();
  };

  const handleAcknowledge = async (id) => {
    await acknowledgeRiskAlert(id);
    load();
  };

  const gxpStatus = gxp?.status || 'attention';
  const gxpLabel = gxpStatus === 'pass' ? 'Pass' : gxpStatus === 'fail' ? 'Fail' : 'Attention';

  return (
    <div className="p-6 space-y-6">
      <GlassPanel hero>
        <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim">Compliance & Traceability</p>
        <h2 className="font-display text-xl font-semibold mt-1">Governance & Compliance</h2>
        <p className="text-sm text-cx-fgMuted mt-2">
          Live audit trail, workflow approval gates, risk alerts, and computed GxP readiness checks.
        </p>
      </GlassPanel>

      <div className="grid sm:grid-cols-4 gap-4">
        <GlassPanel className="p-4">
          <Shield size={18} className="text-cx-accent mb-2" />
          <p className="text-2xs uppercase tracking-wider text-cx-fgDim">Audit Events</p>
          <p className="font-display text-2xl font-semibold mt-1">{audit.length}</p>
        </GlassPanel>
        <GlassPanel className="p-4">
          <AlertTriangle size={18} className="text-cx-warn mb-2" />
          <p className="text-2xs uppercase tracking-wider text-cx-fgDim">Open Risks</p>
          <p className="font-display text-2xl font-semibold mt-1">{alerts.filter((a) => a.status === 'open').length}</p>
        </GlassPanel>
        <GlassPanel className="p-4">
          <Clock size={18} className="text-cx-accent2 mb-2" />
          <p className="text-2xs uppercase tracking-wider text-cx-fgDim">Pending Approvals</p>
          <p className="font-display text-2xl font-semibold mt-1">{approvals.filter((a) => a.status === 'pending').length}</p>
        </GlassPanel>
        <GlassPanel className="p-4">
          <CheckCircle size={18} className={gxpStatus === 'pass' ? 'text-cx-success mb-2' : gxpStatus === 'fail' ? 'text-cx-danger mb-2' : 'text-cx-warn mb-2'} />
          <p className="text-2xs uppercase tracking-wider text-cx-fgDim">GxP Checks</p>
          <p className={`font-display text-2xl font-semibold mt-1 ${
            gxpStatus === 'pass' ? 'text-cx-success' : gxpStatus === 'fail' ? 'text-cx-danger' : 'text-cx-warn'
          }`}>{gxpLabel}</p>
        </GlassPanel>
      </div>

      {gxp?.checks && (
        <GlassPanel>
          <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim mb-3">GxP Readiness</p>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {gxp.checks.map((check) => (
              <div key={check.name} className="p-3 rounded-xl border border-cx-border bg-white/40">
                <p className="text-sm font-medium">{check.name}</p>
                <p className={`text-2xs uppercase mt-1 ${
                  check.status === 'pass' ? 'text-cx-success' : check.status === 'fail' ? 'text-cx-danger' : 'text-cx-warn'
                }`}>{check.status}</p>
                <p className="text-xs text-cx-fgDim mt-1">{check.detail}</p>
              </div>
            ))}
          </div>
        </GlassPanel>
      )}

      <div className="grid lg:grid-cols-2 gap-6">
        <GlassPanel>
          <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim mb-4">Risk Alerts</p>
          <div className="space-y-2 max-h-80 overflow-y-auto">
            {alerts.map((a) => (
              <div key={a.id} className="p-3 rounded-xl border border-cx-border bg-white/40">
                <div className="flex items-start justify-between gap-2">
                  <p className="text-sm font-medium">{a.title}</p>
                  <span className={`text-2xs uppercase shrink-0 px-2 py-0.5 rounded-md ${
                    a.severity === 'high' ? 'text-cx-danger bg-cx-danger/5' : 'text-cx-warn bg-cx-warn/5'
                  }`}>{a.severity}</span>
                </div>
                <p className="text-xs text-cx-fgDim mt-1">{a.category} · {a.status}</p>
                {a.status === 'open' && (
                  <button
                    type="button"
                    onClick={() => handleAcknowledge(a.id)}
                    className="mt-2 text-2xs text-cx-accent hover:underline"
                  >
                    Acknowledge
                  </button>
                )}
              </div>
            ))}
          </div>
        </GlassPanel>

        <GlassPanel>
          <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim mb-4">Human Approvals</p>
          <div className="space-y-2 max-h-80 overflow-y-auto">
            {approvals.map((a) => (
              <div key={a.id} className="p-3 rounded-xl border border-cx-border bg-white/40">
                <p className="text-sm font-medium">{a.title}</p>
                <p className="text-xs text-cx-fgDim mt-1">{a.request_type} · {a.requested_by}</p>
                {a.workflow_run_id && (
                  <p className="text-2xs font-mono text-cx-fgDim mt-1">Workflow: {a.workflow_run_id.slice(0, 8)}…</p>
                )}
                {a.status === 'pending' ? (
                  <div className="flex gap-2 mt-2">
                    <button type="button" onClick={() => handleApproval(a.id, 'approved')} className="flex items-center gap-1 px-3 py-1 rounded-lg text-xs border border-cx-success/30 text-cx-success hover:bg-cx-success/5">
                      <CheckCircle size={12} /> Approve
                    </button>
                    <button type="button" onClick={() => handleApproval(a.id, 'rejected')} className="flex items-center gap-1 px-3 py-1 rounded-lg text-xs border border-cx-danger/30 text-cx-danger hover:bg-cx-danger/5">
                      <XCircle size={12} /> Reject
                    </button>
                  </div>
                ) : (
                  <span className={`inline-block mt-2 text-2xs uppercase px-2 py-0.5 rounded-md ${
                    a.status === 'approved' ? 'text-cx-success bg-cx-success/5' : 'text-cx-danger bg-cx-danger/5'
                  }`}>{a.status}</span>
                )}
              </div>
            ))}
          </div>
        </GlassPanel>
      </div>

      <GlassPanel>
        <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim mb-4">Audit Trail</p>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-2xs uppercase tracking-wider text-cx-fgDim border-b border-cx-line">
                <th className="pb-2 pr-4">Time</th>
                <th className="pb-2 pr-4">Actor</th>
                <th className="pb-2 pr-4">Event</th>
                <th className="pb-2">Action</th>
              </tr>
            </thead>
            <tbody>
              {audit.map((e) => (
                <tr key={e.id} className="border-b border-cx-line/50">
                  <td className="py-2.5 pr-4 font-mono text-xs text-cx-fgDim">{e.created_at?.slice(0, 16).replace('T', ' ')}</td>
                  <td className="py-2.5 pr-4">{e.actor}</td>
                  <td className="py-2.5 pr-4 text-cx-fgMuted">{e.event_type}</td>
                  <td className="py-2.5">{e.action}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </GlassPanel>
    </div>
  );
}
