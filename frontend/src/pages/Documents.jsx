import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, ChevronLeft, ChevronRight, FileText, Search } from 'lucide-react';
import GlassPanel from '../components/ui/GlassPanel';
import { getDocuments } from '../api/client';

const PAGE_SIZE = 15;

function decodeTitle(title) {
  if (!title) return '';
  const el = document.createElement('textarea');
  el.innerHTML = title;
  return el.value;
}

function formatDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

const STATUS_STYLES = {
  indexed: 'text-cx-success bg-cx-success/5 border-cx-success/20',
  processing: 'text-cx-accent bg-cx-accent/5 border-cx-accent/20',
  failed: 'text-cx-danger bg-cx-danger/5 border-cx-danger/20',
};

export default function Documents() {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [formatFilter, setFormatFilter] = useState('');
  const [page, setPage] = useState(1);

  useEffect(() => {
    getDocuments({ limit: 100 })
      .then((r) => setDocuments(r.data))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const formats = useMemo(
    () => [...new Set(documents.map((d) => d.file_format).filter(Boolean))].sort(),
    [documents],
  );

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return documents.filter((d) => {
      if (statusFilter && d.status !== statusFilter) return false;
      if (formatFilter && d.file_format !== formatFilter) return false;
      if (!q) return true;
      const title = decodeTitle(d.title).toLowerCase();
      const filename = (d.metadata_json?.original_filename || '').toLowerCase();
      return title.includes(q) || filename.includes(q) || d.source_type?.toLowerCase().includes(q);
    });
  }, [documents, search, statusFilter, formatFilter]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const currentPage = Math.min(page, totalPages);
  const pageItems = filtered.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);

  useEffect(() => {
    setPage(1);
  }, [search, statusFilter, formatFilter]);

  return (
    <div className="p-6 space-y-6">
      <GlassPanel hero>
        <Link
          to="/data-fabric"
          className="inline-flex items-center gap-1.5 text-xs text-cx-fgMuted hover:text-cx-accent transition-colors mb-3"
        >
          <ArrowLeft size={14} />
          Back to Scientific Data Fabric
        </Link>
        <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim">Document Library</p>
        <h2 className="font-display text-xl font-semibold mt-1">Indexed Documents</h2>
        <p className="text-sm text-cx-fgMuted mt-2">
          Browse, search, and filter all ingested scientific documents across connectors and uploads.
        </p>
        {!loading && (
          <p className="text-xs text-cx-fgDim mt-3">
            {filtered.length} of {documents.length} documents
            {(search || statusFilter || formatFilter) && ' matching filters'}
          </p>
        )}
      </GlassPanel>

      <GlassPanel>
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative flex-1 min-w-[220px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-cx-accent" size={16} />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search title, filename, or source..."
              className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-cx-border bg-white/60 text-sm"
            />
          </div>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="text-xs border border-cx-border rounded-xl px-3 py-2.5 bg-white/60"
          >
            <option value="">All statuses</option>
            <option value="indexed">Indexed</option>
            <option value="processing">Processing</option>
            <option value="failed">Failed</option>
          </select>
          <select
            value={formatFilter}
            onChange={(e) => setFormatFilter(e.target.value)}
            className="text-xs border border-cx-border rounded-xl px-3 py-2.5 bg-white/60"
          >
            <option value="">All formats</option>
            {formats.map((f) => (
              <option key={f} value={f}>{f}</option>
            ))}
          </select>
        </div>
      </GlassPanel>

      <GlassPanel className="p-0 overflow-hidden">
        {loading ? (
          <p className="p-8 text-sm text-cx-fgDim text-center">Loading documents...</p>
        ) : pageItems.length === 0 ? (
          <p className="p-8 text-sm text-cx-fgDim text-center">No documents match your filters.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-cx-border bg-white/40 text-2xs uppercase tracking-wider text-cx-fgDim">
                  <th className="text-left font-medium px-4 py-3">Document</th>
                  <th className="text-left font-medium px-4 py-3 w-28">Format</th>
                  <th className="text-left font-medium px-4 py-3 w-36">Source</th>
                  <th className="text-left font-medium px-4 py-3 w-24">Chunks</th>
                  <th className="text-left font-medium px-4 py-3 w-28">Uploaded</th>
                  <th className="text-left font-medium px-4 py-3 w-24">Status</th>
                </tr>
              </thead>
              <tbody>
                {pageItems.map((d) => (
                  <tr key={d.id} className="border-b border-cx-border/60 hover:bg-white/30 transition-colors">
                    <td className="px-4 py-3 align-top">
                      <div className="flex items-start gap-2.5 min-w-[280px]">
                        <FileText size={16} className="text-cx-accent shrink-0 mt-0.5" />
                        <div className="min-w-0">
                          <p className="font-medium leading-snug break-words">{decodeTitle(d.title)}</p>
                          {d.metadata_json?.original_filename && (
                            <p className="text-2xs font-mono text-cx-fgDim mt-1 truncate max-w-md">
                              {d.metadata_json.original_filename}
                            </p>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3 align-top text-xs text-cx-fgMuted">{d.file_format || '—'}</td>
                    <td className="px-4 py-3 align-top text-xs text-cx-fgMuted">{d.source_type?.replace(/_/g, ' ') || '—'}</td>
                    <td className="px-4 py-3 align-top text-xs font-mono text-cx-fgMuted">
                      {d.metadata_json?.chunk_count ?? '—'}
                    </td>
                    <td className="px-4 py-3 align-top text-xs text-cx-fgMuted whitespace-nowrap">
                      {formatDate(d.created_at)}
                    </td>
                    <td className="px-4 py-3 align-top">
                      <span className={`text-2xs uppercase px-2 py-0.5 rounded border ${STATUS_STYLES[d.status] || 'text-cx-fgDim border-cx-border'}`}>
                        {d.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {!loading && filtered.length > PAGE_SIZE && (
          <div className="flex items-center justify-between gap-3 px-4 py-3 border-t border-cx-border bg-white/30">
            <p className="text-xs text-cx-fgDim">
              Page {currentPage} of {totalPages}
            </p>
            <div className="flex items-center gap-2">
              <button
                type="button"
                disabled={currentPage <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs border border-cx-border disabled:opacity-40 hover:border-cx-accent/30"
              >
                <ChevronLeft size={14} />
                Previous
              </button>
              <button
                type="button"
                disabled={currentPage >= totalPages}
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs border border-cx-border disabled:opacity-40 hover:border-cx-accent/30"
              >
                Next
                <ChevronRight size={14} />
              </button>
            </div>
          </div>
        )}
      </GlassPanel>
    </div>
  );
}
