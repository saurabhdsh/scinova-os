import { useEffect, useState } from 'react';
import AgentCard from '../components/ui/AgentCard';
import GlassPanel from '../components/ui/GlassPanel';
import { getAgents } from '../api/client';

const STAGES = [
  'Target Discovery',
  'Lead Identification',
  'Lead Optimization',
  'Preclinical Studies',
  'Early Development & CMC',
];

const STAGE_COLORS = {
  'Target Discovery': 'from-cx-accent/15 to-cx-accent/5 border-cx-accent/25',
  'Lead Identification': 'from-cx-accent2/15 to-cx-accent2/5 border-cx-accent2/25',
  'Lead Optimization': 'from-cx-success/15 to-cx-success/5 border-cx-success/25',
  'Preclinical Studies': 'from-cx-warn/15 to-cx-warn/5 border-cx-warn/25',
  'Early Development & CMC': 'from-indigo-500/15 to-indigo-500/5 border-indigo-500/25',
};

export default function ValueChain() {
  const [agents, setAgents] = useState([]);

  useEffect(() => {
    getAgents().then((r) => setAgents(r.data)).catch(console.error);
  }, []);

  return (
    <div className="p-6 space-y-6">
      <GlassPanel hero>
        <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim">Overview</p>
        <h2 className="font-display text-xl font-semibold mt-1">Pharma Value Chain</h2>
        <p className="text-sm text-cx-fgMuted mt-2">Agents organized by value chain stage across the full drug discovery pipeline.</p>
      </GlassPanel>

      <div className="overflow-x-auto pb-4">
        <div className="flex gap-4 min-w-max">
          {STAGES.map((stage) => {
            const stageAgents = agents.filter((a) => a.value_chain_stage === stage);
            const color = STAGE_COLORS[stage] || 'from-cx-deep to-white border-cx-border';
            return (
              <div key={stage} className={`w-72 shrink-0 rounded-2xl border bg-gradient-to-b ${color} p-4`}>
                <div className="mb-4">
                  <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim">Stage</p>
                  <h3 className="font-display font-semibold text-sm text-cx-fg mt-1">{stage}</h3>
                  <p className="text-xs text-cx-fgDim mt-1">{stageAgents.length} agents</p>
                </div>
                <div className="space-y-3">
                  {stageAgents.map((agent) => (
                    <AgentCard key={agent.id} agent={agent} />
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
