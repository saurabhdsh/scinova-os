import { useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Plus, Sparkles } from 'lucide-react';
import { useUser } from '../../context/UserContext';
import {
  createLabProtocol,
  getLabOverview,
  getLabProtocols,
  getLabStoryline,
  ingestLabFile,
  labError,
} from '../../api/lab';
import ExperimentScreen from './ExperimentScreen';
import LabAssistant from './LabAssistant';
import { useLab } from './LabShell';
import { experimentLabel, stageFromStoryline } from './stages';

const DEEP_LINKS = new Set(['/lab/planning', '/lab/readiness', '/lab/approval']);

function stripSavedPlan(current, next) {
  if (!next) return null;
  const changed = !current
    || current.protocolId !== next.protocolId
    || JSON.stringify(current.parameters || {}) !== JSON.stringify(next.parameters || {})
    || JSON.stringify(current.criteria || []) !== JSON.stringify(next.criteria || {});
  if (!changed) return next;
  if (next.snapshot && next.snapshot !== current?.snapshot) return next;
  if (!next.planId && !next.snapshot) return next;
  const { planId, snapshot, ...rest } = next;
  return rest;
}

export default function CommandCenter() {
  const navigate = useNavigate();
  const location = useLocation();
  const { displayName } = useUser();
  const { experimentId, setExperimentId, setProgram, reloadStoryline, storyline } = useLab();
  const assistantRef = useRef(null);
  const [protocols, setProtocols] = useState([]);
  const [overview, setOverview] = useState(null);
  const [stories, setStories] = useState({});
  const [draft, setDraft] = useState(null);
  const [workspace, setWorkspace] = useState(null);
  const [heldFile, setHeldFile] = useState(null);
  const [error, setError] = useState('');
  const [assistantOpen, setAssistantOpen] = useState(true);

  const loadOverview = () => {
    getLabOverview().then((response) => setOverview(response.data)).catch((err) => setError(labError(err)));
  };

  useEffect(() => {
    getLabProtocols()
      .then((response) => setProtocols(response.data.filter((row) => row.status === 'approved')))
      .catch((err) => setError(labError(err)));
    loadOverview();
  }, []);

  const deepApplied = useRef(false);
  useEffect(() => {
    if (deepApplied.current || !DEEP_LINKS.has(location.pathname)) return;
    deepApplied.current = true;
    setWorkspace(experimentId ? { type: 'experiment', id: experimentId } : { type: 'draft' });
  }, [location.pathname, experimentId]);

  const experiments = overview?.experiments || [];
  const mine = experiments.filter((row) => row.data_origin !== 'synthetic_historical');
  const pastByCode = useMemo(() => {
    const counts = {};
    experiments.forEach((row) => {
      if (row.data_origin === 'synthetic_historical' || row.status === 'completed') {
        counts[row.protocol_code] = (counts[row.protocol_code] || 0) + 1;
      }
    });
    return counts;
  }, [experiments]);

  useEffect(() => {
    let cancel = false;
    Promise.all(mine.map(async (row) => {
      try {
        const response = await getLabStoryline(row.id);
        return [row.id, response.data];
      } catch {
        return [row.id, null];
      }
    })).then((pairs) => {
      if (!cancel) setStories(Object.fromEntries(pairs));
    });
    return () => {
      cancel = true;
    };
  }, [overview]);

  const title = displayName && displayName !== 'User' ? `${displayName}'s Experiments` : 'My Experiments';

  const updateDraft = (next) => setDraft((current) => stripSavedPlan(current, next));

  const openExperiment = (row) => {
    const protocol = protocols.find((item) => item.protocol_code === row.protocol_code);
    setProgram(protocol || null);
    setDraft(null);
    setExperimentId(row.id);
    setWorkspace({ type: 'experiment', id: row.id });
    if (location.pathname !== '/lab') navigate('/lab');
  };

  const startNewExperiment = () => {
    setDraft({ awaitingIntent: true, intent: '' });
    setWorkspace({ type: 'draft' });
    if (location.pathname !== '/lab') navigate('/lab');
  };

  const backToList = () => {
    setWorkspace(null);
    if (location.pathname !== '/lab') navigate('/lab');
  };

  const createProtocol = async (payload) => {
    const response = await createLabProtocol(payload);
    const protocol = response.data;
    setProtocols((current) => [...current.filter((row) => row.id !== protocol.id), protocol]);
    return protocol;
  };

  const openFollowUp = (plan) => {
    const protocol = protocols.find((item) => item.id === plan.protocol_version_id);
    const seeding = Number(plan.parameters_json?.seeding_density_cells_per_ml);
    const storedTitle = plan.title || '';
    const title = /citing LAB-RULE/i.test(storedTitle) && Number.isFinite(seeding)
      ? `Next experiment · seeding ${Math.round(seeding).toLocaleString()}`
      : (storedTitle || (Number.isFinite(seeding) ? `Next experiment · seeding ${Math.round(seeding).toLocaleString()}` : 'Next experiment'));
    setProgram(protocol || null);
    setDraft({
      protocolId: plan.protocol_version_id,
      protocolCode: protocol?.protocol_code,
      protocolTitle: protocol?.protocol_title,
      versionLabel: protocol?.version_label,
      name: experimentLabel(protocol),
      experimentName: title,
      nameEdited: true,
      planTitle: title,
      parameters: { ...(plan.parameters_json || {}) },
      criteria: [...(plan.success_criteria_json || [])],
      sampleCount: plan.sample_panel_json?.length || 0,
      planId: plan.id,
      snapshot: plan,
      reason: Number.isFinite(seeding)
        ? `Only the seeding density changes, to ${Math.round(seeding).toLocaleString()} cells/mL. Every other planned parameter stays the same. Approve this plan to start the next experiment.`
        : 'This plan applies the recommendation from the last experiment. Approve it to start the next experiment.',
    });
    setWorkspace({ type: 'draft' });
    if (location.pathname !== '/lab') navigate('/lab');
  };

  const onStarted = async (experiment) => {
    const protocol = protocols.find((item) => item.id === draft?.protocolId);
    setProgram(protocol || null);
    setExperimentId(experiment.id);
    setDraft(null);
    setWorkspace({ type: 'experiment', id: experiment.id });
    loadOverview();
  };

  const onFile = async (file) => {
    const currentStory = workspace?.type === 'experiment' ? (stories[experimentId] || storyline) : null;
    const stage = currentStory ? stageFromStoryline(currentStory) : null;
    if (workspace?.type === 'experiment' && experimentId && stage?.key === 'capture') {
      try {
        await ingestLabFile(experimentId, file);
        await reloadStoryline();
        loadOverview();
        return `${file.name} is in the landing zone. Results will compile from it.`;
      } catch (err) {
        return labError(err);
      }
    }
    setHeldFile(file);
    return `${file.name} is attached. It will be ready to use when this experiment reaches capture.`;
  };

  const cards = mine.map((row) => {
    const stage = stageFromStoryline(stories[row.id]);
    return { row, stage };
  });

  return (
    <div className={assistantOpen
      ? 'lg:grid lg:grid-cols-[minmax(0,1.4fr)_minmax(300px,1fr)]'
      : 'lg:grid lg:grid-cols-[minmax(0,1fr)_5.5rem]'}
    >
      <section className={`min-w-0 px-6 py-8 lg:px-10 lg:py-10 ${assistantOpen ? '' : 'pb-36 lg:pb-10'}`}>
        {error && <p className="mb-4 text-sm text-rose-700">{error}</p>}
        {workspace ? (
          <ExperimentScreen
            key={workspace.type === 'experiment' ? workspace.id : 'draft'}
            mode={workspace.type}
            draft={workspace.type === 'draft' ? draft : null}
            protocols={protocols}
            pastByCode={pastByCode}
            onDraftChange={updateDraft}
            onCreateProtocol={createProtocol}
            onBack={backToList}
            onStarted={onStarted}
            onPrepareFollowUp={openFollowUp}
            onRefresh={loadOverview}
            heldFile={heldFile}
            onConsumeFile={() => setHeldFile(null)}
          />
        ) : (
          <div>
            <div className="flex items-end justify-between gap-4">
              <div>
                <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-cx-fgDim">Lab</p>
                <h1 className="mt-2 font-display text-4xl font-semibold tracking-tight text-cx-fg">{title}</h1>
                <p className="mt-2 max-w-md text-sm leading-6 text-cx-fgMuted">
                  Each experiment stays on one screen. Agents move the work forward. You step in for scientific decisions.
                </p>
              </div>
              <button
                type="button"
                onClick={startNewExperiment}
                className="inline-flex shrink-0 items-center gap-2 rounded-full bg-cx-fg px-4 py-2 text-sm text-white"
              >
                <Plus size={16} />
                New experiment
              </button>
            </div>

            <div className="mt-8 space-y-3">
              {draft && (
                <button
                  type="button"
                  onClick={() => setWorkspace({ type: 'draft' })}
                  className="flex w-full items-center justify-between gap-4 rounded-3xl border border-cx-accent/30 bg-white px-5 py-5 text-left shadow-[0_0_0_4px_rgba(8,145,178,0.08)]"
                >
                  <span>
                    <span className="block font-display text-2xl font-semibold tracking-tight text-cx-fg">
                      {draft.awaitingIntent ? 'New experiment' : (draft.planTitle || draft.name || 'New experiment')}
                    </span>
                    <span className="mt-1 block text-sm text-cx-fgMuted">{draft.awaitingIntent ? 'Intent' : (draft.protocolCode || 'Suggested protocol')}</span>
                    <span className="mt-3 block text-sm font-medium text-cx-accent">
                      Next: {draft.awaitingIntent ? 'describe what you want to do.' : 'approve the plan.'}
                    </span>
                  </span>
                  <span className="rounded-full bg-sky-50 px-3 py-1 text-xs font-medium text-cx-accent">Planning</span>
                </button>
              )}

              {cards.map(({ row, stage }) => (
                <button
                  key={row.id}
                  type="button"
                  onClick={() => openExperiment(row)}
                  className={`flex w-full items-center justify-between gap-4 rounded-3xl border bg-white px-5 py-5 text-left shadow-sm transition hover:-translate-y-0.5 ${stage.needsScientist ? 'border-cx-accent/30 shadow-[0_0_0_4px_rgba(8,145,178,0.08)]' : 'border-black/5'}`}
                >
                  <span>
                    <span className="block font-display text-2xl font-semibold tracking-tight text-cx-fg">{row.title || experimentLabel(row)}</span>
                    <span className="mt-1 block text-sm text-cx-fgMuted">{row.protocol_code}</span>
                    <span className={`mt-3 block text-sm ${stage.needsScientist ? 'font-medium text-cx-accent' : 'text-cx-fgMuted'}`}>
                      Next: {stage.next.replace(/\.$/, '')}
                    </span>
                  </span>
                  <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-cx-fg">{stage.label}</span>
                </button>
              ))}

              {!cards.length && !draft && !error && (
                <div className="rounded-3xl border border-dashed border-black/10 px-6 py-16 text-center">
                  <p className="font-display text-2xl font-semibold tracking-tight text-cx-fg">No experiments yet</p>
                  <p className="mx-auto mt-2 max-w-sm text-sm leading-6 text-cx-fgMuted">
                    Tell the assistant what you want to run. It will recommend a protocol and wait for your approval.
                  </p>
                  <button
                    type="button"
                    onClick={startNewExperiment}
                    className="mt-6 rounded-full bg-cx-fg px-4 py-2 text-sm text-white"
                  >
                    New experiment
                  </button>
                </div>
              )}
            </div>
          </div>
        )}
      </section>
      <aside className="border-t border-black/5 bg-white/75 lg:sticky lg:top-0 lg:h-[calc(100dvh-7.5rem)] lg:self-start lg:border-l lg:border-t-0">
        {assistantOpen ? (
          <LabAssistant
            ref={assistantRef}
            protocols={protocols}
            instruments={overview?.instruments || []}
            pastByCode={pastByCode}
            draft={draft}
            experimentId={workspace?.type === 'experiment' ? (experimentId || null) : null}
            onDraftChange={updateDraft}
            onOpenDraft={() => {
              setWorkspace({ type: 'draft' });
              if (location.pathname !== '/lab') navigate('/lab');
            }}
            onFile={onFile}
            onCollapse={() => setAssistantOpen(false)}
          />
        ) : (
          <button
            type="button"
            onClick={() => setAssistantOpen(true)}
            aria-label="Open Lab Assistant"
            className="group fixed inset-x-4 bottom-4 z-30 flex items-center gap-4 overflow-hidden rounded-3xl border border-cyan-200/80 bg-gradient-to-r from-cyan-50 via-white to-sky-100 px-5 py-4 text-left shadow-[0_16px_40px_rgba(8,145,178,0.28)] lg:static lg:inset-auto lg:bottom-auto lg:z-auto lg:h-full lg:flex-col lg:justify-center lg:gap-6 lg:rounded-none lg:border-0 lg:bg-gradient-to-b lg:px-3 lg:py-8 lg:shadow-none"
          >
            <span className="pointer-events-none absolute -right-8 top-1/2 h-28 w-28 -translate-y-1/2 rounded-full bg-cyan-300/50 blur-2xl lg:right-auto lg:top-10 lg:translate-y-0" />
            <span className="relative flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-cx-fg text-white shadow-[0_12px_30px_rgba(8,145,178,0.45)]">
              <Sparkles size={18} />
            </span>
            <span className="relative min-w-0">
              <span className="block text-[11px] font-semibold uppercase tracking-[0.22em] text-cx-accent lg:[writing-mode:vertical-rl]">Help is here</span>
              <span className="mt-1 block font-display text-2xl font-semibold tracking-tight text-cx-fg lg:mt-4 lg:text-[15px] lg:[writing-mode:vertical-rl]">
                Ask the Lab Assistant
              </span>
              <span className="mt-1 block text-sm leading-5 text-cx-fgMuted lg:hidden">Questions, results, and a new experiment.</span>
            </span>
          </button>
        )}
      </aside>
    </div>
  );
}
