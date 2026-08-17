export default function ChemSessionBar({ session, onExport }) {
  if (!session) return null;
  const target = session.target;
  return (
    <div className="flex flex-wrap items-center gap-3 text-xs">
      <span className="text-2xs uppercase tracking-wider text-cx-fgDim">Session</span>
      {target ? (
        <span className="px-2 py-1 rounded-lg border border-cx-accent/25 bg-cx-accent/5 text-cx-accent">
          {target.gene_symbol} · {target.uniprot_id}
        </span>
      ) : (
        <span className="text-cx-fgDim">No target yet</span>
      )}
      {session.last_pdb_id && (
        <span className="px-2 py-1 rounded-lg border border-cx-border bg-white/50 font-mono">
          PDB {session.last_pdb_id}
        </span>
      )}
      <span className="text-cx-fgDim">{session.actives_count || 0} actives</span>
      <span className="text-cx-fgDim">{session.candidates_count || 0} candidates</span>
      <span className="text-cx-fgDim">{session.cards_count || 0} cards</span>
      <button
        type="button"
        onClick={onExport}
        className="ml-auto px-3 py-1.5 rounded-xl border border-cx-border text-cx-fgMuted hover:border-cx-accent/30 hover:text-cx-accent"
      >
        Export session
      </button>
    </div>
  );
}
