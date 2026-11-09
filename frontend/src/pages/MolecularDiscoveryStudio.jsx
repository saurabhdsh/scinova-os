import { useCallback, useEffect, useRef, useState } from 'react';
import { ArrowUp } from 'lucide-react';
import ChemResultCard from '../components/chem/ChemResultCard';
import { chemQuery, chemRoute, createChemSession, exportChemSession, getChemSession, setChemSelection } from '../api/client';
import { apiErrorMessage } from '../lib/auth';

const OPENINGS = [
  {
    kicker: 'Metabolic',
    title: 'GLP-1 receptor',
    detail: 'A receptor in metabolic disease. Start with the protein and its structures.',
    query: 'What are the available crystal structures of the glucagon-like peptide 1 receptor in the Protein Data Bank?',
  },
  {
    kicker: 'Oncology',
    title: 'EGFR',
    detail: 'A kinase in solid tumors. Start with the protein and its structures.',
    query: 'What are the available crystal structures of EGFR in the Protein Data Bank?',
  },
  {
    kicker: 'Signaling',
    title: 'BRAF',
    detail: 'A kinase in the MAPK pathway. Start with the protein and its structures.',
    query: 'What are the available crystal structures of BRAF in the Protein Data Bank?',
  },
];

function followUps(stage) {
  if (stage === 'Target Discovery') return ['Looking into it', 'Reading the protein record', 'Staying with this protein'];
  if (stage === 'Lead Identification') return ['Looking into it', 'Reading the chemistry', 'Staying with these molecules'];
  if (stage === 'Lead Optimization') return ['Looking into it', 'Reading the calculated properties'];
  if (stage === 'Preclinical Studies') return ['Looking into it', 'Reading the study question'];
  if (stage === 'Early Development & CMC') return ['Looking into it', 'Reading the development question'];
  return ['Looking into it', 'Reading what we already have'];
}

function statusLines(agents) {
  if (!agents?.length) {
    return [
      { kicker: '', title: 'Looking into it' },
      { kicker: '', title: 'Reading the question' },
    ];
  }
  return agents.flatMap((agent) => [
    { kicker: 'Invoking', title: agent.stage, detail: agent.name },
    ...followUps(agent.stage).map((title) => ({ kicker: '', title })),
  ]);
}

function AgentPulse({ agents }) {
  const lines = statusLines(agents);
  const signature = lines.map((line) => line.title + (line.detail || '')).join('|');
  const [index, setIndex] = useState(0);
  const [leaving, setLeaving] = useState(false);

  useEffect(() => {
    setIndex(0);
    setLeaving(false);
  }, [signature]);

  useEffect(() => {
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduce) return undefined;
    const hold = setTimeout(() => setLeaving(true), 1480);
    return () => clearTimeout(hold);
  }, [index, signature]);

  const line = lines[index % lines.length];
  const spoken = agents?.[0]
    ? `Invoking ${agents[0].name}`
    : 'Looking into it';

  return (
    <div className="py-8" role="status">
      <span className="sr-only">{spoken}</span>
      <div className="studio-agent-stage relative min-h-[8rem]">
        <div
          key={`${signature}-${index}`}
          className={`studio-agent-line ${leaving ? 'is-leaving' : ''}`}
          onAnimationEnd={(event) => {
            if (event.animationName !== 'studio-agent-out') return;
            setIndex((current) => (current + 1) % lines.length);
            setLeaving(false);
          }}
        >
          {line.kicker && <p className="studio-agent-kicker">{line.kicker}</p>}
          <p className="studio-agent-title">{line.title}</p>
          {line.detail && <p className="studio-agent-detail">{line.detail}</p>}
        </div>
      </div>
      <div className="mt-2 flex items-center gap-1.5" aria-hidden="true">
        {[0, 1, 2].map((n) => (
          <span
            key={n}
            className="studio-look-dot h-1.5 w-1.5 rounded-full bg-[#c45c26]"
            style={{ animationDelay: `${n * 0.18}s` }}
          />
        ))}
      </div>
    </div>
  );
}

function threadPrompts(session) {
  const fromServer = session?.next_actions;
  if (fromServer?.length) return fromServer;
  if (!session?.target) return [];
  const gene = session.target.gene_symbol || 'this target';
  const ligand = String(gene).toUpperCase().startsWith('GLP') ? 'agonists' : 'ligands';
  const prompts = [];
  if (!session.actives_count) prompts.push({ label: `Retrieve known ${gene} ${ligand}`, query: `Retrieve known ${gene} ${ligand} from ChEMBL.` });
  if (!session.candidates_count) prompts.push({ label: `Design molecules for ${gene}`, query: `Generate 12 candidates for ${gene}.` });
  if (session.candidates_count) prompts.push({ label: 'Rank the stored candidates', query: 'Which five candidates should we investigate first?' });
  return prompts.slice(0, 3);
}

export default function MolecularDiscoveryStudio() {
  const [query, setQuery] = useState('');
  const [sessionId, setSessionId] = useState(null);
  const [sessionSummary, setSessionSummary] = useState(null);
  const [selected, setSelected] = useState(null);
  const [cards, setCards] = useState([]);
  const [running, setRunning] = useState(false);
  const [liveAgents, setLiveAgents] = useState([]);
  const [pending, setPending] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const scroller = useRef(null);
  const field = useRef(null);

  const thread = [...cards].reverse();
  const contextReady = Boolean(sessionSummary?.target?.gene_symbol || sessionSummary?.last_pdb_id);
  const prompts = threadPrompts(sessionSummary);
  const title = sessionSummary?.target
    ? sessionSummary.target.gene_symbol
    : 'Where should we begin?';

  useEffect(() => {
    const saved = sessionStorage.getItem('mds.session');
    if (!saved) return undefined;
    let cancelled = false;
    getChemSession(saved)
      .then((response) => {
        if (cancelled) return;
        const stored = response.data;
        setSessionId(stored.id);
        setCards([...(stored.cards || [])].reverse());
        setSessionSummary({
          id: stored.id,
          target: stored.target,
          last_pdb_id: stored.last_pdb_id,
          last_smiles: stored.last_smiles,
          structures_count: (stored.structures || []).length,
          actives_count: (stored.actives || []).length,
          candidates_count: (stored.candidates || []).length,
          cards_count: (stored.cards || []).length,
          selection: stored.selection,
        });
        const chosen = (stored.candidates || []).find((row) => row.candidate_id === stored.selection?.molecule_id);
        if (chosen) setSelected(chosen);
      })
      .catch(() => sessionStorage.removeItem('mds.session'));
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    const node = scroller.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [cards, running]);

  const ensureSession = useCallback(async () => {
    if (sessionId) return sessionId;
    const response = await createChemSession();
    setSessionId(response.data.id);
    return response.data.id;
  }, [sessionId]);

  const run = async (text, options = {}) => {
    const question = (text ?? query).trim();
    if (!question || running) return;
    setRunning(true);
    setLiveAgents([]);
    setPending(question);
    setError('');
    setNotice('');
    setQuery('');
    try {
      const sid = await ensureSession();
      try {
        const routed = await chemRoute({ query: question, session_id: sid });
        setLiveAgents(routed.data?.agents || []);
      } catch {
        setLiveAgents([]);
      }
      const response = await chemQuery({
        query: question,
        session_id: sid,
        selected_molecule_id: selected?.candidate_id || null,
      });
      setSessionId(response.data.session_id);
      sessionStorage.setItem('mds.session', response.data.session_id);
      setSessionSummary(response.data.session);
      setCards((prev) => [response.data.card, ...prev]);
    } catch (err) {
      setError(apiErrorMessage(err, 'Chemistry query failed'));
      setQuery(question);
    } finally {
      setRunning(false);
      setLiveAgents([]);
      setPending('');
      field.current?.focus();
    }
  };

  const startOver = () => {
    setSessionId(null);
    setSessionSummary(null);
    setSelected(null);
    setCards([]);
    setQuery('');
    setPending('');
    setError('');
    setNotice('');
    sessionStorage.removeItem('mds.session');
  };

  const handleExport = async (format = 'markdown') => {
    if (!sessionId) return;
    try {
      await exportChemSession(sessionId, format);
    } catch (err) {
      setError(apiErrorMessage(err, 'Export failed'));
    }
  };

  const chooseMolecule = async (molecule) => {
    setSelected(molecule);
    if (!sessionId || !molecule?.candidate_id) return;
    try {
      await setChemSelection(sessionId, {
        molecule_id: molecule.candidate_id,
        pdb_id: sessionSummary?.last_pdb_id || null,
      });
    } catch (err) {
      setError(apiErrorMessage(err, 'Could not remember the selection'));
    }
  };

  return (
    <div className="flex h-full min-h-0 flex-1 flex-col overflow-hidden bg-[#f5f5f7] text-[#1d1d1f]">
      <header className="flex shrink-0 items-center justify-between gap-4 px-6 pb-3 pt-5 md:px-10">
        <div className="min-w-0">
          <p className="text-[11px] uppercase tracking-[0.22em] text-[#8e8e93]">Molecular Discovery</p>
          <h1 className="mt-1 truncate font-display text-[22px] font-semibold tracking-tight">{title}</h1>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {sessionSummary?.last_pdb_id && (
            <span className="hidden rounded-full bg-white px-3 py-1 font-mono text-xs text-[#6e6e73] sm:inline">
              {sessionSummary.last_pdb_id}
            </span>
          )}
          {sessionId && (
            <button
              type="button"
              onClick={() => handleExport('markdown')}
              className="rounded-full px-3 py-1.5 text-xs text-[#6e6e73] hover:bg-black/[0.04]"
            >
              Export
            </button>
          )}
          {sessionId && (
            <button
              type="button"
              onClick={() => handleExport('json')}
              className="rounded-full px-3 py-1.5 text-xs text-[#6e6e73] hover:bg-black/[0.04]"
            >
              JSON
            </button>
          )}
          {sessionId && (
            <button
              type="button"
              onClick={startOver}
              className="rounded-full bg-white px-3 py-1.5 text-xs font-medium text-[#1d1d1f] shadow-sm"
            >
              Start again
            </button>
          )}
        </div>
      </header>

      <div ref={scroller} className="min-h-0 flex-1 overflow-y-auto px-6 md:px-10">
        {thread.length === 0 && !running ? (
          <div className="mx-auto flex min-h-full max-w-2xl flex-col justify-center py-16">
            <p className="text-[15px] leading-6 text-[#6e6e73]">
              Pick a protein to begin. I will stay with it, so the next questions can build on the same work.
            </p>
            <h2 className="mt-3 font-display text-4xl font-semibold tracking-tight text-[#1d1d1f] md:text-5xl">
              Which target protein should we study?
            </h2>
            <div className="mt-10 overflow-hidden rounded-3xl bg-white shadow-[0_1px_2px_rgba(0,0,0,0.04),0_12px_40px_rgba(0,0,0,0.04)]">
              {OPENINGS.map((opening, index) => (
                <button
                  key={opening.title}
                  type="button"
                  disabled={running}
                  onClick={() => run(opening.query, { opening: true })}
                  className={`flex w-full items-baseline gap-4 px-6 py-5 text-left transition hover:bg-[#fafafa] disabled:opacity-50 ${
                    index ? 'border-t border-black/[0.06]' : ''
                  }`}
                >
                  <span className="w-24 shrink-0 text-[11px] uppercase tracking-[0.16em] text-[#8e8e93]">
                    {opening.kicker}
                  </span>
                  <span className="min-w-0">
                    <span className="block font-display text-lg font-semibold tracking-tight">{opening.title}</span>
                    <span className="mt-0.5 block text-sm text-[#6e6e73]">{opening.detail}</span>
                  </span>
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="w-full space-y-10 py-6">
            {thread.map((card) => (
              <article key={card.card_id}>
                <div className="mb-3 flex justify-end">
                  <p className="max-w-md rounded-[22px] bg-white px-4 py-3 text-sm leading-6 text-[#1d1d1f] shadow-sm">
                    {card.query}
                  </p>
                </div>
                <ChemResultCard
                  card={card}
                  selectedId={selected?.candidate_id}
                  onSelectMolecule={chooseMolecule}
                />
              </article>
            ))}
            {running && (
              <div>
                {pending && (
                  <div className="mb-3 flex justify-end">
                    <p className="max-w-md rounded-[22px] bg-white px-4 py-3 text-sm leading-6 text-[#1d1d1f] shadow-sm">
                      {pending}
                    </p>
                  </div>
                )}
                <AgentPulse agents={liveAgents} />
              </div>
            )}
          </div>
        )}
      </div>

      <div className="relative shrink-0 bg-[#f5f5f7] px-6 pb-5 pt-2 md:px-10">
        <div className="pointer-events-none absolute inset-x-0 -top-10 h-10 bg-gradient-to-b from-transparent to-[#f5f5f7]" />
        <div className="mx-auto max-w-3xl">
          {(notice || error) && (
            <p className={`mb-2 text-sm ${error ? 'text-[#9b3a3a]' : 'text-[#6e6e73]'}`}>{error || notice}</p>
          )}
          {prompts.length > 0 && (
            <div className="mb-2 flex flex-wrap gap-2">
              {prompts.map((prompt) => (
                <button
                  key={prompt.query}
                  type="button"
                  disabled={running}
                  onClick={() => run(prompt.query)}
                  title={prompt.requires || undefined}
                  className="rounded-full bg-white px-3 py-1.5 text-xs text-[#6e6e73] shadow-sm hover:text-[#1d1d1f] disabled:opacity-50"
                >
                  {prompt.label}
                  {prompt.requires ? ` (${prompt.requires})` : ''}
                </button>
              ))}
            </div>
          )}
          <form
            className="flex items-end gap-2 rounded-[28px] border border-black/[0.06] bg-white px-3 py-2 shadow-[0_8px_30px_rgba(0,0,0,0.06)]"
            onSubmit={(event) => {
              event.preventDefault();
              run();
            }}
          >
            <textarea
              ref={field}
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                  event.preventDefault();
                  run();
                }
              }}
              rows={1}
              placeholder={contextReady ? 'Ask a follow-up about this protein' : 'Or type another protein, such as KRAS'}
              disabled={running}
              className="max-h-32 min-h-[40px] flex-1 resize-none bg-transparent px-2 py-2 text-sm leading-6 text-[#1d1d1f] placeholder:text-[#8e8e93] focus:outline-none disabled:opacity-60"
            />
            <button
              type="submit"
              disabled={running || !query.trim()}
              aria-label="Send"
              className="mb-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[#1d1d1f] text-white disabled:opacity-30"
            >
              <ArrowUp size={16} />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
