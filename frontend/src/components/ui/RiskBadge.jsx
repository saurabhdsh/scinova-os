const colors = {
  low: 'bg-cx-success/10 text-cx-success border-cx-success/25',
  medium: 'bg-cx-warn/10 text-cx-warn border-cx-warn/25',
  high: 'bg-cx-danger/10 text-cx-danger border-cx-danger/25',
};

export default function RiskBadge({ level }) {
  const cls = colors[level] || colors.medium;
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-2xs uppercase tracking-wider font-medium border ${cls}`}>
      {level}
    </span>
  );
}
