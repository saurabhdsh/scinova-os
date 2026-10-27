import { useEffect, useMemo, useState } from 'react';
import { Check, ChevronDown, ChevronUp, Plus, Search, Sparkles, X } from 'lucide-react';
import { getAgents, createWorkflowTemplate, getWorkflowSkills } from '../../api/client';
import { apiErrorMessage } from '../../lib/auth';

const STAGE_ORDER = [
  'Target Discovery',
  'Lead Identification',
  'Lead Optimization',
  'Preclinical Studies',
  'Preclinical',
  'Early Development & CMC',
];

function stageRank(stage) {
  const index = STAGE_ORDER.indexOf(stage);
  return index === -1 ? STAGE_ORDER.length : index;
}

export default function WorkflowDesigner({ onCancel, onCreated }) {
  const [agents, setAgents] = useState([]);
  const [query, setQuery] = useState('');
  const [name, setName] = useState('');
  const [note, setNote] = useState('');
  const [picked, setPicked] = useState([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [loadError, setLoadError] = useState('');
  const [loaded, setLoaded] = useState(false);
  const [skills, setSkills] = useState([]);
  const [customDrafts, setCustomDrafts] = useState({});

  useEffect(() => {
    getAgents()
      .then((response) => setAgents(response.data || []))
      .catch((err) => setLoadError(apiErrorMessage(err, 'Could not load agents')))
      .finally(() => setLoaded(true));
    getWorkflowSkills().then((response) => setSkills(response.data || [])).catch(() => {});
  }, []);

  const pickedIds = useMemo(() => new Set(picked.map((agent) => agent.id)), [picked]);

  const grouped = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const visible = agents.filter((agent) => {
      if (!needle) return true;
      return `${agent.name} ${agent.value_chain_stage} ${agent.description || ''}`.toLowerCase().includes(needle);
    });
    const buckets = new Map();
    visible.forEach((agent) => {
      const stage = agent.value_chain_stage || 'Other';
      if (!buckets.has(stage)) buckets.set(stage, []);
      buckets.get(stage).push(agent);
    });
    return [...buckets.entries()].sort((a, b) => stageRank(a[0]) - stageRank(b[0]) || a[0].localeCompare(b[0]));
  }, [agents, query]);

  const toggle = (agent) => {
    setError('');
    setPicked((current) => {
      if (current.some((item) => item.id === agent.id)) {
        return current.filter((item) => item.id !== agent.id);
      }
      if (current.length >= 12) return current;
      return [...current, { ...agent, skills: [] }];
    });
  };

  const move = (index, direction) => {
    setPicked((current) => {
      const next = index + direction;
      if (next < 0 || next >= current.length) return current;
      const copy = [...current];
      const [item] = copy.splice(index, 1);
      copy.splice(next, 0, item);
      return copy;
    });
  };

  const toggleSkill = (agentId, skill) => {
    setPicked((current) => current.map((agent) => {
      if (agent.id !== agentId) return agent;
      const has = agent.skills.some((item) => item.id === skill.id);
      const next = has
        ? agent.skills.filter((item) => item.id !== skill.id)
        : agent.skills.length >= 4
          ? agent.skills
          : [...agent.skills, skill];
      return { ...agent, skills: next };
    }));
  };

  const addCustomSkill = (agentId) => {
    const text = (customDrafts[agentId] || '').trim();
    if (!text) return;
    setPicked((current) => current.map((agent) => {
      if (agent.id !== agentId || agent.skills.some((item) => item.id === 'custom') || agent.skills.length >= 4) return agent;
      return { ...agent, skills: [...agent.skills, { id: 'custom', name: 'Custom skill', instruction: text.slice(0, 240) }] };
    }));
    setCustomDrafts((current) => ({ ...current, [agentId]: '' }));
  };

  const save = async () => {
    if (name.trim().length < 2 || picked.length < 2) return;
    setSaving(true);
    setError('');
    try {
      const response = await createWorkflowTemplate({
        name: name.trim(),
        description: note.trim(),
        agent_ids: picked.map((agent) => agent.id),
        agent_skills: Object.fromEntries(picked.map((agent) => [
          agent.id,
          agent.skills.map((skill) => ({ id: skill.id, instruction: skill.instruction })),
        ])),
      });
      onCreated(response.data);
    } catch (err) {
      setError(apiErrorMessage(err, 'Could not save this pipeline'));
    } finally {
      setSaving(false);
    }
  };

  const ready = name.trim().length >= 2 && picked.length >= 2;

  return (
    <section className="overflow-hidden rounded-3xl border border-cx-borderStrong bg-white shadow-glass">
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-cx-line px-6 py-5 md:px-8">
        <div className="min-w-0 flex-1">
          <button type="button" onClick={onCancel} className="text-sm text-cx-fgMuted hover:text-cx-fg">
            Research Orchestrator
          </button>
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Name this pipeline"
            className="mt-1 w-full bg-transparent font-display text-3xl font-semibold tracking-tight text-cx-fg placeholder:text-slate-300 focus:outline-none"
          />
          <input
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder="A short note about what this pipeline is for"
            className="mt-1 w-full bg-transparent text-sm text-cx-fgMuted placeholder:text-slate-300 focus:outline-none"
          />
        </div>
        <button
          type="button"
          onClick={save}
          disabled={!ready || saving}
          className="rounded-full bg-cx-accent px-5 py-2.5 text-sm font-medium text-white disabled:opacity-40"
        >
          {saving ? 'Saving…' : 'Save pipeline'}
        </button>
      </div>

      {error && <p className="px-6 pt-4 text-sm text-rose-700 md:px-8">{error}</p>}
      {loadError && <p className="px-6 pt-4 text-sm text-rose-700 md:px-8">{loadError}</p>}

      <div className="grid lg:grid-cols-[minmax(0,1.05fr)_minmax(320px,0.95fr)]">
        <div className="border-b border-cx-line lg:border-b-0 lg:border-r">
          <div className="sticky top-0 z-10 bg-white/95 px-6 py-4 backdrop-blur md:px-8">
            <label className="flex items-center gap-2 rounded-full border border-cx-border bg-slate-50 px-4 py-2">
              <Search size={16} className="text-cx-fgDim" />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search agents"
                className="w-full bg-transparent text-sm focus:outline-none"
              />
            </label>
          </div>
          <div className="max-h-[640px] space-y-6 overflow-y-auto px-6 pb-8 md:px-8">
            {grouped.map(([stage, stageAgents]) => (
              <div key={stage}>
                <p className="mb-2 text-xs font-medium text-cx-fgDim">{stage}</p>
                <div className="space-y-1">
                  {stageAgents.map((agent) => {
                    const selected = pickedIds.has(agent.id);
                    return (
                      <button
                        key={agent.id}
                        type="button"
                        onClick={() => toggle(agent)}
                        className={`flex w-full items-start gap-3 rounded-2xl px-3 py-3 text-left transition ${selected ? 'bg-sky-50' : 'hover:bg-slate-50'}`}
                      >
                        <span className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border ${selected ? 'border-cx-accent bg-cx-accent text-white' : 'border-slate-300 text-transparent'}`}>
                          {selected ? <Check size={12} /> : <Plus size={12} />}
                        </span>
                        <span className="min-w-0">
                          <span className="block text-sm font-medium text-cx-fg">{agent.name}</span>
                          <span className="mt-0.5 block text-xs leading-5 text-cx-fgMuted line-clamp-2">{agent.description}</span>
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
            {!loaded && !loadError && (
              <p className="py-8 text-sm text-cx-fgMuted">Loading the agent catalog.</p>
            )}
            {loaded && !grouped.length && !loadError && (
              <p className="py-8 text-sm text-cx-fgMuted">No agents match that search.</p>
            )}
          </div>
        </div>

        <div className="bg-slate-50/70 px-6 py-6 md:px-8">
          <div className="flex items-baseline justify-between">
            <p className="text-sm font-medium text-cx-fg">Pipeline</p>
            <p className="text-xs text-cx-fgDim">{picked.length} selected</p>
          </div>
          {!picked.length && (
            <div className="mt-8 rounded-3xl border border-dashed border-slate-300 bg-white px-6 py-14 text-center">
              <p className="font-display text-xl text-cx-fg">Choose the agents, in order.</p>
              <p className="mx-auto mt-2 max-w-xs text-sm leading-6 text-cx-fgMuted">
                Each agent you select becomes the next step. Two or more are required.
              </p>
            </div>
          )}
          <ol className="mt-4 space-y-2">
            {picked.map((agent, index) => (
              <li
                key={agent.id}
                draggable
                onDragStart={(event) => event.dataTransfer.setData('text/plain', String(index))}
                onDragOver={(event) => event.preventDefault()}
                onDrop={(event) => {
                  event.preventDefault();
                  const from = Number(event.dataTransfer.getData('text/plain'));
                  if (Number.isNaN(from) || from === index) return;
                  setPicked((current) => {
                    const copy = [...current];
                    const [item] = copy.splice(from, 1);
                    copy.splice(index, 0, item);
                    return copy;
                  });
                }}
                className="rounded-2xl border border-white bg-white px-3 py-3 shadow-sm"
              >
                <div className="flex items-center gap-3">
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-slate-100 text-sm font-medium text-cx-fg">
                    {index + 1}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium text-cx-fg">{agent.name}</span>
                    <span className="block truncate text-xs text-cx-fgDim">{agent.value_chain_stage}</span>
                  </span>
                  <span className="flex shrink-0 items-center">
                    <button type="button" aria-label={`Move ${agent.name} up`} onClick={() => move(index, -1)} className="rounded-full p-1 text-cx-fgDim hover:bg-slate-100 hover:text-cx-fg">
                      <ChevronUp size={16} />
                    </button>
                    <button type="button" aria-label={`Move ${agent.name} down`} onClick={() => move(index, 1)} className="rounded-full p-1 text-cx-fgDim hover:bg-slate-100 hover:text-cx-fg">
                      <ChevronDown size={16} />
                    </button>
                    <button type="button" aria-label={`Remove ${agent.name}`} onClick={() => toggle(agent)} className="rounded-full p-1 text-cx-fgDim hover:bg-slate-100 hover:text-cx-fg">
                      <X size={16} />
                    </button>
                  </span>
                </div>
                <div className="mt-3 border-t border-slate-100 pt-3">
                  <p className="mb-2 flex items-center gap-1.5 text-2xs uppercase tracking-[0.14em] text-cx-fgDim">
                    <Sparkles size={12} />
                    Skills for this agent
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {skills.map((skill) => {
                      const on = agent.skills.some((item) => item.id === skill.id);
                      return (
                        <button
                          key={skill.id}
                          type="button"
                          onClick={() => toggleSkill(agent.id, skill)}
                          className={`rounded-full px-2.5 py-1 text-xs transition ${on ? 'bg-cx-fg text-white' : 'bg-slate-100 text-cx-fgMuted hover:bg-slate-200'}`}
                        >
                          {skill.name}
                        </button>
                      );
                    })}
                  </div>
                  {agent.skills.some((item) => item.id === 'custom') ? (
                    <p className="mt-2 text-xs text-cx-fgMuted">
                      {agent.skills.find((item) => item.id === 'custom').instruction}
                    </p>
                  ) : (
                    <form
                      className="mt-2 flex gap-2"
                      onSubmit={(event) => {
                        event.preventDefault();
                        addCustomSkill(agent.id);
                      }}
                    >
                      <input
                        value={customDrafts[agent.id] || ''}
                        onChange={(event) => setCustomDrafts((current) => ({ ...current, [agent.id]: event.target.value }))}
                        maxLength={240}
                        placeholder="Or write a skill for this agent"
                        className="min-w-0 flex-1 rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs text-cx-fg placeholder:text-slate-400 focus:outline-none"
                      />
                      <button type="submit" className="rounded-full px-3 py-1.5 text-xs font-medium text-cx-accent">
                        Add
                      </button>
                    </form>
                  )}
                </div>
              </li>
            ))}
          </ol>
          {picked.length === 1 && (
            <p className="mt-3 text-xs text-cx-fgMuted">Add one more agent to save this pipeline.</p>
          )}
        </div>
      </div>
    </section>
  );
}
