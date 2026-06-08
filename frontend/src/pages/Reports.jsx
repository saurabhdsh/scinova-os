import { useCallback, useEffect, useState } from 'react';
import {
  FileText, Download, Plus, Loader2, Eye, CheckCircle, Send, BookOpen, AlertCircle,
} from 'lucide-react';
import GlassPanel from '../components/ui/GlassPanel';
import {
  getReports, getReport, generateReport, getDocuments,
  updateReportStatus, triggerReportDownload,
} from '../api/client';
import { apiErrorMessage } from '../lib/auth';
import { useProject } from '../context/ProjectContext';

const REPORT_TYPES = [
  { id: 'hypothesis_report', label: 'Hypothesis Report', desc: 'Ranked hypotheses with evidence from literature and your workspace' },
  { id: 'experiment_plan', label: 'Experiment Plan', desc: 'Study design, endpoints, and protocol outline' },
  { id: 'study_report', label: 'Study Report', desc: 'GxP-aware study summary with methods, results, and citations' },
  { id: 'target_discovery', label: 'Target Discovery', desc: 'Target validation narrative from KG and external sources' },
  { id: 'cmc_readiness', label: 'CMC Readiness', desc: 'CMC program readiness assessment' },
];

const TYPE_COLORS = {
  hypothesis_report: 'text-cx-accent',
  study_report: 'text-cx-accent2',
  cmc_readiness: 'text-cx-success',
  experiment_plan: 'text-cx-warn',
  target_discovery: 'text-cx-accent',
};

const STATUS_STYLES = {
  draft: 'text-cx-fgDim border-cx-border',
  under_review: 'text-cx-warn border-cx-warn/25 bg-cx-warn/5',
  approved: 'text-cx-success border-cx-success/25 bg-cx-success/5',
  published: 'text-cx-accent border-cx-accent/25 bg-cx-accent/5',
};

function ReportDetail({ report, onClose, onStatusChange, onRefresh }) {
  const [updating, setUpdating] = useState(false);
  const c = report.content_json || {};

  const setStatus = async (status) => {
    setUpdating(true);
    try {
      await updateReportStatus(report.id, status);
      onStatusChange?.();
      onRefresh?.();
    } catch (err) {
      console.error(err);
    } finally {
      setUpdating(false);
    }
  };

  return (
    <GlassPanel className="lg:sticky lg:top-6 lg:self-start max-h-[calc(100vh-8rem)] overflow-y-auto">
      <div className="flex items-start justify-between gap-3 mb-4">
        <div>
          <p className="text-2xs uppercase tracking-wider text-cx-fgDim">Report detail</p>
          <h3 className="font-display font-semibold text-base mt-1">{report.title}</h3>
          <p className={`text-2xs uppercase mt-1 ${TYPE_COLORS[report.report_type] || 'text-cx-fgDim'}`}>
            {report.report_type?.replace(/_/g, ' ')}
          </p>
        </div>
        <button type="button" onClick={onClose} className="text-xs text-cx-fgMuted hover:text-cx-fg">Close</button>
      </div>

      <div className="flex flex-wrap gap-2 mb-4">
        <span className={`text-2xs uppercase px-2 py-0.5 rounded-md border ${STATUS_STYLES[report.status] || STATUS_STYLES.draft}`}>
          {report.status?.replace(/_/g, ' ')}
        </span>
        {c.confidence != null && (
          <span className="text-2xs px-2 py-0.5 rounded-md border border-cx-border">
            Confidence {(c.confidence * 100).toFixed(0)}%
          </span>
        )}
        {c.mode && (
          <span className="text-2xs px-2 py-0.5 rounded-md border border-cx-accent/20 text-cx-accent">
            {c.mode.replace(/_/g, ' ')}
          </span>
        )}
      </div>

      <div className="flex flex-wrap gap-2 mb-4">
        {['markdown', 'docx', 'pdf'].map((fmt) => (
          <button
            key={fmt}
            type="button"
            onClick={() => triggerReportDownload(report.id, fmt)}
            className="flex items-center gap-1 px-2 py-1 rounded-lg border border-cx-border text-2xs uppercase hover:border-cx-accent/30 hover:text-cx-accent"
          >
            <Download size={12} />
            {fmt === 'markdown' ? 'md' : fmt}
          </button>
        ))}
      </div>

      <div className="flex flex-wrap gap-2 mb-6">
        {report.status === 'draft' && (
          <button
            type="button"
            disabled={updating}
            onClick={() => setStatus('under_review')}
            className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs border border-cx-warn/30 text-cx-warn disabled:opacity-50"
          >
            <Send size={12} /> Submit for review
          </button>
        )}
        {(report.status === 'under_review' || report.status === 'draft') && (
          <button
            type="button"
            disabled={updating}
            onClick={() => setStatus('approved')}
            className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs border border-cx-success/30 text-cx-success disabled:opacity-50"
          >
            <CheckCircle size={12} /> Approve
          </button>
        )}
        {report.status === 'approved' && (
          <button
            type="button"
            disabled={updating}
            onClick={() => setStatus('published')}
            className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs border border-cx-accent/30 text-cx-accent disabled:opacity-50"
          >
            <BookOpen size={12} /> Publish
          </button>
        )}
      </div>

      {c.summary && (
        <div className="mb-4">
          <p className="text-2xs uppercase tracking-wider text-cx-fgDim mb-2">Executive summary</p>
          <p className="text-sm text-cx-fgMuted leading-relaxed">{c.summary}</p>
        </div>
      )}

      {(c.section_content || []).map((sec, i) => (
        sec?.content ? (
          <div key={i} className="mb-4 pb-4 border-b border-cx-line last:border-0">
            <p className="text-2xs uppercase tracking-wider text-cx-fgDim mb-2">{sec.name || `Section ${i + 1}`}</p>
            <div className="text-sm text-cx-fgMuted whitespace-pre-wrap leading-relaxed">{sec.content}</div>
          </div>
        ) : null
      ))}

      {!c.section_content?.length && c.body && (
        <div className="mb-4">
          <p className="text-2xs uppercase tracking-wider text-cx-fgDim mb-2">Full report</p>
          <div className="text-sm text-cx-fgMuted whitespace-pre-wrap leading-relaxed max-h-96 overflow-y-auto">
            {c.body}
          </div>
        </div>
      )}

      {c.hypotheses?.length > 0 && (
        <div className="mb-4">
          <p className="text-2xs uppercase tracking-wider text-cx-fgDim mb-2">Hypotheses</p>
          <div className="space-y-2">
            {c.hypotheses.map((h, i) => (
              <div key={i} className="p-3 rounded-xl border border-cx-border bg-white/40 text-xs">
                <p className="font-medium">{typeof h === 'object' ? h.title || h.hypothesis : h}</p>
                {typeof h === 'object' && h.rationale && (
                  <p className="text-cx-fgMuted mt-1">{h.rationale}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {c.citations_list?.length > 0 && (
        <div className="mb-4">
          <p className="text-2xs uppercase tracking-wider text-cx-fgDim mb-2">
            Evidence & citations ({c.citations_list.length})
          </p>
          <div className="space-y-2 max-h-48 overflow-y-auto">
            {c.citations_list.map((cite, i) => (
              <div key={i} className="p-2 rounded-lg border border-cx-border/60 bg-white/30 text-xs">
                <span className="text-cx-accent font-mono">[{cite.index ?? i + 1}]</span>{' '}
                <span className="font-medium">{cite.title}</span>
                <span className="text-cx-fgDim"> · {cite.source}</span>
                {cite.excerpt && <p className="text-cx-fgMuted mt-1 line-clamp-2">{cite.excerpt}</p>}
              </div>
            ))}
          </div>
        </div>
      )}

      {c.limitations?.length > 0 && (
        <div className="mb-4">
          <p className="text-2xs uppercase tracking-wider text-cx-fgDim mb-2">Limitations</p>
          <ul className="text-xs text-cx-fgMuted list-disc list-inside space-y-1">
            {c.limitations.map((l, i) => <li key={i}>{l}</li>)}
          </ul>
        </div>
      )}

      {c.recommendations?.length > 0 && (
        <div>
          <p className="text-2xs uppercase tracking-wider text-cx-fgDim mb-2">Recommendations</p>
          <ul className="text-xs text-cx-fgMuted list-disc list-inside space-y-1">
            {c.recommendations.map((r, i) => <li key={i}>{r}</li>)}
          </ul>
        </div>
      )}
    </GlassPanel>
  );
}

export default function Reports() {
  const { activeProject } = useProject();
  const [reports, setReports] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [selected, setSelected] = useState(null);
  const [generating, setGenerating] = useState(false);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [reportType, setReportType] = useState('study_report');
  const [title, setTitle] = useState('');
  const [query, setQuery] = useState('');
  const [documentId, setDocumentId] = useState('');
  const [filterType, setFilterType] = useState('');
  const [error, setError] = useState('');

  const loadReports = useCallback(() => {
    setLoading(true);
    const params = { exclude_meeting_briefs: true };
    if (filterType) params.report_type = filterType;
    getReports(params)
      .then((r) => setReports(r.data))
      .catch((err) => setError(apiErrorMessage(err, 'Failed to load reports')))
      .finally(() => setLoading(false));
  }, [filterType]);

  useEffect(() => {
    loadReports();
    getDocuments().then((r) => setDocuments((r.data || []).filter((d) => d.status === 'indexed'))).catch(console.error);
  }, [loadReports]);

  const openReport = async (id) => {
    try {
      const r = await getReport(id);
      setSelected(r.data);
    } catch (err) {
      setError(apiErrorMessage(err, 'Failed to load report'));
    }
  };

  const handleGenerate = async () => {
    if (!query.trim()) return;
    setGenerating(true);
    setError('');
    const typeLabel = REPORT_TYPES.find((t) => t.id === reportType)?.label || 'Report';
    try {
      const r = await generateReport({
        report_type: reportType,
        title: title.trim() || `${typeLabel} — ${new Date().toLocaleDateString()}`,
        source_data: {
          query: query.trim(),
          document_id: documentId || undefined,
          top_k: 10,
        },
      });
      setQuery('');
      setTitle('');
      setDocumentId('');
      setShowForm(false);
      loadReports();
      setSelected(r.data);
    } catch (err) {
      setError(apiErrorMessage(err, 'Report generation failed'));
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="p-6 space-y-6">
      <GlassPanel hero>
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim">Scientific Outputs</p>
            <h2 className="font-display text-xl font-semibold mt-1">Scientific Reports</h2>
            <p className="text-sm text-cx-fgMuted mt-2 max-w-2xl">
              Evidence-grounded reports from your Data Fabric, PubMed, KEGG, ELN, and knowledge graph —
              with GxP traceability, citations, and export to Markdown, Word, or PDF.
              {activeProject && (
                <span className="block mt-1 text-cx-accent">Project: {activeProject.name}</span>
              )}
            </p>
          </div>
          <button
            type="button"
            onClick={() => setShowForm((v) => !v)}
            className="shrink-0 flex items-center gap-2 px-4 py-2 rounded-xl text-sm border border-cx-accent/30 bg-cx-accent/5 text-cx-accent hover:bg-cx-accent/10"
          >
            <Plus size={16} /> Generate Report
          </button>
        </div>

        {showForm && (
          <div className="mt-6 pt-6 border-t border-cx-line space-y-4">
            <div className="grid md:grid-cols-2 gap-4">
              <div>
                <label className="text-2xs uppercase tracking-wider text-cx-fgDim">Report type</label>
                <select
                  value={reportType}
                  onChange={(e) => setReportType(e.target.value)}
                  className="mt-1 w-full text-sm border border-cx-border rounded-xl px-3 py-2 bg-white/60"
                >
                  {REPORT_TYPES.map((t) => (
                    <option key={t.id} value={t.id}>{t.label}</option>
                  ))}
                </select>
                <p className="text-2xs text-cx-fgDim mt-1">
                  {REPORT_TYPES.find((t) => t.id === reportType)?.desc}
                </p>
              </div>
              <div>
                <label className="text-2xs uppercase tracking-wider text-cx-fgDim">Title (optional)</label>
                <input
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="Auto-generated if blank"
                  className="mt-1 w-full text-sm border border-cx-border rounded-xl px-3 py-2 bg-white/60"
                />
              </div>
            </div>
            <div>
              <label className="text-2xs uppercase tracking-wider text-cx-fgDim">Evidence scope</label>
              <select
                value={documentId}
                onChange={(e) => setDocumentId(e.target.value)}
                className="mt-1 w-full text-sm border border-cx-border rounded-xl px-3 py-2 bg-white/60"
              >
                <option value="">All indexed documents + PubMed / KEGG / KG</option>
                {documents.map((d) => (
                  <option key={d.id} value={d.id}>{d.title.slice(0, 60)}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-2xs uppercase tracking-wider text-cx-fgDim">Research question / scope</label>
              <textarea
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="e.g. Generate a GxP study report for JAK1 inhibitor SN-2847 preclinical tox readout including PK, efficacy, and safety findings"
                rows={4}
                className="mt-1 w-full p-3 rounded-xl border border-cx-border bg-white/60 text-sm resize-none focus:outline-none focus:border-cx-accent/40"
              />
            </div>
            {error && (
              <p className="text-sm text-cx-danger flex items-center gap-2">
                <AlertCircle size={14} /> {error}
              </p>
            )}
            <button
              type="button"
              onClick={handleGenerate}
              disabled={generating || !query.trim()}
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm border border-cx-accent/30 bg-cx-accent/5 text-cx-accent hover:bg-cx-accent/10 disabled:opacity-50"
            >
              {generating ? <Loader2 size={16} className="animate-spin" /> : <Plus size={16} />}
              {generating ? 'Gathering evidence & generating…' : 'Generate report'}
            </button>
            {!generating && (
              <p className="text-2xs text-cx-fgDim">
                Pipeline: vector search → PubMed/KEGG → LLM narrative with inline citations. Set OPENAI_API_KEY for full generation.
              </p>
            )}
          </div>
        )}
      </GlassPanel>

      <div className="flex items-center gap-3">
        <select
          value={filterType}
          onChange={(e) => setFilterType(e.target.value)}
          className="text-xs border border-cx-border rounded-xl px-3 py-2 bg-white/60"
        >
          <option value="">All report types</option>
          {REPORT_TYPES.map((t) => (
            <option key={t.id} value={t.id}>{t.label}</option>
          ))}
        </select>
        <span className="text-xs text-cx-fgDim">{reports.length} reports</span>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-16 text-cx-fgMuted">
          <Loader2 className="animate-spin mr-2" size={20} /> Loading reports…
        </div>
      ) : (
        <div className="grid lg:grid-cols-3 gap-6">
          <div className={`space-y-4 ${selected ? 'lg:col-span-2' : 'lg:col-span-3 grid md:grid-cols-2 gap-4'}`}>
            {reports.length === 0 ? (
              <GlassPanel className="md:col-span-2 text-center py-12 text-cx-fgMuted text-sm">
                No reports yet. Upload data in Data Fabric, then generate your first evidence-backed report.
              </GlassPanel>
            ) : reports.map((r) => (
              <GlassPanel key={r.id} className={selected ? '' : ''}>
                <div className="flex items-start gap-3">
                  <div className="p-2.5 rounded-xl bg-cx-deep border border-cx-border">
                    <FileText size={20} className="text-cx-accent" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="font-display font-semibold text-sm">{r.title}</h3>
                    <p className={`text-2xs uppercase tracking-wider mt-1 ${TYPE_COLORS[r.report_type] || 'text-cx-fgDim'}`}>
                      {r.report_type?.replace(/_/g, ' ')}
                    </p>
                    <div className="mt-3 flex flex-wrap gap-3 text-xs text-cx-fgDim">
                      <span>{r.content_json?.word_count?.toLocaleString() || '—'} words</span>
                      <span>{r.content_json?.citations ?? 0} citations</span>
                      {r.content_json?.confidence != null && (
                        <span>{(r.content_json.confidence * 100).toFixed(0)}% conf.</span>
                      )}
                      <span className="text-cx-fgDim">{new Date(r.created_at).toLocaleDateString()}</span>
                    </div>
                    <div className="mt-3 flex flex-wrap items-center gap-2">
                      <span className={`text-2xs uppercase px-2 py-0.5 rounded-md border ${STATUS_STYLES[r.status] || STATUS_STYLES.draft}`}>
                        {r.status?.replace(/_/g, ' ')}
                      </span>
                      <button
                        type="button"
                        onClick={() => openReport(r.id)}
                        className="flex items-center gap-1 text-xs text-cx-accent hover:underline"
                      >
                        <Eye size={12} /> View
                      </button>
                      {['markdown', 'docx', 'pdf'].map((fmt) => (
                        <button
                          key={fmt}
                          type="button"
                          onClick={() => triggerReportDownload(r.id, fmt)}
                          className="flex items-center gap-1 text-xs text-cx-fgMuted hover:text-cx-accent"
                        >
                          <Download size={12} /> {fmt === 'markdown' ? 'md' : fmt}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
                {r.content_json?.summary && !selected && (
                  <p className="mt-4 pt-4 border-t border-cx-line text-xs text-cx-fgMuted line-clamp-3">
                    {r.content_json.summary}
                  </p>
                )}
              </GlassPanel>
            ))}
          </div>

          {selected && (
            <ReportDetail
              report={selected}
              onClose={() => setSelected(null)}
              onRefresh={() => openReport(selected.id)}
              onStatusChange={loadReports}
            />
          )}
        </div>
      )}
    </div>
  );
}
