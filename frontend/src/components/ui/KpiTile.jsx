import { TrendingUp, TrendingDown } from 'lucide-react';
import GlassPanel from './GlassPanel';

export default function KpiTile({ label, value, suffix, trend, trendUp, icon: Icon, accent = 'accent' }) {
  const accentClass = accent === 'accent2' ? 'text-cx-accent2' : accent === 'success' ? 'text-cx-success' : 'text-cx-accent';
  return (
    <GlassPanel className="p-5">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim font-medium">{label}</p>
          <p className="mt-2 font-display text-3xl font-semibold text-cx-fg">
            {value}
            {suffix && <span className="text-lg text-cx-fgMuted ml-1">{suffix}</span>}
          </p>
          {trend && (
            <p className={`mt-1 flex items-center gap-1 text-xs ${trendUp ? 'text-cx-success' : 'text-cx-danger'}`}>
              {trendUp ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
              {trend}
            </p>
          )}
        </div>
        {Icon && (
          <div className={`p-2.5 rounded-xl bg-cx-deep/80 border border-cx-border ${accentClass}`}>
            <Icon size={20} strokeWidth={1.75} />
          </div>
        )}
      </div>
    </GlassPanel>
  );
}
