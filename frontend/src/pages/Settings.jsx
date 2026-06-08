import { useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Bot, CheckCircle, Loader2, Save, Search, Settings2, Sparkles, Users, Wrench } from 'lucide-react';
import GlassPanel from '../components/ui/GlassPanel';
import AdminUsersPanel from '../components/admin/AdminUsersPanel';
import AdminToolFabricPanel from '../components/admin/AdminToolFabricPanel';
import { getAgents, getAgentTaskSettings, updateAgentTaskSettings, getToolFabricCatalog, getAgentToolFabricDefaults } from '../api/client';
import { useUser } from '../context/UserContext';

const TASK_TYPES = [
  {
    id: 'literature',
    label: 'Literature & Evidence',
    hint: 'Extra guidance for Literature Miner, Evidence Scout, Knowledge Scout',
  },
  {
    id: 'hypothesis',
    label: 'Hypothesis',
    hint: 'Target hypotheses, validation criteria, disease context',
  },
  {
    id: 'experiment',
    label: 'Experiment Design',
    hint: 'Study types, models, endpoints, DOE preferences',
  },
  {
    id: 'report',
    label: 'Scientific Reports',
    hint: 'Report structure, tone, regulatory framing',
  },
  {
    id: 'target_discovery',
    label: 'Target Discovery',
    hint: 'Pathway focus, validation thresholds, druggability criteria',
  },
  {
    id: 'knowledge_graph',
    label: 'Knowledge Graph',
    hint: 'Ontology standards, relationship types to emphasize',
  },
  {
    id: 'qa',
    label: 'Semantic Q&A',
    hint: 'Citation style, depth, document scope behavior',
  },
];

const emptySettings = () => ({
  global_instructions: '',
  task_instructions: Object.fromEntries(TASK_TYPES.map((t) => [t.id, ''])),
  agent_instructions: {},
  agent_tool_bindings: {},
});

export default function Settings() {
  const location = useLocation();
  const navigate = useNavigate();
  const { isAdmin, loading: userLoading } = useUser();
  const onUsersPage = location.pathname.endsWith('/settings/users');
  const onToolFabricPage = location.pathname.endsWith('/settings/tool-fabric');
  const initialTab = onUsersPage ? 'users' : onToolFabricPage ? 'tool-fabric' : 'agents';
  const [tab, setTab] = useState(initialTab);
  const [agents, setAgents] = useState([]);
  const [settings, setSettings] = useState(emptySettings);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [agentSearch, setAgentSearch] = useState('');
  const [expandedAgent, setExpandedAgent] = useState(null);
  const [toolCatalog, setToolCatalog] = useState({ tools: [], roles: [] });
  const [agentRoleMap, setAgentRoleMap] = useState({});

  useEffect(() => {
    if (onUsersPage) setTab('users');
    else if (onToolFabricPage) setTab('tool-fabric');
    else setTab('agents');
  }, [onUsersPage, onToolFabricPage]);

  useEffect(() => {
    if ((onUsersPage || onToolFabricPage) && isAdmin) return undefined;
    Promise.all([getAgentTaskSettings(), getAgents(), getToolFabricCatalog()])
      .then(([settingsRes, agentsRes, catalogRes]) => {
        const data = settingsRes.data;
        setSettings({
          global_instructions: data.global_instructions || '',
          task_instructions: {
            ...emptySettings().task_instructions,
            ...(data.task_instructions || {}),
          },
          agent_instructions: data.agent_instructions || {},
          agent_tool_bindings: data.agent_tool_bindings || {},
        });
        setAgents(agentsRes.data);
        setToolCatalog(catalogRes.data);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
    return undefined;
  }, [onUsersPage, onToolFabricPage, isAdmin]);

  const filteredAgents = useMemo(() => {
    const q = agentSearch.trim().toLowerCase();
    if (!q) return agents;
    return agents.filter(
      (a) =>
        a.name.toLowerCase().includes(q)
        || a.category?.toLowerCase().includes(q)
        || a.value_chain_stage?.toLowerCase().includes(q),
    );
  }, [agents, agentSearch]);

  const customizedCount = useMemo(() => {
    const instrCount = Object.values(settings.agent_instructions).filter((v) => v?.trim()).length;
    const toolCount = Object.values(settings.agent_tool_bindings || {}).filter(
      (roles) => roles && Object.keys(roles).length,
    ).length;
    return instrCount + toolCount;
  }, [settings.agent_instructions, settings.agent_tool_bindings]);

  const handleSave = async () => {
    setSaving(true);
    setSaved(false);
    try {
      const r = await updateAgentTaskSettings({
        global_instructions: settings.global_instructions,
        task_instructions: settings.task_instructions,
        agent_instructions: settings.agent_instructions,
        agent_tool_bindings: settings.agent_tool_bindings,
      });
      setSettings({
        global_instructions: r.data.global_instructions || '',
        task_instructions: {
          ...emptySettings().task_instructions,
          ...(r.data.task_instructions || {}),
        },
          agent_instructions: r.data.agent_instructions || {},
          agent_tool_bindings: r.data.agent_tool_bindings || {},
        });
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err) {
      console.error(err);
    } finally {
      setSaving(false);
    }
  };

  const setTaskInstruction = (taskId, value) => {
    setSettings((prev) => ({
      ...prev,
      task_instructions: { ...prev.task_instructions, [taskId]: value },
    }));
  };

  const setAgentInstruction = (agentId, value) => {
    setSettings((prev) => ({
      ...prev,
      agent_instructions: { ...prev.agent_instructions, [agentId]: value },
    }));
  };

  const setAgentToolBinding = (agentId, roleId, toolId) => {
    setSettings((prev) => ({
      ...prev,
      agent_tool_bindings: {
        ...prev.agent_tool_bindings,
        [agentId]: {
          ...(prev.agent_tool_bindings[agentId] || {}),
          [roleId]: toolId,
        },
      },
    }));
  };

  const loadAgentRoles = async (agentId) => {
    if (agentRoleMap[agentId]) return;
    try {
      const r = await getAgentToolFabricDefaults(agentId);
      setAgentRoleMap((prev) => ({ ...prev, [agentId]: r.data.suggested_roles || [] }));
    } catch (err) {
      console.error(err);
    }
  };

  const roleById = useMemo(
    () => Object.fromEntries((toolCatalog.roles || []).map((r) => [r.id, r])),
    [toolCatalog.roles],
  );

  if (userLoading || (loading && !(onUsersPage && isAdmin) && !(onToolFabricPage && isAdmin))) {
    return (
      <div className="p-6 flex items-center justify-center min-h-[40vh] text-cx-fgMuted">
        <Loader2 className="animate-spin mr-2" size={20} />
        Loading settings…
      </div>
    );
  }

  if ((onUsersPage || onToolFabricPage) && !isAdmin) {
    return (
      <div className="p-6 max-w-lg">
        <GlassPanel>
          <h2 className="font-display text-lg font-semibold">Access denied</h2>
          <p className="text-sm text-cx-fgMuted mt-2">
            This section is only available to administrators. Sign in as admin or contact your platform admin.
          </p>
        </GlassPanel>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6 max-w-5xl">
      {isAdmin && (
        <div className="flex gap-2 p-1 rounded-xl border border-cx-border bg-white/40 w-fit">
          <button
            type="button"
            onClick={() => { setTab('agents'); navigate('/settings'); }}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              tab === 'agents' ? 'bg-cx-accent/10 text-cx-accent border border-cx-accent/20' : 'text-cx-fgMuted hover:text-cx-fg'
            }`}
          >
            Agent Tasks
          </button>
          <button
            type="button"
            onClick={() => { setTab('tool-fabric'); navigate('/settings/tool-fabric'); }}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors flex items-center gap-2 ${
              tab === 'tool-fabric' ? 'bg-cx-accent/10 text-cx-accent border border-cx-accent/20' : 'text-cx-fgMuted hover:text-cx-fg'
            }`}
          >
            <Wrench size={14} /> Tool Fabric Registry
          </button>
          <button
            type="button"
            onClick={() => { setTab('users'); navigate('/settings/users'); }}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors flex items-center gap-2 ${
              tab === 'users' ? 'bg-cx-accent/10 text-cx-accent border border-cx-accent/20' : 'text-cx-fgMuted hover:text-cx-fg'
            }`}
          >
            <Users size={14} /> Users
          </button>
        </div>
      )}

      {tab === 'users' && isAdmin ? (
        <AdminUsersPanel />
      ) : tab === 'tool-fabric' && isAdmin ? (
        <AdminToolFabricPanel />
      ) : (
        <>
      <GlassPanel hero>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim flex items-center gap-2">
              <Settings2 size={14} /> Platform
            </p>
            <h2 className="font-display text-xl font-semibold mt-1">Platform Settings</h2>
            <p className="text-sm text-cx-fgMuted mt-2 max-w-2xl">
              Agent task instructions and <strong>Tool Fabric</strong> bindings per agent.
              Stack: global → task type → per-agent tools & instructions → your query.
            </p>
          </div>
          <button
            type="button"
            onClick={handleSave}
            disabled={saving}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-medium border border-cx-accent/30 bg-cx-accent/5 text-cx-accent hover:bg-cx-accent/10 disabled:opacity-50"
          >
            {saving ? <Loader2 size={16} className="animate-spin" /> : saved ? <CheckCircle size={16} /> : <Save size={16} />}
            {saving ? 'Saving…' : saved ? 'Saved' : 'Save settings'}
          </button>
        </div>
      </GlassPanel>

      <GlassPanel>
        <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim mb-2 flex items-center gap-2">
          <Wrench size={12} /> Tool Fabric
        </p>
        <p className="text-xs text-cx-fgMuted mb-3">
          Enterprise stack: <strong>Data Fabric</strong> + <strong>Tool Fabric</strong> + <strong>SLMs</strong> + <strong>Scientific LLMs</strong> + <strong>Agents</strong>.
          Assign tools per agent below. Admins can register custom tools under <strong>Tool Fabric Registry</strong>.
        </p>
        <div className="flex flex-wrap gap-2">
          {(toolCatalog.tools || []).map((t) => (
            <span
              key={t.id}
              className={`text-2xs px-2 py-1 rounded-md border ${
                t.runtime_status === 'available'
                  ? 'border-cx-success/30 text-cx-success bg-cx-success/5'
                  : t.runtime_status === 'planned'
                    ? 'border-cx-warn/30 text-cx-warn bg-cx-warn/5'
                    : 'border-cx-border text-cx-fgDim'
              }`}
              title={t.description}
            >
              {t.label}
              {t.is_custom ? ' · custom' : ''}
              {' · '}
              {t.runtime_status}
            </span>
          ))}
        </div>
      </GlassPanel>

      <GlassPanel>
        <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim mb-2 flex items-center gap-2">
          <Sparkles size={12} /> Global instructions
        </p>
        <p className="text-xs text-cx-fgMuted mb-3">
          Applied to every agent run and workflow step (e.g. company standards, citation format, therapeutic area focus).
        </p>
        <textarea
          value={settings.global_instructions}
          onChange={(e) => setSettings((prev) => ({ ...prev, global_instructions: e.target.value }))}
          rows={4}
          placeholder="e.g. Focus on rheumatoid arthritis. Prefer peer-reviewed sources from 2018+. Use FDA-aligned terminology. Always note evidence gaps."
          className="w-full p-3 rounded-xl border border-cx-border bg-white/60 text-sm resize-y focus:outline-none focus:border-cx-accent/40"
        />
      </GlassPanel>

      <GlassPanel>
        <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim mb-4">Task-type instructions</p>
        <div className="grid md:grid-cols-2 gap-4">
          {TASK_TYPES.map((task) => (
            <div key={task.id} className="p-4 rounded-xl border border-cx-border bg-white/40">
              <p className="font-medium text-sm">{task.label}</p>
              <p className="text-2xs text-cx-fgDim mt-1 mb-3">{task.hint}</p>
              <textarea
                value={settings.task_instructions[task.id] || ''}
                onChange={(e) => setTaskInstruction(task.id, e.target.value)}
                rows={3}
                placeholder={`Optional instructions for ${task.label.toLowerCase()} agents…`}
                className="w-full p-2.5 rounded-lg border border-cx-border bg-white/60 text-xs resize-y focus:outline-none focus:border-cx-accent/40"
              />
            </div>
          ))}
        </div>
      </GlassPanel>

      <GlassPanel>
        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
          <div>
            <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim flex items-center gap-2">
              <Bot size={12} /> Per-agent overrides
            </p>
            <p className="text-xs text-cx-fgMuted mt-1">
              {customizedCount} agent{customizedCount === 1 ? '' : 's'} customized · overrides task-type instructions
            </p>
          </div>
          <div className="relative w-full sm:w-64">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-cx-fgDim" />
            <input
              type="search"
              value={agentSearch}
              onChange={(e) => setAgentSearch(e.target.value)}
              placeholder="Search agents…"
              className="w-full pl-9 pr-3 py-2 rounded-xl border border-cx-border bg-white/60 text-sm focus:outline-none focus:border-cx-accent/40"
            />
          </div>
        </div>

        <div className="space-y-2 max-h-[480px] overflow-y-auto pr-1">
          {filteredAgents.map((agent) => {
            const hasCustomInstr = Boolean(settings.agent_instructions[agent.id]?.trim());
            const hasToolBindings = Boolean(settings.agent_tool_bindings[agent.id] && Object.keys(settings.agent_tool_bindings[agent.id]).length);
            const hasCustom = hasCustomInstr || hasToolBindings;
            const isOpen = expandedAgent === agent.id || hasCustom;
            const suggestedRoles = agentRoleMap[agent.id] || [];
            return (
              <div
                key={agent.id}
                className={`rounded-xl border transition-colors ${
                  hasCustom ? 'border-cx-accent/25 bg-cx-accent/5' : 'border-cx-border bg-white/40'
                }`}
              >
                <button
                  type="button"
                  onClick={() => {
                    const next = isOpen && expandedAgent === agent.id ? null : agent.id;
                    setExpandedAgent(next);
                    if (next) loadAgentRoles(next);
                  }}
                  className="w-full flex items-center gap-3 p-3 text-left"
                >
                  <div className="shrink-0 p-2 rounded-lg border border-cx-border bg-white/50 text-cx-accent">
                    <Bot size={14} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{agent.name}</p>
                    <p className="text-2xs text-cx-fgDim">{agent.category} · {agent.value_chain_stage}</p>
                  </div>
                  {hasCustom && (
                    <span className="text-2xs px-2 py-0.5 rounded-full border border-cx-accent/30 text-cx-accent">
                      Custom
                    </span>
                  )}
                </button>
                {isOpen && (
                  <div className="px-3 pb-3 space-y-3">
                    {suggestedRoles.length > 0 && (
                      <div className="p-3 rounded-lg border border-cx-border bg-white/50 space-y-2">
                        <p className="text-2xs uppercase tracking-wider text-cx-fgDim flex items-center gap-1">
                          <Wrench size={10} /> Tool Fabric bindings
                        </p>
                        {suggestedRoles.map((roleId) => {
                          const role = roleById[roleId];
                          if (!role) return null;
                          const current = settings.agent_tool_bindings[agent.id]?.[roleId] || role.default;
                          return (
                            <label key={roleId} className="block text-xs">
                              <span className="text-cx-fgMuted">{role.label}</span>
                              <select
                                value={current}
                                onChange={(e) => setAgentToolBinding(agent.id, roleId, e.target.value)}
                                className="mt-1 w-full p-2 rounded-lg border border-cx-border bg-white text-xs focus:outline-none focus:border-cx-accent/40"
                              >
                                {role.options.map((opt) => (
                                  <option key={opt.id} value={opt.id}>
                                    {opt.label}
                                    {opt.is_custom ? ' · custom' : ''}
                                    {' ('}
                                    {opt.runtime_status}
                                    )
                                  </option>
                                ))}
                              </select>
                            </label>
                          );
                        })}
                      </div>
                    )}
                    <textarea
                      value={settings.agent_instructions[agent.id] || ''}
                      onChange={(e) => setAgentInstruction(agent.id, e.target.value)}
                      rows={3}
                      placeholder={`Specific instructions for ${agent.name}…`}
                      className="w-full p-2.5 rounded-lg border border-cx-border bg-white/60 text-xs resize-y focus:outline-none focus:border-cx-accent/40"
                    />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </GlassPanel>
        </>
      )}
    </div>
  );
}
