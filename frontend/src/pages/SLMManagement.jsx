import { useEffect, useState } from 'react';
import { Cpu, Zap, Clock, Target } from 'lucide-react';
import GlassPanel from '../components/ui/GlassPanel';
import { getSLMProfiles, routeModel } from '../api/client';

export default function SLMManagement() {
  const [profiles, setProfiles] = useState([]);
  const [routing, setRouting] = useState(null);

  useEffect(() => {
    getSLMProfiles().then((r) => setProfiles(r.data)).catch(console.error);
    routeModel({
      agent_name: 'Literature/Patent Miner',
      task_type: 'summarization',
      risk_level: 'low',
      user_query: 'Summarize recent JAK inhibitor literature',
    }).then((r) => setRouting(r.data)).catch(console.error);
  }, []);

  return (
    <div className="p-6 space-y-6">
      <GlassPanel hero>
        <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim">Models</p>
        <h2 className="font-display text-xl font-semibold mt-1">Model Routing (SLM/LLM)</h2>
        <p className="text-sm text-cx-fgMuted mt-2">
          Pluggable SLM layer with routing logic: SLM for repetitive domain-specific tasks, frontier LLM for complex reasoning.
        </p>
      </GlassPanel>

      {routing && (
        <GlassPanel>
          <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim mb-4">Live Model Router Decision</p>
          <div className="grid sm:grid-cols-4 gap-4">
            <div className="p-4 rounded-xl border border-cx-border bg-white/40">
              <p className="text-xs text-cx-fgDim">Selected Model</p>
              <p className="font-mono text-sm text-cx-accent mt-1">{routing.selected_model}</p>
            </div>
            <div className="p-4 rounded-xl border border-cx-border bg-white/40">
              <p className="text-xs text-cx-fgDim">Type</p>
              <p className="text-sm font-medium mt-1 uppercase">{routing.model_type}</p>
            </div>
            <div className="p-4 rounded-xl border border-cx-border bg-white/40">
              <p className="text-xs text-cx-fgDim">Fallback</p>
              <p className="font-mono text-sm mt-1">{routing.fallback_model}</p>
            </div>
            <div className="p-4 rounded-xl border border-cx-border bg-white/40">
              <p className="text-xs text-cx-fgDim">Human Review</p>
              <p className="text-sm font-medium mt-1">{routing.human_review_required ? 'Required' : 'Not required'}</p>
            </div>
          </div>
          <p className="text-sm text-cx-fgMuted mt-4">{routing.reason_for_selection}</p>
        </GlassPanel>
      )}

      <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
        {profiles.map((p) => (
          <GlassPanel key={p.id}>
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-2">
                <Cpu className="text-cx-accent" size={20} />
                <div>
                  <h3 className="font-display font-semibold text-sm">{p.name}</h3>
                  <p className="font-mono text-2xs text-cx-fgDim mt-0.5">{p.model_name}</p>
                </div>
              </div>
              <span className={`text-2xs uppercase px-2 py-0.5 rounded-md border ${
                p.deployment_status === 'active' ? 'text-cx-success border-cx-success/25 bg-cx-success/5' :
                'text-cx-warn border-cx-warn/25 bg-cx-warn/5'
              }`}>{p.deployment_status}</span>
            </div>
            <p className="text-xs text-cx-fgMuted mt-3 leading-relaxed">{p.task_scope}</p>
            <div className="mt-4 grid grid-cols-3 gap-2 text-center">
              <div className="p-2 rounded-lg bg-white/40 border border-cx-border">
                <Zap size={12} className="mx-auto text-cx-accent mb-1" />
                <p className="text-2xs text-cx-fgDim">Cost</p>
                <p className="text-xs font-medium">${p.token_cost_estimate}/1K</p>
              </div>
              <div className="p-2 rounded-lg bg-white/40 border border-cx-border">
                <Clock size={12} className="mx-auto text-cx-accent2 mb-1" />
                <p className="text-2xs text-cx-fgDim">Latency</p>
                <p className="text-xs font-medium">{p.latency_estimate_ms}ms</p>
              </div>
              <div className="p-2 rounded-lg bg-white/40 border border-cx-border">
                <Target size={12} className="mx-auto text-cx-success mb-1" />
                <p className="text-2xs text-cx-fgDim">Accuracy</p>
                <p className="text-xs font-medium">{((p.accuracy_score || 0) * 100).toFixed(0)}%</p>
              </div>
            </div>
            <div className="mt-3 pt-3 border-t border-cx-line">
              <p className="text-2xs uppercase tracking-wider text-cx-fgDim mb-2">Allowed Agents</p>
              <div className="flex flex-wrap gap-1">
                {p.allowed_agents?.slice(0, 3).map((a) => (
                  <span key={a} className="text-2xs px-2 py-0.5 rounded-md bg-cx-deep border border-cx-border">{a}</span>
                ))}
                {(p.allowed_agents?.length || 0) > 3 && (
                  <span className="text-2xs text-cx-fgDim">+{p.allowed_agents.length - 3} more</span>
                )}
              </div>
              <p className="text-2xs text-cx-fgDim mt-2">Fallback: {p.fallback_model}</p>
              <p className="text-2xs text-cx-fgDim">Eval: {p.evaluation_status} · Dataset: {p.fine_tuning_dataset}</p>
            </div>
          </GlassPanel>
        ))}
      </div>

      <GlassPanel>
        <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim mb-4">Routing Rules</p>
        <div className="grid sm:grid-cols-2 gap-4 text-sm">
          <div className="p-4 rounded-xl border border-cx-accent/20 bg-cx-accent/5">
            <p className="font-medium text-cx-accent">SLM Route</p>
            <p className="text-xs text-cx-fgMuted mt-2">Repetitive, domain-specific, low-risk tasks. Retrieval + graph context before model call.</p>
          </div>
          <div className="p-4 rounded-xl border border-cx-accent2/20 bg-cx-accent2/5">
            <p className="font-medium text-cx-accent2">Frontier LLM Route</p>
            <p className="text-xs text-cx-fgMuted mt-2">Complex reasoning, hypothesis generation, scientific decisions, final review. Human approval for high-risk.</p>
          </div>
        </div>
      </GlassPanel>
    </div>
  );
}
