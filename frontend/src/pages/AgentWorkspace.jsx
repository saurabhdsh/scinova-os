import { useEffect, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { Play, Loader2, Cpu, Shield, FileText, CheckCircle, Sparkles, ExternalLink, Beaker, Database, Wrench } from 'lucide-react';
import GlassPanel from '../components/ui/GlassPanel';
import RiskBadge from '../components/ui/RiskBadge';
import AgentPicker, {
  getAgentIntent,
  isHypothesisAgent,
  isExperimentAgent,
  isReportAgent,
  isLiteratureAgent,
  isTargetAgent,
  isRagAgent,
  isSpecializedAgent,
  isMolecularAgent,
} from '../components/workspace/AgentPicker';
import { getAgents, getAgent, getDocuments, runAgent, getAgentToolFabricBindings } from '../api/client';
import { apiErrorMessage } from '../lib/auth';
import AgentOutputRenderer, { isAgentStructuredOutput } from '../components/agents/AgentOutputRenderer';

function isScreeningAgent(agent) {
  return agent?.name?.toLowerCase().includes('virtual screening');
}

function resolveTaskType(agent, taskMode, workspaceIntent) {
  if (taskMode === 'qa') return 'qa';
  if (workspaceIntent && workspaceIntent !== 'browse' && workspaceIntent !== 'qa') {
    return workspaceIntent;
  }
  if (!agent) return 'analysis';
  const intent = getAgentIntent(agent);
  return intent === 'browse' ? 'analysis' : intent;
}

function getPlaceholder(agent, taskMode) {
  if (taskMode === 'qa') {
    return `Ask ${agent?.name || 'this agent'} a question — answers are grounded in your indexed documents with citations [1], [2]…`;
  }
  if (isLiteratureAgent(agent)) {
    return 'e.g. Summarize JAK inhibitor clinical evidence in rheumatoid arthritis from literature and indexed documents';
  }
  if (isTargetAgent(agent)) {
    return 'e.g. Assess JAK1 pathway role and validation evidence as a target in autoimmune disease';
  }
  if (isHypothesisAgent(agent)) {
    return 'e.g. Generate ranked target hypotheses for JAK1 inhibition in rheumatoid arthritis';
  }
  if (isExperimentAgent(agent)) {
    return 'e.g. Design a 28-day in-vivo efficacy study for ABT-494 in collagen-induced arthritis model';
  }
  if (isReportAgent(agent)) {
    return 'e.g. Generate a preclinical study report for SN-1923 tox study with endpoints and conclusions';
  }
  if (isMolecularAgent(agent)) {
    return 'Optional context, e.g. Rank lead series SN-2847 analogs for oral bioavailability and hERG risk';
  }
  if (isRagAgent(agent)) {
    return 'e.g. What was the primary endpoint in the ABT-494 Phase IIb rheumatoid arthritis study?';
  }
  return 'Enter your research query or parameters...';
}

function decodeTitle(title) {
  if (!title) return '';
  const el = document.createElement('textarea');
  el.innerHTML = title;
  return el.value;
}

function isStructuredResult(output) {
  return isAgentStructuredOutput(output);
}

function toolStatusClass(status) {
  if (status === 'available') return 'border-cx-success/30 text-cx-success bg-cx-success/5';
  if (status === 'planned') return 'border-cx-warn/30 text-cx-warn bg-cx-warn/5';
  if (status === 'conditional') return 'border-cx-accent/30 text-cx-accent bg-cx-accent/5';
  return 'border-cx-border text-cx-fgDim bg-white/40';
}

export default function AgentWorkspace() {
  const { agentId } = useParams();
  const [searchParams] = useSearchParams();
  const [agents, setAgents] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [selected, setSelected] = useState(null);
  const [query, setQuery] = useState('');
  const [smiles, setSmiles] = useState('');
  const [querySmiles, setQuerySmiles] = useState('');
  const [runDocking, setRunDocking] = useState(false);
  const [documentId, setDocumentId] = useState('');
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);
  const [toolFabric, setToolFabric] = useState(null);
  const [toolFabricLoading, setToolFabricLoading] = useState(false);
  const [taskMode, setTaskMode] = useState('qa');
  const [workspaceIntent, setWorkspaceIntent] = useState(null);
  const [runError, setRunError] = useState('');

  useEffect(() => {
    getAgents().then((r) => setAgents(r.data)).catch(console.error);
    getDocuments().then((r) => setDocuments(r.data.filter((d) => d.status === 'indexed'))).catch(console.error);
  }, []);

  useEffect(() => {
    const idFromRoute = agentId || searchParams.get('id');
    if (idFromRoute) {
      getAgent(idFromRoute).then((r) => setSelected(r.data)).catch(console.error);
    }
  }, [agentId, searchParams]);

  useEffect(() => {
    if (!selected?.id) {
      setToolFabric(null);
      return undefined;
    }
    setToolFabricLoading(true);
    getAgentToolFabricBindings(selected.id)
      .then((r) => setToolFabric(r.data))
      .catch(console.error)
      .finally(() => setToolFabricLoading(false));
    return undefined;
  }, [selected?.id]);

  const handleSelectAgent = (agent) => {
    setSelected(agent);
    setResult(null);
  };

  const handleIntentChange = (intentId) => {
    setWorkspaceIntent(intentId);
    if (intentId === 'qa' || intentId === 'browse' || intentId === null) {
      setTaskMode('qa');
    } else if (intentId) {
      setTaskMode('pipeline');
    }
  };

  const handleRun = async () => {
    if (!selected) return;
    const qaRun = taskMode === 'qa';
    const molecular = isMolecularAgent(selected) && !qaRun;
    if (!query.trim()) return;
    if (molecular && !query.trim() && !smiles.trim()) return;
    setRunning(true);
    setResult(null);
    setRunError('');
    try {
      const r = await runAgent(selected.id, {
        input_data: {
          query: query.trim(),
          task_type: resolveTaskType(selected, taskMode, workspaceIntent),
          document_id: documentId || undefined,
          smiles: molecular ? (smiles.trim() || undefined) : undefined,
          query_smiles: !qaRun && isScreeningAgent(selected) ? (querySmiles.trim() || undefined) : undefined,
          run_docking: !qaRun && isScreeningAgent(selected) ? runDocking : undefined,
          top_k: 8,
        },
        context: qaRun
          ? `Document Q&A as ${selected.name} — vector index + citations`
          : (molecular ? 'RDKit cheminformatics + SLM narrative' : 'SciFabric vector index + PubMed + KEGG + knowledge graph'),
      });
      setResult(r.data);
    } catch (err) {
      console.error(err);
      setRunError(apiErrorMessage(err, 'Agent run failed. Check backend logs or try Q&A mode.'));
    } finally {
      setRunning(false);
    }
  };

  const output = result?.output_json;
  const structured = isStructuredResult(output);
  const showDocScope = selected && (taskMode === 'qa' || isRagAgent(selected) || isSpecializedAgent(selected));
  const qaRun = taskMode === 'qa';
  const molecularInput = isMolecularAgent(selected) && !qaRun;
  const selectedDoc = documents.find((d) => d.id === documentId);
  const runToolFabric = output?.tool_fabric;
  const runCustomTools = output?.custom_tool_results;

  return (
    <div className="p-6 grid lg:grid-cols-3 gap-6">
      <GlassPanel className="lg:col-span-1 lg:sticky lg:top-6 lg:self-start">
        <AgentPicker
          agents={agents}
          selected={selected}
          onSelect={handleSelectAgent}
          onIntentChange={handleIntentChange}
        />
      </GlassPanel>

      <div className="lg:col-span-2 space-y-4">
        {selected ? (
          <>
            <GlassPanel hero>
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim">{selected.category}</p>
                  <h2 className="font-display text-lg font-semibold mt-1">{selected.name}</h2>
                  <p className="text-sm text-cx-fgMuted mt-2">{selected.description}</p>
                </div>
                <RiskBadge level={selected.risk_level} />
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                {qaRun && (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-2xs bg-cx-success/8 text-cx-success border border-cx-success/20">
                    <Sparkles size={10} /> Q&A mode · indexed documents
                  </span>
                )}
                {isMolecularAgent(selected) && !qaRun && (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-2xs bg-cx-accent/8 text-cx-accent border border-cx-accent/20">
                    <Beaker size={10} /> RDKit + SLM
                  </span>
                )}
                {isSpecializedAgent(selected) && !isMolecularAgent(selected) && !qaRun && (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-2xs bg-cx-accent2/8 text-cx-accent2 border border-cx-accent2/20">
                    <Beaker size={10} /> LLM + PubMed + KEGG + KG
                  </span>
                )}
                {isRagAgent(selected) && !qaRun && (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-2xs bg-cx-success/8 text-cx-success border border-cx-success/20">
                    <Sparkles size={10} /> RAG + Citations
                  </span>
                )}
                {selected.slm_eligible && (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-2xs bg-cx-accent/8 text-cx-accent border border-cx-accent/20">
                    <Cpu size={10} /> SLM Eligible
                  </span>
                )}
                {selected.human_approval_required && (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-2xs bg-cx-accent2/8 text-cx-accent2 border border-cx-accent2/20">
                    <Shield size={10} /> Human Approval Required
                  </span>
                )}
              </div>
            </GlassPanel>

            <GlassPanel>
              <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim mb-3">Execution Context</p>
              <div className="flex flex-wrap gap-2 mb-3">
                <button
                  type="button"
                  onClick={() => setTaskMode('qa')}
                  className={`px-3 py-1.5 rounded-lg text-xs border transition-colors ${
                    taskMode === 'qa'
                      ? 'border-cx-success/40 bg-cx-success/10 text-cx-success'
                      : 'border-cx-border text-cx-fgMuted hover:text-cx-fg'
                  }`}
                >
                  Q&A — document search
                </button>
                {isSpecializedAgent(selected) && (
                  <button
                    type="button"
                    onClick={() => setTaskMode('pipeline')}
                    className={`px-3 py-1.5 rounded-lg text-xs border transition-colors ${
                      taskMode === 'pipeline'
                        ? 'border-cx-accent/40 bg-cx-accent/10 text-cx-accent'
                        : 'border-cx-border text-cx-fgMuted hover:text-cx-fg'
                    }`}
                  >
                    Full agent pipeline
                  </button>
                )}
              </div>
              <div className="grid sm:grid-cols-2 gap-4">
                <div className="p-3 rounded-xl border border-cx-border bg-white/40 space-y-2">
                  <p className="text-2xs uppercase tracking-wider text-cx-fgDim flex items-center gap-1.5">
                    <Database size={11} /> Data Fabric
                  </p>
                  <p className="text-sm text-cx-fg">
                    {documents.length}
                    {' '}
                    indexed document
                    {documents.length === 1 ? '' : 's'}
                  </p>
                  {selectedDoc ? (
                    <p className="text-xs text-cx-fgMuted line-clamp-2" title={decodeTitle(selectedDoc.title)}>
                      Scoped to:
                      {' '}
                      <span className="text-cx-fg">{decodeTitle(selectedDoc.title)}</span>
                    </p>
                  ) : (
                    <p className="text-xs text-cx-fgMuted">
                      {qaRun
                        ? 'Searching indexed documents in Data Fabric'
                        : showDocScope
                          ? 'All indexed documents + PubMed, KEGG, knowledge graph'
                          : 'External sources + platform knowledge graph'}
                    </p>
                  )}
                  {(qaRun || showDocScope) && documents.length > 0 && (
                    <select
                      value={documentId}
                      onChange={(e) => setDocumentId(e.target.value)}
                      className="w-full text-xs border border-cx-border rounded-lg px-2.5 py-2 bg-white/60"
                    >
                      <option value="">All indexed documents</option>
                      {documents.map((d) => (
                        <option key={d.id} value={d.id}>{decodeTitle(d.title).slice(0, 72)}</option>
                      ))}
                    </select>
                  )}
                </div>

                <div className="p-3 rounded-xl border border-cx-border bg-white/40 space-y-2">
                  <p className="text-2xs uppercase tracking-wider text-cx-fgDim flex items-center gap-1.5">
                    <Wrench size={11} /> Tool Fabric
                    {toolFabric?.has_custom_overrides && (
                      <span className="text-2xs px-1.5 py-0.5 rounded-full border border-cx-accent/30 text-cx-accent normal-case tracking-normal">
                        Custom
                      </span>
                    )}
                  </p>
                  {toolFabricLoading ? (
                    <p className="text-xs text-cx-fgMuted flex items-center gap-2">
                      <Loader2 size={12} className="animate-spin" />
                      Loading bindings…
                    </p>
                  ) : toolFabric?.bindings?.length ? (
                    <ul className="space-y-1.5">
                      {toolFabric.bindings.map((b) => (
                        <li key={b.role_id} className="text-xs">
                          <span className="text-cx-fgDim">{b.role_label}:</span>
                          {' '}
                          <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md border text-2xs ${toolStatusClass(b.runtime_status)}`}>
                            {b.tool_label}
                            {b.is_custom && ' · custom'}
                          </span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-xs text-cx-fgMuted">Default platform tools for this agent type.</p>
                  )}
                  <Link to="/settings" className="text-2xs text-cx-accent hover:underline inline-block">
                    Configure tools in Settings →
                  </Link>
                </div>
              </div>
            </GlassPanel>

            <GlassPanel>
              <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim mb-3">Input</p>
              <textarea
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && (e.metaKey || e.ctrlKey) && handleRun()}
                placeholder={getPlaceholder(selected, taskMode)}
                rows={4}
                className="w-full p-3 rounded-xl border border-cx-border bg-white/60 text-sm resize-none focus:outline-none focus:border-cx-accent/40"
              />
              {molecularInput && (
                <>
                  <textarea
                    value={smiles}
                    onChange={(e) => setSmiles(e.target.value)}
                    placeholder={'SMILES library (one per line)\nSN-2847,CC(C)Cc1ccc(C(C)C(=O)O)cc1\nABT-494,CC1=C(C(=CC=C1)F)C(=O)N2CCC(CC2)N3CCN(CC3)C'}
                    rows={4}
                    className="mt-3 w-full p-3 rounded-xl border border-cx-border bg-white/60 text-xs font-mono resize-none focus:outline-none focus:border-cx-accent/40"
                  />
                  {isScreeningAgent(selected) && (
                    <div className="mt-3 space-y-2">
                      <input
                        value={querySmiles}
                        onChange={(e) => setQuerySmiles(e.target.value)}
                        placeholder="Query SMILES for 3D shape screening (optional)"
                        className="w-full p-3 rounded-xl border border-cx-border bg-white/60 text-xs font-mono focus:outline-none focus:border-cx-accent/40"
                      />
                      <label className="flex items-center gap-2 text-xs text-cx-fgMuted">
                        <input
                          type="checkbox"
                          checked={runDocking}
                          onChange={(e) => setRunDocking(e.target.checked)}
                        />
                        Run AutoDock Vina on top shape hit (requires VINA_BIN)
                      </label>
                    </div>
                  )}
                </>
              )}
              <button
                type="button"
                onClick={handleRun}
                disabled={running || !query.trim()}
                className="mt-3 flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-medium border border-cx-accent/30 bg-cx-accent/5 text-cx-accent hover:bg-cx-accent/10 disabled:opacity-50"
              >
                {running ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
                {running ? 'Gathering evidence & reasoning...' : (qaRun ? 'Ask (Q&A)' : 'Run Agent')}
              </button>
              {runError && (
                <div className="mt-3 p-3 rounded-xl text-sm border border-cx-danger/30 bg-cx-danger/5 text-cx-danger">
                  {runError}
                </div>
              )}
              <p className="text-2xs text-cx-fgDim mt-2">
                ⌘/Ctrl + Enter ·
                {qaRun
                  ? ' Answers from indexed documents with citations · '
                  : ' Pulls from Data Fabric, PubMed, KEGG, and knowledge graph · '}
                <Link to="/settings" className="text-cx-accent hover:underline">
                  Custom instructions in Settings
                </Link>
              </p>
            </GlassPanel>

            {result && (
              <>
                <GlassPanel>
                  <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim mb-3">Model Routing</p>
                  {(runToolFabric || runCustomTools) && (
                    <div className="mb-3 p-3 rounded-xl border border-cx-border bg-white/40">
                      <p className="text-2xs uppercase tracking-wider text-cx-fgDim flex items-center gap-1 mb-2">
                        <Wrench size={10} /> Tools used this run
                      </p>
                      <div className="flex flex-wrap gap-1.5">
                        {Object.entries(runToolFabric || {}).map(([role, toolId]) => (
                          <span
                            key={role}
                            className="text-2xs px-2 py-0.5 rounded-md border border-cx-border bg-white/50"
                            title={role}
                          >
                            {toolFabric?.bindings?.find((b) => b.role_id === role)?.role_label || role}
                            :
                            {' '}
                            {toolFabric?.bindings?.find((b) => b.tool_id === toolId)?.tool_label
                              || toolId.replace(/^custom_/, '').replace(/_/g, ' ')}
                          </span>
                        ))}
                      </div>
                      {runCustomTools && Object.keys(runCustomTools).length > 0 && (
                        <p className="text-2xs text-cx-fgMuted mt-2">
                          Custom tools invoked:
                          {' '}
                          {Object.values(runCustomTools)
                            .map((c) => c.label || c.tool_id)
                            .filter(Boolean)
                            .join(', ')}
                        </p>
                      )}
                    </div>
                  )}
                  <div className="grid sm:grid-cols-3 gap-3 text-sm">
                    <div className="p-3 rounded-xl border border-cx-border bg-white/40">
                      <p className="text-xs text-cx-fgDim">Selected Model</p>
                      <p className="font-mono text-cx-accent mt-1 text-xs">{result.model_selected}</p>
                    </div>
                    <div className="p-3 rounded-xl border border-cx-border bg-white/40">
                      <p className="text-xs text-cx-fgDim">Confidence</p>
                      <p className="font-semibold mt-1">{((result.confidence || 0) * 100).toFixed(0)}%</p>
                    </div>
                    <div className="p-3 rounded-xl border border-cx-border bg-white/40">
                      <p className="text-xs text-cx-fgDim">Citations</p>
                      <p className="font-semibold mt-1">{result.citations_json?.length ?? 0}</p>
                    </div>
                  </div>
                  <p className="text-xs text-cx-fgMuted mt-3">{result.routing_reason}</p>
                  {output?.mode && (
                    <p className="text-2xs uppercase tracking-wider text-cx-fgDim mt-2">
                      Mode: {output.mode.replace(/_/g, ' ')}
                      {output.model_used && ` · ${output.model_used}`}
                    </p>
                  )}
                  {result.status === 'pending_review' && (
                    <div className="mt-3 p-3 rounded-xl border border-cx-warn/30 bg-cx-warn/5 flex items-center gap-2 text-sm">
                      <Shield size={16} className="text-cx-warn" />
                      Pending human review — see Governance console
                    </div>
                  )}
                </GlassPanel>

                <GlassPanel>
                  <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim mb-3">Output</p>
                  {structured ? (
                    <AgentOutputRenderer output={output} />
                  ) : (
                    <pre className="text-xs text-cx-fgMuted whitespace-pre-wrap bg-white/40 p-4 rounded-xl border border-cx-border overflow-auto max-h-96">
                      {JSON.stringify(output, null, 2)}
                    </pre>
                  )}
                </GlassPanel>

                <GlassPanel>
                  <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim mb-3 flex items-center gap-1">
                    <FileText size={12} /> Citations & Evidence
                  </p>
                  {result.citations_json?.length ? (
                    result.citations_json.map((c, i) => (
                      <div key={c.chunk_id || c.document_id || i} className="p-3 mb-2 rounded-xl border border-cx-border bg-white/40">
                        <div className="flex items-start justify-between gap-2">
                          <p className="text-sm font-medium leading-snug">
                            {c.index != null && `[${c.index}] `}
                            {c.title}
                          </p>
                          <span className="text-2xs font-mono text-cx-accent shrink-0">
                            {((c.relevance || 0) * 100).toFixed(0)}%
                          </span>
                        </div>
                        <p className="text-xs text-cx-fgDim mt-1">
                          {c.source}
                          {c.chunk_index != null && ` · chunk ${c.chunk_index}`}
                        </p>
                        {c.excerpt && (
                          <p className="text-xs text-cx-fgMuted mt-2 line-clamp-4 leading-relaxed">{c.excerpt}</p>
                        )}
                        {c.url && (
                          <a href={c.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-2xs text-cx-accent mt-2 hover:underline">
                            Open source <ExternalLink size={10} />
                          </a>
                        )}
                        {c.document_id && c.source === 'vector_index' && (
                          <Link
                            to={`/knowledge-graph?document_id=${c.document_id}`}
                            className="inline-flex items-center gap-1 text-2xs text-cx-accent mt-2 ml-3 hover:underline"
                          >
                            Knowledge Graph <ExternalLink size={10} />
                          </Link>
                        )}
                      </div>
                    ))
                  ) : (
                    <p className="text-xs text-cx-fgDim">No citations available for this run.</p>
                  )}
                </GlassPanel>

                <GlassPanel>
                  <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim mb-3">Execution Logs</p>
                  {result.logs_json?.map((log, i) => (
                    <div key={i} className="flex items-center gap-2 text-xs text-cx-fgMuted mb-1">
                      <CheckCircle size={12} className="text-cx-success shrink-0" />
                      <span className="font-mono text-cx-fgDim">{log.timestamp?.slice(11, 19)}</span>
                      {log.message}
                    </div>
                  ))}
                </GlassPanel>
              </>
            )}
          </>
        ) : (
          <GlassPanel className="flex flex-col items-center justify-center h-64 text-center px-6">
            <p className="text-cx-fgDim text-sm">Pick a task on the left to get started</p>
            <p className="text-2xs text-cx-fgDim mt-2">Ask · Hypothesize · Design · Report</p>
          </GlassPanel>
        )}
      </div>
    </div>
  );
}
