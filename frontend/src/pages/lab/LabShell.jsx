import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { Link, Outlet, useLocation } from 'react-router-dom';
import { getLabStoryline } from '../../api/lab';
import { experimentLabel } from './stages';

const LabContext = createContext(null);
const EXPERIMENT_KEY = 'scinova_lab_experiment_id';
const DOSSIER_KEY = 'scinova_lab_dossier_id';

export function useLab() {
  return useContext(LabContext);
}

export { experimentLabel };

export function StatusPill({ value }) {
  const raw = String(value || '');
  const label = raw.toLowerCase() === 'your turn' ? 'Next step' : (value || '—');
  const tone = /pass|approved|complete|resolved|current|succeeded|ready/i.test(raw)
    ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
    : /fail|reject|blocked|due|open/i.test(raw)
      ? 'bg-rose-50 text-rose-800 border-rose-200'
      : 'bg-slate-50 text-slate-700 border-slate-200';
  return <span className={`inline-flex rounded-full border px-2.5 py-0.5 text-xs font-medium ${tone}`}>{label}</span>;
}

export default function LabShell() {
  const location = useLocation();
  const [experimentId, setExperimentIdState] = useState(() => localStorage.getItem(EXPERIMENT_KEY) || '');
  const [dossierId, setDossierIdState] = useState(() => localStorage.getItem(DOSSIER_KEY) || '');
  const [program, setProgram] = useState(null);
  const [storyline, setStoryline] = useState(null);
  const [error, setError] = useState('');

  const setExperimentId = (id) => {
    const next = id || '';
    if (next !== experimentId) setStoryline(null);
    setExperimentIdState(next);
    if (next) localStorage.setItem(EXPERIMENT_KEY, next);
    else localStorage.removeItem(EXPERIMENT_KEY);
  };
  const setDossierId = useCallback((id) => {
    setDossierIdState(id || '');
    if (id) localStorage.setItem(DOSSIER_KEY, id);
    else localStorage.removeItem(DOSSIER_KEY);
  }, []);

  const reloadStoryline = useCallback(async () => {
    if (!experimentId) {
      setStoryline(null);
      return null;
    }
    const response = await getLabStoryline(experimentId);
    setStoryline(response.data);
    const dossier = response.data?.moments?.moment_4_results?.dossier_id;
    if (dossier) setDossierId(dossier);
    setError('');
    return response.data;
  }, [experimentId, setDossierId]);

  useEffect(() => {
    reloadStoryline().catch((err) => setError(err?.response?.data?.message || 'Could not load the experiment.'));
  }, [reloadStoryline]);

  const home = location.pathname === '/lab'
    || location.pathname === '/lab/planning'
    || location.pathname === '/lab/readiness'
    || location.pathname === '/lab/approval';

  return (
    <LabContext.Provider value={{
      experimentId,
      setExperimentId,
      dossierId,
      setDossierId,
      storyline,
      setStoryline,
      error,
      setError,
      program,
      setProgram,
      reloadStoryline,
    }}
    >
      {home ? (
        <div className="min-h-full">
          <Outlet />
        </div>
      ) : (
        <div className="mx-auto max-w-[1600px] space-y-5 p-6">
          <Link to="/lab" className="text-sm font-medium text-cx-accent">Experiments</Link>
          <Outlet />
        </div>
      )}
    </LabContext.Provider>
  );
}
