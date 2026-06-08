import { lazy, Suspense, useEffect, useState, useCallback } from 'react';
import { Search, Filter, RefreshCw, Database, Share2, GitBranch, Loader2 } from 'lucide-react';
import GlassPanel from '../components/ui/GlassPanel';
import {
  getFullGraph, searchGraph, getNeighborhood, getGraphStats, getDocuments, syncGraphToNeo4j,
} from '../api/client';

const KnowledgeGraph3D = lazy(() => import('../components/graph/KnowledgeGraph3D'));

const SOURCE_OPTIONS = [
  { value: 'auto', label: 'Auto (Neo4j if online)' },
  { value: 'neo4j', label: 'Neo4j graph DB' },
  { value: 'sql', label: 'SQL graph' },
];

export default function KnowledgeGraph() {
  const [graphNodes, setGraphNodes] = useState([]);
  const [graphRelationships, setGraphRelationships] = useState([]);
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState(null);
  const [selectedNodeId, setSelectedNodeId] = useState(null);
  const [filter, setFilter] = useState('');
  const [documentId, setDocumentId] = useState('');
  const [liveOnly, setLiveOnly] = useState(false);
  const [graphSource, setGraphSource] = useState('auto');
  const [activeSource, setActiveSource] = useState('sql');
  const [stats, setStats] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [graphHint, setGraphHint] = useState(null);

  const graphParams = useCallback(() => ({
    live_only: liveOnly,
    document_id: documentId || undefined,
    source: graphSource,
  }), [liveOnly, documentId, graphSource]);

  const applyGraphData = useCallback((data) => {
    if (data.graph_source) setActiveSource(data.graph_source);
    setGraphNodes(data.nodes || []);
    setGraphRelationships(data.relationships || []);
    setGraphHint(data.graph_hint || null);
  }, []);

  const refreshStats = useCallback(() => {
    getGraphStats().then((r) => setStats(r.data)).catch(console.error);
  }, []);

  const loadGraph = useCallback(async (overrides = {}) => {
    setLoading(true);
    try {
      const params = { ...graphParams(), ...overrides };
      let r = await getFullGraph(params);
      let data = r.data;

      if ((data.relationships?.length ?? 0) === 0 && (data.nodes?.length ?? 0) > 0) {
        const fallback = await getFullGraph({
          ...params,
          live_only: false,
          document_id: undefined,
        });
        if ((fallback.data.relationships?.length ?? 0) > 0) {
          data = {
            ...fallback.data,
            graph_hint: data.graph_hint
              || 'No relationships matched your filters — showing the connected knowledge graph.',
          };
        }
      }

      applyGraphData(data);
      setSelected(null);
      setSelectedNodeId(null);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [applyGraphData, graphParams]);

  useEffect(() => {
    refreshStats();
    getDocuments().then((r) => setDocuments(r.data.filter((d) => d.status === 'indexed'))).catch(console.error);
  }, [refreshStats]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const docParam = params.get('document_id');
    const entityParam = params.get('entity');
    if (docParam) {
      setDocumentId(docParam);
    }
    if (entityParam) {
      setSelectedNodeId(entityParam);
      getNeighborhood(entityParam, { source: graphSource })
        .then((r) => {
          setSelected(r.data);
          if (r.data.graph_source) setActiveSource(r.data.graph_source);
          const center = r.data.center_node;
          if (center?.name) setSearch(center.name);
          applyGraphData({
            nodes: r.data.nodes || [],
            relationships: r.data.relationships || [],
            graph_source: r.data.graph_source,
          });
        })
        .catch(console.error);
      return;
    }
    loadGraph({ document_id: docParam || undefined });
  // eslint-disable-next-line react-hooks/exhaustive-deps -- mount-only deep link
  }, []);

  useEffect(() => {
    loadGraph();
  }, [graphSource, liveOnly, documentId]);

  const handleSearch = async () => {
    setLoading(true);
    try {
      const params = {
        entity_type: filter || undefined,
        ...graphParams(),
      };
      const r = !search.trim() && !filter
        ? await getFullGraph(params)
        : await searchGraph({ q: search, ...params });
      let data = r.data;

      if ((data.relationships?.length ?? 0) === 0 && (data.nodes?.length ?? 0) > 0) {
        const fallback = await getFullGraph({
          ...params,
          live_only: false,
          document_id: undefined,
        });
        if ((fallback.data.relationships?.length ?? 0) > 0) {
          data = {
            ...fallback.data,
            graph_hint: data.graph_hint
              || 'No relationships matched your search — showing the connected knowledge graph.',
          };
        }
      }

      applyGraphData(data);
      setSelected(null);
      setSelectedNodeId(null);
    } finally {
      setLoading(false);
    }
  };

  const handleNodeClick = async (node) => {
    setSelectedNodeId(node.id);
    try {
      const r = await getNeighborhood(node.id, {
        source: graphSource,
        depth: graphSource === 'neo4j' || (graphSource === 'auto' && stats?.neo4j_connected) ? 2 : 1,
      });
      setSelected(r.data);
      if (r.data.graph_source) setActiveSource(r.data.graph_source);
    } catch {
      setSelected(null);
    }
  };

  const handleSync = async () => {
    setSyncing(true);
    try {
      await syncGraphToNeo4j();
      refreshStats();
      loadGraph();
    } catch (err) {
      console.error(err);
    } finally {
      setSyncing(false);
    }
  };

  const entityTypes = ['Gene', 'Protein', 'Disease', 'Compound', 'Target', 'Biomarker', 'Pathway', 'Study'];

  return (
    <div className="p-6 space-y-4 h-full flex flex-col">
      <GlassPanel hero className="shrink-0">
        <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim">Evidence</p>
        <h2 className="font-display text-xl font-semibold mt-1">Knowledge Graph Explorer</h2>
        {stats && (
          <div className="mt-3 flex flex-wrap gap-4 text-xs text-cx-fgMuted">
            <span className="flex items-center gap-1">
              <Share2 size={12} /> {stats.sql_nodes} SQL nodes · {stats.sql_relationships} rels
            </span>
            <span className="flex items-center gap-1">
              <Database size={12} /> {stats.live_ingested_nodes} from ingestion
            </span>
            <span className={stats.neo4j_connected ? 'text-cx-success' : 'text-cx-warn'}>
              Neo4j: {stats.neo4j_connected ? `${stats.neo4j_nodes} nodes · ${stats.neo4j_relationships} rels` : 'offline'}
            </span>
            <span className="flex items-center gap-1 text-cx-accent">
              <GitBranch size={12} /> Querying: {activeSource.toUpperCase()}
            </span>
          </div>
        )}
      </GlassPanel>

      <GlassPanel className="shrink-0">
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-cx-accent" size={16} />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              placeholder="Search entities (JAK1, Rheumatoid Arthritis...)"
              className="w-full pl-10 pr-4 py-2 rounded-xl border border-cx-border bg-white/60 text-sm"
            />
          </div>
          <select
            value={graphSource}
            onChange={(e) => setGraphSource(e.target.value)}
            className="text-xs border border-cx-border rounded-xl px-3 py-2 bg-white/60"
            title="Graph query engine"
          >
            {SOURCE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value} disabled={o.value === 'neo4j' && stats && !stats.neo4j_connected}>
                {o.label}
              </option>
            ))}
          </select>
          <select
            value={documentId}
            onChange={(e) => setDocumentId(e.target.value)}
            className="text-xs border border-cx-border rounded-xl px-3 py-2 bg-white/60 max-w-[200px]"
          >
            <option value="">All documents</option>
            {documents.map((d) => (
              <option key={d.id} value={d.id}>{d.title.slice(0, 40)}</option>
            ))}
          </select>
          <div className="flex items-center gap-2">
            <Filter size={14} className="text-cx-fgDim" />
            <select
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              className="text-xs border border-cx-border rounded-xl px-3 py-2 bg-white/60"
            >
              <option value="">All types</option>
              {entityTypes.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <button
            type="button"
            onClick={() => setLiveOnly((v) => !v)}
            className={`px-3 py-2 rounded-xl text-xs border ${liveOnly ? 'border-cx-accent/30 bg-cx-accent/5 text-cx-accent' : 'border-cx-border'}`}
          >
            Live ingested only
          </button>
          <button type="button" onClick={handleSearch} className="px-4 py-2 rounded-xl text-xs font-medium border border-cx-accent/30 bg-cx-accent/5 text-cx-accent">
            Search
          </button>
          <button type="button" onClick={() => loadGraph()} className="p-2 rounded-xl border border-cx-border hover:border-cx-accent/30" title="Refresh">
            <RefreshCw size={14} className={loading ? 'animate-spin text-cx-accent' : 'text-cx-fgDim'} />
          </button>
          {stats?.neo4j_connected && (
            <button
              type="button"
              onClick={handleSync}
              disabled={syncing}
              className="px-3 py-2 rounded-xl text-xs border border-cx-success/30 text-cx-success hover:bg-cx-success/5 disabled:opacity-50"
              title="Sync SQL graph to Neo4j"
            >
              {syncing ? 'Syncing…' : 'Sync Neo4j'}
            </button>
          )}
        </div>
      </GlassPanel>

      <div className="flex-1 flex gap-4 min-h-[520px]">
        <GlassPanel className="flex-1 p-0 overflow-hidden min-h-[500px] flex flex-col">
          {graphHint && (
            <div className="px-4 py-2 text-xs text-cx-warn border-b border-cx-warn/20 bg-cx-warn/5 shrink-0">
              {graphHint}
            </div>
          )}
          {graphNodes.length === 0 && !loading ? (
            <div className="h-full flex items-center justify-center text-sm text-cx-fgDim p-8 text-center min-h-[480px]">
              No graph data yet. Upload a scientific PDF in Data Fabric, then refresh.
            </div>
          ) : (
            <Suspense fallback={
              <div className="flex-1 min-h-[480px] flex items-center justify-center text-cx-fgMuted">
                <Loader2 className="animate-spin mr-2" size={20} />
                Loading 3D graph…
              </div>
            }>
              <KnowledgeGraph3D
                nodes={graphNodes}
                relationships={graphRelationships}
                loading={loading}
                selectedNodeId={selectedNodeId}
                onNodeClick={handleNodeClick}
              />
            </Suspense>
          )}
        </GlassPanel>

        {selected && (
          <GlassPanel className="w-96 shrink-0 overflow-y-auto">
            <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim">Entity Detail</p>
            <h3 className="font-display font-semibold mt-2">{selected.center_node.label}</h3>
            <p className="text-xs text-cx-fgDim mt-1">{selected.center_node.node_type}</p>
            <p className="text-2xs mt-2">
              <span className={selected.graph_source === 'neo4j' ? 'text-cx-success' : 'text-cx-fgDim'}>
                Source: {selected.graph_source?.toUpperCase() || 'SQL'}
                {selected.traversal_depth > 1 && ` · ${selected.traversal_depth}-hop traversal`}
              </span>
            </p>

            <p className="text-2xs uppercase tracking-wider text-cx-fgDim mt-4 mb-2">
              Neighborhood ({selected.relationships.length})
            </p>
            {selected.relationships.map((r) => (
              <div key={r.id} className="p-2 mb-2 rounded-lg border border-cx-border bg-white/40 text-xs">
                <span className="text-cx-accent font-medium">{r.relationship_type.replace(/_/g, ' ')}</span>
                <p className="text-cx-fgDim mt-0.5">Confidence: {((r.confidence || 0) * 100).toFixed(0)}%</p>
                {r.evidence_json?.[0] && (
                  <p className="text-cx-fgMuted mt-1 line-clamp-3">
                    {r.evidence_json[0].excerpt || r.evidence_json[0].text}
                  </p>
                )}
              </div>
            ))}

            {selected.source_chunks?.length > 0 && (
              <>
                <p className="text-2xs uppercase tracking-wider text-cx-fgDim mt-4 mb-2">Source Chunks</p>
                {selected.source_chunks.map((c) => (
                  <div key={c.id} className="p-2 mb-2 rounded-lg border border-cx-accent/20 bg-cx-accent/5 text-xs">
                    <p className="text-2xs text-cx-fgDim mb-1">Chunk {c.chunk_index}</p>
                    <p className="text-cx-fgMuted line-clamp-4">{c.content}</p>
                  </div>
                ))}
              </>
            )}

            {selected.center_node.evidence_json?.length > 0 && (
              <>
                <p className="text-2xs uppercase tracking-wider text-cx-fgDim mt-4 mb-2">Provenance</p>
                {selected.center_node.evidence_json.map((ev, i) => (
                  <p key={i} className="text-xs text-cx-fgMuted mb-1">
                    {ev.document_title || ev.document_id}
                    {ev.chunk_index != null && ` · chunk ${ev.chunk_index}`}
                  </p>
                ))}
              </>
            )}
          </GlassPanel>
        )}
      </div>
    </div>
  );
}
