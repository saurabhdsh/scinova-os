import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { Check } from 'lucide-react';
import PlanDraft from './PlanDraft';
import {
  approveLabPlan,
  compileLabResults,
  createFollowUp,
  createLabDossier,
  createLabPlan,
  decideLabDossier,
  draftLabPlanFromIntent,
  evaluateReadiness,
  fetchVicellFixtureFile,
  getLabDossier,
  getLabExperiment,
  getLabIssues,
  getLabResults,
  ingestLabFile,
  labError,
  resolveLabIssue,
} from '../../api/lab';
import { useLab } from './LabShell';
import {
  WORKFLOW,
  actionDetail,
  approvalLabel,
  approvalRecord,
  experimentLabel,
  experimentTitle,
  findingSentence,
  formatMeasure,
  formatParam,
  measureUnit,
  metricLabel,
  outcomeWord,
  planFields,
  recommendationReady,
  recommendationSentence,
  resultsSummary,
  readinessRows,
  stageFromStoryline,
} from './stages';
import { draftFromIntentResponse } from './assistantLogic';

const pause = (ms) => new Promise((resolve) => { setTimeout(resolve, ms); });

function Activity({ happened, status, next }) {
  return (
    <div className="grid gap-4 rounded-3xl bg-slate-50 px-4 py-4 sm:grid-cols-3">
      <div>
        <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-cx-fgDim">What happened</p>
        <p className="mt-1 text-sm leading-5 text-cx-fg">{happened}</p>
      </div>
      <div>
        <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-cx-fgDim">Status</p>
        <p className="mt-1 text-sm leading-5 text-cx-fg">{status}</p>
      </div>
      <div>
        <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-cx-fgDim">Next</p>
        <p className="mt-1 text-sm leading-5 text-cx-fg">{next}</p>
      </div>
    </div>
  );
}

function AgentTrail({ lines, live }) {
  if (!lines.length) return null;
  return (
    <div className="rounded-3xl border border-black/5 bg-white px-4 py-3">
      <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-cx-fgDim">Lab assistant</p>
      <ul className="mt-2 space-y-1.5">
        {lines.map((line, index) => {
          const current = index === lines.length - 1;
          return (
            <li key={`${index}-${line}`} className={`text-sm leading-5 ${current ? 'text-cx-fg' : 'text-cx-fgMuted'}`}>
              {current && live ? '… ' : ''}{line}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function canonical(value) {
  if (Array.isArray(value)) return value.map(canonical);
  if (value && typeof value === 'object') {
    return Object.keys(value)
      .filter((key) => !String(key).startsWith('_'))
      .sort()
      .reduce((acc, key) => {
        acc[key] = canonical(value[key]);
        return acc;
      }, {});
  }
  return value;
}

function planMatchesSnapshot(draft) {
  if (!draft?.snapshot) return false;
  return JSON.stringify(canonical(draft.parameters)) === JSON.stringify(canonical(draft.snapshot.parameters_json))
    && JSON.stringify(canonical(draft.criteria || [])) === JSON.stringify(canonical(draft.snapshot.success_criteria_json || []));
}

export default function ExperimentScreen({
  mode,
  draft,
  protocols,
  pastByCode,
  onDraftChange,
  onCreateProtocol,
  onBack,
  onStarted,
  onPrepareFollowUp,
  onRefresh,
  heldFile,
  onConsumeFile,
}) {
  const { experimentId, storyline, reloadStoryline, setDossierId } = useLab();
  const [record, setRecord] = useState(null);
  const [issues, setIssues] = useState([]);
  const [results, setResults] = useState(null);
  const [dossier, setDossier] = useState(null);
  const [feedback, setFeedback] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState('');
  const [openStage, setOpenStage] = useState(null);
  const [captureSummary, setCaptureSummary] = useState(null);
  const [trail, setTrail] = useState([]);
  const marks = useRef(new Set());

  const say = (happened, status, next) => {
    setTrail((current) => [...current, happened].slice(-8));
    setFeedback({ happened, status, next });
  };

  const stage = mode === 'draft'
    ? {
      key: 'planning',
      label: 'Planning',
      status: 'Planning',
      next: (draft?.protocolId || draft?.newProtocol)
        ? 'Review the drafted plan, then approve it.'
        : 'Describe what you want this experiment to do.',
      needsScientist: true,
    }
    : stageFromStoryline(storyline, issues);
  const activeKey = openStage || (stage.key === 'done' ? 'approval' : stage.key);

  useEffect(() => {
    setOpenStage(null);
  }, [stage.key]);

  useEffect(() => {
    if (mode !== 'experiment' || !experimentId) return undefined;
    let cancel = false;
    getLabExperiment(experimentId)
      .then((response) => {
        if (!cancel) setRecord(response.data);
      })
      .catch((err) => {
        if (!cancel) setError(labError(err));
      });
    return () => {
      cancel = true;
    };
  }, [mode, experimentId]);

  useEffect(() => {
    if (mode !== 'experiment' || !experimentId || !storyline) return undefined;
    let cancel = false;
    const moments = storyline.moments || {};
    const readiness = moments.moment_2_readiness || {};

    const run = async () => {
      if (!moments.moment_1_planning?.complete || cancel) return;
      const readyKey = `${experimentId}:ready`;
      if (!readiness.complete && !readiness.issue_count && !marks.current.has(readyKey)) {
        marks.current.add(readyKey);
        setBusy('readiness');
        try {
          const steps = [
            'Checking the samples on the plan.',
            'Checking reagent expiry and materials.',
            'Checking instrument calibration.',
            'Checking whether the operator is qualified.',
            'Checking compliance holds.',
          ];
          for (const step of steps) {
            if (cancel) return;
            say(step, 'Readiness', 'The checks are still running.');
            await pause(700);
          }
          if (cancel) return;
          const response = await evaluateReadiness(experimentId);
          const open = (response.data || []).filter((issue) => issue.status === 'open');
          if (cancel) return;
          setIssues(response.data || []);
          setFeedback({
            happened: open.length
              ? `Readiness checks finished. ${open.length === 1 ? 'One exception needs' : `${open.length} exceptions need`} a decision.`
              : 'Readiness checks finished with nothing to review.',
            status: open.length ? 'Readiness · exceptions' : 'Readiness complete',
            next: open.length ? 'Review the exception and approve the corrective action.' : 'Add the instrument file.',
          });
          await reloadStoryline();
        } catch (err) {
          marks.current.delete(readyKey);
          if (!cancel) setError(labError(err));
        } finally {
          if (!cancel) setBusy('');
        }
        return;
      }
      if (readiness.complete || readiness.issue_count) {
        try {
          const response = await getLabIssues(experimentId);
          if (!cancel) setIssues(response.data || []);
        } catch (err) {
          if (!cancel) setError(labError(err));
        }
      }
      if (!readiness.complete || cancel) {
        if (!cancel && !readiness.complete) {
          setFeedback((current) => current || {
            happened: 'Opened during readiness.',
            status: readiness.issue_count ? 'Readiness · exceptions' : 'Readiness',
            next: readiness.open_blocking ? 'Review the exception and approve the corrective action.' : 'Readiness checks are running.',
          });
        }
        return;
      }
      if (!moments.moment_3_ingestion?.complete) {
        setFeedback((current) => current || {
          happened: 'Gate 2 is closed.',
          status: 'Capture',
          next: 'Add the instrument file.',
        });
        return;
      }
      const resultsMoment = moments.moment_4_results || {};
      const resultsReady = Boolean(resultsMoment.outcome) || Boolean(resultsMoment.complete);
      if (!resultsReady && !marks.current.has(`${experimentId}:results`)) {
        marks.current.add(`${experimentId}:results`);
        setBusy('results');
        try {
          const steps = [
            'Reading the captured instrument file.',
            'Comparing each measurement with the success criteria.',
          ];
          for (const step of steps) {
            if (cancel) {
              marks.current.delete(`${experimentId}:results`);
              return;
            }
            say(step, 'Results', 'Results are being compiled.');
            await pause(700);
          }
          if (cancel) {
            marks.current.delete(`${experimentId}:results`);
            return;
          }
          await compileLabResults(experimentId);
          const response = await getLabResults(experimentId);
          if (cancel) return;
          setResults(response.data);
          setFeedback({
            happened: 'Results were compiled from the captured file.',
            status: 'Results',
            next: 'A draft dossier is being prepared for approval.',
          });
          await reloadStoryline();
        } catch (err) {
          marks.current.delete(`${experimentId}:results`);
          if (!cancel) setError(labError(err));
        } finally {
          if (!cancel) setBusy('');
        }
        return;
      }
      if (resultsReady) {
        const response = await getLabResults(experimentId).catch(() => null);
        if (!cancel && response) setResults(response.data);
      }
      const dossierId = resultsMoment.dossier_id;
      if (resultsReady && !dossierId && !marks.current.has(`${experimentId}:dossier`)) {
        setBusy('dossier');
        try {
          say('Writing the draft dossier from the compiled results.', 'Approval', 'The draft will be ready to review.');
          await pause(700);
          if (cancel) return;
          const response = await createLabDossier(experimentId);
          if (cancel) return;
          marks.current.add(`${experimentId}:dossier`);
          setDossier(response.data);
          setDossierId(response.data.id);
          setFeedback({
            happened: 'Results are in. A draft dossier is ready to review.',
            status: 'Approval',
            next: 'Read the draft, then approve it.',
          });
          await reloadStoryline();
        } catch (err) {
          if (!cancel) setError(labError(err));
        } finally {
          if (!cancel) setBusy('');
        }
        return;
      }
      if (dossierId) {
        try {
          const response = await getLabDossier(dossierId);
          if (!cancel) {
            setDossier(response.data);
            setDossierId(dossierId);
          }
        } catch (err) {
          if (!cancel) setError(labError(err));
        }
      }
      if (!cancel) {
        const current = stageFromStoryline(storyline, []);
        setFeedback((existing) => existing || {
          happened: `Opened during ${current.label.toLowerCase()}.`,
          status: current.status,
          next: current.next,
        });
      }
    };

    const timer = setTimeout(run, 0);
    return () => {
      cancel = true;
      clearTimeout(timer);
      if (!readiness.complete && !readiness.issue_count) marks.current.delete(`${experimentId}:ready`);
    };
  }, [mode, experimentId, storyline, reloadStoryline, setDossierId]);

  const createPlan = async () => {
    if (!draft?.protocolId && !draft?.newProtocol) return;
    setError('');
    setBusy('plan');
    try {
      let current = draft;
      if (!current.protocolId) {
        say('Saving the suggested protocol.', 'Planning', 'The plan is being written from it.');
        await pause(700);
        const created = await onCreateProtocol({
          title: current.protocolTitle || current.name || experimentTitle(current),
          parameters: current.parameters,
          success_criteria: current.criteria,
          exact: true,
        });
        if (!created?.id) {
          setError('The suggested protocol could not be saved.');
          return;
        }
        current = {
          ...current,
          protocolId: created.id,
          protocolCode: created.protocol_code,
          protocolTitle: created.protocol_title || current.protocolTitle,
          versionLabel: created.version_label || '1.0',
          newProtocol: false,
        };
      }
      say('Writing the experiment plan and success criteria.', 'Planning', 'The draft will appear when it is saved.');
      await pause(700);
      const response = await createLabPlan({
        protocol_version_id: current.protocolId,
        title: experimentTitle(current) || `Plan: ${current.name}`,
        parameters: {
          ...current.parameters,
          ...(current.intent ? { _scientist_intent: current.intent } : {}),
        },
        success_criteria: current.criteria,
      });
      onDraftChange({ ...current, planId: response.data.id, snapshot: response.data });
      setFeedback({
        happened: 'The draft plan is saved.',
        status: 'Planning · draft',
        next: 'Review the draft below, then approve it.',
      });
    } catch (err) {
      setError(labError(err));
    } finally {
      setBusy('');
    }
  };

  const submitIntent = async () => {
    const intent = (draft?.intent || '').trim();
    if (intent.length < 8 || busy === 'intent') return;
    setError('');
    setBusy('intent');
    try {
      say('Reading what you want this experiment to do.', 'Planning', 'The plan is being drafted from that intent.');
      await pause(700);
      say('Writing a protocol and filling the fields it needs.', 'Planning', 'You can change anything before you approve.');
      const response = await draftLabPlanFromIntent({ intent });
      const next = draftFromIntentResponse(protocols, pastByCode, intent, response.data);
      if (!next?.parameters || !Object.keys(next.parameters).length) {
        setError('A protocol could not be drafted from that description. Try again in a moment.');
        return;
      }
      onDraftChange(next);
      setFeedback({
        happened: 'The plan is drafted from your intent.',
        status: 'Planning',
        next: 'Review the protocol and parameters, then approve the plan.',
      });
    } catch (err) {
      setError(labError(err));
    } finally {
      setBusy('');
    }
  };

  const approvePlan = async () => {
    const planId = draft?.planId;
    if (!planId) return;
    setError('');
    setBusy('approve');
    try {
      say('Approving the plan.', 'Planning', 'Readiness will start next.');
      await pause(700);
      const response = await approveLabPlan(planId, {
        comment: draft?.intent
          ? `Scientist intent: ${draft.intent}`
          : 'Scientist approved the draft plan.',
        title: experimentTitle(draft) || undefined,
      });
      setFeedback({
        happened: 'The plan is approved. Readiness checks are starting.',
        status: 'Planning complete',
        next: 'Review any exception the checks return.',
      });
      await onStarted(response.data);
    } catch (err) {
      setError(labError(err));
    } finally {
      setBusy('');
    }
  };

  const approveIssue = async (issue) => {
    setError('');
    setBusy(issue.id);
    try {
      await resolveLabIssue(issue.id, {
        decision: 'approve',
        comment: `Approved ${approvalLabel(issue)}.`,
      });
      const response = await getLabIssues(experimentId);
      const open = (response.data || []).filter((row) => row.status === 'open');
      setIssues(response.data || []);
      const closed = open.length === 0;
      setFeedback({
        happened: approvalRecord(issue, closed),
        status: closed ? 'Readiness complete' : `Readiness · ${open.length} still open`,
        next: closed ? 'Add the instrument file.' : 'Review the next exception. Gate 2 closes when every corrective action is approved.',
      });
      await reloadStoryline();
      await onRefresh?.();
    } catch (err) {
      setError(labError(err));
    } finally {
      setBusy('');
    }
  };

  const captureFile = async (file) => {
    if (!file || !experimentId) return;
    setError('');
    setBusy('capture');
    try {
      say(`Reading ${file.name}.`, 'Capture', 'The file is being checked against the plan.');
      await pause(700);
      say('Checking completeness and recording the checksum.', 'Capture', 'Results will compile after the file is accepted.');
      const response = await ingestLabFile(experimentId, file);
      setCaptureSummary(response.data);
      setFeedback({
        happened: `${file.name} is in the landing zone and the checksum is recorded.`,
        status: 'Capture complete',
        next: 'Results will compile from this file.',
      });
      onConsumeFile?.();
      await reloadStoryline();
    } catch (err) {
      setError(labError(err));
    } finally {
      setBusy('');
    }
  };

  const prepareFollowUp = async () => {
    if (!experimentId || !onPrepareFollowUp) return;
    setError('');
    setBusy('follow');
    try {
      say('Preparing the next experiment with the higher seeding density.', 'Approval', 'The other planned parameters stay the same.');
      await pause(700);
      const response = await createFollowUp(experimentId);
      await onPrepareFollowUp(response.data);
    } catch (err) {
      setError(labError(err));
    } finally {
      setBusy('');
    }
  };

  const decide = async (decision) => {
    if (!dossier?.id) return;
    setError('');
    setBusy('decision');
    try {
      const response = await decideLabDossier(dossier.id, {
        decision,
        comment: decision === 'approve' ? 'Approved the draft dossier.' : 'Sent the draft dossier back.',
      });
      setDossier(response.data);
      const approved = decision === 'approve';
      setFeedback({
        happened: approved ? `Dossier version ${response.data.version} is approved.` : `Dossier version ${response.data.version} is marked ${decision.replaceAll('_', ' ')}.`,
        status: approved ? 'Complete' : 'Approval',
        next: approved ? 'This experiment is finished.' : 'Review the updated draft.',
      });
      await reloadStoryline();
      await onRefresh?.();
    } catch (err) {
      setError(labError(err));
    } finally {
      setBusy('');
    }
  };

  const plan = record?.plan;
  const linkedProtocol = (protocols || []).find((row) => row.id === plan?.protocol_version_id);
  const title = mode === 'draft'
    ? (experimentTitle(draft) || 'New experiment')
    : (record?.experiment?.title || experimentLabel(linkedProtocol) || 'Experiment');
  const sampleCount = plan?.sample_panel_json?.length || draft?.sampleCount || draft?.snapshot?.sample_panel_json?.length || 0;
  const readinessMoment = mode === 'draft' ? {} : (storyline?.moments?.moment_2_readiness || {});
  const issuesLoaded = issues.length > 0 || (Boolean(readinessMoment.complete) && !readinessMoment.issue_count);
  const evaluated = Boolean(readinessMoment.issue_count) || issues.length > 0 || Boolean(readinessMoment.complete);
  const checks = readinessRows(issues, { evaluated, sampleCount, issuesLoaded });
  const openIssues = [...issues].filter((issue) => issue.status === 'open').sort((a, b) => {
    if (a.code === 'COMPLIANCE_HOLD') return 1;
    if (b.code === 'COMPLIANCE_HOLD') return -1;
    return 0;
  });
  const othersOpen = openIssues.some((issue) => issue.code !== 'COMPLIANCE_HOLD');
  const activity = feedback || {
    happened: mode === 'draft'
      ? (draft?.protocolId || draft?.newProtocol ? 'The plan is drafted from your intent.' : 'A new experiment starts with what you want to do.')
      : 'Loading this experiment.',
    status: stage.status,
    next: stage.next,
  };
  const ingestion = storyline?.moments?.moment_3_ingestion;

  const renderStage = (key, reviewing = false) => {
    const stageIndex = WORKFLOW.findIndex((step) => step.key === key);
    const currentIndex = stage.key === 'done' ? WORKFLOW.length : WORKFLOW.findIndex((step) => step.key === stage.key);
    if (stageIndex > currentIndex) {
      const label = WORKFLOW[stageIndex]?.label || 'This step';
      return <p className="mt-3 text-sm text-cx-fgMuted">{label} has not started.</p>;
    }

    if (key === 'planning') {
      if (mode === 'experiment') {
        return (
          <div className="mt-3 text-sm">
            <p className="font-medium text-cx-fg">{plan?.title || 'Approved plan'}</p>
            {plan?.parameters_json?._scientist_intent && (
              <p className="mt-2 text-cx-fgMuted">Intent: {plan.parameters_json._scientist_intent}</p>
            )}
            <ul className="mt-3 space-y-1 text-cx-fgMuted">
              {planFields(plan?.parameters_json).map(([field, label, unit]) => (
                <li key={field}>{label}: {formatParam(field, plan?.parameters_json?.[field])}{unit ? ` ${unit}` : ''}</li>
              ))}
            </ul>
            <ul className="mt-3 space-y-1 text-cx-fgMuted">
              {(plan?.success_criteria_json || []).map((item) => (
                <li key={item.id}>{metricLabel(item.metric)} {item.operator} {item.threshold} {item.unit}</li>
              ))}
            </ul>
          </div>
        );
      }
      if (!draft?.protocolId && !draft?.newProtocol) {
        const intent = draft?.intent || '';
        const examples = [
          'Check cell viability tomorrow after 24 hours at 200,000 cells/mL.',
          'Compare seeding densities and see which one keeps viability above 85%.',
          'Measure post-thaw recovery of the CHO-K1 vials.',
          'Sequence tumor DNA and identify mutations.',
        ];
        return (
          <div className="mt-3 rounded-3xl border border-black/5 bg-white p-4 shadow-sm">
            <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-cx-fgDim">Intent</p>
            <h2 className="mt-2 font-display text-2xl font-semibold tracking-tight text-cx-fg">What do you want this experiment to do?</h2>
            <p className="mt-2 text-sm leading-6 text-cx-fgMuted">
              Write the scientific aim in your own words. The plan, protocol, and success criteria are drafted from this. You can still change them before you approve.
            </p>
            <textarea
              value={intent}
              rows={4}
              onChange={(event) => onDraftChange({ awaitingIntent: true, intent: event.target.value })}
              placeholder="For example: check CHO cell viability tomorrow, 24 hour incubation, mean viability at least 85%."
              className="mt-4 w-full resize-none rounded-2xl border border-black/10 px-3 py-3 text-sm leading-6 text-cx-fg outline-none"
            />
            <div className="mt-3 flex flex-col items-start gap-2">
              {examples.map((example) => (
                <button
                  key={example}
                  type="button"
                  onClick={() => onDraftChange({ awaitingIntent: true, intent: example })}
                  className="rounded-full border border-black/10 px-3 py-1.5 text-left text-xs leading-5 text-cx-fgMuted"
                >
                  {example}
                </button>
              ))}
            </div>
            <button
              type="button"
              onClick={submitIntent}
              disabled={intent.trim().length < 8 || busy === 'intent'}
              className="mt-4 rounded-full bg-cx-fg px-4 py-2 text-sm text-white disabled:opacity-40"
            >
              {busy === 'intent' ? 'Drafting the plan…' : 'Draft the plan'}
            </button>
          </div>
        );
      }
      const matches = planMatchesSnapshot(draft);
      return (
        <div className="mt-3">
          {draft?.intent && (
            <div className="mb-3 rounded-2xl bg-slate-50 px-4 py-3">
              <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-cx-fgDim">Intent</p>
              <p className="mt-1 text-sm leading-6 text-cx-fg">{draft.intent}</p>
              <button
                type="button"
                onClick={() => {
                  setFeedback(null);
                  onDraftChange({ awaitingIntent: true, intent: draft.intent });
                }}
                className="mt-2 text-sm font-medium text-cx-accent"
              >
                Change intent
              </button>
            </div>
          )}
          <PlanDraft draft={draft} protocols={protocols} pastByCode={pastByCode} onChange={onDraftChange} onCreateProtocol={onCreateProtocol}>
            <div className="mt-4 flex flex-wrap gap-2">
              <button
                type="button"
                onClick={createPlan}
                disabled={(!draft?.protocolId && !draft?.newProtocol) || busy === 'plan'}
                className="rounded-full bg-cx-fg px-4 py-2 text-sm text-white disabled:opacity-40"
              >
                {busy === 'plan' ? 'Saving…' : 'Create experiment plan'}
              </button>
              <button
                type="button"
                onClick={approvePlan}
                disabled={!matches || busy === 'approve'}
                className="rounded-full bg-cx-accent px-4 py-2 text-sm text-white disabled:opacity-40"
              >
                {busy === 'approve' ? 'Approving…' : 'Approve this plan'}
              </button>
            </div>
            {draft?.snapshot && !matches && (
              <p className="mt-3 text-sm text-cx-fgMuted">The draft changed. Create the experiment plan again, then approve that version.</p>
            )}
            {matches && (
              <p className="mt-3 text-sm text-cx-fgMuted">The draft above is the plan this approval will start.</p>
            )}
          </PlanDraft>
        </div>
      );
    }

    if (key === 'readiness') {
      const quietChecks = checks.filter((check) => check.state !== 'Exception');
      const stillChecking = checks.some((check) => check.state === 'Checking');
      const waitingForExceptions = (readinessMoment.open_blocking || 0) > 0 && openIssues.length === 0;
      return (
        <div className="mt-3 space-y-3">
          <p className="text-sm text-cx-fgMuted">
            {stillChecking || busy === 'readiness' || waitingForExceptions
              ? 'Readiness checks are running.'
              : openIssues.length
                ? `${openIssues.length === 1 ? 'One exception needs' : `${openIssues.length} exceptions need`} a decision.`
                : reviewing
                  ? 'Recorded checks.'
                  : 'Every check is clear.'}
          </p>
          {openIssues.map((issue) => {
            const blocked = issue.code === 'COMPLIANCE_HOLD' && othersOpen;
            return (
              <div key={issue.id} className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3">
                <p className="text-sm font-medium text-cx-fg">{issue.message}</p>
                <p className="mt-2 text-sm text-cx-fg">{actionDetail(issue)}</p>
                <button
                  type="button"
                  onClick={() => approveIssue(issue)}
                  disabled={blocked || !recommendationReady(issue) || busy === issue.id}
                  className="mt-3 rounded-full bg-cx-fg px-4 py-2 text-sm text-white disabled:opacity-40"
                >
                  {busy === issue.id ? 'Approving…' : approvalLabel(issue)}
                </button>
                {blocked && (
                  <p className="mt-2 text-xs text-cx-fgMuted">Gate 2 closes when every corrective action is approved. The other exceptions are still open.</p>
                )}
              </div>
            );
          })}
          <ul className="grid gap-2 sm:grid-cols-2">
            {quietChecks.map((check) => (
              <li key={check.code} className="rounded-2xl bg-slate-50 px-3 py-2 text-sm">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium text-cx-fg">{check.label}</span>
                  <span className={check.state === 'Checking' ? 'text-cx-fgMuted' : 'text-cx-fgMuted'}>{check.state}</span>
                </div>
                {check.detail && <p className="mt-1 text-xs leading-5 text-cx-fgMuted">{check.detail}</p>}
              </li>
            ))}
          </ul>
        </div>
      );
    }

    if (key === 'capture') {
      const captured = Boolean(ingestion?.complete);
      const sequencing = linkedProtocol?.protocol_code === 'SYN-SEQ-001' || draft?.protocolCode === 'SYN-SEQ-001';
      return (
        <div className="mt-3">
          {captured && (
            <p className="text-sm text-cx-fgMuted">
              Completeness {ingestion.completeness_percent ?? '—'}%.
              {ingestion.sha256 ? ` Checksum ${ingestion.sha256}.` : ''}
            </p>
          )}
          {!reviewing && <p className="text-sm text-cx-fgMuted">Add the instrument file to move into results.</p>}
          {!reviewing && (
          <div className="mt-3 flex flex-wrap gap-2">
            <label className="cursor-pointer rounded-full bg-cx-fg px-4 py-2 text-sm text-white">
              Upload instrument file
              <input
                type="file"
                accept=".csv,text/csv"
                className="hidden"
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  event.target.value = '';
                  if (file) captureFile(file);
                }}
              />
            </label>
            <button
              type="button"
              onClick={async () => {
                const file = heldFile || await fetchVicellFixtureFile(experimentId);
                await captureFile(file);
              }}
              disabled={busy === 'capture'}
              className="rounded-full border border-black/10 px-4 py-2 text-sm disabled:opacity-40"
            >
              {heldFile ? `Use ${heldFile.name}` : (sequencing ? 'Use the sequencing file for this plan' : 'Use the Vi-CELL file for this plan')}
            </button>
          </div>
          )}
          {!reviewing && (
            <p className="mt-3 text-sm text-cx-fgMuted">
              {sequencing
                ? 'This file is the sequencing summary for the tumor sample. Coverage and on-target bases are checked against the plan.'
                : 'This file follows the plan. At 200,000 cells/mL one sample stays weak. A higher seeding density brings that sample up, and a post-thaw plan uses its own recovery plate.'}
            </p>
          )}
          {captureSummary && (
            <p className="mt-3 text-xs text-cx-fgMuted">Checksum {captureSummary.sha256}. Completeness {captureSummary.completeness_percent}%.</p>
          )}
        </div>
      );
    }

    if (key === 'results') {
      const rows = results?.results || [];
      return (
        <div className="mt-3 space-y-2 text-sm">
          {busy === 'results' && <p className="text-cx-fgMuted">Compiling results against the success criteria.</p>}
          {rows.map((row) => (
            <div key={row.id} className="flex items-center justify-between rounded-2xl bg-slate-50 px-3 py-2">
              <span>{metricLabel(row.metric)}: {formatMeasure(row.metric, row.value)}{measureUnit(row.unit)}</span>
              <span className={row.outcome === 'fail' ? 'font-medium text-amber-700' : 'text-cx-fgMuted'}>{outcomeWord(row.outcome)}</span>
            </div>
          ))}
          {!rows.length && !busy && (
            <button
              type="button"
              onClick={() => {
                marks.current.delete(`${experimentId}:results`);
                reloadStoryline();
              }}
              className="rounded-full border border-black/10 px-4 py-2"
            >
              Compile results
            </button>
          )}
        </div>
      );
    }

    if (key === 'approval') {
      const rows = results?.results || [];
      const insights = results?.insights || [];
      const findings = insights.filter((item) => item.insight_type !== 'recommendation');
      const recommendation = insights.find((item) => item.insight_type === 'recommendation');
      return (
        <div className="mt-3 space-y-3 text-sm">
          {dossier && (
            <div className="rounded-2xl bg-slate-50 px-4 py-3">
              <p className="font-medium text-cx-fg">Dossier version {dossier.version}</p>
              <p className="mt-2 text-cx-fg">{resultsSummary(rows)}</p>
              <ul className="mt-3 space-y-2">
                {rows.map((row) => (
                  <li key={row.id}>
                    <span className="text-cx-fg">
                      {metricLabel(row.metric)} is {formatMeasure(row.metric, row.value)}{measureUnit(row.unit)}.
                    </span>
                    {row.operator && row.threshold != null && (
                      <span className="text-cx-fgMuted"> The plan required {row.operator} {row.threshold}{measureUnit(row.unit)}.</span>
                    )}
                    <span className={row.outcome === 'fail' ? ' font-medium text-amber-700' : ' text-cx-fgMuted'}> {outcomeWord(row.outcome)}.</span>
                  </li>
                ))}
              </ul>
              {findings.length > 0 && (
                <ul className="mt-3 space-y-1 text-cx-fgMuted">
                  {findings.map((item) => (
                    <li key={item.id}>{findingSentence(item)}</li>
                  ))}
                </ul>
              )}
              {recommendation && (
                <div className="mt-3">
                  <p className="text-cx-fg">{recommendationSentence(recommendation)}</p>
                  <button
                    type="button"
                    onClick={prepareFollowUp}
                    disabled={busy === 'follow' || !onPrepareFollowUp}
                    className="mt-3 rounded-full bg-cx-fg px-4 py-2 text-sm text-white disabled:opacity-40"
                  >
                    {busy === 'follow' ? 'Preparing…' : 'Prepare the next experiment'}
                  </button>
                </div>
              )}
            </div>
          )}
          {busy === 'dossier' && <p className="text-cx-fgMuted">Preparing the draft dossier.</p>}
          {dossier && dossier.status !== 'approved' && !dossier.publishable && (
            <div className="flex flex-wrap gap-2">
              <button type="button" onClick={() => decide('approve')} disabled={busy === 'decision'} className="rounded-full bg-cx-fg px-4 py-2 text-white disabled:opacity-40">
                Approve dossier version {dossier.version}
              </button>
              <button type="button" onClick={() => decide('revision_requested')} disabled={busy === 'decision'} className="rounded-full border border-black/10 px-4 py-2 disabled:opacity-40">
                Request a revision
              </button>
            </div>
          )}
          {dossier?.publishable && <p className="text-cx-fgMuted">This dossier is approved.</p>}
        </div>
      );
    }
    return null;
  };

  if (mode === 'experiment' && storyline?.experiment_id !== experimentId) {
    return (
      <div className="space-y-3">
        <button type="button" onClick={onBack} className="text-sm font-medium text-cx-accent">Experiments</button>
        <h1 className="font-display text-4xl font-semibold tracking-tight text-cx-fg">Opening experiment</h1>
        <p className="text-sm text-cx-fgMuted">Loading the current stage.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <button type="button" onClick={onBack} className="text-sm font-medium text-cx-accent">Experiments</button>
        <h1 className="mt-2 font-display text-4xl font-semibold tracking-tight text-cx-fg">{title}</h1>
        {mode === 'experiment' && linkedProtocol?.protocol_code && (
          <p className="mt-1 text-sm text-cx-fgMuted">{linkedProtocol.protocol_code}</p>
        )}
        {mode === 'draft' && draft?.protocolCode && (
          <p className="mt-1 text-sm text-cx-fgMuted">{draft.protocolCode}</p>
        )}
      </div>

      <Activity happened={activity.happened} status={activity.status} next={activity.next} />
      <AgentTrail lines={trail} live={Boolean(busy)} />
      {error && <p className="text-sm text-rose-700">{error}</p>}

      <ol className="space-y-2">
        {WORKFLOW.map((step, index) => {
          const currentIndex = WORKFLOW.findIndex((item) => item.key === stage.key);
          const done = stage.key === 'done' || (currentIndex > -1 && index < currentIndex);
          const current = step.key === stage.key;
          const open = activeKey === step.key;
          return (
            <li key={step.key}>
              <button
                type="button"
                onClick={() => setOpenStage(step.key)}
                className={`flex w-full items-center gap-3 rounded-2xl px-3 py-3 text-left ${current ? 'bg-white shadow-sm ring-1 ring-cx-accent/40' : 'bg-transparent'}`}
              >
                <span className={`flex h-7 w-7 items-center justify-center rounded-full text-xs ${done ? 'bg-cx-fg text-white' : current ? 'bg-cx-accent text-white' : 'bg-slate-200 text-cx-fgMuted'}`}>
                  {done ? <Check size={14} /> : index + 1}
                </span>
                <span className="flex-1">
                  <span className={`block text-sm font-medium ${current ? 'text-cx-fg' : 'text-cx-fgMuted'}`}>{step.label}</span>
                  {current && <span className="block text-xs text-cx-fgMuted">{stage.next}</span>}
                </span>
              </button>
              {(open || done) && <div className="pb-2 pl-12 pr-2">{renderStage(step.key, done && !current)}</div>}
            </li>
          );
        })}
      </ol>

      {mode === 'experiment' && (
        <p className="text-sm text-cx-fgMuted">
          <Link to="/lab/lineage" className="underline-offset-2 hover:underline">Lineage</Link>
          <span className="px-2">·</span>
          <Link to="/lab/audit" className="underline-offset-2 hover:underline">Audit</Link>
          <span className="px-2">·</span>
          <Link to="/lab/next" className="underline-offset-2 hover:underline">Next experiment</Link>
        </p>
      )}
    </div>
  );
}
