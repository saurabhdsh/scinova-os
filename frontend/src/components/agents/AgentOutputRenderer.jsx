import {
  Beaker, CheckCircle2, FlaskConical, Lightbulb, Sparkles, Target, TrendingUp,
} from 'lucide-react';

const ACCENT_GRADIENTS = [
  'from-cx-accent/15 via-cx-accent/5 to-transparent border-cx-accent/25',
  'from-cx-accent2/15 via-cx-accent2/5 to-transparent border-cx-accent2/25',
  'from-cx-success/15 via-cx-success/5 to-transparent border-cx-success/25',
  'from-violet-500/15 via-violet-500/5 to-transparent border-violet-400/25',
];

const VERDICT_STYLES = {
  supported: 'bg-cx-success/10 text-cx-success border-cx-success/30',
  partially_supported: 'bg-cx-warn/10 text-cx-warn border-cx-warn/30',
  insufficient_evidence: 'bg-cx-fgDim/10 text-cx-fgMuted border-cx-border',
  contradicted: 'bg-cx-danger/10 text-cx-danger border-cx-danger/30',
};

function stripMarkdown(text) {
  if (!text) return '';
  return String(text)
    .replace(/^#{1,6}\s+/gm, '')
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/\*([^*]+)\*/g, '$1')
    .replace(/`([^`]+)`/g, '$1')
    .trim();
}

function renderInline(text) {
  const parts = stripMarkdown(text).split(/(\[[^\]]+\])/g);
  return parts.map((part, i) => {
    if (/^\[[^\]]+\]$/.test(part)) {
      return (
        <span
          key={i}
          className="inline-flex mx-0.5 px-1.5 py-0.5 rounded-md text-2xs font-mono bg-cx-accent/10 text-cx-accent border border-cx-accent/20"
        >
          {part}
        </span>
      );
    }
    return part;
  });
}

function ProseBlock({ text, variant = 'default' }) {
  if (!text) return null;
  const clean = stripMarkdown(text);
  const blocks = clean.split(/\n\n+/);

  const shell = variant === 'hero'
    ? 'rounded-2xl border bg-gradient-to-br from-cx-accent/8 via-white/70 to-cx-accent2/8 border-cx-accent/20 p-5 shadow-inner-soft'
    : 'rounded-xl border border-cx-border/80 bg-white/55 p-4';

  return (
    <div className={shell}>
      {blocks.map((block, i) => {
        const lines = block.split('\n').filter(Boolean);
        const isList = lines.every((l) => l.startsWith('•') || /^\d+\./.test(l.trim()));
        if (isList) {
          return (
            <ul key={i} className={`space-y-2 ${i > 0 ? 'mt-4' : ''}`}>
              {lines.map((line, j) => (
                <li key={j} className="flex gap-2.5 text-sm text-cx-fg leading-relaxed">
                  <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-cx-accent shrink-0" />
                  <span>{renderInline(line.replace(/^•\s*/, '').replace(/^\d+\.\s*/, ''))}</span>
                </li>
              ))}
            </ul>
          );
        }
        return (
          <p key={i} className={`text-sm text-cx-fg leading-relaxed ${i > 0 ? 'mt-3' : ''}`}>
            {renderInline(block.replace(/\n/g, ' '))}
          </p>
        );
      })}
    </div>
  );
}

function SectionLabel({ icon: Icon, children, color = 'text-cx-accent' }) {
  return (
    <p className={`text-2xs uppercase tracking-[0.18em] font-medium mb-3 flex items-center gap-2 ${color}`}>
      {Icon && <Icon size={13} />}
      {children}
    </p>
  );
}

function FindingCards({ items, label = 'Key findings' }) {
  if (!items?.length) return null;
  return (
    <div>
      <SectionLabel icon={Sparkles}>{label}</SectionLabel>
      <div className="grid gap-2 sm:grid-cols-2">
        {items.map((item, i) => (
          <div
            key={i}
            className={`p-3 rounded-xl border bg-gradient-to-br ${ACCENT_GRADIENTS[i % ACCENT_GRADIENTS.length]} text-sm text-cx-fg leading-relaxed`}
          >
            {renderInline(typeof item === 'string' ? item : item.claim || item.takeaway || JSON.stringify(item))}
          </div>
        ))}
      </div>
    </div>
  );
}

function ConfidenceBar({ value }) {
  if (value == null) return null;
  const pct = Math.round(Number(value) * 100);
  return (
    <div className="flex items-center gap-3">
      <div className="flex-1 h-2 rounded-full bg-cx-border/40 overflow-hidden">
        <div
          className="h-full rounded-full bg-gradient-to-r from-cx-accent to-cx-accent2 transition-all"
          style={{ width: `${Math.min(100, pct)}%` }}
        />
      </div>
      <span className="text-xs font-semibold text-cx-accent tabular-nums">{pct}%</span>
    </div>
  );
}

export default function AgentOutputRenderer({ output, compact = false }) {
  if (!output) return null;

  const summary = output.summary || output.executive_summary;
  const answer = output.answer || output.narrative || output.report_body;
  const verdictKey = (output.verdict || '').toLowerCase();

  const hasBody = Boolean(
    summary || answer || output.verdict || output.hypotheses?.length
    || output.key_findings?.length || output.findings?.length
    || output.admet_predictions?.length || output.admet_flags?.length
    || output.recommendations?.length || output.hit_list?.length
    || output.pathways?.length || output.druggable_targets?.length
    || output.gap_analysis?.length || output.recommendation
    || output.validation_score != null || output.compound_count != null,
  );

  if (!hasBody && output.mode === 'mock') {
    return <ProseBlock text={output.findings?.join('\n\n') || 'No structured output returned.'} />;
  }

  if (!hasBody) {
    return (
      <p className="text-sm text-cx-fgMuted p-4 rounded-xl border border-cx-border bg-white/40">
        Run completed but no narrative was returned. Check execution logs and citations below, or retry in Q&A mode.
      </p>
    );
  }

  return (
    <div className={`space-y-5 ${compact ? 'text-sm' : ''}`}>
      {(summary || output.confidence != null) && (
        <div className="rounded-2xl border border-cx-accent/20 bg-gradient-to-r from-cx-accent/5 via-white/60 to-cx-accent2/5 p-4 space-y-3">
          {summary && (
            <p className="text-sm font-medium text-cx-fg leading-relaxed">{renderInline(summary)}</p>
          )}
          {output.confidence != null && (
            <div>
              <p className="text-2xs uppercase tracking-wider text-cx-fgDim mb-1.5">Confidence</p>
              <ConfidenceBar value={output.confidence} />
            </div>
          )}
        </div>
      )}

      {answer && answer !== summary && (
        <div>
          <SectionLabel icon={Lightbulb} color="text-cx-accent2">Analysis</SectionLabel>
          <ProseBlock text={answer} variant="hero" />
        </div>
      )}

      {!answer && !summary && output.mode === 'mock' && (
        <ProseBlock text={output.findings?.join('\n\n')} />
      )}

      {output.verdict && (
        <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full border text-sm font-medium capitalize ${
          VERDICT_STYLES[verdictKey] || 'bg-cx-accent/10 text-cx-accent border-cx-accent/30'
        }`}>
          <CheckCircle2 size={14} />
          {output.verdict.replace(/_/g, ' ')}
        </div>
      )}

      {output.hypotheses?.length > 0 && (
        <div>
          <SectionLabel icon={Target}>Hypotheses</SectionLabel>
          <div className="space-y-3">
            {output.hypotheses.map((h, i) => (
              <div
                key={i}
                className="relative pl-4 pr-4 py-3 rounded-xl border border-cx-border bg-white/50 overflow-hidden"
              >
                <div className={`absolute left-0 top-0 bottom-0 w-1 bg-gradient-to-b ${
                  i % 2 === 0 ? 'from-cx-accent to-cx-accent/40' : 'from-cx-accent2 to-cx-accent2/40'
                }`} />
                <p className="text-sm font-semibold text-cx-fg">{h.title || `Hypothesis ${i + 1}`}</p>
                <p className="text-sm text-cx-fgMuted mt-1 leading-relaxed">{h.statement}</p>
                {h.rationale && (
                  <p className="text-xs text-cx-fgDim mt-2 leading-relaxed">{h.rationale}</p>
                )}
                <div className="flex flex-wrap gap-2 mt-2">
                  {h.evidence_strength && (
                    <span className="text-2xs px-2 py-0.5 rounded-full bg-cx-accent/10 text-cx-accent border border-cx-accent/20 capitalize">
                      {h.evidence_strength} evidence
                    </span>
                  )}
                  {h.confidence != null && (
                    <span className="text-2xs px-2 py-0.5 rounded-full bg-cx-accent2/10 text-cx-accent2 border border-cx-accent2/20">
                      {(h.confidence * 100).toFixed(0)}% confidence
                    </span>
                  )}
                </div>
                {h.suggested_experiments?.length > 0 && (
                  <ul className="mt-2 space-y-1">
                    {h.suggested_experiments.map((exp, j) => (
                      <li key={j} className="text-2xs text-cx-fgMuted flex gap-2">
                        <FlaskConical size={11} className="text-cx-accent shrink-0 mt-0.5" />
                        {exp}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      <FindingCards items={output.key_findings} label="Key findings" />
      <FindingCards items={output.findings} label="Findings" />
      <FindingCards items={output.evidence_for} label="Evidence for" />
      {output.evidence_against?.length > 0 && (
        <FindingCards items={output.evidence_against} label="Evidence against" />
      )}

      {output.experiment_plan && (
        <div className="rounded-xl border border-cx-accent2/25 bg-gradient-to-br from-cx-accent2/8 to-white/50 p-4">
          <SectionLabel icon={FlaskConical} color="text-cx-accent2">Experiment plan</SectionLabel>
          {output.experiment_plan.objective && (
            <p className="text-sm text-cx-fg"><span className="text-cx-fgDim">Objective: </span>{output.experiment_plan.objective}</p>
          )}
          {output.experiment_plan.primary_endpoints?.length > 0 && (
            <ul className="mt-3 space-y-1.5">
              {output.experiment_plan.primary_endpoints.map((e, i) => (
                <li key={i} className="text-sm text-cx-fgMuted flex gap-2">
                  <span className="text-cx-accent2">→</span>{e}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {output.doe_design && (
        <div className="rounded-xl border border-violet-400/25 bg-gradient-to-br from-violet-500/8 to-white/50 p-4 text-sm">
          <SectionLabel icon={TrendingUp} color="text-violet-600">DOE design</SectionLabel>
          <p className="text-cx-fg font-medium">{output.doe_design.design_type}</p>
          <p className="text-cx-fgMuted mt-1">{output.doe_design.runs?.length || 0} experimental runs planned</p>
        </div>
      )}

      {output.section_names?.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {output.section_names.map((s) => (
            <span key={s} className="text-2xs px-2.5 py-1 rounded-lg bg-cx-accent/8 text-cx-accent border border-cx-accent/20 font-medium">
              {s}
            </span>
          ))}
        </div>
      )}

      {output.recommendation && (
        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border text-sm font-medium capitalize bg-cx-accent/10 text-cx-accent border-cx-accent/30">
          Recommendation: {String(output.recommendation).replace(/_/g, ' ')}
        </div>
      )}

      {output.validation_score != null && (
        <div>
          <p className="text-2xs uppercase tracking-wider text-cx-fgDim mb-1.5">Validation score</p>
          <ConfidenceBar value={output.validation_score} />
        </div>
      )}

      {output.druggable_targets?.length > 0 && (
        <FindingCards
          items={output.druggable_targets.map((t) => (
            typeof t === 'object'
              ? `${t.target || t.name || 'Target'} — ${t.rationale || t.mechanism || ''}`.trim()
              : String(t)
          ))}
          label="Druggable targets"
        />
      )}

      {output.pathways?.length > 0 && (
        <FindingCards
          items={output.pathways.map((p) => (
            typeof p === 'object' ? `${p.name || 'Pathway'} — ${p.role || ''}`.trim() : String(p)
          ))}
          label="Pathways"
        />
      )}

      {output.gap_analysis?.length > 0 && (
        <FindingCards items={output.gap_analysis} label="Gap analysis" />
      )}

      {output.evidence_sources && (
        <div className="flex flex-wrap gap-2 text-2xs">
          {[
            ['Docs', output.evidence_sources.vector_chunks],
            ['PubMed', output.evidence_sources.pubmed],
            ['KEGG', output.evidence_sources.kegg],
            ['ELN', output.evidence_sources.eln_records],
          ].filter(([, v]) => v != null && v > 0).map(([label, count]) => (
            <span key={label} className="px-2 py-1 rounded-lg bg-white/60 border border-cx-border text-cx-fgMuted">
              {count} {label}
            </span>
          ))}
        </div>
      )}

      {output.admet_predictions?.length > 0 && (
        <div>
          <SectionLabel icon={Beaker}>ADMET predictions</SectionLabel>
          <div className="overflow-x-auto rounded-xl border border-cx-border">
            <table className="w-full text-xs">
              <thead className="bg-gradient-to-r from-cx-accent/10 to-cx-accent2/10">
                <tr>
                  {['Compound', 'MW', 'LogP', 'TPSA', 'QED', 'Lipinski'].map((h) => (
                    <th key={h} className="text-left p-2.5 font-medium text-cx-fgDim">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {output.admet_predictions.slice(0, 15).map((row, i) => (
                  <tr key={i} className={`border-t border-cx-border/60 ${i % 2 === 0 ? 'bg-white/40' : 'bg-white/20'}`}>
                    <td className="p-2.5 font-mono text-cx-accent">{row.compound_id}</td>
                    <td className="p-2.5">{row.molecular_weight}</td>
                    <td className="p-2.5">{row.logp}</td>
                    <td className="p-2.5">{row.tpsa}</td>
                    <td className="p-2.5 font-medium">{row.qed}</td>
                    <td className="p-2.5">
                      <span className={`px-1.5 py-0.5 rounded ${row.lipinski_pass ? 'bg-cx-success/15 text-cx-success' : 'bg-cx-danger/15 text-cx-danger'}`}>
                        {row.lipinski_pass ? 'Pass' : 'Fail'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {(output.docking?.shape_hits?.length > 0 || output.hit_list?.length > 0) && (
        <div>
          <SectionLabel icon={Beaker}>Screening hits</SectionLabel>
          <div className="space-y-2">
            {(output.docking?.shape_hits || output.hit_list || []).slice(0, 10).map((h, i) => (
              <div
                key={i}
                className="flex items-center gap-3 p-3 rounded-xl border border-cx-border bg-gradient-to-r from-white/60 to-cx-accent/5 text-xs"
              >
                <span className="w-7 h-7 rounded-lg bg-cx-accent/15 text-cx-accent font-semibold flex items-center justify-center shrink-0">
                  {h.rank || i + 1}
                </span>
                <div className="min-w-0 flex-1 font-mono text-cx-fg truncate">
                  {h.compound_id}
                  {h.smiles && <span className="text-cx-fgDim ml-2">{h.smiles.slice(0, 36)}</span>}
                </div>
                <span className="text-cx-accent2 font-medium shrink-0">
                  QED {h.qed ?? h.shape_similarity ?? h.screening_score ?? '—'}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {output.connections?.length > 0 && (
        <FindingCards
          items={output.connections.map((c) => `${c.entity_a} → ${c.relationship} → ${c.entity_b}`)}
          label="Knowledge connections"
        />
      )}

      {output.evidence_items?.length > 0 && (
        <div>
          <SectionLabel icon={Sparkles}>Evidence items</SectionLabel>
          <div className="space-y-2">
            {output.evidence_items.map((item, i) => (
              <div key={i} className="p-3 rounded-xl border border-cx-border bg-white/50 text-sm">
                <div className="flex items-start justify-between gap-2">
                  <p className="text-cx-fg font-medium">{item.claim}</p>
                  {item.strength && (
                    <span className="text-2xs px-2 py-0.5 rounded-full bg-cx-accent/10 text-cx-accent capitalize shrink-0">
                      {item.strength}
                    </span>
                  )}
                </div>
                {item.supporting_excerpt && (
                  <p className="text-xs text-cx-fgMuted mt-2 leading-relaxed">{item.supporting_excerpt}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export function AgentProseRenderer({ text, compact = false }) {
  if (!text) return null;
  return (
    <div className={compact ? '' : 'space-y-3'}>
      <ProseBlock text={text} variant={compact ? 'default' : 'hero'} />
    </div>
  );
}

export function isAgentStructuredOutput(output) {
  if (!output) return false;
  if (output.mode) return true;
  return Boolean(
    output.answer || output.summary || output.hypotheses?.length
    || output.findings?.length || output.key_findings?.length,
  );
}
