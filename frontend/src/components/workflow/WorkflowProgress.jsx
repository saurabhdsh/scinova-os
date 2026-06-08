import { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
import {
  Activity,
  Bot,
  CheckCircle,
  Clock,
  Download,
  FileText,
  Loader2,
  PauseCircle,
  Shield,
  Sparkles,
  AlertTriangle,
  Zap,
} from 'lucide-react';
import { triggerWorkflowDownload, triggerWorkflowStepDownload } from '../../api/client';
import AgentOutputRenderer, { AgentProseRenderer } from '../agents/AgentOutputRenderer';

const ACTIVITY_MESSAGES = [
  'Gathering PubMed literature…',
  'Scanning indexed document chunks…',
  'Querying knowledge graph…',
  'Routing to specialized SLM…',
  'Synthesizing structured output…',
];

const STATUS_STYLES = {
  completed: {
    ring: 'border-cx-success/40 bg-cx-success/10 text-cx-success',
    chip: 'border-cx-success/30 bg-cx-success/8 text-cx-success',
    glow: 'shadow-[0_0_20px_rgba(5,150,105,0.15)]',
  },
  running: {
    ring: 'border-cx-accent/50 bg-cx-accent/12 text-cx-accent',
    chip: 'border-cx-accent/40 bg-cx-accent/10 text-cx-accent',
    glow: 'shadow-[0_0_24px_rgba(8,145,178,0.22)]',
  },
  awaiting_approval: {
    ring: 'border-cx-warn/40 bg-cx-warn/10 text-cx-warn',
    chip: 'border-cx-warn/30 bg-cx-warn/8 text-cx-warn',
    glow: '',
  },
  failed: {
    ring: 'border-cx-danger/40 bg-cx-danger/10 text-cx-danger',
    chip: 'border-cx-danger/30 bg-cx-danger/8 text-cx-danger',
    glow: '',
  },
  rejected: {
    ring: 'border-cx-danger/40 bg-cx-danger/10 text-cx-danger',
    chip: 'border-cx-danger/30 bg-cx-danger/8 text-cx-danger',
    glow: '',
  },
  pending: {
    ring: 'border-cx-border bg-white/50 text-cx-fgDim',
    chip: 'border-cx-border bg-white/40 text-cx-fgDim',
    glow: '',
  },
};

function shortAgentName(name) {
  if (!name) return 'Agent';
  const parts = name.split(/[\s/]+/);
  return parts.length > 2 ? `${parts[0]} ${parts[1]}` : name.split(' ')[0];
}

function StepIcon({ status, size = 16 }) {
  if (status === 'completed') return <CheckCircle size={size} />;
  if (status === 'running') return <Loader2 size={size} className="animate-spin" />;
  if (status === 'awaiting_approval') return <PauseCircle size={size} />;
  if (status === 'failed' || status === 'rejected') return <AlertTriangle size={size} />;
  return <Clock size={size} />;
}

export default function WorkflowProgress({ template, run, isExpressRun }) {
  const steps = template?.steps_json || [];
  const runSteps = run?.steps_json || [];
  const activeStepRef = useRef(null);
  const [activityIdx, setActivityIdx] = useState(0);

  const completedCount = runSteps.filter((s) => s.status === 'completed').length;
  const totalSteps = steps.length || runSteps.length;
  const runningStep = runSteps.find((s) => s.status === 'running');
  const runningIndex = runSteps.findIndex((s) => s.status === 'running');
  const progressPct = totalSteps ? Math.round((completedCount / totalSteps) * 100) : 0;
  const isRunning = run?.status === 'running';
  const isComplete = run?.status === 'completed';
  const isFailed = run?.status === 'failed';

  const totalCitations = useMemo(
    () => runSteps.reduce((sum, s) => sum + (s.citations_count || 0), 0),
    [runSteps],
  );

  useEffect(() => {
    if (!isRunning) return undefined;
    const timer = setInterval(() => {
      setActivityIdx((i) => (i + 1) % ACTIVITY_MESSAGES.length);
    }, 2200);
    return () => clearInterval(timer);
  }, [isRunning]);

  useEffect(() => {
    if (runningStep && activeStepRef.current) {
      activeStepRef.current.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }, [runningStep?.agent, runningIndex]);

  if (!run || !template) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
      className="space-y-5"
    >
      {/* Live orchestration header */}
      <div className={`relative overflow-hidden rounded-2xl border p-5 ${
        isComplete ? 'border-cx-success/25 bg-gradient-to-br from-cx-success/8 to-white/60' :
        isFailed ? 'border-cx-danger/25 bg-gradient-to-br from-cx-danger/8 to-white/60' :
        'border-cx-accent/25 bg-gradient-to-br from-cx-accent/8 via-white/70 to-cx-accent2/5'
      }`}>
        {isRunning && (
          <div className="workflow-shimmer absolute inset-0 pointer-events-none opacity-40" />
        )}

        <div className="relative flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              {isRunning && (
                <span className="relative flex h-2.5 w-2.5">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cx-accent opacity-60" />
                  <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-cx-accent" />
                </span>
              )}
              <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim">
                {isRunning ? 'Live orchestration' : isComplete ? 'Workflow complete' : 'Workflow status'}
              </p>
            </div>
            <h3 className="font-display text-lg font-semibold mt-1">
              {isRunning
                ? (runningStep ? runningStep.agent : 'Initializing agent pipeline…')
                : isComplete
                  ? 'All agents finished — report ready'
                  : `Workflow ${run.status.replace(/_/g, ' ')}`}
            </h3>
            {isRunning && (
              <motion.p
                key={activityIdx}
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                className="text-xs text-cx-accent mt-2 flex items-center gap-1.5"
              >
                <Activity size={12} className="animate-pulse" />
                {ACTIVITY_MESSAGES[activityIdx]}
              </motion.p>
            )}
          </div>

          <div className="flex flex-wrap gap-3 text-xs">
            <div className="px-3 py-2 rounded-xl border border-cx-border bg-white/60">
              <p className="text-2xs uppercase tracking-wider text-cx-fgDim">Progress</p>
              <p className="font-display font-semibold text-cx-fg mt-0.5">
                {completedCount} / {totalSteps} agents
              </p>
            </div>
            {totalCitations > 0 && (
              <div className="px-3 py-2 rounded-xl border border-cx-border bg-white/60">
                <p className="text-2xs uppercase tracking-wider text-cx-fgDim">Evidence</p>
                <p className="font-display font-semibold text-cx-fg mt-0.5">{totalCitations} citations</p>
              </div>
            )}
            {run.confidence != null && isComplete && (
              <div className="px-3 py-2 rounded-xl border border-cx-success/25 bg-cx-success/5">
                <p className="text-2xs uppercase tracking-wider text-cx-fgDim">Confidence</p>
                <p className="font-display font-semibold text-cx-success mt-0.5">
                  {(run.confidence * 100).toFixed(0)}%
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Animated progress bar */}
        <div className="relative mt-5 h-2 rounded-full bg-cx-border/40 overflow-hidden">
          <motion.div
            className={`absolute inset-y-0 left-0 rounded-full ${
              isComplete ? 'bg-gradient-to-r from-cx-success to-emerald-400' :
              isFailed ? 'bg-cx-danger' :
              'bg-gradient-to-r from-cx-accent via-cyan-400 to-cx-accent2'
            }`}
            initial={{ width: 0 }}
            animate={{ width: `${isComplete ? 100 : Math.max(progressPct, isRunning ? 8 : 0)}%` }}
            transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
          />
          {isRunning && (
            <div className="workflow-progress-sheen absolute inset-0 pointer-events-none" />
          )}
        </div>
        <div className="flex justify-between mt-2 text-2xs text-cx-fgDim uppercase tracking-wider">
          <span>{progressPct}% complete</span>
          {isRunning && runningStep && (
            <span className="text-cx-accent">Step {runningIndex + 1} of {totalSteps}</span>
          )}
        </div>
      </div>

      {/* Horizontal agent pipeline strip */}
      <div className="overflow-x-auto pb-1 -mx-1 px-1">
        <div className="flex items-center gap-0 min-w-max">
          {steps.map((step, i) => {
            const runStep = runSteps[i];
            const status = runStep?.status || 'pending';
            const styles = STATUS_STYLES[status] || STATUS_STYLES.pending;
            const connectorDone = runSteps[i]?.status === 'completed';
            const connectorActive = runSteps[i]?.status === 'running';

            return (
              <div key={step.agent} className="flex items-center">
                <motion.div
                  initial={{ scale: 0.85, opacity: 0.5 }}
                  animate={{
                    scale: status === 'running' ? 1.05 : status === 'completed' ? 1 : 0.95,
                    opacity: status === 'pending' ? 0.55 : 1,
                  }}
                  transition={{ type: 'spring', stiffness: 260, damping: 22 }}
                  className={`relative flex flex-col items-center w-[88px] ${styles.glow}`}
                >
                  {status === 'running' && (
                    <motion.span
                      className="absolute inset-0 rounded-2xl border-2 border-cx-accent/30"
                      animate={{ scale: [1, 1.15, 1], opacity: [0.6, 0, 0.6] }}
                      transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
                    />
                  )}
                  <div className={`relative z-10 w-11 h-11 rounded-xl border-2 flex items-center justify-center ${styles.ring}`}>
                    <StepIcon status={status} size={18} />
                  </div>
                  <p className={`mt-2 text-2xs text-center leading-tight max-w-[80px] ${
                    status === 'running' ? 'text-cx-accent font-medium' :
                    status === 'completed' ? 'text-cx-success' : 'text-cx-fgDim'
                  }`}>
                    {shortAgentName(step.agent)}
                  </p>
                  {runStep?.citations_count > 0 && status === 'completed' && (
                    <span className="mt-1 text-[9px] px-1.5 py-0.5 rounded bg-cx-success/10 text-cx-success border border-cx-success/20">
                      {runStep.citations_count} cites
                    </span>
                  )}
                </motion.div>

                {i < steps.length - 1 && (
                  <div className="relative w-8 h-0.5 mx-0.5 bg-cx-border/50 overflow-hidden rounded-full">
                    <motion.div
                      className={`absolute inset-y-0 left-0 rounded-full ${
                        connectorActive ? 'workflow-flow-line bg-cx-accent' :
                        connectorDone ? 'bg-cx-success' : 'bg-transparent'
                      }`}
                      initial={{ width: '0%' }}
                      animate={{
                        width: connectorDone ? '100%' : connectorActive ? '100%' : '0%',
                      }}
                      transition={{ duration: connectorActive ? 1.8 : 0.5, ease: 'easeInOut' }}
                    />
                  </div>
                )}
              </div>
            );
          })}
          {isComplete && (
            <motion.div
              initial={{ scale: 0, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ type: 'spring', delay: 0.2 }}
              className="ml-3 flex items-center gap-2 px-3 py-2 rounded-xl border border-cx-success/30 bg-cx-success/10 text-cx-success"
            >
              <Sparkles size={14} />
              <span className="text-xs font-medium">Report</span>
            </motion.div>
          )}
        </div>
      </div>

      {/* Vertical step timeline with live output */}
      <div className="space-y-0">
        <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim mb-4 flex items-center gap-2">
          <Zap size={12} className="text-cx-accent" />
          Agent execution trace
        </p>

        {steps.map((step, i) => {
          const runStep = runSteps[i];
          const status = runStep?.status || 'pending';
          const styles = STATUS_STYLES[status] || STATUS_STYLES.pending;
          const isActive = status === 'running';
          const prevCompleted = i === 0 || runSteps[i - 1]?.status === 'completed';
          const connectorFill = status === 'completed' || (isActive && prevCompleted);

          return (
            <div
              key={`${step.agent}-${i}`}
              ref={isActive ? activeStepRef : null}
              className="flex gap-4"
            >
              <div className="flex flex-col items-center w-10 shrink-0">
                <motion.div
                  layout
                  className={`relative w-9 h-9 rounded-full flex items-center justify-center border-2 ${styles.ring}`}
                  animate={isActive ? { boxShadow: ['0 0 0 0 rgba(8,145,178,0.3)', '0 0 0 8px rgba(8,145,178,0)', '0 0 0 0 rgba(8,145,178,0.3)'] } : {}}
                  transition={isActive ? { duration: 2, repeat: Infinity } : {}}
                >
                  <StepIcon status={status} />
                </motion.div>
                {i < steps.length - 1 && (
                  <div className="relative w-0.5 flex-1 my-1 min-h-[28px] bg-cx-border/40 overflow-hidden rounded-full">
                    <motion.div
                      className={`absolute inset-x-0 top-0 rounded-full ${
                        connectorFill ? (isActive ? 'bg-cx-accent workflow-flow-vertical' : 'bg-cx-success') : 'bg-transparent'
                      }`}
                      initial={{ height: '0%' }}
                      animate={{ height: connectorFill ? '100%' : '0%' }}
                      transition={{ duration: isActive ? 2 : 0.4, ease: 'easeOut' }}
                      style={{ width: '100%' }}
                    />
                  </div>
                )}
              </div>

              <div className="flex-1 pb-5 min-w-0">
                <div className="flex items-center gap-2 flex-wrap w-full">
                  <Bot size={14} className={isActive ? 'text-cx-accent' : 'text-cx-fgDim'} />
                  <p className={`font-medium text-sm ${isActive ? 'text-cx-accent' : ''}`}>{step.agent}</p>
                  {step.requires_approval && !isExpressRun && (
                    <span className="text-2xs text-cx-accent2 flex items-center gap-0.5">
                      <Shield size={10} /> Approval gate
                    </span>
                  )}
                  <span className={`text-2xs px-2 py-0.5 rounded-full border capitalize ${styles.chip}`}>
                    {status.replace(/_/g, ' ')}
                  </span>
                  {status === 'completed' && run?.id && (
                    <button
                      type="button"
                      onClick={() => triggerWorkflowStepDownload(run.id, i)}
                      className="ml-auto flex items-center gap-1 text-2xs text-cx-accent hover:text-cx-accent/80 border border-cx-accent/25 px-2 py-0.5 rounded-lg hover:bg-cx-accent/5"
                    >
                      <Download size={11} /> Download
                    </button>
                  )}
                </div>

                <AnimatePresence mode="wait">
                  {(runStep?.output || isActive) && (
                    <motion.div
                      key={runStep?.agent_run_id || `${status}-${i}`}
                      initial={{ opacity: 0, height: 0, marginTop: 0 }}
                      animate={{ opacity: 1, height: 'auto', marginTop: 8 }}
                      exit={{ opacity: 0, height: 0 }}
                      transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
                      className={`rounded-xl border text-xs overflow-hidden ${
                        isActive
                          ? 'border-cx-accent/30 bg-gradient-to-br from-cx-accent/5 to-white/60'
                          : status === 'completed'
                            ? 'border-cx-success/20 bg-cx-success/5'
                            : 'border-cx-border bg-white/40'
                      }`}
                    >
                      {isActive && !runStep?.output && (
                        <div className="p-4 space-y-3">
                          <div className="flex items-center gap-2 text-cx-accent">
                            <Loader2 size={14} className="animate-spin" />
                            <span className="font-medium">Agent running…</span>
                          </div>
                          <div className="space-y-2">
                            {[0, 1, 2].map((bar) => (
                              <div
                                key={bar}
                                className="h-2 rounded-full bg-cx-border/30 overflow-hidden"
                              >
                                <motion.div
                                  className="h-full rounded-full bg-gradient-to-r from-cx-accent/40 to-cx-accent2/40"
                                  animate={{ x: ['-100%', '100%'] }}
                                  transition={{
                                    duration: 1.4,
                                    repeat: Infinity,
                                    delay: bar * 0.2,
                                    ease: 'easeInOut',
                                  }}
                                  style={{ width: '40%' }}
                                />
                              </div>
                            ))}
                          </div>
                          <p className="text-cx-fgMuted">{ACTIVITY_MESSAGES[activityIdx]}</p>
                        </div>
                      )}

                      {runStep?.output && (
                        <div className="p-4 space-y-3">
                          <div className="flex flex-wrap gap-3 text-cx-fgDim">
                            {runStep.citations_count != null && (
                              <span>{runStep.citations_count} citations</span>
                            )}
                            {runStep.confidence != null && (
                              <span>{(runStep.confidence * 100).toFixed(0)}% confidence</span>
                            )}
                            {runStep.model_selected && (
                              <span className="font-mono text-[10px]">{runStep.model_selected}</span>
                            )}
                          </div>
                          {runStep.output_json ? (
                            <AgentOutputRenderer output={runStep.output_json} compact />
                          ) : (
                            <AgentProseRenderer text={runStep.output} compact />
                          )}
                        </div>
                      )}
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </div>
          );
        })}
      </div>

      {/* Export bundle */}
      {completedCount > 0 && run?.id && (
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => triggerWorkflowDownload(run.id, 'markdown')}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm border border-cx-accent/30 bg-cx-accent/5 text-cx-accent hover:bg-cx-accent/10"
          >
            <Download size={14} />
            Download all agent outputs (.md)
          </button>
          <button
            type="button"
            onClick={() => triggerWorkflowDownload(run.id, 'json')}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm border border-cx-border bg-white/50 text-cx-fgMuted hover:text-cx-fg"
          >
            <Download size={14} />
            Export JSON
          </button>
        </div>
      )}

      {/* Completion footer */}
      <AnimatePresence>
        {isComplete && run.output_json?.report_id && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="p-4 rounded-xl border border-cx-success/25 bg-cx-success/5"
          >
            <p className="text-sm text-cx-fg">{run.output_json?.summary}</p>
            <Link
              to="/reports"
              className="inline-flex items-center gap-2 mt-3 px-4 py-2.5 rounded-xl text-sm font-medium border border-cx-success/30 bg-cx-success/10 text-cx-success hover:bg-cx-success/15 transition-colors"
            >
              <FileText size={16} />
              View generated report
            </Link>
          </motion.div>
        )}

        {run.status === 'pending_approval' && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="p-4 rounded-xl border border-cx-warn/25 bg-cx-warn/5"
          >
            <Link to="/governance" className="inline-flex items-center gap-1 text-sm text-cx-warn hover:underline">
              <Shield size={14} /> Approval required in Governance →
            </Link>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
