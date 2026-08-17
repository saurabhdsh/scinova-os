import { useEffect, useState } from 'react';
import { Download } from 'lucide-react';
import { chemDepict } from '../../api/client';

export default function SmilesDepict({ smiles, label, className = '' }) {
  const [svg, setSvg] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!smiles) {
      setSvg(null);
      return undefined;
    }
    let cancelled = false;
    chemDepict({ smiles })
      .then((r) => {
        if (cancelled) return;
        if (r.data?.ok && r.data.svg) setSvg(r.data.svg);
        else setError(r.data?.error || 'Depict failed');
      })
      .catch(() => {
        if (!cancelled) setError('Depict unavailable');
      });
    return () => { cancelled = true; };
  }, [smiles]);

  const exportSvg = () => {
    if (!svg) return;
    const blob = new Blob([svg], { type: 'image/svg+xml' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${(label || 'molecule').replace(/\s+/g, '_')}.svg`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (!smiles) return null;

  return (
    <div className={`rounded-xl border border-cx-border bg-white/70 p-3 ${className}`}>
      <div className="flex items-center justify-between mb-2">
        <p className="text-2xs uppercase tracking-wider text-cx-fgDim">2D depiction{label ? ` · ${label}` : ''}</p>
        <button
          type="button"
          onClick={exportSvg}
          disabled={!svg}
          className="inline-flex items-center gap-1 text-2xs text-cx-accent disabled:opacity-40"
        >
          <Download size={12} /> SVG
        </button>
      </div>
      {error && <p className="text-xs text-cx-danger">{error}</p>}
      {svg ? (
        <div
          className="flex justify-center overflow-hidden [&_svg]:max-w-full"
          dangerouslySetInnerHTML={{ __html: svg }}
        />
      ) : (
        <p className="text-xs text-cx-fgDim font-mono break-all">{smiles}</p>
      )}
      <p className="mt-2 text-2xs font-mono text-cx-fgDim break-all">{smiles}</p>
    </div>
  );
}
