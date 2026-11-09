export const WORKFLOW = [
  { key: 'planning', label: 'Planning' },
  { key: 'readiness', label: 'Readiness' },
  { key: 'capture', label: 'Capture' },
  { key: 'results', label: 'Results' },
  { key: 'approval', label: 'Approval' },
];

export const PARAM_FIELDS = [
  ['seeding_density_cells_per_ml', 'Seeding density', 'cells/mL', 'number'],
  ['incubation_hours', 'Incubation', 'hours', 'number'],
  ['passage_number', 'Passage', '', 'number'],
  ['trypan_blue_percent', 'Trypan blue', '%', 'number'],
  ['operator', 'Operator', '', 'text'],
  ['instrument_serial', 'Instrument', '', 'text'],
  ['reagent_lot', 'Reagent lot', '', 'text'],
];

const SEQUENCING_FIELDS = {
  sample_type: ['sample_type', 'Sample', '', 'text'],
  assay: ['assay', 'Assay', '', 'text'],
  gene_panel: ['gene_panel', 'Gene panel', '', 'text'],
  target_coverage_x: ['target_coverage_x', 'Target coverage', 'x', 'number'],
  tumor_fraction_percent: ['tumor_fraction_percent', 'Tumor fraction', '%', 'number'],
  library_lot: ['library_lot', 'Library lot', '', 'text'],
};

export function planFields(parameters) {
  const known = new Map(PARAM_FIELDS.map((row) => [row[0], row]));
  return Object.keys(parameters || {})
    .filter((key) => !key.startsWith('_'))
    .map((key) => known.get(key) || SEQUENCING_FIELDS[key] || [key, key.replaceAll('_', ' '), '', 'text']);
}

const CHECKS = [
  { code: 'CALIBRATION_DUE', label: 'Calibration' },
  { code: 'NEAR_EXPIRY', label: 'Expiry' },
  { code: 'TRAINING_GAP', label: 'Training' },
  { code: 'COMPLIANCE_HOLD', label: 'Compliance hold' },
  { code: 'SAMPLES', label: 'Samples' },
  { code: 'MATERIALS', label: 'Materials and consumables' },
];

export function experimentTitle(draft) {
  const custom = (draft?.experimentName || '').trim();
  if (custom) return custom;
  if (draft?.planTitle) return draft.planTitle;
  if (draft?.name) return draft.name;
  return '';
}

export function experimentLabel(protocol) {
  if (protocol?.protocol_code === 'SYN-SEQ-001') return 'Tumor DNA sequencing';
  if (protocol?.protocol_code === 'SYN-CVP-001') return 'Cell viability';
  if (protocol?.protocol_code === 'SYN-CVP-002') return 'Seeding-density screen';
  if (protocol?.protocol_code === 'SYN-CVP-003') return 'Post-thaw recovery';
  return protocol?.protocol_title || protocol?.title || 'Experiment';
}

export function metricLabel(metric) {
  if (metric === 'mean_coverage_x') return 'Mean coverage';
  if (metric === 'on_target_percent') return 'On-target bases';
  if (metric === 'mean_viability_percent') return 'Mean viability';
  if (metric === 'cv_percent') return 'Coefficient of variation';
  return String(metric || '').replaceAll('_', ' ');
}

export function formatMeasure(metric, value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return value == null || value === '' ? '—' : String(value);
  if (metric === 'mean_coverage_x') return String(Math.round(number));
  if (metric === 'on_target_percent') return number.toFixed(1);
  if (metric === 'cv_percent') return number.toFixed(1);
  if (metric === 'mean_viability_percent') return number.toFixed(2);
  return String(value);
}

export function measureUnit(unit) {
  if (unit === 'x') return 'x';
  if (!unit || unit === 'percent') return '%';
  return ` ${unit}`;
}

export function outcomeWord(outcome) {
  if (outcome === 'pass') return 'Passed';
  if (outcome === 'fail') return 'Failed';
  return outcome || '—';
}

export function resultsSummary(rows) {
  const list = rows || [];
  const failed = list.filter((row) => row.outcome === 'fail');
  if (!list.length) return 'Results are not compiled yet.';
  if (!failed.length) return 'Every success criterion passed.';
  if (failed.length === list.length) {
    return failed.length === 1
      ? 'The run did not meet its success criterion.'
      : 'The run did not meet its success criteria.';
  }
  return `${failed.length} of ${list.length} success criteria failed.`;
}

function insightEvidence(insight) {
  return insight?.evidence_json || insight?.evidence || {};
}

export function findingSentence(insight) {
  const evidence = insightEvidence(insight);
  const rule = insight?.rule_id || '';
  if (rule === 'LAB-RULE-VIAB-ABS' || /low viability/i.test(insight?.title || '')) {
    const count = (evidence.calculated_values || []).length;
    const threshold = evidence.threshold ?? 70;
    if (count) return `${count} sample${count === 1 ? '' : 's'} measured below ${threshold}% viability.`;
  }
  if (rule === 'LAB-RULE-CV-001' || /coefficient of variation/i.test(insight?.title || '')) {
    const value = formatMeasure('cv_percent', evidence.calculated_value);
    const limit = evidence.threshold ?? 10;
    if (evidence.calculated_value != null) {
      return `The samples vary more than the plan allows: ${value}% versus a limit of ${limit}%.`;
    }
  }
  if (rule === 'LAB-RULE-VIAB-HIST' || /historical/i.test(insight?.title || '')) {
    return 'Mean viability is below the range of earlier experiments.';
  }
  return String(insight?.statement || insight?.title || '')
    .replace(/\s*\([A-Z][A-Z0-9-]*\)\.?/g, '')
    .trim();
}

export function recommendationSentence(insight) {
  const evidence = insightEvidence(insight);
  const from = Number(evidence.current_value);
  const to = Number(evidence.proposed_value);
  if (evidence.parameter === 'seeding_density_cells_per_ml' && Number.isFinite(from) && Number.isFinite(to)) {
    return `Raise seeding density from ${Math.round(from).toLocaleString()} to ${Math.round(to).toLocaleString()} cells/mL, and keep every other planned parameter the same.`;
  }
  return findingSentence(insight);
}

export function formatParam(key, value) {
  if (value === null || value === undefined || value === '') return '—';
  if (key === 'target_coverage_x' && Number.isFinite(Number(value))) return Number(value).toLocaleString();
  if (key === 'seeding_density_cells_per_ml' && Number.isFinite(Number(value))) {
    return Number(value).toLocaleString();
  }
  return String(value);
}

export function stageFromStoryline(storyline, issues = []) {
  const moments = storyline?.moments || {};
  const open = issues.filter((issue) => issue.status === 'open');
  if (!moments.moment_1_planning?.complete) {
    return {
      key: 'planning',
      label: 'Planning',
      status: 'Planning',
      next: 'Choose a protocol and approve the plan.',
      needsScientist: true,
    };
  }
  if (!moments.moment_2_readiness?.complete) {
    const count = open.length || moments.moment_2_readiness?.open_blocking || 0;
    return {
      key: 'readiness',
      label: 'Readiness',
      status: count ? 'Readiness · exceptions' : 'Readiness',
      next: count
        ? `Review ${count === 1 ? 'the exception' : `${count} exceptions`}.`
        : 'Readiness checks are running.',
      needsScientist: count > 0,
    };
  }
  if (!moments.moment_3_ingestion?.complete) {
    return {
      key: 'capture',
      label: 'Capture',
      status: 'Capture',
      next: 'Add the instrument file.',
      needsScientist: true,
    };
  }
  const results = moments.moment_4_results || {};
  const resultsReady = Boolean(results.outcome) || Boolean(results.complete);
  if (!resultsReady) {
    return {
      key: 'results',
      label: 'Results',
      status: 'Results',
      next: 'Results are being compiled.',
      needsScientist: false,
    };
  }
  if (!results.publishable) {
    return {
      key: 'approval',
      label: 'Approval',
      status: 'Approval',
      next: 'Review the draft dossier.',
      needsScientist: true,
    };
  }
  return {
    key: 'done',
    label: 'Complete',
    status: 'Complete',
    next: 'This experiment is finished.',
    needsScientist: false,
  };
}

export function actionDetail(issue) {
  const recommendation = issue?.recommendation_json || {};
  switch (recommendation.action) {
    case 'swap_lot':
      return `Use lot ${recommendation.lot_number} in place of the lot that is near expiry.`;
    case 'use_alternate_instrument':
      return `Run on ${recommendation.instrument_serial}, which has a current calibration.`;
    case 'assign_alternate':
      return recommendation.operator_name
        ? `Assign ${recommendation.operator_name}, who is qualified on this protocol.`
        : 'No qualified operator is on record for this protocol.';
    case 'resolve_blocking_issues':
      return 'Release the compliance hold once the other exceptions are approved.';
    default:
      return issue?.message || 'Review this exception.';
  }
}

export function approvalRecord(issue, closed) {
  const recommendation = issue?.recommendation_json || {};
  let sentence = 'The corrective action is approved.';
  if (recommendation.action === 'swap_lot') sentence = `Lot ${recommendation.lot_number} is approved.`;
  if (recommendation.action === 'use_alternate_instrument') sentence = `Instrument ${recommendation.instrument_serial} is approved.`;
  if (recommendation.action === 'assign_alternate' && recommendation.operator_name) sentence = `${recommendation.operator_name} is approved as the operator.`;
  if (recommendation.action === 'resolve_blocking_issues') sentence = 'The compliance release is approved.';
  return closed ? `${sentence} Gate 2 is closed.` : sentence;
}

export function recommendationReady(issue) {
  const recommendation = issue?.recommendation_json || {};
  if (recommendation.action === 'assign_alternate') return Boolean(recommendation.operator_name);
  if (recommendation.action === 'swap_lot') return Boolean(recommendation.lot_number);
  if (recommendation.action === 'use_alternate_instrument') return Boolean(recommendation.instrument_serial);
  return Boolean(recommendation.action);
}

export function approvalLabel(issue) {
  const recommendation = issue?.recommendation_json || {};
  switch (recommendation.action) {
    case 'swap_lot':
      return `Approve lot ${recommendation.lot_number}`;
    case 'use_alternate_instrument':
      return `Approve instrument ${recommendation.instrument_serial}`;
    case 'assign_alternate':
      return recommendation.operator_name ? `Approve ${recommendation.operator_name}` : 'No qualified operator to approve';
    case 'resolve_blocking_issues':
      return 'Approve the compliance release';
    default:
      return 'Approve this action';
  }
}

export function readinessRows(issues, { evaluated, sampleCount, issuesLoaded = true }) {
  const known = evaluated && issuesLoaded;
  return CHECKS.map((check) => {
    if (check.code === 'SAMPLES') {
      if (!known) return { ...check, state: 'Checking' };
      return { ...check, state: sampleCount ? 'Clear' : 'Exception', detail: sampleCount ? `${sampleCount} samples on the plan.` : 'The plan has no samples.' };
    }
    if (check.code === 'MATERIALS') {
      const lot = issues.find((issue) => issue.code === 'NEAR_EXPIRY');
      if (!known) return { ...check, state: 'Checking' };
      if (!lot) return { ...check, state: 'Clear', detail: 'Materials and consumables are available.' };
      return { ...check, state: lot.status === 'open' ? 'Exception' : 'Approved', detail: actionDetail(lot) };
    }
    const issue = issues.find((row) => row.code === check.code);
    if (!known) return { ...check, state: 'Checking' };
    if (!issue) return { ...check, state: 'Clear' };
    return {
      ...check,
      state: issue.status === 'open' ? 'Exception' : 'Approved',
      detail: actionDetail(issue),
    };
  });
}

export function samePlan(left, right) {
  if (!left || !right) return false;
  return JSON.stringify(left.parameters || {}) === JSON.stringify(right.parameters_json || left.parameters || {})
    && JSON.stringify(left.criteria || []) === JSON.stringify(right.success_criteria_json || left.criteria || {});
}
