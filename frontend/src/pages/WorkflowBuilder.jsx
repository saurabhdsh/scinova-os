import { useEffect, useState, useCallback } from 'react';
import { Play, Loader2, FlaskConical, Beaker, Target, Sparkles } from 'lucide-react';
import GlassPanel from '../components/ui/GlassPanel';
import WorkflowProgress from '../components/workflow/WorkflowProgress';
import { getWorkflowTemplates, getWorkflowPipelines, runWorkflow, getWorkflowRuns, getWorkflowStatus, getAccountQuotas } from '../api/client';
import { apiErrorMessage } from '../lib/auth';

const PIPELINE_ICONS = {
  flask: FlaskConical,
  beaker: Beaker,
  target: Target,
};

export default function WorkflowBuilder() {
  const [templates, setTemplates] = useState([]);
  const [pipelines, setPipelines] = useState([]);
  const [runs, setRuns] = useState([]);
  const [selected, setSelected] = useState(null);
  const [activePipeline, setActivePipeline] = useState(null);
  const [query, setQuery] = useState('');
  const [running, setRunning] = useState(false);
  const [activeRun, setActiveRun] = useState(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [quotas, setQuotas] = useState(null);
  const [workflowError, setWorkflowError] = useState('');

  const refreshRun = useCallback(async (runId) => {
    if (!runId) return;
    try {
      const r = await getWorkflowStatus(runId);
      setActiveRun(r.data);
    } catch (err) {
      console.error(err);
    }
  }, []);

  useEffect(() => {
    getWorkflowPipelines().then((r) => {
      setPipelines(r.data.filter((p) => p.available));
      if (r.data.length) {
        setActivePipeline(r.data[0]);
        setQuery(r.data[0].query || '');
      }
    }).catch(console.error);
    getWorkflowTemplates().then((r) => setTemplates(r.data)).catch(console.error);
    getWorkflowRuns().then((r) => setRuns(r.data)).catch(console.error);
    getAccountQuotas().then((r) => setQuotas(r.data)).catch(console.error);
  }, []);

  useEffect(() => {
    if (!activeRun?.id) return undefined;
    const isLive = activeRun.status === 'pending_approval' || activeRun.status === 'running';
    if (isLive) {
      refreshRun(activeRun.id);
      const timer = setInterval(() => refreshRun(activeRun.id), 1500);
      return () => clearInterval(timer);
    }
    if (activeRun.status === 'completed' || activeRun.status === 'failed') {
      getWorkflowRuns().then((res) => setRuns(res.data)).catch(console.error);
    }
    return undefined;
  }, [activeRun?.id, activeRun?.status, refreshRun]);

  const runPipeline = async (pipeline) => {
    if (!pipeline?.template_id || !query.trim()) return;
    if (quotas?.quotas_enabled && !quotas.workflows_allowed) {
      setWorkflowError(`Workflow limit reached (${quotas.workflows_used}/${quotas.max_workflows}). Contact your administrator.`);
      return;
    }
    setRunning(true);
    setActiveRun(null);
    setWorkflowError('');
    setActivePipeline(pipeline);
    try {
      const r = await runWorkflow({
        template_id: pipeline.template_id,
        name: `${pipeline.name} — ${new Date().toLocaleDateString()}`,
        input_data: {
          query: query.trim(),
          project: 'SciNova R&D',
          initiated_by: 'scientist',
          auto_approve: true,
          generate_report: true,
          report_type: pipeline.report_type,
        },
      });
      setActiveRun(r.data);
      getAccountQuotas().then((res) => setQuotas(res.data)).catch(console.error);
    } catch (err) {
      setWorkflowError(apiErrorMessage(err, 'Workflow failed to start'));
    } finally {
      setRunning(false);
    }
  };

  const runTemplate = async () => {
    if (!selected) return;
    if (quotas?.quotas_enabled && !quotas.workflows_allowed) {
      setWorkflowError(`Workflow limit reached (${quotas.workflows_used}/${quotas.max_workflows}). Contact your administrator.`);
      return;
    }
    setRunning(true);
    setActiveRun(null);
    setWorkflowError('');
    try {
      const r = await runWorkflow({
        template_id: selected.id,
        input_data: {
          query: query.trim() || 'Scientific workflow analysis',
          project: 'SciNova R&D',
          initiated_by: 'scientist',
          auto_approve: false,
          generate_report: true,
          report_type: 'study_report',
        },
      });
      setActiveRun(r.data);
      getAccountQuotas().then((res) => setQuotas(res.data)).catch(console.error);
    } catch (err) {
      setWorkflowError(apiErrorMessage(err, 'Workflow failed to start'));
    } finally {
      setRunning(false);
    }
  };

  const activeTemplate = activePipeline
    ? templates.find((t) => t.id === activePipeline.template_id)
    : selected;

  const progressRun = activeRun?.template_id === activeTemplate?.id ? activeRun : null;
  const workflowLive = progressRun && ['running', 'pending_approval', 'completed', 'failed'].includes(progressRun.status);
  const isExpressRun = activeRun?.output_json?.workflow_input?.auto_approve;
  const isWorkflowBusy = running || progressRun?.status === 'running';
  const workflowBlocked = quotas?.quotas_enabled && !quotas.workflows_allowed;

  return (
    <div className="p-6 space-y-6">
      {quotas?.quotas_enabled && (
        <p className={`text-xs ${workflowBlocked ? 'text-cx-danger' : 'text-cx-fgMuted'}`}>
          Workflow quota: {quotas.workflows_used}/{quotas.max_workflows} runs used
        </p>
      )}
      {workflowError && (
        <div className="p-3 rounded-xl border border-cx-danger/30 bg-cx-danger/5 text-sm text-cx-danger">
          {workflowError}
        </div>
      )}
      <GlassPanel hero>
        <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim">Research Orchestrator</p>
        <h2 className="font-display text-xl font-semibold mt-1">Research Orchestrator</h2>
        <p className="text-sm text-cx-fgMuted mt-2">
          Multi-agent pipelines that chain evidence gathering, analysis, and traceable scientific reports across the R&D value chain.
        </p>
      </GlassPanel>

      <GlassPanel>
        <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim mb-3">Research Question</p>
        <textarea
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          rows={3}
          placeholder="Describe your scientific question..."
          disabled={isWorkflowBusy || workflowBlocked}
          className="w-full p-3 rounded-xl border border-cx-border bg-white/60 text-sm resize-none focus:outline-none focus:border-cx-accent/40 disabled:opacity-60"
        />
      </GlassPanel>

      <div className="grid lg:grid-cols-3 gap-4">
        {pipelines.map((pipeline) => {
          const Icon = PIPELINE_ICONS[pipeline.icon] || Sparkles;
          const isActive = activePipeline?.id === pipeline.id;
          const isThisRunning = isActive && progressRun?.status === 'running';
          return (
            <GlassPanel
              key={pipeline.id}
              className={`transition-all hover:scale-[1.01] ${isActive ? 'ring-2 ring-cx-accent/30' : ''} ${
                isThisRunning ? 'ring-cx-accent/50 shadow-[0_0_32px_rgba(8,145,178,0.12)]' : ''
              }`}
            >
              <button
                type="button"
                className="w-full text-left"
                onClick={() => { setActivePipeline(pipeline); setQuery(pipeline.query); setSelected(null); }}
              >
                <div className={`inline-flex p-2 rounded-xl border mb-3 ${isActive ? 'border-cx-accent/30 bg-cx-accent/10 text-cx-accent' : 'border-cx-border bg-white/40'}`}>
                  <Icon size={20} />
                </div>
                <h3 className="font-display font-semibold text-sm">{pipeline.name}</h3>
                <p className="text-xs text-cx-fgMuted mt-2 line-clamp-3">{pipeline.description}</p>
                <div className="mt-3 flex flex-wrap gap-1">
                  {pipeline.steps_highlight?.map((s) => (
                    <span key={s} className="text-2xs px-1.5 py-0.5 rounded-md bg-white/50 border border-cx-border">{s}</span>
                  ))}
                </div>
                <p className="text-2xs text-cx-fgDim mt-3">{pipeline.step_count} steps · auto-report</p>
              </button>
              <button
                type="button"
                onClick={() => runPipeline(pipeline)}
                disabled={isWorkflowBusy || workflowBlocked || !query.trim()}
                className="mt-4 w-full flex items-center justify-center gap-2 py-2.5 rounded-xl text-sm font-medium border border-cx-accent/30 bg-cx-accent/5 text-cx-accent hover:bg-cx-accent/10 disabled:opacity-50 transition-all"
              >
                {running && isActive ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : isThisRunning ? (
                  <span className="relative flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cx-accent opacity-75" />
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-cx-accent" />
                  </span>
                ) : (
                  <Play size={16} />
                )}
                {running && isActive ? 'Launching…' : isThisRunning ? 'Orchestrating…' : 'Run Workflow'}
              </button>
            </GlassPanel>
          );
        })}
      </div>

      {workflowLive && activeTemplate && (
        <GlassPanel className="overflow-hidden">
          <WorkflowProgress
            template={activeTemplate}
            run={progressRun}
            isExpressRun={isExpressRun}
          />
        </GlassPanel>
      )}

      <div className="grid lg:grid-cols-3 gap-6">
        <GlassPanel className="lg:col-span-1">
          <button
            type="button"
            onClick={() => setShowAdvanced((v) => !v)}
            className="text-2xs uppercase tracking-wider text-cx-fgDim hover:text-cx-accent"
          >
            {showAdvanced ? '▼' : '▶'} Advanced: all templates
          </button>
          {showAdvanced && (
            <div className="mt-4 space-y-2">
              {templates.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => { setSelected(t); setActivePipeline(null); }}
                  className={`w-full text-left p-3 rounded-xl border text-xs ${selected?.id === t.id ? 'border-cx-accent/30 bg-cx-accent/5' : 'border-cx-border bg-white/40'}`}
                >
                  <p className="font-medium">{t.name}</p>
                  <p className="text-cx-fgDim mt-1">{t.steps_json?.length} steps · governance gates enabled</p>
                </button>
              ))}
              {selected && (
                <button
                  type="button"
                  onClick={runTemplate}
                  disabled={running || workflowBlocked}
                  className="w-full py-2 rounded-xl text-xs border border-cx-border hover:bg-white/50 disabled:opacity-50"
                >
                  Run with approval gates
                </button>
              )}
            </div>
          )}

          {runs.length > 0 && (
            <div className="mt-6 pt-4 border-t border-cx-border">
              <p className="text-2xs uppercase tracking-wider text-cx-fgDim mb-2">Recent runs</p>
              <div className="space-y-1.5 max-h-48 overflow-y-auto">
                {runs.slice(0, 6).map((r) => (
                  <button
                    key={r.id}
                    type="button"
                    onClick={() => {
                      const tmpl = templates.find((t) => t.id === r.template_id);
                      if (tmpl) {
                        setActivePipeline(pipelines.find((p) => p.template_id === r.template_id) || null);
                        setSelected(null);
                      }
                      setActiveRun(r);
                    }}
                    className={`w-full text-left px-2 py-1.5 rounded-lg text-2xs truncate hover:bg-white/50 ${
                      activeRun?.id === r.id ? 'bg-cx-accent/5 text-cx-accent' : 'text-cx-fgMuted'
                    }`}
                  >
                    {r.name} · {r.status.replace(/_/g, ' ')}
                  </button>
                ))}
              </div>
            </div>
          )}
        </GlassPanel>

        {!workflowLive && activeTemplate && (
          <GlassPanel className="lg:col-span-2">
            <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim mb-4">
              Pipeline — {activeTemplate.name}
            </p>
            <p className="text-sm text-cx-fgMuted">
              Click <span className="text-cx-accent font-medium">Run Workflow</span> to start live agent orchestration.
              You will see each agent activate in sequence with real progress, citations, and confidence scores.
            </p>
            <ol className="mt-4 space-y-2">
              {activeTemplate.steps_json?.map((step, i) => (
                <li key={i} className="flex items-center gap-3 text-sm text-cx-fgMuted">
                  <span className="w-6 h-6 rounded-full border border-cx-border flex items-center justify-center text-2xs text-cx-fgDim">
                    {i + 1}
                  </span>
                  {step.agent}
                </li>
              ))}
            </ol>
          </GlassPanel>
        )}
      </div>
    </div>
  );
}
