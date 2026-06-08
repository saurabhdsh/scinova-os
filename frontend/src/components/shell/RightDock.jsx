import { X, Sparkles } from 'lucide-react';

export default function RightDock({ open, onClose, children, title = 'Evidence Panel', subtitle = 'Citations & Context' }) {
  if (!open) return null;
  return (
    <aside className="shrink-0 w-[340px] border-l border-cx-line bg-white/75 backdrop-blur-xl shadow-dock flex flex-col h-full">
      <div className="p-4 border-b border-cx-line flex items-start justify-between">
        <div>
          <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim flex items-center gap-1.5">
            <Sparkles size={12} className="text-cx-accent" /> {subtitle}
          </p>
          <h3 className="font-display font-semibold text-sm text-cx-fg mt-1">{title}</h3>
        </div>
        <button onClick={onClose} className="p-1.5 rounded-lg border border-cx-border hover:border-cx-borderStrong">
          <X size={14} className="text-cx-fgDim" />
        </button>
      </div>
      <div className="flex-1 overflow-y-auto p-4">{children}</div>
    </aside>
  );
}
