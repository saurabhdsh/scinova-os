import { useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import NavRail from './NavRail';
import TopBar from './TopBar';
import StatusStrip from './StatusStrip';
import RightDock from './RightDock';

const PAGE_TITLES = {
  '/': 'Drug Research Command Center',
  '/value-chain': 'Pharma Value Chain',
  '/data-fabric': 'Scientific Data Fabric',
  '/knowledge-graph': 'Knowledge Graph Explorer',
  '/agents': 'Research Agent Catalog',
  '/agents/workspace': 'Ask & Run Agents',
  '/workflows': 'Research Orchestrator',
  '/slm': 'Model Routing (SLM/LLM)',
  '/governance': 'Governance & Compliance',
  '/collaboration': 'Collaboration & Briefs',
  '/reports': 'Scientific Reports',
  '/settings': 'Platform Settings',
  '/settings/users': 'User Administration',
  '/settings/tool-fabric': 'Tool Fabric Registry',
};

export default function AppShell() {
  const [navExpanded, setNavExpanded] = useState(true);
  const [dockOpen, setDockOpen] = useState(false);
  const location = useLocation();

  const title = PAGE_TITLES[location.pathname]
    || (location.pathname.startsWith('/settings/users') ? 'User Administration' : null)
    || (location.pathname.startsWith('/settings/tool-fabric') ? 'Tool Fabric Registry' : null)
    || (location.pathname.startsWith('/agents/run') ? 'Ask & Run Agents' : 'SciAi-Nova OS');

  return (
    <div className="h-full flex min-h-0">
      <NavRail expanded={navExpanded} onToggle={() => setNavExpanded((v) => !v)} />
      <div className="flex-1 flex flex-col min-h-0 min-w-0">
        <TopBar
          title={title}
          breadcrumb="SciAi-Nova OS"
          dockOpen={dockOpen}
          onDockToggle={() => setDockOpen((v) => !v)}
        />
        <div className="flex-1 flex min-h-0">
          <main className="flex-1 min-h-0 overflow-y-auto grid-bg">
            <Outlet context={{ dockOpen, setDockOpen }} />
          </main>
          <RightDock open={dockOpen} onClose={() => setDockOpen(false)}>
            <div className="space-y-3">
              <div className="glass-panel p-3 text-xs">
                <p className="text-2xs uppercase tracking-wider text-cx-fgDim mb-2">Platform Positioning</p>
                <p className="text-cx-fgMuted leading-relaxed">
                  SciFabric AgentOS is an AI-native Scientific Data Fabric and Agent Operating System for Pharma R&D.
                </p>
              </div>
              <div className="glass-panel p-3 text-xs">
                <p className="text-2xs uppercase tracking-wider text-cx-fgDim mb-2">Key Outcome</p>
                <p className="text-cx-fg leading-relaxed font-medium">
                  AI Assistance empowers scientists to reclaim an extra day each week for high-value research.
                </p>
              </div>
            </div>
          </RightDock>
        </div>
        <StatusStrip />
      </div>
    </div>
  );
}
