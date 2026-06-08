export default function GlassPanel({ children, className = '', hero = false }) {
  return (
    <div className={`${hero ? 'glass-panel-hero' : 'glass-panel'} p-6 ${className}`}>
      {children}
    </div>
  );
}
