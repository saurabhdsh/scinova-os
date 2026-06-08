import { Bot, Cpu, Shield, Play } from 'lucide-react';
import { Link } from 'react-router-dom';
import RiskBadge from './RiskBadge';

export default function AgentCard({ agent, onLaunch }) {
  return (
    <div className="glass-panel p-4 hover:border-cx-borderStrong transition-all group">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <div className="shrink-0 p-2 rounded-lg bg-cx-deep border border-cx-border text-cx-accent">
            <Bot size={16} strokeWidth={1.75} />
          </div>
          <div className="min-w-0">
            <h3 className="font-display font-semibold text-sm text-cx-fg truncate">{agent.name}</h3>
            <p className="text-2xs uppercase tracking-wider text-cx-fgDim">{agent.category}</p>
          </div>
        </div>
        <RiskBadge level={agent.risk_level} />
      </div>
      <p className="mt-3 text-xs text-cx-fgMuted line-clamp-2 leading-relaxed">{agent.description}</p>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {agent.slm_eligible && (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-2xs bg-cx-accent/8 text-cx-accent border border-cx-accent/20">
            <Cpu size={10} /> SLM
          </span>
        )}
        {agent.human_approval_required && (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-2xs bg-cx-accent2/8 text-cx-accent2 border border-cx-accent2/20">
            <Shield size={10} /> Approval
          </span>
        )}
      </div>
      <div className="mt-4 flex gap-2">
        <Link
          to={`/agents/run/${agent.id}`}
          className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-xl text-xs font-medium border border-cx-accent/30 bg-cx-accent/5 text-cx-accent hover:bg-cx-accent/10 transition-colors"
        >
          <Play size={12} /> Launch
        </Link>
        {onLaunch && (
          <button
            onClick={() => onLaunch(agent)}
            className="px-3 py-2 rounded-xl text-xs border border-cx-border bg-white/50 hover:border-cx-borderStrong transition-colors"
          >
            Quick Run
          </button>
        )}
      </div>
    </div>
  );
}
