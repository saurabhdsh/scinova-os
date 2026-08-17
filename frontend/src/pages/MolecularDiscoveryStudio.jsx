import { useCallback, useState } from 'react';
import { Loader2, Sparkles, Send } from 'lucide-react';
import GlassPanel from '../components/ui/GlassPanel';
import ChemSessionBar from '../components/chem/ChemSessionBar';
import ChemResultCard from '../components/chem/ChemResultCard';
import { chemQuery, createChemSession, exportChemSession } from '../api/client';
import { apiErrorMessage } from '../lib/auth';

const SUGGESTIONS = [
  'What are the available crystal structures of janus kinase 2 in the Protein Data Bank (PDB)?',
  'Retrieve the PDB structure of 3UGC',
  'Analyze druggability / binding pockets of 3UGC',
  'Design 10 small molecules against 3UGC that bind to pocket P_0',
  'Show known JAK2 inhibitors from ChEMBL',
  'Are these novel vs known inhibitors?',
  'Which motifs matter and are they present?',
  'Can the top molecule be made?',
  'Export this for review',
];

export default function MolecularDiscoveryStudio() {
  const [query, setQuery] = useState('');
  const [sessionId, setSessionId] = useState(null);
  const [sessionSummary, setSessionSummary] = useState(null);
  const [cards, setCards] = useState([]);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState('');

  const ensureSession = useCallback(async () => {
    if (sessionId) return sessionId;
    const r = await createChemSession();
    setSessionId(r.data.id);
    return r.data.id;
  }, [sessionId]);

  const run = async (text, intent) => {
    const q = (text ?? query).trim();
    if (!q) return;
    setRunning(true);
    setError('');
    try {
      const sid = await ensureSession();
      const r = await chemQuery({ query: q, session_id: sid, intent: intent || undefined });
      setSessionId(r.data.session_id);
      setSessionSummary(r.data.session);
      setCards((prev) => [r.data.card, ...prev]);
      setQuery('');
    } catch (err) {
      setError(apiErrorMessage(err, 'Chemistry query failed'));
    } finally {
      setRunning(false);
    }
  };

  const handleExport = async () => {
    if (!sessionId) return;
    try {
      await exportChemSession(sessionId);
    } catch (err) {
      setError(apiErrorMessage(err, 'Export failed'));
    }
  };

  return (
    <div className="p-4 lg:p-6 h-full flex flex-col min-h-0 gap-4">
      <div className="flex-1 grid gap-4 min-h-0 lg:grid-cols-[minmax(300px,360px)_minmax(0,1fr)]">
        {/* Composer column (static) */}
        <div className="flex flex-col gap-3 min-h-0 lg:overflow-y-auto lg:pr-1">
          <GlassPanel hero className="shrink-0 py-4">
            <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim">Discovery</p>
            <h2 className="font-display text-lg font-semibold mt-1">Molecular Discovery Studio</h2>
            <p className="text-xs text-cx-fgMuted mt-1.5">
              Target to candidate — structures, design, and traceable chemistry.
            </p>
          </GlassPanel>

          <GlassPanel className="shrink-0 space-y-3">
            <ChemSessionBar session={sessionSummary} onExport={handleExport} />
            <textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  run();
                }
              }}
              rows={3}
              placeholder="Ask a chemistry question… e.g. Tell me about JAK2"
              disabled={running}
              className="w-full p-3 rounded-xl border border-cx-border bg-white/60 text-sm resize-none focus:outline-none focus:border-cx-accent/40 disabled:opacity-60"
            />
            <button
              type="button"
              onClick={() => run()}
              disabled={running || !query.trim()}
              className="w-full px-4 py-2.5 rounded-xl border border-cx-accent/30 bg-cx-accent/5 text-cx-accent hover:bg-cx-accent/10 disabled:opacity-50 inline-flex items-center justify-center gap-2"
            >
              {running ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
              Run
            </button>
            <div className="flex flex-wrap gap-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  type="button"
                  disabled={running}
                  onClick={() => run(s)}
                  className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-2xs border border-cx-border bg-white/50 hover:border-cx-accent/30 text-cx-fgMuted"
                >
                  <Sparkles size={10} /> {s}
                </button>
              ))}
            </div>
            {error && (
              <div className="p-2 rounded-lg border border-cx-danger/30 bg-cx-danger/5 text-sm text-cx-danger">{error}</div>
            )}
          </GlassPanel>
        </div>

        {/* Results column (large, scrollable) */}
        <div className="min-h-0 overflow-y-auto space-y-4 pb-6 pr-1">
          {running && (
            <GlassPanel className="flex items-center gap-2 text-sm text-cx-fgMuted">
              <Loader2 size={16} className="animate-spin text-cx-accent" /> Running…
            </GlassPanel>
          )}
          {cards.length === 0 && !running && (
            <GlassPanel>
              <p className="text-sm text-cx-fgMuted">
                Start with <strong>Tell me about JAK2</strong> (C1), then walk the scientist journey:
                known inhibitors → design → novelty → motifs → Mol* 3D → synthesis → export.
              </p>
            </GlassPanel>
          )}
          {cards.map((card) => (
            <ChemResultCard key={card.card_id} card={card} />
          ))}
        </div>
      </div>
    </div>
  );
}
