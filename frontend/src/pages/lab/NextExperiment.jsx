import { useState } from 'react';
import GlassPanel from '../../components/ui/GlassPanel';
import { createFollowUp, getLabWhatIf, labError } from '../../api/lab';
import { StatusPill, useLab } from './LabShell';

export default function NextExperiment() {
  const { experimentId } = useLab();
  const [preview, setPreview] = useState(null);
  const [plan, setPlan] = useState(null);
  const [error, setError] = useState('');

  const loadPreview = async () => {
    setError('');
    try {
      const response = await getLabWhatIf(experimentId);
      setPreview(response.data);
    } catch (err) {
      setError(labError(err));
    }
  };

  const persist = async () => {
    setError('');
    try {
      const response = await createFollowUp(experimentId);
      setPlan(response.data);
    } catch (err) {
      setError(labError(err));
    }
  };

  const change = preview?.change;

  return (
    <div className="space-y-5">
      <GlassPanel>
        <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim">Moment 5 — learning and next experiment</p>
        <h2 className="font-display text-xl mt-1">LAB-A1 consumes the cited insight</h2>
        <div className="mt-4 flex gap-2">
          <button type="button" onClick={loadPreview} disabled={!experimentId} className="rounded-xl border border-cx-border px-3 py-2 text-sm disabled:opacity-50">Preview what-if</button>
          <button type="button" onClick={persist} disabled={!experimentId} className="rounded-xl bg-cx-accent text-white px-3 py-2 text-sm disabled:opacity-50">Create follow-up plan</button>
        </div>
        {error && <p className="mt-3 text-sm text-rose-700">{error}</p>}
        {change && (
          <div className="mt-4 text-sm">
            <p className="font-medium">{change.parameter}</p>
            <p className="mt-1">{change.from} → {change.to}</p>
            <p className="mt-1 text-cx-fgMuted">Rule {change.rule_id}. Insight {change.insight_id}. This preview is not saved.</p>
          </div>
        )}
        {plan && (
          <div className="mt-4 rounded-xl border border-cx-border p-4 text-sm">
            <div className="flex items-center gap-2"><p className="font-medium">{plan.title}</p><StatusPill value={plan.status} /></div>
            <p className="mt-2">Seeding density: {plan.parameters_json?.seeding_density_cells_per_ml}</p>
            <p className="mt-1 text-cx-fgMuted">Cited insights: {(plan.cited_insight_ids_json || []).join(', ')}</p>
            <p className="mt-2 text-xs text-cx-fgDim">The follow-up plan stays in draft until a scientist approves gate G1.</p>
          </div>
        )}
      </GlassPanel>
    </div>
  );
}
