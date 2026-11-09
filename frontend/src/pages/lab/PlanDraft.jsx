import { useState } from 'react';
import { labError } from '../../api/lab';
import { recommendationFromProtocol } from './assistantLogic';
import { WORKFLOW, formatParam, metricLabel, planFields } from './stages';

export default function PlanDraft({
  draft,
  protocols,
  pastByCode,
  onChange,
  onCreateProtocol,
  children,
}) {
  const [choosing, setChoosing] = useState(!draft?.protocolId);
  const [protocolName, setProtocolName] = useState('');
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState('');
  const approved = (protocols || []).filter((row) => row.status === 'approved');

  const createProtocol = async (event) => {
    event.preventDefault();
    const title = protocolName.trim();
    if (!title || !onCreateProtocol) return;
    setCreating(true);
    setCreateError('');
    try {
      const created = await onCreateProtocol({
        title,
        parameters: draft?.parameters,
        success_criteria: draft?.criteria,
      });
      setProtocolName('');
      if (created) choose(created);
    } catch (err) {
      setCreateError(labError(err));
    } finally {
      setCreating(false);
    }
  };

  const choose = (protocol) => {
    const next = recommendationFromProtocol(protocol, {
      when: draft?.when || null,
      pastCount: pastByCode?.[protocol.protocol_code] || 0,
    });
    const custom = (draft?.experimentName || '').trim();
    onChange({
      ...next,
      intent: draft?.intent,
      experimentName: draft?.experimentName || '',
      nameEdited: Boolean(draft?.nameEdited),
      ...(draft?.nameEdited && custom ? { planTitle: custom } : {}),
    });
    setChoosing(false);
  };

  const setParam = (key, value) => {
    onChange({
      ...draft,
      parameters: { ...draft.parameters, [key]: value },
    });
  };

  const setThreshold = (id, value) => {
    onChange({
      ...draft,
      criteria: draft.criteria.map((item) => (item.id === id ? { ...item, threshold: value } : item)),
    });
  };

  return (
    <div className="rounded-3xl border border-black/5 bg-white p-4 shadow-sm">
      <label className="block text-xs text-cx-fgDim">
        Experiment name
        <input
          value={draft?.experimentName ?? ''}
          placeholder="Name this experiment"
          onChange={(event) => onChange({
            ...(draft || {}),
            experimentName: event.target.value,
            nameEdited: true,
          })}
          className="mt-1 w-full rounded-xl border border-black/10 bg-white px-3 py-2 text-sm text-cx-fg"
        />
      </label>

      <div className="mt-4 flex items-start justify-between gap-3">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-cx-fgDim">{draft?.reason ? 'Recommended protocol' : 'Protocol'}</p>
          <p className="mt-1 font-display text-lg font-semibold tracking-tight text-cx-fg">
            {draft?.name || 'Choose a protocol'}
          </p>
          {draft?.protocolCode && (
            <p className="mt-0.5 text-xs text-cx-fgMuted">{draft.protocolCode} · v{draft.versionLabel}</p>
          )}
        </div>
        <button
          type="button"
          onClick={() => setChoosing((open) => !open)}
          className="shrink-0 rounded-full bg-cx-fg px-3 py-1.5 text-xs font-medium text-white"
        >
          Choose Protocol
        </button>
      </div>

      {draft?.reason && <p className="mt-3 text-sm leading-6 text-cx-fgMuted">{draft.reason}</p>}

      {choosing && (
        <div className="mt-3 grid gap-2">
          {approved.map((protocol) => {
            const selected = protocol.id === draft?.protocolId;
            return (
              <button
                key={protocol.id}
                type="button"
                onClick={() => choose(protocol)}
                className={`rounded-2xl border px-3 py-3 text-left ${selected ? 'border-cx-accent bg-sky-50' : 'border-black/5 bg-slate-50'}`}
              >
                <p className="text-sm font-medium text-cx-fg">{protocol.protocol_code}</p>
                <p className="mt-0.5 text-xs leading-5 text-cx-fgMuted">{protocol.protocol_title}</p>
              </button>
            );
          })}
          <form onSubmit={createProtocol} className="rounded-2xl border border-dashed border-black/10 px-3 py-3">
            <p className="text-sm font-medium text-cx-fg">Create a protocol</p>
            <p className="mt-1 text-xs leading-5 text-cx-fgMuted">Use this when the experiment needs a protocol that is not in the list above.</p>
            <div className="mt-2 flex gap-2">
              <input
                value={protocolName}
                onChange={(event) => setProtocolName(event.target.value)}
                placeholder="Protocol name"
                className="min-w-0 flex-1 rounded-xl border border-black/10 bg-white px-3 py-2 text-sm text-cx-fg"
              />
              <button
                type="submit"
                disabled={!protocolName.trim() || creating}
                className="shrink-0 rounded-full bg-cx-fg px-3 py-2 text-xs font-medium text-white disabled:opacity-40"
              >
                {creating ? 'Creating…' : 'Create'}
              </button>
            </div>
            {createError && <p className="mt-2 text-xs text-rose-700">{createError}</p>}
          </form>
        </div>
      )}

      {draft?.protocolId || draft?.newProtocol ? (
        <>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {planFields(draft.parameters).map(([key, label, unit, kind]) => (
              <label key={key} className="block text-xs text-cx-fgDim">
                {label}{unit ? ` (${unit})` : ''}
                <input
                  value={draft.parameters?.[key] ?? ''}
                  onChange={(event) => {
                    const raw = event.target.value;
                    setParam(key, kind === 'number' && raw !== '' ? Number(raw) : raw);
                  }}
                  className="mt-1 w-full rounded-xl border border-black/10 bg-white px-3 py-2 text-sm text-cx-fg"
                />
              </label>
            ))}
          </div>

          <div className="mt-4">
            <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-cx-fgDim">Success criteria</p>
            <div className="mt-2 space-y-2">
              {(draft.criteria || []).map((item) => (
                <label key={item.id} className="flex items-center justify-between gap-3 text-sm text-cx-fg">
                  <span>{metricLabel(item.metric)} {item.operator}</span>
                  <span className="flex items-center gap-2">
                    <input
                      type="number"
                      value={item.threshold}
                      onChange={(event) => setThreshold(item.id, Number(event.target.value))}
                      className="w-20 rounded-xl border border-black/10 px-2 py-1.5 text-right text-sm"
                    />
                    <span className="text-xs text-cx-fgMuted">{item.unit === 'percent' ? '%' : item.unit}</span>
                  </span>
                </label>
              ))}
            </div>
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            {WORKFLOW.map((step) => (
              <span key={step.key} className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] text-cx-fgMuted">
                {step.label}
              </span>
            ))}
          </div>

          {draft.snapshot && (
            <div className="mt-4 rounded-2xl bg-slate-50 px-3 py-3 text-sm">
              <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-cx-fgDim">Draft plan</p>
              <p className="mt-1 font-medium text-cx-fg">{draft.snapshot.title}</p>
              <ul className="mt-2 space-y-1 text-cx-fgMuted">
                {planFields(draft.snapshot.parameters_json).map(([key, label, unit]) => (
                  <li key={key}>
                    {label}: {formatParam(key, draft.snapshot.parameters_json?.[key])}{unit ? ` ${unit}` : ''}
                  </li>
                ))}
              </ul>
              <ul className="mt-2 space-y-1 text-cx-fgMuted">
                {(draft.snapshot.success_criteria_json || []).map((item) => (
                  <li key={item.id}>{metricLabel(item.metric)} {item.operator} {item.threshold} {item.unit}</li>
                ))}
              </ul>
            </div>
          )}
        </>
      ) : null}
      {children}
    </div>
  );
}
