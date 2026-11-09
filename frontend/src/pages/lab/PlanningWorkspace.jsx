import { useEffect, useState } from 'react';
import GlassPanel from '../../components/ui/GlassPanel';
import { approveLabPlan, createLabPlan, getLabProtocols, labError, searchLabDocuments } from '../../api/lab';
import { StatusPill, useLab } from './LabShell';

export default function PlanningWorkspace() {
  const { setExperimentId, program } = useLab();
  const [protocols, setProtocols] = useState([]);
  const [selected, setSelected] = useState('');
  const [plan, setPlan] = useState(null);
  const [hits, setHits] = useState([]);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    getLabProtocols().then((response) => {
      const approved = response.data.filter((row) => row.status === 'approved');
      setProtocols(approved);
      const chosen = approved.find((row) => row.id === program?.id);
      const primary = approved.find((row) => row.protocol_code === 'SYN-CVP-001');
      if (chosen) setSelected(chosen.id);
      else if (primary) setSelected(primary.id);
    }).catch((err) => setError(labError(err)));
  }, []);

  const current = protocols.find((row) => row.id === selected);

  const search = async () => {
    const response = await searchLabDocuments('trypan');
    setHits(response.data.hits || []);
  };

  const create = async () => {
    setError('');
    try {
      const response = await createLabPlan({
        protocol_version_id: selected,
        title: `Plan: ${current.protocol_code} cell viability`,
      });
      setPlan(response.data);
      setMessage('Draft plan created. It is not approved.');
    } catch (err) {
      setError(labError(err));
    }
  };

  const approve = async () => {
    setError('');
    try {
      const response = await approveLabPlan(plan.id, { comment: 'Scientist approves the plan at gate G1.' });
      setExperimentId(response.data.id);
      setMessage(`Gate G1 approved. Experiment ${response.data.id} is ready for readiness review.`);
    } catch (err) {
      setError(labError(err));
    }
  };

  return (
    <div className="space-y-5">
      <GlassPanel>
        <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim">Moment 1 — experiment planning</p>
        <h2 className="font-display text-xl mt-1">Choose an approved protocol</h2>
        <div className="mt-4 grid md:grid-cols-3 gap-3">
          {protocols.map((row) => (
            <button
              key={row.id}
              type="button"
              onClick={() => setSelected(row.id)}
              className={`text-left rounded-xl border p-3 ${selected === row.id ? 'border-cx-accent bg-cx-accent/5' : 'border-cx-border'}`}
            >
              <p className="text-sm font-medium">{row.protocol_code} v{row.version_label}</p>
              <p className="text-xs text-cx-fgMuted mt-1">{row.protocol_title}</p>
              <div className="mt-2"><StatusPill value={`${row.status} · ${row.data_origin}`} /></div>
            </button>
          ))}
        </div>
        {current && (
          <div className="mt-4 grid md:grid-cols-2 gap-4 text-sm">
            <div>
              <p className="font-medium mb-2">Success criteria</p>
              <ul className="space-y-1 text-cx-fgMuted">
                {(current.success_criteria_json || []).map((item) => (
                  <li key={item.id}>{item.id}: {item.metric} {item.operator} {item.threshold} {item.unit}</li>
                ))}
              </ul>
            </div>
            <div>
              <p className="font-medium mb-2">Planned parameters</p>
              <ul className="space-y-1 text-cx-fgMuted">
                {Object.entries(current.parameters_json || {}).map(([key, value]) => (
                  <li key={key}>{key}: {String(value)}</li>
                ))}
              </ul>
            </div>
          </div>
        )}
        <div className="mt-4 flex flex-wrap gap-2">
          <button type="button" onClick={search} className="rounded-xl border border-cx-border px-3 py-2 text-sm">Search SOP citations</button>
          <button type="button" onClick={create} disabled={!selected} className="rounded-xl bg-cx-accent text-white px-3 py-2 text-sm disabled:opacity-50">Create experiment plan</button>
          <button type="button" onClick={approve} disabled={!plan} className="rounded-xl border border-cx-accent text-cx-accent px-3 py-2 text-sm disabled:opacity-50">Approve plan (G1)</button>
        </div>
        {message && <p className="mt-3 text-sm text-emerald-800">{message}</p>}
        {error && <p className="mt-3 text-sm text-rose-700">{error}</p>}
        {!!hits.length && (
          <ul className="mt-4 space-y-2 text-sm">
            {hits.map((hit) => (
              <li key={hit.citation} className="rounded-lg bg-slate-50 p-3">
                <span className="font-medium">{hit.citation}</span> — {hit.excerpt}
              </li>
            ))}
          </ul>
        )}
      </GlassPanel>
    </div>
  );
}
