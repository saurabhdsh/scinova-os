import { useEffect, useState } from 'react';
import GlassPanel from '../../components/ui/GlassPanel';
import { getLabAgentHealth, getLabAudit, invokeLabAgent, labError } from '../../api/lab';
import { StatusPill, useLab } from './LabShell';

export default function AuditConsole() {
  const { experimentId } = useLab();
  const [events, setEvents] = useState([]);
  const [health, setHealth] = useState(null);
  const [job, setJob] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!experimentId) return;
    getLabAudit(experimentId).then((response) => setEvents(response.data)).catch((err) => setError(labError(err)));
    getLabAgentHealth('LAB-A6').then((response) => setHealth(response.data)).catch(() => {});
  }, [experimentId]);

  const runHealthJob = async () => {
    setError('');
    try {
      const response = await invokeLabAgent('LAB-A1', { trigger: 'what_if', experiment_id: experimentId, context: {} });
      setJob(response.data);
    } catch (err) {
      setError(labError(err));
    }
  };

  return (
    <div className="space-y-5">
      <GlassPanel>
        <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim">Agent execution and audit</p>
        <button type="button" onClick={runHealthJob} disabled={!experimentId} className="mt-3 rounded-xl border border-cx-border px-3 py-2 text-sm disabled:opacity-50">Invoke LAB-A1 what-if</button>
        {job && <p className="mt-3 text-sm">Job {job.id} <StatusPill value={job.status} /> correlation {job.correlation_id}</p>}
        {health && (
          <p className="mt-3 text-sm text-cx-fgMuted">
            Landing zone {health.dependencies.landing_zone.mode}, simulation {String(health.dependencies.landing_zone.simulation)}. ExperimentCompleted flag {String(health.dependencies.experiment_completed_flag)}.
          </p>
        )}
        {error && <p className="mt-3 text-sm text-rose-700">{error}</p>}
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-cx-fgDim"><tr><th className="py-2">When</th><th>Actor</th><th>Event</th><th>Action</th></tr></thead>
            <tbody>
              {events.map((row) => (
                <tr key={row.id} className="border-t border-cx-line align-top">
                  <td className="py-2 whitespace-nowrap">{row.created_at}</td>
                  <td>{row.actor}</td>
                  <td>{row.event_type}</td>
                  <td>{row.action}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </GlassPanel>
    </div>
  );
}
