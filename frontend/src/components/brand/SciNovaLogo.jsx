/** Shared SciAi-Nova mark — same asset as /favicon.svg */
export default function SciNovaLogo({ size = 40, className = '' }) {
  return (
    <img
      src="/favicon.svg"
      alt="SciAi-Nova OS"
      width={size}
      height={size}
      className={`shrink-0 rounded-xl shadow-sm ring-1 ring-cx-accent/20 ${className}`}
      draggable={false}
    />
  );
}
