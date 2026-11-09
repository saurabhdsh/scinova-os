import { useEffect, useState } from 'react';
import GlassPanel from '../../components/ui/GlassPanel';
import { evaluateReadiness, getLabIssues, labError, resolveLabIssue } from '../../api/lab';
import { StatusPill, useLab } from './LabShell';

export default function ReadinessCockpit() {
  const { experimentId } = useLab();
  const [issues, setIssues] = useState([]);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  const load = () => {
    if (!experimentId) return;
    getLabIssues(experimentId).then((response) => setIssues(response.data)).catch((err) => setError(labError(err)));
  };

  useEffect(() => { load(); }, [experimentId]);

  const evaluate = async () => {
    setError('');
    try {
      const response = await evaluateReadiness(experimentId);
      setIssues(response.data);
      setMessage('LAB-A2 through LAB-A5 evaluated this experiment.');
    } catch (err) {
      setError(labError(err));
    }
  };

  const resolve = async (issue) => {
    setError('');
    try {
      await resolveLabIssue(issue.id, { decision: 'approve', comment: `Scientist approves corrective action for ${issue.code} at gate G2.` });
      setMessage(`${issue.code} resolved and audited at G2.`);
      load();
    } catch (err) {
      setError(labError(err));
    }
  };

  return (
    <div className="space-y-5">
      <GlassPanel>
        <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim">Moment 2 — readiness and compliance</p>
        <h2 className="font-display text-xl mt-1">Seeded issues require an explicit decision</h2>
        {!experimentId && <p className="mt-3 text-sm text-cx-fgMuted">Approve a plan in Planning before evaluating readiness.</p>}
        <button type="button" onClick={evaluate} disabled={!experimentId} className="mt-4 rounded-xl bg-cx-accent text-white px-3 py-2 text-sm disabled:opacity-50">Evaluate readiness</button>
        {message && <p className="mt-3 text-sm text-emerald-800">{message}</p>}
        {error && <p className="mt-3 text-sm text-rose-700">{error}</p>}
        <div className="mt-4 space-y-3">
          {issues.map((issue) => (
            <div key={issue.id} className="rounded-xl border border-cx-border p-4">
              <div className="flex flex-wrap items-center gap-2">
                <p className="font-medium text-sm">{issue.agent_id} · {issue.code}</p>
                <StatusPill value={issue.status} />
                <StatusPill value={issue.severity} />
              </div>
              <p className="mt-2 text-sm text-cx-fgMuted">{issue.message}</p>
              <p className="mt-2 text-xs text-cx-fgDim">Recommended action: {JSON.stringify(issue.recommendation_json)}</p>
              {issue.status === 'open' && (
                <button type="button" onClick={() => resolve(issue)} className="mt-3 rounded-xl border border-cx-accent text-cx-accent px-3 py-1.5 text-sm">
                  Approve corrective action (G2)
                </button>
              )}
            </div>
          ))}
        </div>
      </GlassPanel>
    </div>
  );
}
