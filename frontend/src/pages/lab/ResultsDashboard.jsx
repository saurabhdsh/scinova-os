import { useEffect, useState } from 'react';
import { Bar, BarChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import GlassPanel from '../../components/ui/GlassPanel';
import { compileLabResults, getLabIngestion, getLabResults, labError } from '../../api/lab';
import { StatusPill, useLab } from './LabShell';

export default function ResultsDashboard() {
  const { experimentId } = useLab();
  const [payload, setPayload] = useState(null);
  const [chart, setChart] = useState([]);
  const [error, setError] = useState('');

  const load = async () => {
    if (!experimentId) return;
    const [results, ingestion] = await Promise.all([getLabResults(experimentId), getLabIngestion(experimentId)]);
    setPayload(results.data);
    setChart(
      (ingestion.data.measurements || [])
        .filter((row) => row.readout_key === 'viability_percent' && row.sample_id)
        .map((row) => ({ name: row.sample_code_observed, viability: row.value })),
    );
  };

  useEffect(() => { load().catch((err) => setError(labError(err))); }, [experimentId]);

  const compile = async () => {
    setError('');
    try {
      await compileLabResults(experimentId);
      await load();
    } catch (err) {
      setError(labError(err));
    }
  };

  return (
    <div className="space-y-5">
      <GlassPanel>
        <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim">Moment 4 — scientific results</p>
        <div className="mt-3 flex items-center gap-3">
          <button type="button" onClick={compile} disabled={!experimentId} className="rounded-xl bg-cx-accent text-white px-3 py-2 text-sm disabled:opacity-50">Compile results</button>
          {payload?.results?.[0] && <StatusPill value={payload.results.find((row) => row.metric === 'mean_viability_percent')?.outcome} />}
        </div>
        {error && <p className="mt-3 text-sm text-rose-700">{error}</p>}
        <div className="mt-4 h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chart}>
              <XAxis dataKey="name" tick={{ fontSize: 11 }} />
              <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
              <Tooltip />
              <ReferenceLine y={85} stroke="#d97706" strokeDasharray="4 4" label="85%" />
              <Bar dataKey="viability" fill="#0891b2" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </GlassPanel>
      <div className="grid lg:grid-cols-2 gap-4">
        <GlassPanel>
          <p className="font-medium text-sm mb-3">Criteria</p>
          {(payload?.results || []).map((row) => (
            <div key={row.id} className="flex items-center justify-between border-t border-cx-line py-2 text-sm">
              <span>{row.metric}: {row.value} {row.unit}</span>
              <StatusPill value={row.outcome} />
            </div>
          ))}
        </GlassPanel>
        <GlassPanel>
          <p className="font-medium text-sm mb-3">Insights</p>
          <div className="space-y-3">
            {(payload?.insights || []).map((row) => (
              <div key={row.id} className="text-sm">
                <p className="font-medium">{row.rule_id} · {row.title}</p>
                <p className="text-cx-fgMuted mt-1">{row.statement}</p>
                <p className="text-xs text-cx-fgDim mt-1">AI-generated: {String(row.ai_generated)}. Citations: {(row.citations_json || []).length}</p>
              </div>
            ))}
          </div>
        </GlassPanel>
      </div>
    </div>
  );
}
