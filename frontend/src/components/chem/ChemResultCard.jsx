import { useState } from 'react';
import { ChevronDown, ChevronRight, Beaker, Wrench } from 'lucide-react';
import GlassPanel from '../ui/GlassPanel';
import MolStarViewer from './MolStarViewer';
import SmilesDepict from './SmilesDepict';

function TracePanel({ trace }) {
  const [open, setOpen] = useState(false);
  if (!trace) return null;
  return (
    <div className="mt-4 border-t border-cx-border pt-3">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 text-2xs uppercase tracking-wider text-cx-fgDim hover:text-cx-accent"
      >
        {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        <Wrench size={12} /> Reasoning Trace · {trace.specialist}
      </button>
      {open && (
        <div className="mt-2 space-y-2 text-xs text-cx-fgMuted">
          <p><span className="text-cx-fgDim">Run ID:</span> <span className="font-mono">{trace.run_id}</span></p>
          <p><span className="text-cx-fgDim">Tools:</span> {(trace.tools || []).join(', ') || '—'}</p>
          {trace.parameters && (
            <pre className="text-2xs bg-white/50 border border-cx-border rounded-lg p-2 overflow-x-auto">
              {JSON.stringify(trace.parameters, null, 2)}
            </pre>
          )}
          {(trace.observations || []).length > 0 && (
            <ul className="list-disc pl-4 space-y-0.5">
              {trace.observations.map((o, i) => <li key={i}>{o}</li>)}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

function StructuresTable({ structures, activePdbId, onSelect }) {
  if (!structures?.length) return null;
  const showRes = structures.some((s) => s.resolution != null);
  return (
    <div className="mt-3 overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="text-left text-cx-fgDim border-b border-cx-border">
            <th className="py-1.5 pr-2">#</th>
            <th className="py-1.5 pr-2">PDB ID</th>
            {showRes && <th className="py-1.5 pr-2">Resolution (Å)</th>}
            <th className="py-1.5 pr-2">Method</th>
            <th className="py-1.5">Title</th>
          </tr>
        </thead>
        <tbody>
          {structures.map((s, i) => (
            <tr key={s.pdb_id} className="border-b border-cx-border/60">
              <td className="py-1.5 pr-2 text-cx-fgDim">{i}</td>
              <td className="py-1.5 pr-2">
                <button
                  type="button"
                  onClick={() => onSelect?.(s.pdb_id)}
                  className={`font-mono ${
                    activePdbId === s.pdb_id ? 'text-cx-accent font-semibold' : 'text-cx-accent hover:underline'
                  }`}
                >
                  {s.pdb_id}
                </button>
              </td>
              {showRes && (
                <td className="py-1.5 pr-2">
                  {s.resolution != null ? Number(s.resolution).toFixed(2) : '—'}
                </td>
              )}
              <td className="py-1.5 pr-2 text-cx-fgMuted">{s.method || '—'}</td>
              <td className="py-1.5 text-cx-fgMuted max-w-[280px] truncate" title={s.title}>
                {s.title || '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function LigandsTable({ ligands }) {
  if (!ligands?.length) return null;
  return (
    <div className="mt-3 overflow-x-auto">
      <p className="text-2xs uppercase text-cx-fgDim mb-1">Ligands in binding site</p>
      <table className="w-full text-xs">
        <thead>
          <tr className="text-left text-cx-fgDim border-b border-cx-border">
            <th className="py-1.5 pr-2">#</th>
            <th className="py-1.5 pr-2">Ligand ID</th>
            <th className="py-1.5">Chemical name</th>
          </tr>
        </thead>
        <tbody>
          {ligands.map((lg, i) => (
            <tr key={`${lg.comp_id}-${i}`} className="border-b border-cx-border/60">
              <td className="py-1.5 pr-2 text-cx-fgDim">{i}</td>
              <td className="py-1.5 pr-2 font-mono font-semibold">{lg.comp_id}</td>
              <td className="py-1.5 text-cx-fgMuted break-words">{lg.name}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ActivesTable({ actives }) {
  if (!actives?.length) return null;
  return (
    <div className="mt-3 overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="text-left text-cx-fgDim border-b border-cx-border">
            <th className="py-1.5 pr-2">#</th>
            <th className="py-1.5 pr-2">ChEMBL</th>
            <th className="py-1.5 pr-2">Name</th>
            <th className="py-1.5 pr-2">pChEMBL</th>
            <th className="py-1.5 pr-2">Assay</th>
            <th className="py-1.5">SMILES</th>
          </tr>
        </thead>
        <tbody>
          {actives.slice(0, 15).map((a) => (
            <tr key={a.chembl_id || a.rank} className="border-b border-cx-border/60">
              <td className="py-1.5 pr-2">{a.rank}</td>
              <td className="py-1.5 pr-2 font-mono text-cx-accent">{a.chembl_id}</td>
              <td className="py-1.5 pr-2">{a.pref_name}</td>
              <td className="py-1.5 pr-2">{a.pchembl ?? '—'}</td>
              <td className="py-1.5 pr-2 max-w-[140px] truncate" title={a.assay}>{a.assay}</td>
              <td className="py-1.5 font-mono max-w-[180px] truncate" title={a.smiles}>{a.smiles}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const VERDICT_TONE = {
  'drug-like analog': 'text-emerald-400',
  'close analog': 'text-amber-400',
  'very close analog': 'text-amber-400',
  'duplicate of known drug': 'text-rose-400',
};

function CandidatesTable({ candidates }) {
  if (!candidates?.length) return null;
  const showDock = candidates.some((c) => c.docking_score != null);
  const showRank = showDock || candidates.some((c) => c.rank != null);
  const showDrug = candidates.some((c) => c.drug_similarity != null);
  const showScaffold = candidates.some((c) => c.scaffold_parent);
  return (
    <div className="mt-3 overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="text-left text-cx-fgDim border-b border-cx-border">
            {showRank && <th className="py-1.5 pr-2">Rank</th>}
            <th className="py-1.5 pr-2">ID</th>
            {showDock && <th className="py-1.5 pr-2">Docking score</th>}
            <th className="py-1.5 pr-2">MW</th>
            <th className="py-1.5 pr-2">cLogP</th>
            <th className="py-1.5 pr-2">QED</th>
            {showScaffold && <th className="py-1.5 pr-2">Built on</th>}
            {showDrug && <th className="py-1.5 pr-2">Closest drug</th>}
            {showDrug && <th className="py-1.5 pr-2">Similarity</th>}
            {showDrug && <th className="py-1.5 pr-2">Verdict</th>}
            <th className="py-1.5">SMILES</th>
          </tr>
        </thead>
        <tbody>
          {candidates.map((c) => (
            <tr key={c.candidate_id} className="border-b border-cx-border/60">
              {showRank && <td className="py-1.5 pr-2">{c.rank ?? '—'}</td>}
              <td className="py-1.5 pr-2 font-medium">{c.candidate_id}</td>
              {showDock && (
                <td className="py-1.5 pr-2 font-mono text-cx-accent">{c.docking_score}</td>
              )}
              <td className="py-1.5 pr-2">{c.mw}</td>
              <td className="py-1.5 pr-2">{c.clogp}</td>
              <td className="py-1.5 pr-2">{c.qed}</td>
              {showScaffold && (
                <td className="py-1.5 pr-2 text-cx-fgMuted" title={c.neural_fragment ? `Neural R-group: ${c.neural_fragment}` : ''}>
                  {c.scaffold_parent || '—'}
                </td>
              )}
              {showDrug && (
                <td className="py-1.5 pr-2" title={c.closest_drug_smiles || ''}>
                  {c.closest_drug || '—'}
                </td>
              )}
              {showDrug && (
                <td className="py-1.5 pr-2 font-mono">{c.drug_similarity ?? '—'}</td>
              )}
              {showDrug && (
                <td className={`py-1.5 pr-2 ${VERDICT_TONE[c.drug_likeness_verdict] || 'text-cx-fgMuted'}`}>
                  {c.drug_likeness_verdict || '—'}
                </td>
              )}
              <td className="py-1.5 font-mono max-w-[200px] truncate" title={c.smiles}>{c.smiles}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function DrugBenchmark({ benchmark }) {
  if (!benchmark?.available) return null;
  const [lo, hi] = benchmark.analog_window || [];
  return (
    <div className="mt-3 rounded-lg border border-cx-border bg-cx-surface/60 p-2.5 space-y-1 text-xs">
      <p className="text-2xs uppercase text-cx-fgDim">Match against existing drugs</p>
      <p className="text-cx-fgMuted">
        Compared with <strong>{benchmark.reference_drug_count}</strong> approved / clinical drugs using{' '}
        {benchmark.fingerprint}.
      </p>
      <p className="text-cx-fgMuted">
        Mean similarity <strong>{benchmark.mean_drug_similarity ?? '—'}</strong> · max{' '}
        <strong>{benchmark.max_drug_similarity ?? '—'}</strong> ·{' '}
        <strong>{benchmark.in_analog_window}</strong> inside the drug-like analog window{' '}
        {lo != null ? `${lo}–${hi}` : ''}
      </p>
      <p className="text-cx-fgDim">
        {benchmark.duplicates_removed
          ? `${benchmark.duplicates_removed} exact duplicate(s) of known drugs were removed.`
          : 'No generated molecule duplicated a known drug.'}
      </p>
    </div>
  );
}

function NoveltyTable({ novelty }) {
  if (!novelty?.length) return null;
  return (
    <div className="mt-3 overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="text-left text-cx-fgDim border-b border-cx-border">
            <th className="py-1.5 pr-2">Candidate</th>
            <th className="py-1.5 pr-2">Tanimoto</th>
            <th className="py-1.5 pr-2">Label</th>
            <th className="py-1.5">Closest analog</th>
          </tr>
        </thead>
        <tbody>
          {novelty.map((n) => (
            <tr key={n.candidate_id} className="border-b border-cx-border/60">
              <td className="py-1.5 pr-2">{n.candidate_id}</td>
              <td className="py-1.5 pr-2">{n.max_tanimoto}</td>
              <td className="py-1.5 pr-2">{n.novelty_label}</td>
              <td className="py-1.5 font-mono max-w-[200px] truncate" title={n.closest_analog_smiles}>
                {n.closest_analog_smiles || '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function ChemResultCard({ card }) {
  const payload = card?.payload || {};
  const viz = card?.visualization || payload.visualization;
  const defaultPdbId = viz?.pdb_id || payload.default_pdb_id || payload.pdb_id || payload.dossier?.pdb_id;
  const [activePdbId, setActivePdbId] = useState(null);
  const pdbId = activePdbId || defaultPdbId;
  const narrative = card?.narrative || payload.narrative;
  const smiles =
    viz?.smiles
    || payload.actives?.[0]?.smiles
    || payload.candidates?.[0]?.smiles
    || payload.route?.smiles;
  const dossier = payload.dossier;
  const ligands = payload.ligands || dossier?.ligands;
  const pockets = payload.pockets;
  const method = payload.method;

  return (
    <GlassPanel className="space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim flex items-center gap-1.5">
            <Beaker size={11} /> {card.capability} · {payload.capability_name || card.intent}
          </p>
          <h3 className="font-display font-semibold text-sm mt-1 break-words">{card.summary}</h3>
          {narrative && narrative !== card.summary && (
            <p className="text-xs text-cx-fgMuted mt-1 break-words">{narrative}</p>
          )}
          <p className="text-2xs text-cx-fgDim mt-2 italic break-words">“{card.query}”</p>
        </div>
      </div>

      {payload.target && (
        <div className="grid sm:grid-cols-2 gap-2 text-xs">
          <div className="p-3 rounded-xl border border-cx-border bg-white/40">
            <p className="text-2xs text-cx-fgDim uppercase">Profile</p>
            <p className="font-medium mt-1">{payload.target.name}</p>
            <p className="text-cx-fgMuted mt-1">UniProt {payload.target.uniprot_id}</p>
            <p className="text-cx-fgMuted">{payload.target.organism}</p>
            {payload.structure_count != null && (
              <p className="text-cx-fgMuted mt-1">
                {payload.structure_count} filtered structures
                {payload.structure_filters?.max_resolution_A
                  ? ` (≤ ${payload.structure_filters.max_resolution_A} Å)`
                  : ''}
              </p>
            )}
          </div>
          <div className="p-3 rounded-xl border border-cx-border bg-white/40">
            <p className="text-2xs text-cx-fgDim uppercase">Quick pick</p>
            <div className="mt-1 flex flex-wrap gap-1">
              {(payload.structures || []).slice(0, 10).map((s) => (
                <button
                  key={s.pdb_id}
                  type="button"
                  onClick={() => setActivePdbId(s.pdb_id)}
                  title={`Render ${s.pdb_id} in 3D`}
                  className={`px-1.5 py-0.5 rounded-md border font-mono text-2xs transition-colors ${
                    pdbId === s.pdb_id
                      ? 'border-cx-accent/60 text-cx-accent bg-cx-accent/10'
                      : 'border-cx-border hover:border-cx-accent/40 hover:text-cx-accent'
                  }`}
                >
                  {s.pdb_id}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      <StructuresTable
        structures={payload.structures}
        activePdbId={pdbId}
        onSelect={setActivePdbId}
      />

      {dossier && (
        <div className="p-3 rounded-xl border border-cx-border bg-white/40 text-xs space-y-1">
          <p className="text-2xs uppercase text-cx-fgDim">Structure overview</p>
          <p className="font-medium">{dossier.title}</p>
          <p className="text-cx-fgMuted">
            Resolution: <strong>{dossier.resolution != null ? `${dossier.resolution} Å` : 'n/a'}</strong>
            {' · '}
            Method: <strong>{dossier.method || 'n/a'}</strong>
          </p>
        </div>
      )}

      <LigandsTable ligands={ligands} />

      {pockets?.length > 0 && (
        <div className="space-y-2">
          <div className="p-3 rounded-xl border border-cx-border bg-white/40 text-xs">
            <p className="text-2xs uppercase text-cx-fgDim mb-2">Top binding pocket</p>
            {(payload.top_pocket || pockets[0]) && (
              <>
                <p>
                  Pocket <strong>{(payload.top_pocket || pockets[0]).pocket_id}</strong>
                  {' · '}druggability{' '}
                  <strong className="text-cx-accent">
                    {(payload.top_pocket || pockets[0]).druggability_score}
                  </strong>
                </p>
                <p className="text-cx-fgMuted mt-1">{(payload.top_pocket || pockets[0]).note}</p>
              </>
            )}
            <table className="w-full text-xs mt-2">
              <thead>
                <tr className="text-left text-cx-fgDim border-b border-cx-border">
                  <th className="py-1 pr-2">Pocket</th>
                  <th className="py-1 pr-2">Score</th>
                  <th className="py-1">Label</th>
                </tr>
              </thead>
              <tbody>
                {pockets.map((p) => (
                  <tr key={p.pocket_id} className="border-b border-cx-border/60">
                    <td className="py-1 pr-2 font-mono">{p.pocket_id}</td>
                    <td className="py-1 pr-2 font-semibold text-cx-accent">{p.druggability_score}</td>
                    <td className="py-1 text-cx-fgMuted">{p.label}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {payload.method_note && (
            <p className="text-2xs text-cx-fgDim italic">{payload.method_note}</p>
          )}
        </div>
      )}

      {method?.steps?.length > 0 && (
        <div className="p-3 rounded-xl border border-cx-border bg-white/40 text-xs space-y-2">
          <p className="text-2xs uppercase text-cx-fgDim">Design methodology · {method.name}</p>
          <p className="text-cx-fgMuted">{method.framework}</p>
          {method.model && (
            <p className="text-cx-fgMuted">
              Model: <strong>{method.model.name}</strong>
              {method.model.architecture ? ` · ${method.model.architecture}` : ''}
              {method.model.n_train_smiles != null ? ` · trained on ${method.model.n_train_smiles} SMILES` : ''}
              {method.model.epochs != null ? ` · ${method.model.epochs} epochs` : ''}
            </p>
          )}
          <ol className="list-decimal pl-4 space-y-1.5">
            {method.steps.map((s) => (
              <li key={s.step}>
                <strong>{s.name}.</strong> {s.detail}
              </li>
            ))}
          </ol>
          {method.rationale && <p className="text-cx-fgMuted italic">{method.rationale}</p>}
        </div>
      )}

      {payload.neural_count != null && (
        <p className="text-2xs text-cx-fgDim">
          Neural samples kept: {payload.neural_count} / {(payload.candidates || []).length} shown
          {payload.analog_count
            ? ` · ${payload.analog_count} are drug-scaffold analogs (RNN-A…), the rest free samples (RNN-…)`
            : ' · IDs like RNN-01 are model-sampled'}
        </p>
      )}

      <ActivesTable actives={payload.actives} />
      <CandidatesTable candidates={payload.candidates} />
      <DrugBenchmark benchmark={payload.drug_benchmark} />
      <NoveltyTable novelty={payload.novelty} />

      {payload.motif_matrix && (
        <div className="mt-2 text-xs">
          <p className="text-2xs uppercase text-cx-fgDim mb-2">Motif matrix</p>
          <div className="space-y-1">
            {payload.motif_matrix.slice(0, 8).map((row) => (
              <div key={row.candidate_id} className="flex gap-2 flex-wrap items-center">
                <span className="font-medium w-24 shrink-0">{row.candidate_id}</span>
                {(row.motif_names || []).map((n) => (
                  <span key={n} className="px-1.5 py-0.5 rounded-md bg-cx-accent/8 border border-cx-accent/20 text-2xs">
                    {n}
                  </span>
                ))}
              </div>
            ))}
          </div>
        </div>
      )}

      {payload.route && (
        <div className="p-3 rounded-xl border border-cx-border bg-white/40 text-xs space-y-1">
          <p className="text-2xs uppercase text-cx-fgDim">Synthetic route</p>
          <p>Status: <strong>{payload.route.status}</strong> · confidence {payload.route.confidence} · ~{payload.route.steps_estimate} steps</p>
          {(payload.route.tree?.children || []).map((step) => (
            <p key={step.id} className="text-cx-fgMuted">• {step.reaction}</p>
          ))}
        </div>
      )}

      {payload.docking?.hits?.length > 0 && (
        <div className="p-3 rounded-xl border border-cx-border bg-white/40 text-xs">
          <p className="text-2xs uppercase text-cx-fgDim mb-1">Shape / pose analogs</p>
          <p className="text-cx-fgMuted mb-2">{payload.docking.note}</p>
          <ul className="space-y-1">
            {payload.docking.hits.map((h) => (
              <li key={`${h.compound_id}-${h.rank}`}>
                #{h.rank} {h.compound_id} · shape {h.shape_similarity}
              </li>
            ))}
          </ul>
        </div>
      )}

      {payload.export && (
        <pre className="text-2xs bg-white/50 border border-cx-border rounded-lg p-3 overflow-x-auto max-h-48">
          {JSON.stringify(payload.export, null, 2)}
        </pre>
      )}

      <div className="grid lg:grid-cols-2 gap-3 mt-2">
        {smiles && (
          <SmilesDepict
            smiles={smiles}
            label={payload.actives?.[0]?.pref_name || payload.candidates?.[0]?.candidate_id}
          />
        )}
        {pdbId && (
          <MolStarViewer
            key={pdbId}
            pdbId={pdbId}
            structureUrl={pdbId === viz?.pdb_id ? viz?.file_url : null}
            height={420}
            label={pdbId}
          />
        )}
      </div>

      <TracePanel trace={card.trace} />
    </GlassPanel>
  );
}
