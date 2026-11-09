import { experimentLabel, metricLabel } from './stages';

const PROTOCOL_RULES = [
  { code: 'SYN-SEQ-001', test: /sequenc|mutation|tumor|dna|ngs|variant/i },
  { code: 'SYN-CVP-003', test: /thaw|cryo|recover/i },
  { code: 'SYN-CVP-002', test: /seed|density screen|seeding-density/i },
  { code: 'SYN-CVP-001', test: /viab|trypan|vicell|cho/i },
];

function approvedProtocols(protocols) {
  return (protocols || []).filter((row) => row.status === 'approved');
}

function matchProtocol(text, protocols) {
  for (const rule of PROTOCOL_RULES) {
    if (!rule.test.test(text)) continue;
    const found = approvedProtocols(protocols).find((row) => row.protocol_code === rule.code);
    if (found) return found;
  }
  return null;
}

function isRunIntent(text) {
  return /\b(want|run|prepare|plan|start|switch|instead|use the|let's|lets|tomorrow|today|tonight)\b/i.test(text);
}

export function recommendationFromProtocol(protocol, { when = null, pastCount = 0 } = {}) {
  const name = experimentLabel(protocol);
  const history = pastCount
    ? `${pastCount} earlier ${pastCount === 1 ? 'run used' : 'runs used'} ${protocol.protocol_code}.`
    : `No earlier run is on record for ${protocol.protocol_code}.`;
  const timing = when ? ` Scheduled for ${when}.` : '';
  return {
    protocolId: protocol.id,
    protocolCode: protocol.protocol_code,
    protocolTitle: protocol.protocol_title,
    versionLabel: protocol.version_label,
    name,
    planTitle: when ? `${name} · ${when}` : name,
    parameters: { ...(protocol.parameters_json || {}) },
    criteria: (protocol.success_criteria_json || []).map((item) => ({ ...item })),
    sampleCount: protocol.sample_panel_json?.length || 0,
    when,
    pastCount,
    reason: `${name} is the protocol for this request. ${history}${timing}`,
  };
}

function criteriaSentence(draft) {
  const parts = (draft.criteria || []).map((item) => (
    `${metricLabel(item.metric)} ${item.operator} ${item.threshold}${item.unit === 'percent' ? '%' : item.unit ? ` ${item.unit}` : ''}`
  ));
  return parts.length
    ? `Success is ${parts.join(', and ')}.`
    : 'This protocol has no success criteria on record.';
}

function instrumentSentence(instruments, draft) {
  if (!instruments?.length) return 'Instrument calibration loads with the lab record.';
  const lines = instruments.map((row) => `${row.serial_number || row.name} is ${row.calibration_status}`).join('. ');
  const serial = draft?.parameters?.instrument_serial;
  const current = instruments.find((row) => row.serial_number === serial);
  const alternate = instruments.find((row) => row.calibration_status === 'current' && row.serial_number !== serial);
  const extra = current && current.calibration_status !== 'current' && alternate
    ? ` The plan names ${serial}. If that calibration is due, readiness will recommend ${alternate.serial_number} and wait for your approval.`
    : ' Expiry, training, samples, and materials are checked after the plan is approved.';
  return `${lines}.${extra}`;
}

function keepCustomName(previous, next) {
  if (!next) return next;
  const withIntent = previous?.intent ? { ...next, intent: previous.intent } : next;
  if (!previous?.nameEdited) return withIntent;
  const custom = (previous.experimentName || '').trim();
  return {
    ...withIntent,
    experimentName: previous.experimentName || '',
    nameEdited: true,
    ...(custom ? { planTitle: custom, name: custom } : {}),
  };
}

function cloneDraft(draft) {
  return {
    ...draft,
    parameters: { ...(draft.parameters || {}) },
    criteria: (draft.criteria || []).map((item) => ({ ...item })),
  };
}

export function draftFromIntentResponse(protocols, pastByCode, intent, payload) {
  const approved = approvedProtocols(protocols);
  const protocol = payload?.protocol_code
    ? approved.find((row) => row.protocol_code === payload.protocol_code)
    : null;
  const name = String(payload?.experiment_name || '').trim();
  const suggestedCriteria = (payload?.criteria || []).map((item, index) => ({
    id: item.id || `SC-${index + 1}`,
    metric: item.metric,
    operator: item.operator || '>=',
    threshold: Number(item.threshold),
    unit: item.unit || '',
  })).filter((item) => item.metric && Number.isFinite(item.threshold));
  if (protocol && !payload?.new_protocol) {
    const next = recommendationFromProtocol(protocol, {
      pastCount: pastByCode?.[protocol.protocol_code] || 0,
    });
    const parameters = { ...(next.parameters || {}), ...(payload?.parameters || {}) };
    const merged = suggestedCriteria.length
      ? suggestedCriteria.map((item) => {
        const base = (next.criteria || []).find((row) => row.metric === item.metric);
        return base ? { ...base, threshold: item.threshold, operator: item.operator || base.operator, unit: item.unit || base.unit } : item;
      })
      : (next.criteria || []);
    const seen = new Set(merged.map((item) => item.metric));
    const criteria = [...merged, ...(next.criteria || []).filter((item) => !seen.has(item.metric))];
    return {
      ...next,
      parameters,
      criteria,
      newProtocol: false,
      intent,
      experimentName: name || next.name,
      nameEdited: Boolean(name),
      planTitle: name || next.planTitle,
      reason: payload?.reason || next.reason,
    };
  }
  const title = String(payload?.protocol_title || name || 'Suggested protocol').trim();
  return {
    awaitingIntent: false,
    newProtocol: true,
    protocolId: null,
    protocolCode: '',
    protocolTitle: title,
    versionLabel: '1.0',
    name: title,
    planTitle: name || title,
    experimentName: name || title,
    nameEdited: Boolean(name),
    parameters: payload?.parameters || {},
    criteria: suggestedCriteria,
    intent,
    reason: payload?.reason || '',
    sampleCount: 1,
  };
}

const NEW_RUN = /\b(prepare|plan|start|draft)\b.{0,48}\b(experiment|protocol|plan|run)\b|\b(want to run|let's run|lets run|run cell|run a)\b/i;
const PLAN_EDIT = /(?:seeding|density)[^\d]{0,32}\d|incubat\w*[^\d]{0,20}\d|(?:threshold|mean viability)[^\d]{0,20}\d|\boperator(?:\s+to)?\s+[A-Z]/i;

function isAsking(text) {
  return /\b(why|what|how|explain|which|when did|did the|should I|can you tell)\b|\?\s*$/i.test(text);
}

export function isPlanEdit(text, { protocols, draft } = {}) {
  const trimmed = String(text || '').trim();
  if (!draft?.protocolId || !trimmed || isAsking(trimmed) || NEW_RUN.test(trimmed)) return false;
  if (isRunIntent(trimmed) && matchProtocol(trimmed, protocols)) return false;
  return PLAN_EDIT.test(trimmed);
}

export function wantsExperimentDraft(text, { protocols, draft } = {}) {
  const trimmed = String(text || '').trim();
  if (!trimmed) return false;
  if (NEW_RUN.test(trimmed)) return true;
  if (!isAsking(trimmed) && isRunIntent(trimmed) && matchProtocol(trimmed, protocols)) return true;
  return isPlanEdit(trimmed, { protocols, draft });
}

export function assist({ text, protocols, instruments, pastByCode, draft }) {
  const trimmed = text.trim();
  const library = approvedProtocols(protocols);
  if (!library.length) {
    return { text: 'Approved protocols are still loading. Ask again in a moment.', draft };
  }
  if (/^(hi|hello|hey)\b/i.test(trimmed) && trimmed.length < 20) {
    return {
      text: 'Tell me what you want to run. A useful start is cell viability tomorrow, including a check that the lab is ready.',
      draft,
    };
  }

  const whenMatch = trimmed.match(/\b(tomorrow|today|tonight)\b/i);
  const when = whenMatch ? whenMatch[1].toLowerCase() : draft?.when || null;
  const seeding = trimmed.match(/(?:seeding|density)[^\d]{0,32}(\d[\d,]*)/i);
  const incubation = trimmed.match(/incubat\w*[^\d]{0,20}(\d+)/i);
  const threshold = trimmed.match(/(?:threshold|mean viability|viability)[^\d]{0,20}(\d+(?:\.\d+)?)\s*%?/i);
  const operator = trimmed.match(/\boperator(?:\s+to)?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)/);
  const matched = matchProtocol(trimmed, library);
  const runIntent = isRunIntent(trimmed);
  const question = /\?/.test(trimmed) && !runIntent;

  if (draft && question && /criteria|success/i.test(trimmed)) {
    return { text: criteriaSentence(draft), draft };
  }
  if (draft && question && /instrument|calibrat|ready|expir|train|material|sample/i.test(trimmed)) {
    return { text: instrumentSentence(instruments, draft), draft };
  }
  if (draft && /what happens|after I approve|after approval|workflow/i.test(trimmed)) {
    return {
      text: 'Approval starts the checks. Readiness looks at calibration, expiry, training, compliance, samples, and materials. Only an exception comes back to you. After every exception is approved, the experiment moves to capture, then results, then the dossier.',
      draft,
    };
  }

  let next = draft?.protocolId ? cloneDraft(draft) : null;
  const shouldSwitch = matched && (!next || next.protocolId !== matched.id) && (runIntent || !draft?.protocolId);
  if (!next || shouldSwitch) {
    const chosen = matched || library.find((row) => row.protocol_code === 'SYN-CVP-001') || library[0];
    next = recommendationFromProtocol(chosen, {
      when,
      pastCount: pastByCode?.[chosen.protocol_code] || 0,
    });
  } else if (when && when !== next.when && !draft?.nameEdited) {
    const protocol = library.find((row) => row.id === next.protocolId);
    next.when = when;
    next.planTitle = `${next.name} · ${when}`;
    if (protocol) {
      next.reason = recommendationFromProtocol(protocol, { when, pastCount: next.pastCount || 0 }).reason;
    }
  }
  next = keepCustomName(draft, next);

  const changes = [];
  if (seeding) {
    const value = Number(seeding[1].replace(/,/g, ''));
    next.parameters.seeding_density_cells_per_ml = value;
    changes.push(`seeding density is ${value.toLocaleString()} cells/mL`);
  }
  if (incubation) {
    next.parameters.incubation_hours = Number(incubation[1]);
    changes.push(`incubation is ${incubation[1]} hours`);
  }
  if (operator) {
    next.parameters.operator = operator[1];
    changes.push(`the operator is ${operator[1]}`);
  }
  if (threshold) {
    const viability = next.criteria.find((item) => /viab/i.test(item.metric || ''));
    if (viability) {
      viability.threshold = Number(threshold[1]);
      changes.push(`mean viability must be at least ${threshold[1]}%`);
    }
  }

  if (changes.length && !shouldSwitch) {
    return {
      text: `Updated. ${changes.join(', and ')}. The rest of the recommendation is unchanged. Approve it when the draft looks right, or keep editing.`,
      draft: next,
    };
  }

  const ready = /ready|check/i.test(trimmed) ? ` ${instrumentSentence(instruments, next)}` : '';
  const textOut = `${next.reason} ${criteriaSentence(next)} The workflow is Planning, Readiness, Capture, Results, then Approval. Change the protocol, any parameter, or a success criterion, then approve. Approval starts the checks.${ready}`;
  return { text: textOut, draft: next };
}
