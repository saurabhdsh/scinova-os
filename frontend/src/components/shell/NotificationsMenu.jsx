import { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  AlertTriangle, Bell, CheckCircle, Clock, FileText, Loader2, Workflow,
} from 'lucide-react';
import {
  acknowledgeRiskAlert, getCollaborationActivity, processApproval,
} from '../../api/client';

function severityClass(severity) {
  if (severity === 'high') return 'text-cx-danger';
  if (severity === 'medium') return 'text-cx-warn';
  return 'text-cx-fgMuted';
}

export default function NotificationsMenu({ open, onClose, onCountChange }) {
  const panelRef = useRef(null);
  const [loading, setLoading] = useState(false);
  const [activity, setActivity] = useState(null);
  const [acting, setActing] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await getCollaborationActivity();
      setActivity(r.data);
      const count = (r.data?.open_risks?.length || 0) + (r.data?.pending_approvals?.length || 0);
      onCountChange?.(count);
    } catch {
      setActivity(null);
      onCountChange?.(0);
    } finally {
      setLoading(false);
    }
  }, [onCountChange]);

  useEffect(() => {
    if (open) load();
  }, [open, load]);

  useEffect(() => {
    if (!open) return undefined;
    const onPointerDown = (e) => {
      if (panelRef.current && !panelRef.current.contains(e.target)) {
        onClose();
      }
    };
    document.addEventListener('mousedown', onPointerDown);
    return () => document.removeEventListener('mousedown', onPointerDown);
  }, [open, onClose]);

  const handleAcknowledge = async (id) => {
    setActing(id);
    try {
      await acknowledgeRiskAlert(id);
      await load();
    } finally {
      setActing(null);
    }
  };

  const handleApproval = async (id, decision) => {
    setActing(id);
    try {
      await processApproval({ approval_id: id, decision });
      await load();
    } finally {
      setActing(null);
    }
  };

  if (!open) return null;

  const risks = activity?.open_risks || [];
  const approvals = activity?.pending_approvals || [];
  const recentWorkflows = (activity?.recent_workflows || []).slice(0, 3);
  const recentDocs = (activity?.recent_documents || []).slice(0, 3);
  const empty = !loading && risks.length === 0 && approvals.length === 0
    && recentWorkflows.length === 0 && recentDocs.length === 0;

  return (
    <div
      ref={panelRef}
      className="absolute right-0 top-full mt-2 w-[360px] max-h-[70vh] overflow-hidden rounded-2xl border border-cx-border bg-white/95 shadow-2xl backdrop-blur-xl z-50 flex flex-col"
    >
      <div className="px-4 py-3 border-b border-cx-line flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Bell size={16} className="text-cx-accent" />
          <p className="text-sm font-semibold text-cx-fg">Notifications</p>
        </div>
        <Link
          to="/governance"
          onClick={onClose}
          className="text-2xs text-cx-accent hover:underline"
        >
          View all
        </Link>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-4">
        {loading && (
          <div className="flex items-center justify-center py-8 text-cx-fgMuted">
            <Loader2 size={18} className="animate-spin mr-2" />
            Loading…
          </div>
        )}

        {empty && (
          <div className="py-8 text-center">
            <CheckCircle size={28} className="mx-auto text-cx-success mb-2" />
            <p className="text-sm text-cx-fgMuted">You&apos;re all caught up.</p>
          </div>
        )}

        {approvals.length > 0 && (
          <section>
            <p className="text-2xs uppercase tracking-wider text-cx-fgDim px-1 mb-2 flex items-center gap-1">
              <Clock size={12} /> Pending approvals ({approvals.length})
            </p>
            <div className="space-y-2">
              {approvals.map((a) => (
                <div key={a.id} className="p-3 rounded-xl border border-cx-border bg-white/60">
                  <p className="text-sm font-medium text-cx-fg">{a.title}</p>
                  <p className="text-2xs text-cx-fgDim mt-0.5 capitalize">{a.type || a.request_type || 'approval'}</p>
                  <div className="flex gap-2 mt-2">
                    <button
                      type="button"
                      disabled={acting === a.id}
                      onClick={() => handleApproval(a.id, 'approved')}
                      className="flex-1 py-1.5 text-2xs rounded-lg border border-cx-success/30 text-cx-success hover:bg-cx-success/5 disabled:opacity-50"
                    >
                      Approve
                    </button>
                    <button
                      type="button"
                      disabled={acting === a.id}
                      onClick={() => handleApproval(a.id, 'rejected')}
                      className="flex-1 py-1.5 text-2xs rounded-lg border border-cx-danger/30 text-cx-danger hover:bg-cx-danger/5 disabled:opacity-50"
                    >
                      Reject
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        {risks.length > 0 && (
          <section>
            <p className="text-2xs uppercase tracking-wider text-cx-fgDim px-1 mb-2 flex items-center gap-1">
              <AlertTriangle size={12} /> Risk alerts ({risks.length})
            </p>
            <div className="space-y-2">
              {risks.map((r) => (
                <div key={r.id} className="p-3 rounded-xl border border-cx-border bg-white/60">
                  <p className={`text-sm font-medium ${severityClass(r.severity)}`}>{r.title}</p>
                  {r.description && (
                    <p className="text-2xs text-cx-fgMuted mt-1 line-clamp-2">{r.description}</p>
                  )}
                  <button
                    type="button"
                    disabled={acting === r.id}
                    onClick={() => handleAcknowledge(r.id)}
                    className="mt-2 text-2xs text-cx-accent hover:underline disabled:opacity-50"
                  >
                    {acting === r.id ? 'Acknowledging…' : 'Acknowledge'}
                  </button>
                </div>
              ))}
            </div>
          </section>
        )}

        {recentWorkflows.length > 0 && (
          <section>
            <p className="text-2xs uppercase tracking-wider text-cx-fgDim px-1 mb-2 flex items-center gap-1">
              <Workflow size={12} /> Recent workflows
            </p>
            <div className="space-y-1">
              {recentWorkflows.map((w) => (
                <Link
                  key={w.id}
                  to="/workflows"
                  onClick={onClose}
                  className="block px-3 py-2 rounded-xl hover:bg-cx-accent/5 text-sm text-cx-fg truncate"
                >
                  {w.name || w.template_name || 'Workflow run'}
                  <span className="text-2xs text-cx-fgDim ml-2 capitalize">{w.status}</span>
                </Link>
              ))}
            </div>
          </section>
        )}

        {recentDocs.length > 0 && (
          <section>
            <p className="text-2xs uppercase tracking-wider text-cx-fgDim px-1 mb-2 flex items-center gap-1">
              <FileText size={12} /> Recent documents
            </p>
            <div className="space-y-1">
              {recentDocs.map((d, i) => (
                <Link
                  key={d.id || `${d.title}-${i}`}
                  to="/documents"
                  onClick={onClose}
                  className="block px-3 py-2 rounded-xl hover:bg-cx-accent/5 text-sm text-cx-fg truncate"
                >
                  {d.title || d.filename || 'Document'}
                </Link>
              ))}
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
