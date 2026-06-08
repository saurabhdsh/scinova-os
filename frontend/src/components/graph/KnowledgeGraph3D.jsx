import '../../lib/graph-three-init';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import ForceGraph3D from 'react-force-graph-3d';
import SpriteText from 'three-spritetext';
import { Maximize2, RotateCcw, ZoomIn, ZoomOut } from 'lucide-react';

export const NODE_COLORS = {
  Gene: '#22d3ee',
  Protein: '#a78bfa',
  Disease: '#f87171',
  Compound: '#34d399',
  Target: '#fbbf24',
  Biomarker: '#818cf8',
  Pathway: '#2dd4bf',
  Assay: '#94a3b8',
  Study: '#c4b5fd',
  'ADMET attribute': '#4ade80',
  default: '#64748b',
};

const LEGEND_TYPES = ['Gene', 'Protein', 'Disease', 'Compound', 'Target', 'Biomarker', 'Pathway', 'Study'];
const BG = '#060a12';

function nodeVal(linkCount) {
  return Math.max(2.5, 1.8 + linkCount * 0.45);
}

function truncateLabel(label, max = 26) {
  const text = (label || '').trim();
  if (text.length <= max) return text;
  return `${text.slice(0, max - 1)}…`;
}

function makeNodeLabel(node, selectedNodeId) {
  const color = NODE_COLORS[node.node_type] || NODE_COLORS.default;
  const isSelected = node.id === selectedNodeId;
  const sprite = new SpriteText(truncateLabel(node.label || node.id));
  sprite.color = '#f1f5f9';
  sprite.textHeight = isSelected ? 4.2 : 3.4;
  sprite.fontFace = 'Inter, system-ui, sans-serif';
  sprite.fontWeight = isSelected ? '700' : '600';
  sprite.backgroundColor = 'rgba(6, 10, 18, 0.88)';
  sprite.padding = 2.5;
  sprite.borderWidth = isSelected ? 1 : 0.6;
  sprite.borderColor = color;
  sprite.strokeWidth = 0;
  sprite.material.depthWrite = false;
  sprite.material.depthTest = false;
  sprite.renderOrder = 999;
  sprite.center.y = -1.15;
  return sprite;
}

export default function KnowledgeGraph3D({
  nodes = [],
  relationships = [],
  loading = false,
  selectedNodeId = null,
  onNodeClick,
}) {
  const fgRef = useRef();
  const containerRef = useRef();
  const [dimensions, setDimensions] = useState({ width: 800, height: 520 });

  const linkCounts = useMemo(() => {
    const counts = {};
    relationships.forEach((r) => {
      const src = r.source_node_id ?? r.source;
      const tgt = r.target_node_id ?? r.target;
      counts[src] = (counts[src] || 0) + 1;
      counts[tgt] = (counts[tgt] || 0) + 1;
    });
    return counts;
  }, [relationships]);

  const graphData = useMemo(() => {
    const nodeList = nodes.map((n) => ({
      id: n.id,
      label: n.label,
      node_type: n.node_type,
      val: nodeVal(linkCounts[n.id] || 0),
    }));
    const nodeIds = new Set(nodeList.map((n) => n.id));
    const links = relationships
      .map((r) => ({
        id: r.id,
        source: r.source_node_id ?? r.source,
        target: r.target_node_id ?? r.target,
        relationship_type: r.relationship_type,
        confidence: r.confidence ?? 0.75,
      }))
      .filter((l) => nodeIds.has(l.source) && nodeIds.has(l.target));
    return { nodes: nodeList, links };
  }, [nodes, relationships, linkCounts]);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return undefined;

    const updateSize = () => {
      const { width, height } = el.getBoundingClientRect();
      if (width > 0 && height > 0) setDimensions({ width, height });
    };

    updateSize();
    const ro = new ResizeObserver(updateSize);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    const fg = fgRef.current;
    if (!fg || graphData.nodes.length === 0) return undefined;

    fg.d3Force('charge')?.strength(-260);
    fg.d3Force('link')?.distance(55);
    fg.d3Force('center')?.strength(0.06);

    const fit = () => fg.zoomToFit(600, 80);
    const t1 = setTimeout(fit, 800);
    const t2 = setTimeout(fit, 2200);
    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
    };
  }, [graphData]);

  const nodeThreeObject = useCallback(
    (node) => makeNodeLabel(node, selectedNodeId),
    [selectedNodeId],
  );

  const handleEngineStop = useCallback(() => {
    fgRef.current?.zoomToFit(500, 70);
  }, []);

  const handleNodeClick = useCallback((node) => {
    onNodeClick?.(node);
    const fg = fgRef.current;
    if (!fg || node.x == null) return;
    const dist = 120;
    fg.cameraPosition(
      { x: node.x + dist * 0.3, y: node.y + dist * 0.2, z: node.z + dist },
      node,
      1200,
    );
  }, [onNodeClick]);

  const zoom = (factor) => {
    const fg = fgRef.current;
    if (!fg) return;
    const { x, y, z } = fg.cameraPosition();
    fg.cameraPosition({ x: x * factor, y: y * factor, z: z * factor }, null, 400);
  };

  const resetView = () => fgRef.current?.zoomToFit(500, 70);

  return (
    <div
      ref={containerRef}
      className="relative w-full flex-1 min-h-[480px] overflow-hidden"
      style={{ background: BG, height: '100%' }}
    >
      {graphData.nodes.length > 0 && dimensions.width > 0 && dimensions.height > 0 && (
        <div className="absolute inset-0 z-0">
          <ForceGraph3D
            ref={fgRef}
            width={dimensions.width}
            height={dimensions.height}
            graphData={graphData}
            backgroundColor={BG}
            showNavInfo={false}
            enableNodeDrag
            enableNavigationControls
            controlType="orbit"
            nodeRelSize={5}
            nodeVal="val"
            nodeColor={(node) => NODE_COLORS[node.node_type] || NODE_COLORS.default}
            nodeOpacity={0.92}
            nodeResolution={24}
            nodeThreeObject={nodeThreeObject}
            nodeThreeObjectExtend
            linkColor={(link) => {
              const c = link.confidence ?? 0.5;
              return `rgba(94, 200, 242, ${0.4 + c * 0.5})`;
            }}
            linkWidth={(link) => 0.8 + (link.confidence || 0.5) * 1.8}
            linkOpacity={0.85}
            linkCurvature={0.12}
            linkDirectionalParticles={(link) => (link.confidence > 0.5 ? 3 : 2)}
            linkDirectionalParticleWidth={2}
            linkDirectionalParticleSpeed={0.006}
            linkDirectionalParticleColor={() => '#7dd3fc'}
            linkLabel={(link) => link.relationship_type?.replace(/_/g, ' ')}
            nodeLabel={(node) => `${node.label}\n${node.node_type}`}
            onNodeClick={handleNodeClick}
            onEngineStop={handleEngineStop}
            d3AlphaDecay={0.015}
            d3VelocityDecay={0.25}
            warmupTicks={100}
            cooldownTicks={200}
          />
        </div>
      )}

      {loading && (
        <div className="absolute inset-0 flex items-center justify-center bg-[#060a12]/70 backdrop-blur-sm z-10">
          <div className="flex flex-col items-center gap-3">
            <div className="w-10 h-10 rounded-full border-2 border-cyan-400/30 border-t-cyan-400 animate-spin" />
            <p className="text-xs text-slate-400 tracking-wide">Simulating graph physics…</p>
          </div>
        </div>
      )}

      <div className="absolute top-3 right-3 flex flex-col gap-1.5 z-20 pointer-events-auto">
        {[
          { fn: () => zoom(0.72), icon: ZoomIn, title: 'Zoom in' },
          { fn: () => zoom(1.28), icon: ZoomOut, title: 'Zoom out' },
          { fn: resetView, icon: Maximize2, title: 'Fit graph' },
          { fn: resetView, icon: RotateCcw, title: 'Reset camera' },
        ].map(({ fn, icon: Icon, title }) => (
          <button
            key={title}
            type="button"
            onClick={fn}
            className="p-2 rounded-lg border border-slate-600/50 bg-slate-900/80 text-slate-300 hover:text-cyan-300 backdrop-blur-sm"
            title={title}
          >
            <Icon size={14} />
          </button>
        ))}
      </div>

      <div className="absolute bottom-3 left-3 z-20 p-3 rounded-xl border border-slate-600/40 bg-slate-900/85 backdrop-blur-md max-w-[240px] pointer-events-none">
        <p className="text-2xs uppercase tracking-[0.18em] text-slate-500 mb-2">Entity types</p>
        <div className="flex flex-wrap gap-x-3 gap-y-1.5">
          {LEGEND_TYPES.map((type) => (
            <span key={type} className="inline-flex items-center gap-1.5 text-2xs text-slate-400">
              <span
                className="w-2 h-2 rounded-full shrink-0"
                style={{ background: NODE_COLORS[type], boxShadow: `0 0 8px ${NODE_COLORS[type]}` }}
              />
              {type}
            </span>
          ))}
        </div>
        <p className="text-2xs text-slate-500 mt-2 leading-relaxed">
          Drag nodes · scroll to zoom · click to explore neighborhood
        </p>
      </div>

      {graphData.nodes.length > 0 && (
        <div className="absolute top-3 left-3 z-20 px-3 py-1.5 rounded-lg border border-cyan-500/30 bg-slate-900/80 backdrop-blur-sm pointer-events-none">
          <p className="text-2xs text-cyan-300 font-medium">
            {nodes.length} nodes · {relationships.length} relationships
          </p>
        </div>
      )}
    </div>
  );
}
