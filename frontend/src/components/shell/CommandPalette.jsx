import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Bot, FileText, GitBranch, LayoutDashboard, Loader2, Search, Share2, Sparkles,
  Workflow, Settings, Shield, Users, Cpu, Play,
} from 'lucide-react';
import { fabricSearch, getAgents, getDocuments, searchGraph } from '../../api/client';

const NAV_ITEMS = [
  { id: 'nav-home', label: 'Drug Research Command Center', path: '/', icon: LayoutDashboard, group: 'Pages' },
  { id: 'nav-value-chain', label: 'Pharma Value Chain', path: '/value-chain', icon: GitBranch, group: 'Pages' },
  { id: 'nav-fabric', label: 'Scientific Data Fabric', path: '/data-fabric', icon: Sparkles, group: 'Pages' },
  { id: 'nav-docs', label: 'Documents', path: '/documents', icon: FileText, group: 'Pages' },
  { id: 'nav-graph', label: 'Knowledge Graph Explorer', path: '/knowledge-graph', icon: Share2, group: 'Pages' },
  { id: 'nav-agents', label: 'Research Agent Catalog', path: '/agents', icon: Bot, group: 'Pages' },
  { id: 'nav-workspace', label: 'Ask & Run Agents', path: '/agents/workspace', icon: Play, group: 'Pages' },
  { id: 'nav-workflows', label: 'Research Orchestrator', path: '/workflows', icon: Workflow, group: 'Pages' },
  { id: 'nav-slm', label: 'Model Routing (SLM/LLM)', path: '/slm', icon: Cpu, group: 'Pages' },
  { id: 'nav-reports', label: 'Scientific Reports', path: '/reports', icon: FileText, group: 'Pages' },
  { id: 'nav-collab', label: 'Collaboration & Briefs', path: '/collaboration', icon: Users, group: 'Pages' },
  { id: 'nav-governance', label: 'Governance & Compliance', path: '/governance', icon: Shield, group: 'Pages' },
  { id: 'nav-settings', label: 'Platform Settings', path: '/settings', icon: Settings, group: 'Pages' },
];

function matchQuery(text, query) {
  return text?.toLowerCase().includes(query.toLowerCase());
}

export default function CommandPalette({ open, onClose, initialQuery = '' }) {
  const navigate = useNavigate();
  const inputRef = useRef(null);
  const listRef = useRef(null);
  const [query, setQuery] = useState(initialQuery);
  const [loading, setLoading] = useState(false);
  const [remoteResults, setRemoteResults] = useState([]);
  const [activeIndex, setActiveIndex] = useState(0);

  useEffect(() => {
    if (open) {
      setQuery(initialQuery);
      setActiveIndex(0);
      setRemoteResults([]);
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open, initialQuery]);

  const navResults = useMemo(() => {
    const q = query.trim();
    if (!q) return NAV_ITEMS.slice(0, 6);
    return NAV_ITEMS.filter((item) => matchQuery(item.label, q));
  }, [query]);

  useEffect(() => {
    const q = query.trim();
    if (!open || q.length < 2) {
      setRemoteResults([]);
      return undefined;
    }

    let cancelled = false;
    const timer = setTimeout(async () => {
      setLoading(true);
      try {
        const [agentsRes, docsRes, graphRes] = await Promise.all([
          getAgents(),
          getDocuments({ limit: 80 }),
          searchGraph({ q, live_only: false }).catch(() => ({ data: { nodes: [] } })),
        ]);
        if (cancelled) return;

        const items = [];
        (agentsRes.data || [])
          .filter((a) => matchQuery(a.name, q) || matchQuery(a.description, q))
          .slice(0, 5)
          .forEach((a) => {
            items.push({
              id: `agent-${a.id}`,
              label: a.name,
              hint: a.value_chain_stage || 'Agent',
              path: `/agents/run/${a.id}`,
              icon: Bot,
              group: 'Agents',
            });
          });

        (docsRes.data || [])
          .filter((d) => matchQuery(d.title, q) || matchQuery(d.filename, q))
          .slice(0, 5)
          .forEach((d) => {
            items.push({
              id: `doc-${d.id}`,
              label: d.title || d.filename,
              hint: d.source_type || 'Document',
              path: '/documents',
              icon: FileText,
              group: 'Documents',
            });
          });

        (graphRes.data?.nodes || [])
          .slice(0, 5)
          .forEach((n) => {
            items.push({
              id: `entity-${n.id}`,
              label: n.name,
              hint: n.entity_type || 'Entity',
              path: `/knowledge-graph?entity=${encodeURIComponent(n.id)}`,
              icon: GitBranch,
              group: 'Knowledge Graph',
            });
          });

        if (q.length >= 3) {
          try {
            const searchRes = await fabricSearch({ query: q, top_k: 3 });
            if (!cancelled) {
              (searchRes.data || []).forEach((hit, i) => {
                items.push({
                  id: `vector-${hit.document_id}-${i}`,
                  label: hit.content?.slice(0, 80) || hit.metadata?.title || 'Semantic match',
                  hint: hit.metadata?.title || `Doc ${hit.document_id?.slice(0, 8)}`,
                  path: '/data-fabric',
                  icon: Search,
                  group: 'Semantic Search',
                });
              });
            }
          } catch {
            /* vector index may be empty */
          }
        }

        setRemoteResults(items);
      } catch {
        if (!cancelled) setRemoteResults([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }, 250);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [open, query]);

  const flatResults = useMemo(
    () => [...navResults, ...remoteResults],
    [navResults, remoteResults],
  );

  useEffect(() => {
    setActiveIndex(0);
  }, [query]);

  const selectItem = useCallback((item) => {
    if (!item?.path) return;
    navigate(item.path);
    onClose();
  }, [navigate, onClose]);

  useEffect(() => {
    if (!open) return undefined;

    const onKeyDown = (e) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
        return;
      }
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setActiveIndex((i) => Math.min(i + 1, flatResults.length - 1));
        return;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setActiveIndex((i) => Math.max(i - 1, 0));
        return;
      }
      if (e.key === 'Enter' && flatResults[activeIndex]) {
        e.preventDefault();
        selectItem(flatResults[activeIndex]);
      }
    };

    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [open, flatResults, activeIndex, onClose, selectItem]);

  useEffect(() => {
    const el = listRef.current?.querySelector('[data-active="true"]');
    el?.scrollIntoView({ block: 'nearest' });
  }, [activeIndex]);

  if (!open) return null;

  const grouped = flatResults.reduce((acc, item, index) => {
    const group = item.group || 'Results';
    if (!acc[group]) acc[group] = [];
    acc[group].push({ ...item, index });
    return acc;
  }, {});

  return (
    <div className="fixed inset-0 z-[100] flex items-start justify-center pt-[12vh] px-4">
      <button
        type="button"
        aria-label="Close search"
        className="absolute inset-0 bg-cx-void/40 backdrop-blur-sm"
        onClick={onClose}
      />
      <div className="relative w-full max-w-xl rounded-2xl border border-cx-border bg-white/95 shadow-2xl backdrop-blur-xl overflow-hidden">
        <div className="flex items-center gap-3 px-4 py-3 border-b border-cx-line">
          <Search size={18} className="text-cx-accent shrink-0" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search pages, documents, agents, entities…"
            className="flex-1 bg-transparent text-sm focus:outline-none placeholder:text-cx-fgDim"
          />
          {loading && <Loader2 size={16} className="animate-spin text-cx-fgDim" />}
          <kbd className="font-mono text-2xs text-cx-fgDim border border-cx-border px-1.5 py-0.5 rounded bg-cx-deep/30">
            Esc
          </kbd>
        </div>

        <div ref={listRef} className="max-h-[50vh] overflow-y-auto p-2">
          {flatResults.length === 0 && !loading && (
            <p className="px-3 py-6 text-sm text-cx-fgMuted text-center">
              {query.trim().length < 2
                ? 'Type to search or pick a destination below.'
                : 'No matches found.'}
            </p>
          )}

          {Object.entries(grouped).map(([group, items]) => (
            <div key={group} className="mb-2">
              <p className="px-3 py-1.5 text-2xs uppercase tracking-wider text-cx-fgDim">{group}</p>
              {items.map((item) => {
                const Icon = item.icon || Search;
                const isActive = item.index === activeIndex;
                return (
                  <button
                    key={item.id}
                    type="button"
                    data-active={isActive}
                    onClick={() => selectItem(item)}
                    className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-left transition-colors ${
                      isActive ? 'bg-cx-accent/10 border border-cx-accent/20' : 'hover:bg-white/80 border border-transparent'
                    }`}
                  >
                    <Icon size={16} className={isActive ? 'text-cx-accent' : 'text-cx-fgMuted'} />
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-cx-fg truncate">{item.label}</p>
                      {item.hint && (
                        <p className="text-2xs text-cx-fgDim truncate">{item.hint}</p>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>
          ))}
        </div>

        <div className="px-4 py-2 border-t border-cx-line flex items-center justify-between text-2xs text-cx-fgDim">
          <span>↑↓ navigate · Enter open · Esc close</span>
          <span>Cmd+K anytime</span>
        </div>
      </div>
    </div>
  );
}
