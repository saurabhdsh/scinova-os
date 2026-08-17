import { useCallback, useEffect, useRef, useState } from 'react';
import {
  Camera, Loader2, Maximize2, Pause, Play, RotateCcw, Rotate3d,
} from 'lucide-react';
import { createPluginUI } from 'molstar/lib/mol-plugin-ui';
import { renderReact18 } from 'molstar/lib/mol-plugin-ui/react18';
import { DefaultPluginUISpec } from 'molstar/lib/mol-plugin-ui/spec';
import { PluginCommands } from 'molstar/lib/mol-plugin/commands';
import { PluginConfig } from 'molstar/lib/mol-plugin/config';
import 'molstar/build/viewer/molstar.css';

const REPRESENTATIONS = [
  { id: 'cartoon', label: 'Cartoon', type: 'cartoon' },
  { id: 'surface', label: 'Surface', type: 'molecular-surface' },
  { id: 'ball-and-stick', label: 'Ball & stick', type: 'ball-and-stick' },
  { id: 'spacefill', label: 'Spacefill', type: 'spacefill' },
];

const COLOR_THEMES = [
  { id: 'chain-id', label: 'Chain' },
  { id: 'secondary-structure', label: 'Secondary structure' },
  { id: 'element-symbol', label: 'Element' },
  { id: 'hydrophobicity', label: 'Hydrophobicity' },
];

const ANIMATIONS = [
  { id: 'off', label: 'Static' },
  { id: 'spin', label: 'Spin' },
  { id: 'rock', label: 'Rock' },
];

function structureUrlFor(pdbId, explicitUrl) {
  if (explicitUrl) return explicitUrl;
  if (pdbId) return `https://files.rcsb.org/download/${pdbId.toUpperCase()}.cif`;
  return null;
}

function readStructureDetails(structureCell) {
  const details = {
    title: null, atoms: null, residues: null, chains: null, models: null, hasLigand: false,
  };
  try {
    const data = structureCell?.data;
    if (!data) return details;
    details.atoms = data.elementCount ?? null;
    details.residues = data.polymerResidueCount ?? null;
    details.chains = data.units?.length ?? null;
    const model = data.model || data.models?.[0];
    if (model) {
      details.title = model.label || model.entry || null;
      details.models = data.models?.length ?? 1;
    }
  } catch {
    // Detail extraction is best-effort; viewer still works without it.
  }
  return details;
}

export default function MolStarCanvas({
  pdbId,
  structureUrl,
  height = 420,
  label,
  className = '',
}) {
  const hostRef = useRef(null);
  const wrapRef = useRef(null);
  const pluginRef = useRef(null);
  const [ready, setReady] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [rep, setRep] = useState('cartoon');
  const [theme, setTheme] = useState('chain-id');
  const [animation, setAnimation] = useState('spin');
  const [details, setDetails] = useState(null);

  const url = structureUrlFor(pdbId, structureUrl);

  useEffect(() => {
    let disposed = false;
    let plugin = null;

    async function init() {
      if (!hostRef.current) return;
      try {
        // Every control lives in the SciNova chrome above, so Mol*'s own
        // viewport widgets are switched off to keep the canvas clean.
        const spec = {
          ...DefaultPluginUISpec(),
          layout: { initial: { isExpanded: false, showControls: false } },
          components: { remoteState: 'none' },
          config: [
            [PluginConfig.Viewport.ShowExpand, false],
            [PluginConfig.Viewport.ShowControls, false],
            [PluginConfig.Viewport.ShowSettings, false],
            [PluginConfig.Viewport.ShowSelectionMode, false],
            [PluginConfig.Viewport.ShowAnimation, false],
            [PluginConfig.Viewport.ShowTrajectoryControls, false],
          ],
        };
        plugin = await createPluginUI({
          target: hostRef.current,
          spec,
          render: renderReact18,
        });
        if (disposed) {
          plugin.dispose();
          return;
        }
        pluginRef.current = plugin;
        setReady(true);
      } catch (err) {
        if (!disposed) setError(err?.message || 'Mol* failed to initialize');
      }
    }

    init();
    return () => {
      disposed = true;
      try {
        pluginRef.current?.dispose();
      } catch {
        // ignore dispose races
      }
      pluginRef.current = null;
    };
  }, []);

  const applyAnimation = useCallback((mode) => {
    const plugin = pluginRef.current;
    if (!plugin?.canvas3d) return;
    const animate = mode === 'spin'
      ? { name: 'spin', params: { speed: 1 } }
      : mode === 'rock'
        ? { name: 'rock', params: { speed: 0.3, angle: 10 } }
        : { name: 'off', params: {} };
    try {
      plugin.canvas3d.setProps({ trackball: { animate } });
    } catch {
      // animation is cosmetic
    }
  }, []);

  useEffect(() => {
    if (!ready || !url) return;
    let cancelled = false;

    async function load() {
      const plugin = pluginRef.current;
      if (!plugin) return;
      setLoading(true);
      setError('');
      try {
        await plugin.clear();
        const isBinary = url.endsWith('.bcif');
        const data = await plugin.builders.data.download(
          { url, isBinary },
          { state: { isGhost: true } },
        );
        const trajectory = await plugin.builders.structure.parseTrajectory(data, 'mmcif');
        const model = await plugin.builders.structure.createModel(trajectory);
        const structure = await plugin.builders.structure.createStructure(model);
        if (cancelled) return;

        const repType = REPRESENTATIONS.find((r) => r.id === rep)?.type || 'cartoon';
        const polymer = await plugin.builders.structure.tryCreateComponentStatic(structure, 'polymer');
        const ligand = await plugin.builders.structure.tryCreateComponentStatic(structure, 'ligand');

        if (polymer) {
          await plugin.builders.structure.representation.addRepresentation(polymer, {
            type: repType,
            color: theme,
          });
        }
        if (ligand) {
          await plugin.builders.structure.representation.addRepresentation(ligand, {
            type: 'ball-and-stick',
            color: 'element-symbol',
          });
        }
        if (cancelled) return;

        const info = readStructureDetails(structure);
        info.hasLigand = Boolean(ligand);
        setDetails(info);

        await PluginCommands.Camera.Reset(plugin, {});
        applyAnimation(animation);
      } catch (err) {
        if (!cancelled) setError(err?.message || 'Failed to load structure');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => { cancelled = true; };
  }, [ready, url, rep, theme, applyAnimation, animation]);

  useEffect(() => {
    applyAnimation(animation);
  }, [animation, applyAnimation]);

  const resetCamera = async () => {
    const plugin = pluginRef.current;
    if (!plugin) return;
    await PluginCommands.Camera.Reset(plugin, {});
  };

  const snapshot = async () => {
    const plugin = pluginRef.current;
    const helper = plugin?.helpers?.viewportScreenshot;
    if (!helper) return;
    try {
      const uri = await helper.getImageDataUri();
      const a = document.createElement('a');
      a.href = uri;
      a.download = `${(pdbId || label || 'structure')}.png`;
      a.click();
    } catch {
      setError('Snapshot unavailable');
    }
  };

  const toggleFullscreen = () => {
    const el = wrapRef.current;
    if (!el) return;
    if (document.fullscreenElement) document.exitFullscreen();
    else el.requestFullscreen?.();
  };

  if (!url) {
    return (
      <div
        className={`rounded-xl border border-cx-border bg-slate-950/90 text-slate-400 flex items-center justify-center text-sm ${className}`}
        style={{ height }}
      >
        Select a PDB structure to render in 3D
      </div>
    );
  }

  return (
    <div ref={wrapRef} className={`rounded-xl border border-cx-border overflow-hidden bg-slate-950 ${className}`}>
      <div className="flex flex-wrap items-center gap-2 px-3 py-2 border-b border-white/10 bg-slate-900/80">
        <span className="text-2xs uppercase tracking-wider text-slate-400">3D structure</span>
        {pdbId && <span className="text-xs font-mono text-cyan-300">{pdbId}</span>}
        {loading && <Loader2 size={12} className="animate-spin text-cyan-300" />}
        <div className="flex items-center gap-1 ml-auto">
          {ANIMATIONS.map((a) => (
            <button
              key={a.id}
              type="button"
              onClick={() => setAnimation(a.id)}
              className={`px-2 py-0.5 rounded text-2xs border inline-flex items-center gap-1 ${
                animation === a.id
                  ? 'border-cyan-400/50 text-cyan-300 bg-cyan-400/10'
                  : 'border-white/10 text-slate-400 hover:text-slate-200'
              }`}
              title={`${a.label} animation`}
            >
              {a.id === 'off' ? <Pause size={10} /> : a.id === 'spin' ? <Rotate3d size={10} /> : <Play size={10} />}
              {a.label}
            </button>
          ))}
          <button type="button" onClick={resetCamera} className="p-1 rounded border border-white/10 text-slate-300 hover:text-white" title="Reset camera">
            <RotateCcw size={12} />
          </button>
          <button type="button" onClick={snapshot} className="p-1 rounded border border-white/10 text-slate-300 hover:text-white" title="Download PNG snapshot">
            <Camera size={12} />
          </button>
          <button type="button" onClick={toggleFullscreen} className="p-1 rounded border border-white/10 text-slate-300 hover:text-white" title="Fullscreen">
            <Maximize2 size={12} />
          </button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2 px-3 py-2 border-b border-white/10 bg-slate-900/50">
        <div className="flex gap-1">
          {REPRESENTATIONS.map((r) => (
            <button
              key={r.id}
              type="button"
              onClick={() => setRep(r.id)}
              className={`px-2 py-0.5 rounded text-2xs border ${
                rep === r.id
                  ? 'border-cyan-400/50 text-cyan-300 bg-cyan-400/10'
                  : 'border-white/10 text-slate-400 hover:text-slate-200'
              }`}
            >
              {r.label}
            </button>
          ))}
        </div>
        <select
          value={theme}
          onChange={(e) => setTheme(e.target.value)}
          className="ml-auto text-2xs bg-slate-900 border border-white/10 text-slate-300 rounded px-2 py-1"
          title="Color theme"
        >
          {COLOR_THEMES.map((t) => (
            <option key={t.id} value={t.id}>{t.label}</option>
          ))}
        </select>
      </div>

      <div className="relative" style={{ height }}>
        <div ref={hostRef} className="absolute inset-0" />
        {!ready && !error && (
          <div className="absolute inset-0 flex items-center justify-center text-slate-400 text-sm gap-2">
            <Loader2 size={16} className="animate-spin" /> Starting 3D engine…
          </div>
        )}
      </div>

      {error && (
        <p className="px-3 py-2 text-2xs text-rose-300 border-t border-white/10 bg-rose-500/10">{error}</p>
      )}

      <div className="px-3 py-2 border-t border-white/10 grid grid-cols-2 sm:grid-cols-5 gap-2 text-2xs">
        <div>
          <p className="text-slate-500 uppercase tracking-wider">Entry</p>
          <p className="text-slate-300 truncate" title={details?.title || pdbId || ''}>
            {details?.title || pdbId || '—'}
          </p>
        </div>
        <div>
          <p className="text-slate-500 uppercase tracking-wider">Chains</p>
          <p className="text-slate-300">{details?.chains ?? '—'}</p>
        </div>
        <div>
          <p className="text-slate-500 uppercase tracking-wider">Residues</p>
          <p className="text-slate-300">{details?.residues?.toLocaleString?.() ?? '—'}</p>
        </div>
        <div>
          <p className="text-slate-500 uppercase tracking-wider">Atoms</p>
          <p className="text-slate-300">{details?.atoms?.toLocaleString?.() ?? '—'}</p>
        </div>
        <div>
          <p className="text-slate-500 uppercase tracking-wider">Ligand</p>
          <p className="text-slate-300">{details ? (details.hasLigand ? 'Present' : 'None') : '—'}</p>
        </div>
      </div>

      <p className="px-3 py-1.5 text-2xs text-slate-500 border-t border-white/10">
        Drag to rotate · scroll to zoom · right-drag to pan. Rendered in SciNova via Mol*.
      </p>
    </div>
  );
}
