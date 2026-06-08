import { useEffect, useState } from 'react';
import { Activity, Shield, Wifi, WifiOff } from 'lucide-react';
import { getDashboardStats, getWorkflowRuns } from '../../api/client';

export default function StatusStrip() {
  const [connected, setConnected] = useState(true);
  const [neo4jOk, setNeo4jOk] = useState(null);
  const [activeAgents, setActiveAgents] = useState(null);
  const [runningWorkflows, setRunningWorkflows] = useState(null);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      try {
        const readyRes = await fetch('/health/ready');
        const ready = await readyRes.json();
        if (cancelled) return;
        const dbOk = ready.checks?.database === 'ok';
        setConnected(dbOk);
        setNeo4jOk(ready.checks?.neo4j === 'ok');
      } catch {
        if (!cancelled) {
          setConnected(false);
          setNeo4jOk(false);
        }
      }

      try {
        const [statsRes, runsRes] = await Promise.all([
          getDashboardStats(),
          getWorkflowRuns(),
        ]);
        if (cancelled) return;
        setActiveAgents(statsRes.data?.active_agents ?? 0);
        const running = (runsRes.data || []).filter(
          (r) => r.status === 'running' || r.status === 'pending_approval',
        ).length;
        setRunningWorkflows(running);
      } catch {
        if (!cancelled) {
          setActiveAgents(null);
          setRunningWorkflows(null);
        }
      }
    };

    load();
    const interval = setInterval(load, 45_000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  const graphLabel = neo4jOk === null
    ? 'Graph sync unknown'
    : neo4jOk
      ? 'Neo4j connected'
      : 'Graph offline';

  return (
    <footer className="shrink-0 h-9 border-t border-cx-line bg-white/70 backdrop-blur-xl relative">
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/80 to-transparent" />
      <div className="h-full px-4 flex items-center justify-between text-2xs tracking-wide">
        <div className="flex items-center gap-2 text-cx-fg">
          {connected ? (
            <Wifi size={14} className="text-cx-success" />
          ) : (
            <WifiOff size={14} className="text-cx-danger" />
          )}
          <span>{connected ? 'SciFabric Connected' : 'Connection degraded'}</span>
          <span className="text-cx-fgDim hidden sm:inline">· {graphLabel}</span>
        </div>
        <div className="hidden sm:flex items-center gap-2 text-cx-fgDim">
          <Activity size={14} className="text-cx-accent" />
          <span>
            {activeAgents != null ? `${activeAgents} agents ready` : 'Loading agents…'}
            {runningWorkflows != null && ` · ${runningWorkflows} workflow${runningWorkflows === 1 ? '' : 's'} active`}
          </span>
        </div>
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1 text-cx-fgDim">
            <Shield size={12} /> GxP Mode
          </span>
          <span className="font-mono text-cx-fgDim">v1.0.0</span>
        </div>
      </div>
    </footer>
  );
}
