import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Search, Sparkles, FlaskConical, Beaker, FileText, LayoutGrid,
  ChevronLeft, Check, X, BookOpen, Target, Atom,
} from 'lucide-react';

const HYPOTHESIS_KEYWORDS = ['hypothesis builder', 'hypothesis validation', 'target hypothesis', 'hypothesis generation'];
const EXPERIMENT_KEYWORDS = ['experiment planner', 'doe designer', 'assay design', 'in-vivo study design'];
const REPORT_KEYWORDS = ['study report generator', 'scientific writer', 'result capture'];
const LITERATURE_KEYWORDS = ['literature/patent miner', 'literature miner', 'evidence scout', 'paper summarizer', 'knowledge scout'];
const TARGET_KEYWORDS = ['pathway insight', 'target validation', 'biomarker discovery', 'druggability finder', 'druggability'];
const KG_KEYWORDS = ['ontology mapper', 'kg builder'];
const MOLECULAR_KEYWORDS = ['admet', 'virtual screening', 'mpo scoring', 'molecular property', 'explainable admet'];

export function matchesKeywords(name, keywords) {
  const n = (name || '').toLowerCase();
  return keywords.some((k) => n.includes(k));
}

export function isHypothesisAgent(agent) {
  return matchesKeywords(agent?.name, HYPOTHESIS_KEYWORDS);
}

export function isExperimentAgent(agent) {
  return matchesKeywords(agent?.name, EXPERIMENT_KEYWORDS);
}

export function isReportAgent(agent) {
  return matchesKeywords(agent?.name, REPORT_KEYWORDS);
}

export function isLiteratureAgent(agent) {
  return matchesKeywords(agent?.name, LITERATURE_KEYWORDS);
}

export function isTargetAgent(agent) {
  return matchesKeywords(agent?.name, TARGET_KEYWORDS);
}

export function isKgAgent(agent) {
  return matchesKeywords(agent?.name, KG_KEYWORDS);
}

export function isMolecularAgent(agent) {
  return matchesKeywords(agent?.name, MOLECULAR_KEYWORDS);
}

export function isRagAgent(agent) {
  if (!agent) return false;
  const tools = agent.tools_used || [];
  const name = (agent.name || '').toLowerCase();
  return tools.includes('Vector Search') || tools.includes('KG Query') || name.includes('q&a') || name.includes('semantic q');
}

/** Every marketplace agent can run document Q&A when task_type is qa. */
export function supportsQaMode(agent) {
  return Boolean(agent);
}

export function isSpecializedAgent(agent) {
  return isHypothesisAgent(agent) || isExperimentAgent(agent) || isReportAgent(agent)
    || isLiteratureAgent(agent) || isTargetAgent(agent) || isKgAgent(agent) || isMolecularAgent(agent);
}

export function getAgentIntent(agent) {
  if (isHypothesisAgent(agent)) return 'hypothesis';
  if (isExperimentAgent(agent)) return 'experiment';
  if (isReportAgent(agent)) return 'report';
  if (isLiteratureAgent(agent)) return 'literature';
  if (isTargetAgent(agent)) return 'target_discovery';
  if (isKgAgent(agent)) return 'knowledge_graph';
  if (isMolecularAgent(agent)) return 'molecular';
  if (isRagAgent(agent)) return 'qa';
  return 'browse';
}

const INTENTS = [
  {
    id: 'qa',
    label: 'Ask & Search',
    hint: 'Q&A with citations — any agent',
    icon: Sparkles,
    accent: 'text-cx-accent border-cx-accent/30 bg-cx-accent/5',
    active: 'ring-2 ring-cx-accent/40 border-cx-accent/50 bg-cx-accent/10',
    filter: supportsQaMode,
  },
  {
    id: 'hypothesis',
    label: 'Hypothesize',
    hint: 'Targets & validation',
    icon: FlaskConical,
    accent: 'text-cx-accent2 border-cx-accent2/30 bg-cx-accent2/5',
    active: 'ring-2 ring-cx-accent2/40 border-cx-accent2/50 bg-cx-accent2/10',
    filter: isHypothesisAgent,
  },
  {
    id: 'experiment',
    label: 'Design Experiment',
    hint: 'Plans & DOE',
    icon: Beaker,
    accent: 'text-cx-warn border-cx-warn/30 bg-cx-warn/5',
    active: 'ring-2 ring-cx-warn/40 border-cx-warn/50 bg-cx-warn/10',
    filter: isExperimentAgent,
  },
  {
    id: 'literature',
    label: 'Mine Literature',
    hint: 'PubMed + patents',
    icon: BookOpen,
    accent: 'text-cx-accent border-cx-accent/25 bg-cx-accent/5',
    active: 'ring-2 ring-cx-accent/35 border-cx-accent/45 bg-cx-accent/10',
    filter: isLiteratureAgent,
  },
  {
    id: 'target_discovery',
    label: 'Target Discovery',
    hint: 'Pathways & validation',
    icon: Target,
    accent: 'text-cx-accent2 border-cx-accent2/30 bg-cx-accent2/5',
    active: 'ring-2 ring-cx-accent2/40 border-cx-accent2/50 bg-cx-accent2/10',
    filter: isTargetAgent,
  },
  {
    id: 'report',
    label: 'Write Report',
    hint: 'Study outputs',
    icon: FileText,
    accent: 'text-cx-success border-cx-success/30 bg-cx-success/5',
    active: 'ring-2 ring-cx-success/40 border-cx-success/50 bg-cx-success/10',
    filter: isReportAgent,
  },
  {
    id: 'molecular',
    label: 'ADMET & Screening',
    hint: 'RDKit descriptors',
    icon: Atom,
    accent: 'text-cx-accent border-cx-accent/30 bg-cx-accent/5',
    active: 'ring-2 ring-cx-accent/40 border-cx-accent/50 bg-cx-accent/10',
    filter: isMolecularAgent,
  },
];

const STAGE_ORDER = [
  'Target Discovery', 'Lead Identification', 'Lead Optimization',
  'Preclinical Studies', 'Early Development & CMC', 'Cross-Functional', 'Foundation',
];

function shortName(name) {
  return (name || '')
    .replace(/\s+(Agent|Assistant)$/i, '')
    .replace(/^Semantic\s+/i, '');
}

function riskDot(level) {
  if (level === 'high') return 'bg-cx-danger';
  if (level === 'medium') return 'bg-cx-warn';
  return 'bg-cx-success';
}

function AgentMiniCard({ agent, selected, onSelect, intentMeta }) {
  const Icon = intentMeta?.icon || LayoutGrid;
  return (
    <button
      type="button"
      onClick={() => onSelect(agent)}
      className={`w-full text-left p-3 rounded-xl border transition-all ${
        selected
          ? intentMeta?.active || 'ring-2 ring-cx-accent/40 border-cx-accent/50 bg-cx-accent/10'
          : 'border-cx-border bg-white/40 hover:bg-white/60 hover:border-cx-borderStrong'
      }`}
    >
      <div className="flex items-start gap-2.5">
        <div className={`shrink-0 p-1.5 rounded-lg border ${intentMeta?.accent || 'border-cx-border bg-cx-deep/50'}`}>
          <Icon size={14} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5">
            <p className="text-xs font-medium leading-snug truncate">{shortName(agent.name)}</p>
            {selected && <Check size={12} className="text-cx-accent shrink-0" />}
          </div>
          <p className="text-2xs text-cx-fgDim mt-0.5 truncate">{agent.value_chain_stage}</p>
        </div>
        <span className={`shrink-0 w-1.5 h-1.5 rounded-full mt-1 ${riskDot(agent.risk_level)}`} title={`${agent.risk_level} risk`} />
      </div>
    </button>
  );
}

export default function AgentPicker({ agents, selected, onSelect, onIntentChange }) {
  const [view, setView] = useState('tasks');
  const [intent, setIntent] = useState(null);
  const [search, setSearch] = useState('');
  const [stageFilter, setStageFilter] = useState('All');
  const deepLinkedRef = useRef(null);

  const intentMeta = INTENTS.find((i) => i.id === intent);

  useEffect(() => {
    if (!selected || view !== 'tasks') return;
    if (deepLinkedRef.current === selected.id) return;
    deepLinkedRef.current = selected.id;
    const i = getAgentIntent(selected);
    if (i === 'browse') {
      setView('browse');
    } else {
      setIntent(i);
      setView('agents');
    }
  }, [selected?.id, view]);

  const intentAgents = useMemo(() => {
    if (!intent) return [];
    const def = INTENTS.find((i) => i.id === intent);
    return agents.filter(def?.filter || (() => false)).sort((a, b) => a.name.localeCompare(b.name));
  }, [agents, intent]);

  const browseAgents = useMemo(() => {
    let list = [...agents];
    if (stageFilter !== 'All') {
      list = list.filter((a) => a.value_chain_stage === stageFilter);
    }
    const q = search.trim().toLowerCase();
    if (q) {
      list = list.filter(
        (a) => a.name.toLowerCase().includes(q)
          || a.category?.toLowerCase().includes(q)
          || a.value_chain_stage?.toLowerCase().includes(q),
      );
    }
    return list.sort((a, b) => a.name.localeCompare(b.name)).slice(0, 24);
  }, [agents, search, stageFilter]);

  const notifyIntent = (intentId) => {
    onIntentChange?.(intentId);
  };

  const pickIntent = (id) => {
    const def = INTENTS.find((i) => i.id === id);
    setIntent(id);
    setView('agents');
    notifyIntent(id);
    const matches = agents.filter(def?.filter || (() => false));
    if (id === 'qa') {
      return;
    }
    if (matches.length === 1) {
      onSelect(matches[0]);
    } else if (matches.length > 0) {
      const preferred = matches.find((a) =>
        a.name.includes('Builder') || a.name.includes('Semantic Q&A') || a.name.includes('Planner'),
      );
      onSelect(preferred || matches[0]);
    }
  };

  const goToTasks = () => {
    setView('tasks');
    setIntent(null);
    setSearch('');
    setStageFilter('All');
    notifyIntent(null);
  };

  const clearSelection = () => {
    deepLinkedRef.current = null;
    goToTasks();
    onSelect(null);
  };

  const openBrowse = () => {
    setView('browse');
    setIntent(null);
    setSearch('');
    notifyIntent('browse');
  };

  const handleSelectAgent = (agent) => {
    onSelect(agent);
    if (view === 'browse') {
      notifyIntent('browse');
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim">Select Agent</p>
        <p className="text-xs text-cx-fgMuted mt-1">What do you want to accomplish?</p>
      </div>

      {selected && (
        <div className="p-3 rounded-xl border border-cx-accent/25 bg-cx-accent/5">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <p className="text-2xs uppercase tracking-wider text-cx-accent">Active agent</p>
              <p className="text-sm font-medium mt-0.5 truncate">{shortName(selected.name)}</p>
              <p className="text-2xs text-cx-fgDim truncate">{selected.category}</p>
            </div>
            <button
              type="button"
              onClick={clearSelection}
              className="p-1 rounded-lg hover:bg-white/50 text-cx-fgDim"
              title="Clear selection"
            >
              <X size={14} />
            </button>
          </div>
        </div>
      )}

      {view === 'tasks' && (
        <div className="grid grid-cols-2 gap-2">
          {INTENTS.map((item) => {
            const Icon = item.icon;
            const count = agents.filter(item.filter).length;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => pickIntent(item.id)}
                className={`p-3 rounded-xl border text-left transition-all hover:scale-[1.02] active:scale-[0.98] ${item.accent}`}
              >
                <Icon size={18} className="mb-2 opacity-90" />
                <p className="text-xs font-semibold leading-tight">{item.label}</p>
                <p className="text-2xs opacity-75 mt-1">{item.hint}</p>
                <p className="text-2xs mt-2 font-mono opacity-60">{count} agent{count !== 1 ? 's' : ''}</p>
              </button>
            );
          })}
          <button
            type="button"
            onClick={openBrowse}
            className="col-span-2 p-3 rounded-xl border border-cx-border bg-white/30 hover:bg-white/50 text-left transition-all flex items-center gap-3 active:scale-[0.99]"
          >
            <div className="p-2 rounded-lg border border-cx-border bg-cx-deep/40">
              <LayoutGrid size={16} className="text-cx-fgDim" />
            </div>
            <div>
              <p className="text-xs font-semibold">Browse all agents</p>
              <p className="text-2xs text-cx-fgDim">Search {agents.length}+ agents by stage</p>
            </div>
          </button>
        </div>
      )}

      {view === 'agents' && intent && (
        <div className="space-y-3">
          <button
            type="button"
            onClick={goToTasks}
            className="flex items-center gap-1 text-2xs text-cx-fgDim hover:text-cx-accent transition-colors"
          >
            <ChevronLeft size={12} /> Change task
          </button>
          <p className="text-2xs uppercase tracking-wider text-cx-fgDim">
            {intentMeta?.label} · pick one
          </p>
          <div className="grid grid-cols-1 gap-2">
            {intentAgents.map((a) => (
              <AgentMiniCard
                key={a.id}
                agent={a}
                selected={selected?.id === a.id}
                onSelect={handleSelectAgent}
                intentMeta={intentMeta}
              />
            ))}
          </div>
        </div>
      )}

      {view === 'browse' && (
        <div className="space-y-3">
          <button
            type="button"
            onClick={goToTasks}
            className="flex items-center gap-1 text-2xs text-cx-fgDim hover:text-cx-accent transition-colors"
          >
            <ChevronLeft size={12} /> Back to tasks
          </button>

          <div className="relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-cx-fgDim" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search agents..."
              className="w-full pl-9 pr-3 py-2 text-xs rounded-xl border border-cx-border bg-white/60 focus:outline-none focus:border-cx-accent/40"
            />
          </div>

          <div className="flex gap-1.5 overflow-x-auto pb-1">
            <button
              type="button"
              onClick={() => setStageFilter('All')}
              className={`shrink-0 px-2.5 py-1 rounded-lg text-2xs border transition-colors ${
                stageFilter === 'All' ? 'border-cx-accent/30 bg-cx-accent/10 text-cx-accent' : 'border-cx-border bg-white/40'
              }`}
            >
              All
            </button>
            {STAGE_ORDER.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => setStageFilter(s)}
                className={`shrink-0 px-2.5 py-1 rounded-lg text-2xs border transition-colors whitespace-nowrap ${
                  stageFilter === s ? 'border-cx-accent/30 bg-cx-accent/10 text-cx-accent' : 'border-cx-border bg-white/40'
                }`}
              >
                {s.split(' ')[0]}
              </button>
            ))}
          </div>

          {browseAgents.length === 0 ? (
            <p className="text-xs text-cx-fgDim py-4 text-center">No agents match — try another search</p>
          ) : (
            <div className="grid grid-cols-1 gap-2 max-h-[260px] overflow-y-auto pr-1">
              {browseAgents.map((a) => (
                <AgentMiniCard
                  key={a.id}
                  agent={a}
                  selected={selected?.id === a.id}
                  onSelect={handleSelectAgent}
                />
              ))}
            </div>
          )}
          {browseAgents.length >= 24 && (
            <p className="text-2xs text-cx-fgDim text-center">Showing first 24 · refine search or open Research Agent Catalog</p>
          )}
        </div>
      )}
    </div>
  );
}
