import { createContext, useContext, useEffect, useState } from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { getLabStoryline } from '../../api/lab';

const LabContext = createContext(null);
const EXPERIMENT_KEY = 'scinova_lab_experiment_id';
const DOSSIER_KEY = 'scinova_lab_dossier_id';

export function useLab() {
  return useContext(LabContext);
}

export function experimentLabel(protocol) {
  if (protocol?.protocol_code === 'SYN-CVP-001') return 'Cell viability';
  if (protocol?.protocol_code === 'SYN-CVP-002') return 'Seeding-density screen';
  if (protocol?.protocol_code === 'SYN-CVP-003') return 'Post-thaw recovery';
  return protocol?.protocol_title || 'Experiment';
}

const LINKS = [
  ['/lab', 'Command'],
  ['/lab/planning', 'Planning'],
  ['/lab/readiness', 'Readiness'],
  ['/lab/ingestion', 'Ingestion'],
  ['/lab/results', 'Results'],
  ['/lab/lineage', 'Lineage'],
  ['/lab/dossier', 'Dossier'],
  ['/lab/approval', 'Approval'],
  ['/lab/next', 'Next experiment'],
  ['/lab/audit', 'Audit'],
];

export function LabNotice() {
  return (
    <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-950">
      Protocol text, inventory, and Vi-CELL rows in this demo are synthetic. Checksums, parsing, statistics, gates, and audit records are executed by the application. No external ELN or live instrument is connected.
    </div>
  );
}

export function StatusPill({ value }) {
  const tone = /pass|approved|complete|resolved|current|succeeded|ready/i.test(value || '')
    ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
    : /fail|reject|blocked|due|open/i.test(value || '')
      ? 'bg-rose-50 text-rose-800 border-rose-200'
      : 'bg-slate-50 text-slate-700 border-slate-200';
  return <span className={`inline-flex rounded-full border px-2.5 py-0.5 text-xs font-medium ${tone}`}>{value || '—'}</span>;
}

export default function LabShell() {
  const location = useLocation();
  const [experimentId, setExperimentIdState] = useState(() => localStorage.getItem(EXPERIMENT_KEY) || '');
  const [dossierId, setDossierIdState] = useState(() => localStorage.getItem(DOSSIER_KEY) || '');
  const [program, setProgram] = useState(null);
  const [storyline, setStoryline] = useState(null);
  const [error, setError] = useState('');

  const setExperimentId = (id) => {
    setExperimentIdState(id || '');
    if (id) localStorage.setItem(EXPERIMENT_KEY, id);
    else {
      localStorage.removeItem(EXPERIMENT_KEY);
      setStoryline(null);
    }
  };
  const setDossierId = (id) => {
    setDossierIdState(id || '');
    if (id) localStorage.setItem(DOSSIER_KEY, id);
    else localStorage.removeItem(DOSSIER_KEY);
  };

  useEffect(() => {
    if (!experimentId) {
      setStoryline(null);
      return;
    }
    getLabStoryline(experimentId)
      .then((response) => {
        setStoryline(response.data);
        const dossier = response.data?.moments?.moment_4_results?.dossier_id;
        if (dossier) setDossierId(dossier);
        setError('');
      })
      .catch((err) => setError(err?.response?.data?.message || 'Could not load the experiment storyline.'));
  }, [experimentId]);

  const showWorkflowNav = Boolean(program) || location.pathname !== '/lab';

  return (
    <LabContext.Provider value={{ experimentId, setExperimentId, dossierId, setDossierId, storyline, setStoryline, error, setError, program, setProgram }}>
      <div className="p-6 space-y-5 max-w-[1600px]">
        <div>
          <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim">SciNova Lab</p>
          <h1 className="font-display text-2xl font-semibold text-cx-fg mt-1">
            {program ? experimentLabel(program) : 'Lab Command Center'}
          </h1>
        </div>
        {showWorkflowNav && (
          <div className="flex gap-2 overflow-x-auto pb-1">
            {LINKS.map(([to, label]) => (
              <NavLink
                key={to}
                to={to}
                end={to === '/lab'}
                className={({ isActive }) => `shrink-0 rounded-full border px-3 py-1.5 text-sm ${isActive ? 'bg-cx-accent text-white border-cx-accent' : 'bg-white text-cx-fgMuted border-cx-border'}`}
              >
                {label}
              </NavLink>
            ))}
          </div>
        )}
        <Outlet />
      </div>
    </LabContext.Provider>
  );
}
