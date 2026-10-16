import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import GlassPanel from '../../components/ui/GlassPanel';
import KpiTile from '../../components/ui/KpiTile';
import { getLabAgentHealth, getLabAgents, getLabIssues, getLabOverview, getLabProtocols, labError } from '../../api/lab';
import { experimentLabel, LabNotice, StatusPill, useLab } from './LabShell';
import { Database, Droplets, FlaskConical, Layers, Share2, Shield, Snowflake } from 'lucide-react';

const PROGRAM_ICONS = {
  'SYN-CVP-001': Droplets,
  'SYN-CVP-002': Layers,
  'SYN-CVP-003': Snowflake,
};

const READINESS_AGENTS = ['LAB-A2', 'LAB-A3', 'LAB-A4', 'LAB-A5'];

function gateDecision(storyline, gate) {
  return (storyline?.gates || []).find((row) => row.gate === gate && row.decision === 'approve');
}

function nextAction(experimentId, storyline, issues) {
  const moments = storyline?.moments || {};
  if (!experimentId || !moments.moment_1_planning?.complete) {
    return {
      title: 'LAB-A1 is waiting for an approved protocol and your plan approval.',
      detail: 'You select the protocol. The agent creates the plan. Gate G1 stays with you.',
      to: '/lab/planning',
      button: 'Start with LAB-A1',
    };
  }
  const open = issues.filter((issue) => issue.status === 'open');
  if (!moments.moment_2_readiness?.complete) {
    if (!issues.length) {
      return {
        title: 'LAB-A2 through LAB-A5 can now check samples, the instrument, training, and compliance.',
        detail: 'Each agent records its own finding. You approve every corrective action at gate G2.',
        to: '/lab/readiness',
        button: 'Run the readiness agents',
      };
    }
    const first = open[0];
    return {
      title: first ? `${first.agent_id} found ${first.code}.` : 'Readiness findings are waiting for your decision.',
      detail: 'Approve the recommended corrective action. The experiment stays held until the blocking findings are closed.',
      to: '/lab/readiness',
      button: 'Review the finding',
    };
  }
  if (!moments.moment_3_ingestion?.complete) {
    return {
      title: 'LAB-A6 is ready to take the Vi-CELL file.',
      detail: 'The agent checksums the file, parses it, maps the measurements, and publishes them to the lab fabric.',
      to: '/lab/ingestion',
      button: 'Open data capture',
    };
  }
  if (!moments.moment_4_results?.complete) {
    return {
      title: 'LAB-A6 can compile the results and draft the dossier.',
      detail: 'Pass and fail come from the plan criteria. The draft stays unpublished until you approve it.',
      to: '/lab/results',
      button: 'Open results',
    };
  }
  if (!moments.moment_4_results?.publishable) {
    return {
      title: 'The dossier is a machine-generated draft. Gate G6 is yours.',
      detail: 'Read the measurements, citations, and insights, then approve, reject, or request a revision.',
      to: '/lab/approval',
      button: 'Review the dossier',
    };
  }
  if (!moments.moment_5_learning?.complete) {
    return {
      title: 'LAB-A1 can turn the cited insight into the next plan.',
      detail: 'The follow-up plan changes seeding density and stays in draft until you approve gate G1 again.',
      to: '/lab/next',
      button: 'Open the next experiment',
    };
  }
  return {
    title: 'Every agent has finished, and you have approved gates G1, G2, and G6.',
    detail: 'The audit console keeps the ordered history of this experiment.',
    to: '/lab/audit',
    button: 'Read the audit',
  };
}

function AgentCard({ id, agent, status, detail, href, current }) {
  return (
    <Link
      to={href}
      className={`block rounded-2xl border p-4 transition-colors ${current ? 'border-cx-accent bg-sky-50' : 'border-cx-border bg-white hover:border-cx-accent'}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold tracking-wide text-cx-accent">{id}</p>
          <p className="mt-1 font-medium text-cx-fg">{agent?.name || 'Lab agent'}</p>
        </div>
        <StatusPill value={status} />
      </div>
      <p className="mt-2 text-sm text-cx-fgMuted">{agent?.summary}</p>
      {detail && <p className="mt-2 text-sm text-cx-fg">{detail}</p>}
      <p className="mt-3 text-sm font-medium text-cx-accent">Open this step</p>
    </Link>
  );
}

function Gate({ gate, label, decision }) {
  return (
    <div className="flex items-center gap-3 px-1 py-1">
      <span className="h-px flex-1 bg-cx-line" />
      <p className="text-center text-xs text-cx-fgMuted">
        <span className="font-semibold text-cx-fg">You · {gate}</span>
        {' · '}
        {decision ? `approved by ${decision.actor}` : label}
      </p>
      <span className="h-px flex-1 bg-cx-line" />
    </div>
  );
}

function ExperimentGallery({ protocols, error, onOpen }) {
  const ordered = [...protocols].sort((a, b) => String(a.protocol_code).localeCompare(String(b.protocol_code)));
  return (
    <div className="relative overflow-hidden rounded-3xl border border-cx-borderStrong bg-white shadow-glass">
      <div className="pointer-events-none absolute inset-0 grid-bg" />
      <div className="relative px-6 py-8 md:px-10 md:py-12">
        <p className="text-2xs uppercase tracking-[0.22em] text-cx-accent">Choose an experiment</p>
        <h2 className="mt-3 max-w-2xl font-display text-3xl font-semibold tracking-tight text-cx-fg md:text-4xl">
          The workflow stays closed until you open one.
        </h2>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-cx-fgMuted">
          Cell viability sits alongside the other approved experiments. Pick one to start its agents, gates, and dossier.
        </p>
        {error && <p className="mt-4 text-sm text-rose-700">{error}</p>}
        {!ordered.length && !error && <p className="mt-8 text-sm text-cx-fgMuted">Loading experiments.</p>}
        <div className="mt-8 grid gap-4 lg:grid-cols-3">
          {ordered.map((protocol) => {
            const Icon = PROGRAM_ICONS[protocol.protocol_code] || FlaskConical;
            const primary = protocol.protocol_code === 'SYN-CVP-001';
            const samples = protocol.sample_panel_json?.length || 0;
            return (
              <button
                key={protocol.id}
                type="button"
                onClick={() => onOpen(protocol)}
                className={`group flex h-full flex-col rounded-2xl border p-5 text-left transition duration-200 hover:-translate-y-0.5 hover:shadow-glass ${primary ? 'border-cx-accent bg-gradient-to-b from-sky-50 to-white' : 'border-cx-border bg-white hover:border-cx-accent'}`}
              >
                <div className="flex items-start justify-between gap-3">
                  <span className={`flex h-11 w-11 items-center justify-center rounded-2xl ${primary ? 'bg-cx-accent text-white' : 'bg-slate-100 text-cx-fg'}`}>
                    <Icon size={18} />
                  </span>
                  <StatusPill value={primary ? 'ready' : protocol.status} />
                </div>
                <p className="mt-5 text-xs font-semibold tracking-wide text-cx-fgDim">{protocol.protocol_code} · v{protocol.version_label}</p>
                <p className="mt-1 font-display text-2xl font-semibold text-cx-fg">{experimentLabel(protocol)}</p>
                <p className="mt-2 flex-1 text-sm leading-6 text-cx-fgMuted">{protocol.protocol_title}</p>
                <p className="mt-4 text-xs text-cx-fgDim">{samples} samples · synthetic protocol · {protocol.data_origin}</p>
                <span className="mt-5 inline-flex w-fit rounded-xl bg-cx-accent px-3 py-2 text-sm text-white">
                  Open {experimentLabel(protocol)}
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export default function CommandCenter() {
  const { storyline, experimentId, setExperimentId, program, setProgram, error: storylineError } = useLab();
  const [agents, setAgents] = useState(null);
  const [health, setHealth] = useState(null);
  const [issues, setIssues] = useState([]);
  const [overview, setOverview] = useState(null);
  const [protocols, setProtocols] = useState([]);
  const [error, setError] = useState('');

  useEffect(() => {
    getLabProtocols().then((response) => {
      setProtocols(response.data.filter((row) => row.status === 'approved'));
    }).catch((err) => setError(labError(err)));
    getLabOverview().then((response) => setOverview(response.data)).catch((err) => setError(labError(err)));
  }, []);

  useEffect(() => {
    if (!program) return;
    getLabAgents().then((response) => setAgents(response.data)).catch((err) => setError(labError(err)));
    getLabAgentHealth('LAB-A6').then((response) => setHealth(response.data)).catch(() => {});
  }, [program]);

  const openProgram = (protocol) => {
    const live = (overview?.experiments || []).find(
      (row) => row.protocol_code === protocol.protocol_code && row.data_origin !== 'synthetic_historical',
    );
    setExperimentId(live?.id || '');
    setProgram(protocol);
  };

  useEffect(() => {
    if (!experimentId) {
      setIssues([]);
      return;
    }
    getLabIssues(experimentId).then((response) => setIssues(response.data)).catch((err) => setError(labError(err)));
  }, [experimentId]);

  const activeStoryline = experimentId ? storyline : null;
  const activeIssues = experimentId ? issues : [];
  const waitingForStory = Boolean(experimentId) && !activeStoryline && !storylineError;
  const moments = activeStoryline?.moments || {};
  const planned = Boolean(moments.moment_1_planning?.complete);
  const ready = Boolean(moments.moment_2_readiness?.complete);
  const captured = Boolean(moments.moment_3_ingestion?.complete);
  const compiled = Boolean(moments.moment_4_results?.complete);
  const publishable = Boolean(moments.moment_4_results?.publishable);
  const learned = Boolean(moments.moment_5_learning?.complete);
  const action = nextAction(experimentId, activeStoryline, activeIssues);
  const experiments = (overview?.experiments || []).filter((row) => row.data_origin !== 'synthetic_historical');
  const historical = (overview?.experiments || []).filter((row) => row.data_origin === 'synthetic_historical').length;

  const readinessStatus = (agentId) => {
    if (waitingForStory) return 'loading';
    if (!planned) return 'not started';
    const mine = activeIssues.filter((issue) => issue.agent_id === agentId);
    if (!mine.length) return ready ? 'complete' : 'your turn';
    return mine.some((issue) => issue.status === 'open') ? 'open' : 'resolved';
  };

  const readinessDetail = (agentId) => {
    const mine = activeIssues.filter((issue) => issue.agent_id === agentId);
    if (!mine.length) return planned ? 'Waiting to evaluate this experiment.' : 'Starts after you approve the plan.';
    return mine.map((issue) => `${issue.code}: ${issue.message}`).join(' ');
  };

  if (!program) {
    return <ExperimentGallery protocols={protocols} error={error} onOpen={openProgram} />;
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-cx-fgMuted">{program.protocol_code} is open. The agents below belong to this experiment.</p>
        <button type="button" onClick={() => setProgram(null)} className="rounded-xl border border-cx-border bg-white px-3 py-2 text-sm">
          Change experiment
        </button>
      </div>
      <LabNotice />
      {error && <p className="text-sm text-rose-700">{error}</p>}

      <GlassPanel hero>
        <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim">Agentic workflow</p>
        <h2 className="font-display text-xl font-semibold text-cx-fg mt-1">Six agents run the experiment. You approve the gates.</h2>
        <p className="mt-2 max-w-3xl text-sm text-cx-fgMuted">
          LAB-A1 plans the work. LAB-A2 through LAB-A5 check whether it can run. LAB-A6 captures the Vi-CELL file and writes the dossier. LAB-A1 then proposes the next experiment from a cited insight.
          {health?.status && (
            <> Agents are {health.status}. Landing zone {health.dependencies?.landing_zone?.mode}.</>
          )}
        </p>

        <div className={`mt-5 rounded-2xl border px-4 py-4 ${learned ? 'border-emerald-200 bg-emerald-50' : 'border-cx-accent bg-sky-50'}`}>
          <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim">Your next action</p>
          {waitingForStory ? (
            <p className="mt-1 font-medium text-cx-fg">Loading this experiment’s agent status.</p>
          ) : (
            <>
              <p className="mt-1 font-medium text-cx-fg">{action.title}</p>
              <p className="mt-1 text-sm text-cx-fgMuted">{action.detail}</p>
              <Link to={action.to} className="mt-3 inline-flex rounded-xl bg-cx-accent px-3 py-2 text-sm text-white">{action.button}</Link>
            </>
          )}
        </div>

        <ol className="mt-6 space-y-4">
          <li className="space-y-3">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-cx-fgDim">1 · Plan</p>
            <AgentCard
              id="LAB-A1"
              agent={agents?.['LAB-A1']}
              status={waitingForStory ? 'loading' : planned ? 'complete' : 'your turn'}
              detail={planned ? 'The plan is approved and the experiment exists.' : 'Choose a cell-viability protocol and approve the plan.'}
              href="/lab/planning"
              current={!waitingForStory && !planned}
            />
            <Gate gate="G1" label="approve the plan before any agent can continue" decision={gateDecision(activeStoryline, 'G1')} />
          </li>

          <li className="space-y-3">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-cx-fgDim">2 · Readiness</p>
            <div className="grid gap-3 md:grid-cols-2">
              {READINESS_AGENTS.map((agentId) => (
                <AgentCard
                  key={agentId}
                  id={agentId}
                  agent={agents?.[agentId]}
                  status={readinessStatus(agentId)}
                  detail={readinessDetail(agentId)}
                  href="/lab/readiness"
                  current={planned && !ready}
                />
              ))}
            </div>
            <Gate gate="G2" label="approve each corrective action" decision={gateDecision(activeStoryline, 'G2')} />
          </li>

          <li className="space-y-3">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-cx-fgDim">3 · Capture and results</p>
            <AgentCard
              id="LAB-A6"
              agent={agents?.['LAB-A6']}
              status={waitingForStory ? 'loading' : publishable ? 'complete' : ready ? 'your turn' : 'not started'}
              detail={
                publishable
                  ? 'Results are compiled and the dossier is publishable.'
                  : captured
                    ? 'The file is in the landing zone. Compile the results, then approve the draft dossier.'
                    : 'Ingests the instrument file, then compares it with historical runs.'
              }
              href={captured ? (compiled && !publishable ? '/lab/approval' : '/lab/results') : '/lab/ingestion'}
              current={!waitingForStory && ready && !publishable}
            />
            <div className="flex flex-wrap gap-2 text-sm">
              <Link to="/lab/ingestion" className="rounded-full border border-cx-border px-3 py-1">Data capture <StatusPill value={waitingForStory ? 'loading' : captured ? 'complete' : ready ? 'your turn' : 'not started'} /></Link>
              <Link to="/lab/results" className="rounded-full border border-cx-border px-3 py-1">Results <StatusPill value={waitingForStory ? 'loading' : compiled ? 'complete' : captured ? 'your turn' : 'not started'} /></Link>
              <Link to="/lab/dossier" className="rounded-full border border-cx-border px-3 py-1">Dossier</Link>
            </div>
            <Gate gate="G6" label="approve the dossier before it can be published" decision={gateDecision(activeStoryline, 'G6')} />
          </li>

          <li className="space-y-3">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-cx-fgDim">4 · Next experiment</p>
            <AgentCard
              id="LAB-A1"
              agent={agents?.['LAB-A1']}
              status={waitingForStory ? 'loading' : learned ? 'complete' : publishable ? 'your turn' : 'not started'}
              detail={learned ? 'A follow-up plan cites the insight and changes seeding density.' : 'Uses the stored insight to propose one parameter change.'}
              href="/lab/next"
              current={!waitingForStory && publishable && !learned}
            />
          </li>
        </ol>
      </GlassPanel>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiTile label="Approved protocols" value={overview?.protocols?.length ?? '—'} icon={FlaskConical} />
        <KpiTile label="Vi-CELL instruments" value={overview?.instruments?.length ?? '—'} icon={Database} />
        <KpiTile label="Historical baselines" value={historical || '—'} icon={Share2} />
        <KpiTile label="Demo experiments" value={experiments.length} icon={Shield} />
      </div>
    </div>
  );
}
