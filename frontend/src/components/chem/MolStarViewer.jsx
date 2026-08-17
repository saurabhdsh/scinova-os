import { Component, Suspense, lazy } from 'react';
import { Loader2 } from 'lucide-react';

const MolStarCanvas = lazy(() => import('./MolStarCanvas'));

function Placeholder({ height, message, tone = 'slate' }) {
  const color = tone === 'rose' ? 'text-rose-300' : 'text-slate-400';
  return (
    <div
      className={`rounded-xl border border-cx-border bg-slate-950/90 flex items-center justify-center gap-2 text-sm ${color}`}
      style={{ height }}
    >
      {tone === 'slate' && <Loader2 size={16} className="animate-spin" />}
      {message}
    </div>
  );
}

class ViewerBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { failed: false };
  }

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    if (this.state.failed) {
      return <Placeholder height={this.props.height} message="3D engine could not be loaded" tone="rose" />;
    }
    return this.props.children;
  }
}

/**
 * Mol* 3D viewer rendered natively inside the SciNova canvas.
 * The heavy engine is code-split so it only loads when a structure is shown.
 */
export default function MolStarViewer({ pdbId, structureUrl, height = 420, label, className = '' }) {
  return (
    <ViewerBoundary height={height}>
      <Suspense fallback={<Placeholder height={height} message="Loading 3D engine…" />}>
        <MolStarCanvas
          pdbId={pdbId}
          structureUrl={structureUrl}
          height={height}
          label={label}
          className={className}
        />
      </Suspense>
    </ViewerBoundary>
  );
}
