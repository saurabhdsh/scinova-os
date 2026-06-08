import { useEffect, useState } from 'react';
import { Cpu, Filter } from 'lucide-react';
import AgentCard from '../components/ui/AgentCard';
import GlassPanel from '../components/ui/GlassPanel';
import { getAgents } from '../api/client';

const STAGES = [
  'All', 'Target Discovery', 'Lead Identification', 'Lead Optimization',
  'Preclinical Studies', 'Early Development & CMC', 'Cross-Functional', 'Foundation',
];

const CATEGORIES = ['All', 'Target Discovery', 'Lead Identification', 'Lead Optimization', 'Preclinical', 'Early Development & CMC', 'Cross-Functional', 'Foundation'];

export default function AgentMarketplace() {
  const [agents, setAgents] = useState([]);
  const [stage, setStage] = useState('All');
  const [category, setCategory] = useState('All');
  const [slmOnly, setSlmOnly] = useState(false);
  const [riskFilter, setRiskFilter] = useState('All');

  useEffect(() => {
    const params = {};
    if (stage !== 'All') params.value_chain_stage = stage;
    if (category !== 'All') params.category = category;
    if (slmOnly) params.slm_eligible = true;
    getAgents(params).then((r) => setAgents(r.data)).catch(console.error);
  }, [stage, category, slmOnly]);

  const filtered = agents.filter((a) => riskFilter === 'All' || a.risk_level === riskFilter.toLowerCase());

  const grouped = STAGES.slice(1).reduce((acc, s) => {
    const items = filtered.filter((a) => a.value_chain_stage === s);
    if (items.length) acc[s] = items;
    return acc;
  }, {});

  const showGrouped = stage === 'All';

  return (
    <div className="p-6 space-y-6">
      <GlassPanel hero>
        <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim">Agents & Runs</p>
        <h2 className="font-display text-xl font-semibold mt-1">Research Agent Catalog</h2>
        <p className="text-sm text-cx-fgMuted mt-2">{filtered.length} agents available across the research value chain.</p>
      </GlassPanel>

      <GlassPanel className="p-4">
        <div className="flex flex-wrap items-center gap-3">
          <Filter size={14} className="text-cx-fgDim" />
          <select value={stage} onChange={(e) => setStage(e.target.value)} className="text-xs border border-cx-border rounded-xl px-3 py-2 bg-white/60">
            {STAGES.map((s) => <option key={s} value={s}>{s === 'All' ? 'All Stages' : s}</option>)}
          </select>
          <select value={category} onChange={(e) => setCategory(e.target.value)} className="text-xs border border-cx-border rounded-xl px-3 py-2 bg-white/60">
            {CATEGORIES.map((c) => <option key={c} value={c}>{c === 'All' ? 'All Categories' : c}</option>)}
          </select>
          <select value={riskFilter} onChange={(e) => setRiskFilter(e.target.value)} className="text-xs border border-cx-border rounded-xl px-3 py-2 bg-white/60">
            {['All', 'Low', 'Medium', 'High'].map((r) => <option key={r} value={r}>{r === 'All' ? 'All Risk Levels' : r + ' Risk'}</option>)}
          </select>
          <button
            onClick={() => setSlmOnly((v) => !v)}
            className={`flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs border transition-colors ${slmOnly ? 'border-cx-accent/30 bg-cx-accent/5 text-cx-accent' : 'border-cx-border bg-white/50'}`}
          >
            <Cpu size={12} /> SLM Eligible Only
          </button>
        </div>
      </GlassPanel>

      {showGrouped ? (
        Object.entries(grouped).map(([stageName, stageAgents]) => (
          <div key={stageName}>
            <h3 className="font-display font-semibold text-sm text-cx-fg mb-3 px-1">{stageName}</h3>
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {stageAgents.map((agent) => <AgentCard key={agent.id} agent={agent} />)}
            </div>
          </div>
        ))
      ) : (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {filtered.map((agent) => <AgentCard key={agent.id} agent={agent} />)}
        </div>
      )}
    </div>
  );
}
