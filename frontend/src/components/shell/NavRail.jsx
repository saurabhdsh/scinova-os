import { motion } from 'framer-motion';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard, Database, Share2, Bot, Play,
  Workflow, Cpu, Shield, FileText, Layers, ChevronLeft, Settings2,
  Users, LogOut, MessageSquare, Wrench,
} from 'lucide-react';
import SciNovaLogo from '../brand/SciNovaLogo';
import { useUser } from '../../context/UserContext';

const NAV_ITEMS = [
  { to: '/', icon: LayoutDashboard, label: 'Drug Discovery Command Center', group: 'Overview' },
  { to: '/value-chain', icon: Layers, label: 'Pharma Value Chain', group: 'Overview' },
  { to: '/data-fabric', icon: Database, label: 'Scientific Data Fabric', group: 'Evidence' },
  { to: '/knowledge-graph', icon: Share2, label: 'Knowledge Graph Explorer', group: 'Evidence' },
  { to: '/agents', icon: Bot, label: 'Research Agent Catalog', group: 'Agents & Runs' },
  { to: '/agents/workspace', icon: Play, label: 'Ask & Run Agents', group: 'Agents & Runs' },
  { to: '/workflows', icon: Workflow, label: 'Research Orchestrator', group: 'Orchestration' },
  { to: '/slm', icon: Cpu, label: 'Model Routing (SLM/LLM)', group: 'Models' },
  { to: '/governance', icon: Shield, label: 'Governance & Compliance', group: 'Compliance' },
  { to: '/collaboration', icon: MessageSquare, label: 'Collaboration & Briefs', group: 'Decisions' },
  { to: '/reports', icon: FileText, label: 'Scientific Reports', group: 'Outputs' },
  { to: '/settings', icon: Settings2, label: 'Platform Settings', group: 'Platform' },
];

export default function NavRail({ expanded, onToggle }) {
  const { user, isAdmin, displayName, logout } = useUser();

  return (
    <motion.aside
      animate={{ width: expanded ? 248 : 76 }}
      transition={{ type: 'spring', stiffness: 400, damping: 42, mass: 0.7 }}
      className="shrink-0 flex flex-col border-r border-cx-line bg-white/60 backdrop-blur-2xl h-full"
    >
      <div className="p-4 border-b border-cx-line">
        <div className="flex items-center gap-3">
          <SciNovaLogo size={40} />
          {expanded && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="min-w-0">
              <h1 className="font-display font-semibold text-cx-fg text-sm">SciAi-Nova OS</h1>
              <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim">SciFabric AgentOS</p>
              <p className="text-2xs text-cx-fgMuted mt-0.5 leading-snug">Tata Consultancy Services</p>
            </motion.div>
          )}
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto py-3 px-2 space-y-0.5">
        {NAV_ITEMS.map(({ to, icon: Icon, label, group }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all ${
                isActive
                  ? 'bg-cx-accent/8 border border-cx-accent/25 text-cx-fg'
                  : 'text-cx-fgDim hover:text-cx-fgMuted hover:bg-white/50 border border-transparent'
              }`
            }
          >
            <Icon size={20} strokeWidth={1.75} className="shrink-0" />
            {expanded && (
              <motion.div initial={{ opacity: 0, x: -4 }} animate={{ opacity: 1, x: 0 }} className="min-w-0">
                <p className="text-sm font-medium truncate">{label}</p>
                <p className="text-2xs uppercase tracking-wider text-cx-fgDim">{group}</p>
              </motion.div>
            )}
          </NavLink>
        ))}

        {isAdmin && (
          <>
          <NavLink
            to="/settings/tool-fabric"
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all ${
                isActive
                  ? 'bg-cx-accent/8 border border-cx-accent/25 text-cx-fg'
                  : 'text-cx-fgDim hover:text-cx-fgMuted hover:bg-white/50 border border-transparent'
              }`
            }
          >
            <Wrench size={20} strokeWidth={1.75} className="shrink-0" />
            {expanded && (
              <motion.div initial={{ opacity: 0, x: -4 }} animate={{ opacity: 1, x: 0 }} className="min-w-0">
                <p className="text-sm font-medium truncate">Tool Fabric Registry</p>
                <p className="text-2xs uppercase tracking-wider text-cx-fgDim">Admin</p>
              </motion.div>
            )}
          </NavLink>
          <NavLink
            to="/settings/users"
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all ${
                isActive
                  ? 'bg-cx-accent/8 border border-cx-accent/25 text-cx-fg'
                  : 'text-cx-fgDim hover:text-cx-fgMuted hover:bg-white/50 border border-transparent'
              }`
            }
          >
            <Users size={20} strokeWidth={1.75} className="shrink-0" />
            {expanded && (
              <motion.div initial={{ opacity: 0, x: -4 }} animate={{ opacity: 1, x: 0 }} className="min-w-0">
                <p className="text-sm font-medium truncate">User Administration</p>
                <p className="text-2xs uppercase tracking-wider text-cx-fgDim">Admin</p>
              </motion.div>
            )}
          </NavLink>
          </>
        )}
      </nav>

      <div className="p-3 border-t border-cx-line space-y-2">
        {user && (
          <div className={`rounded-xl border border-cx-border bg-white/40 ${expanded ? 'px-3 py-2.5' : 'p-2 flex justify-center'}`}>
            {expanded ? (
              <>
                <p className="text-sm font-medium truncate text-cx-fg">{displayName}</p>
                <p className="text-2xs text-cx-fgDim truncate">@{user.username}</p>
                <p className="text-2xs text-cx-fgDim capitalize mt-0.5">{user.role}</p>
              </>
            ) : (
              <div
                className="w-8 h-8 rounded-lg bg-cx-accent/10 border border-cx-accent/20 flex items-center justify-center text-xs font-semibold text-cx-accent"
                title={displayName}
              >
                {(displayName[0] || '?').toUpperCase()}
              </div>
            )}
          </div>
        )}
        <button
          type="button"
          onClick={logout}
          className="w-full flex items-center justify-center gap-2 py-2 rounded-xl border border-cx-border bg-white/50 text-2xs uppercase tracking-wider text-cx-fgDim hover:border-cx-danger/30 hover:text-cx-danger transition-colors"
          title="Sign out"
        >
          <LogOut size={14} />
          {expanded && 'Sign out'}
        </button>
        <button
          type="button"
          onClick={onToggle}
          className="w-full flex items-center justify-center gap-2 py-2 rounded-xl border border-cx-border bg-white/50 text-2xs uppercase tracking-wider text-cx-fgDim hover:border-cx-borderStrong transition-colors"
        >
          <ChevronLeft size={14} className={`transition-transform ${expanded ? '' : 'rotate-180'}`} />
          {expanded && 'Collapse'}
        </button>
      </div>
    </motion.aside>
  );
}
