import { useEffect, useState, useRef, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
  Upload, CheckCircle, Circle, Loader2, Database, Link2, FileSearch, Search, AlertCircle, ArrowRight,
} from 'lucide-react';
import GlassPanel from '../components/ui/GlassPanel';
import {
  getDocuments, getDataSources, getEntities, uploadDocument,
  getIngestionStatus, getIngestionStages, getFabricStats, fabricSearch,
  getAccountQuotas, getDocumentQC, getLimsPlates, syncLimsPlate,
  retryIngestion,
} from '../api/client';
import { useProject } from '../context/ProjectContext';
import { apiErrorMessage } from '../lib/auth';

const STAGE_LABELS = {
  upload: 'Upload',
  metadata_extract: 'Metadata',
  text_extract: 'Text Extract',
  qc_check: 'Assay QC',
  chunk: 'Chunk',
  embed: 'Embed',
  vector_index: 'Vector Index',
  entity_extract: 'Entity Extract',
  relationship_extract: 'Relationship',
  ontology_map: 'Ontology Map',
  graph_update: 'Graph Update',
  neo4j_sync: 'Neo4j Sync',
  complete: 'Complete',
};

const RECENT_DOC_LIMIT = 8;

export default function DataFabric() {
  const { activeProject } = useProject();
  const [documents, setDocuments] = useState([]);
  const [sources, setSources] = useState([]);
  const [entities, setEntities] = useState([]);
  const [stats, setStats] = useState(null);
  const [stages, setStages] = useState([]);
  const [activeJob, setActiveJob] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [quotas, setQuotas] = useState(null);
  const [uploadError, setUploadError] = useState('');
  const [qcReport, setQcReport] = useState(null);
  const [lims, setLims] = useState(null);
  const [limsSyncing, setLimsSyncing] = useState(null);
  const [limsFeedback, setLimsFeedback] = useState(null);
  const [retryingJob, setRetryingJob] = useState(false);
  const [pipelineStuck, setPipelineStuck] = useState(false);
  const fileRef = useRef();
  const pollRef = useRef(null);
  const pipelineRef = useRef(null);
  const stuckPollsRef = useRef(0);

  const load = useCallback(() => {
    getDocuments().then((r) => setDocuments(r.data)).catch(console.error);
    getDataSources().then((r) => setSources(r.data)).catch(console.error);
    getEntities({ limit: 30 }).then((r) => setEntities(r.data)).catch(console.error);
    getFabricStats().then((r) => setStats(r.data)).catch(console.error);
    getAccountQuotas().then((r) => setQuotas(r.data)).catch(console.error);
    getLimsPlates().then((r) => setLims(r.data)).catch(console.error);
  }, []);

  useEffect(() => {
    load();
    getIngestionStages().then((r) => setStages(r.data.stages)).catch(console.error);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [load]);

  const handleLimsSync = async (plateId) => {
    if (quotas?.quotas_enabled && !quotas.uploads_allowed) {
      setLimsFeedback({
        type: 'error',
        message: `Upload limit reached (${quotas.uploads_used}/${quotas.max_uploads}). Contact your administrator.`,
      });
      return;
    }
    setLimsSyncing(plateId);
    setLimsFeedback(null);
    setUploadError('');
    try {
      const r = await syncLimsPlate(plateId);
      setActiveJob({
        id: r.data.job_id,
        status: 'processing',
        stage: 'upload',
        progress: 0,
        stages_completed: [],
        document_id: r.data.document_id,
      });
      pollJob(r.data.job_id);
      setLimsFeedback({
        type: 'success',
        message: `Plate ${plateId} imported — ingestion running (see pipeline above).`,
      });
      pipelineRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      getAccountQuotas().then((res) => setQuotas(res.data)).catch(console.error);
    } catch (err) {
      setLimsFeedback({ type: 'error', message: apiErrorMessage(err, 'LIMS sync failed') });
    } finally {
      setLimsSyncing(null);
    }
  };

  const pollJob = (jobId) => {
    if (pollRef.current) clearInterval(pollRef.current);
    stuckPollsRef.current = 0;
    setPipelineStuck(false);
    pollRef.current = setInterval(async () => {
      try {
        const r = await getIngestionStatus(jobId);
        setActiveJob(r.data);
        const stuck = r.data.status === 'processing'
          && (r.data.progress ?? 0) <= 7
          && (r.data.stages_completed?.length ?? 0) <= 1;
        if (stuck) {
          stuckPollsRef.current += 1;
          if (stuckPollsRef.current >= 5) setPipelineStuck(true);
          if (stuckPollsRef.current === 15 && !retryingJob) {
            setLimsFeedback({
              type: 'error',
              message: 'Pipeline appears stuck. Click "Retry pipeline" below or import again after refreshing.',
            });
          }
        } else {
          stuckPollsRef.current = 0;
          setPipelineStuck(false);
        }
        if (r.data.status === 'completed' || r.data.status === 'failed') {
          clearInterval(pollRef.current);
          pollRef.current = null;
          if (r.data.status === 'completed' && r.data.document_id) {
            getDocumentQC(r.data.document_id).then((qc) => setQcReport(qc.data)).catch(() => setQcReport(null));
            setLimsFeedback((prev) => (
              prev?.type === 'success'
                ? { ...prev, message: `${prev.message} Completed — assay QC available in upload panel.` }
                : prev
            ));
          }
          if (r.data.status === 'failed') {
            setLimsFeedback({ type: 'error', message: r.data.error_message || 'LIMS ingestion failed' });
          }
          load();
        }
      } catch (err) {
        clearInterval(pollRef.current);
        setLimsFeedback({ type: 'error', message: apiErrorMessage(err, 'Lost connection to ingestion job') });
      }
    }, 800);
  };

  const handleRetryPipeline = async () => {
    if (!activeJob?.id) return;
    setRetryingJob(true);
    setLimsFeedback(null);
    try {
      const r = await retryIngestion(activeJob.id);
      setActiveJob(r.data);
      pollJob(r.data.id);
      setPipelineStuck(false);
      setLimsFeedback({ type: 'success', message: 'Pipeline restarted — stages should advance now.' });
    } catch (err) {
      setLimsFeedback({ type: 'error', message: apiErrorMessage(err, 'Failed to retry pipeline') });
    } finally {
      setRetryingJob(false);
    }
  };

  const handleUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (quotas?.quotas_enabled && !quotas.uploads_allowed) {
      setUploadError(`Upload limit reached (${quotas.uploads_used}/${quotas.max_uploads}). Contact your administrator.`);
      if (fileRef.current) fileRef.current.value = '';
      return;
    }
    setUploading(true);
    setActiveJob(null);
    setUploadError('');
    const fd = new FormData();
    fd.append('file', file);
    fd.append('source_type', 'file_upload');
    try {
      const r = await uploadDocument(fd);
      setActiveJob(r.data);
      pollJob(r.data.id);
      getAccountQuotas().then((res) => setQuotas(res.data)).catch(console.error);
    } catch (err) {
      setUploadError(apiErrorMessage(err, 'Upload failed'));
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    setSearching(true);
    try {
      const r = await fabricSearch({ query: searchQuery, top_k: 8 });
      setSearchResults(r.data);
    } catch (err) {
      console.error(err);
    } finally {
      setSearching(false);
    }
  };

  const completedStages = activeJob?.stages_completed || [];
  const progress = activeJob?.progress ?? 0;
  const isFailed = activeJob?.status === 'failed';
  const recentDocuments = documents.slice(0, RECENT_DOC_LIMIT);
  const olderDocumentCount = Math.max(documents.length - RECENT_DOC_LIMIT, 0);
  const isStuck = pipelineStuck && activeJob?.status === 'processing';
  const uploadDisabled = uploading
    || activeJob?.status === 'processing'
    || (quotas?.quotas_enabled && !quotas.uploads_allowed);

  return (
    <div className="p-6 space-y-6">
      <GlassPanel hero>
        <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim">Evidence</p>
        <h2 className="font-display text-xl font-semibold mt-1">Scientific Data Fabric</h2>
        <p className="text-sm text-cx-fgMuted mt-2">
          Real ingestion pipeline: parse, chunk, embed, index in ChromaDB, extract entities, and update the knowledge graph.
          {activeProject && (
            <span className="block mt-1 text-cx-accent">Uploads go to project: {activeProject.name}</span>
          )}
        </p>
        {stats && (
          <div className="mt-4 flex flex-wrap gap-4 text-xs text-cx-fgMuted">
            <span>{stats.total_documents} indexed documents</span>
            <span>{stats.total_chunks} vector chunks</span>
            <span>{stats.total_entities} entities</span>
            <span className="font-mono text-cx-accent">ChromaDB: {stats.mode}</span>
            {quotas?.quotas_enabled && (
              <span className={quotas.uploads_allowed ? 'text-cx-fg' : 'text-cx-danger'}>
                Uploads: {quotas.uploads_used}/{quotas.max_uploads}
              </span>
            )}
          </div>
        )}
      </GlassPanel>

      <div className="grid lg:grid-cols-3 gap-6">
        <GlassPanel className="lg:col-span-1">
          <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim mb-3">Upload Panel</p>
          <input ref={fileRef} type="file" className="hidden" onChange={handleUpload} accept=".pdf,.csv,.xlsx,.json,.txt,.docx" />
          <button
            onClick={() => fileRef.current?.click()}
            disabled={uploadDisabled}
            className="w-full p-8 rounded-xl border-2 border-dashed border-cx-border hover:border-cx-accent/40 bg-white/40 transition-colors flex flex-col items-center gap-2 disabled:opacity-60"
          >
            {uploading || activeJob?.status === 'processing' ? (
              <Loader2 className="animate-spin text-cx-accent" size={32} />
            ) : (
              <Upload className="text-cx-accent" size={32} />
            )}
            <span className="text-sm font-medium text-cx-fg">
              {uploadDisabled && quotas?.quotas_enabled && !quotas.uploads_allowed
                ? 'Upload limit reached'
                : uploading
                  ? 'Uploading...'
                  : activeJob?.status === 'processing'
                    ? 'Pipeline running...'
                    : 'Drop files or click to upload'}
            </span>
            <span className="text-xs text-cx-fgDim">PDF, CSV, XLSX, JSON, TXT, DOCX</span>
          </button>
          {uploadError && (
            <div className="mt-3 p-3 rounded-xl border border-cx-danger/30 bg-cx-danger/5 flex gap-2 text-xs text-cx-danger">
              <AlertCircle size={14} className="shrink-0 mt-0.5" />
              {uploadError}
            </div>
          )}
          {qcReport && (
            <div className={`mt-3 p-3 rounded-xl border text-xs ${
              qcReport.status === 'pass' ? 'border-cx-success/30 bg-cx-success/5 text-cx-success'
                : qcReport.status === 'warn' ? 'border-cx-warn/30 bg-cx-warn/5 text-cx-warn'
                  : 'border-cx-danger/30 bg-cx-danger/5 text-cx-danger'
            }`}>
              <p className="font-medium">Assay QC: {qcReport.status?.toUpperCase()} (score {qcReport.score})</p>
              <p className="mt-1 opacity-90">{qcReport.summary}</p>
              {qcReport.flags?.length > 0 && (
                <ul className="mt-2 list-disc list-inside opacity-90">
                  {qcReport.flags.slice(0, 4).map((f, i) => <li key={i}>{f}</li>)}
                </ul>
              )}
            </div>
          )}
          {isFailed && (
            <div className="mt-3 p-3 rounded-xl border border-cx-danger/30 bg-cx-danger/5 flex gap-2 text-xs text-cx-danger">
              <AlertCircle size={14} className="shrink-0 mt-0.5" />
              {activeJob.error_message || 'Ingestion failed'}
            </div>
          )}
        </GlassPanel>

        <div ref={pipelineRef} className="lg:col-span-2">
        <GlassPanel>
          <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim mb-4">
            Ingestion Pipeline {activeJob ? `— ${activeJob.status}` : ''}
          </p>
          <div className="flex flex-wrap gap-x-1 gap-y-2">
            {(stages.length ? stages : Object.keys(STAGE_LABELS)).map((stage, i, arr) => {
              const done = completedStages.includes(stage);
              const current = activeJob?.stage === stage && activeJob?.status === 'processing';
              return (
                <div key={stage} className="flex items-center gap-1.5">
                  {done ? (
                    <CheckCircle size={14} className="text-cx-success" />
                  ) : current ? (
                    <Loader2 size={14} className="text-cx-accent animate-spin" />
                  ) : (
                    <Circle size={14} className="text-cx-fgDim" />
                  )}
                  <span className={`text-xs ${done ? 'text-cx-fg' : current ? 'text-cx-accent font-medium' : 'text-cx-fgMuted'}`}>
                    {STAGE_LABELS[stage] || stage}
                  </span>
                  {i < arr.length - 1 && <span className="text-cx-fgDim mx-0.5">→</span>}
                </div>
              );
            })}
          </div>
          <div className="mt-4 h-1.5 rounded-full bg-cx-border overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-500 ${isFailed ? 'bg-cx-danger' : 'bg-gradient-to-r from-cx-accent to-cx-accent2'}`}
              style={{ width: `${progress}%` }}
            />
          </div>
          <p className="text-2xs text-cx-fgDim mt-2 uppercase tracking-wider">
            {activeJob ? `Progress: ${progress}% · Stage: ${STAGE_LABELS[activeJob.stage] || activeJob.stage}` : 'Upload a document or import a LIMS plate to start the pipeline'}
          </p>
          {(isStuck || isFailed) && activeJob?.id && (
            <button
              type="button"
              onClick={handleRetryPipeline}
              disabled={retryingJob}
              className="mt-3 px-4 py-2 rounded-xl text-xs font-medium border border-cx-accent/30 bg-cx-accent/5 text-cx-accent hover:bg-cx-accent/10 disabled:opacity-50"
            >
              {retryingJob ? 'Restarting…' : 'Retry pipeline'}
            </button>
          )}
        </GlassPanel>
        </div>
      </div>

      <GlassPanel>
        <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim mb-3">Semantic Search (Vector Index)</p>
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-cx-accent" size={16} />
            <input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              placeholder="Search ingested documents..."
              className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-cx-border bg-white/60 text-sm"
            />
          </div>
          <button
            onClick={handleSearch}
            disabled={searching}
            className="px-5 py-2.5 rounded-xl text-sm border border-cx-accent/30 bg-cx-accent/5 text-cx-accent hover:bg-cx-accent/10 disabled:opacity-50"
          >
            {searching ? 'Searching...' : 'Search'}
          </button>
        </div>
        {searchResults.length > 0 && (
          <div className="mt-4 space-y-2">
            {searchResults.map((r) => (
              <div key={r.chunk_id} className="p-3 rounded-xl border border-cx-border bg-white/40">
                <div className="flex justify-between text-2xs text-cx-fgDim mb-1">
                  <span>Chunk {r.chunk_index} · Doc {r.document_id.slice(0, 8)}...</span>
                  <span className="text-cx-accent font-mono">{(r.score * 100).toFixed(0)}% match</span>
                </div>
                <p className="text-xs text-cx-fgMuted line-clamp-3">{r.content}</p>
              </div>
            ))}
          </div>
        )}
      </GlassPanel>

      <div className="grid lg:grid-cols-2 gap-6 lg:items-start">
        <GlassPanel>
          <div className="flex items-center gap-2 mb-4">
            <Link2 size={16} className="text-cx-accent" />
            <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim">Source Connectors</p>
          </div>
          <div className="space-y-2">
            {sources.map((s) => (
              <div key={s.id} className="flex items-center justify-between p-3 rounded-xl border border-cx-border bg-white/40">
                <div>
                  <p className="text-sm font-medium">{s.name}</p>
                  <p className="text-xs text-cx-fgDim">{s.source_type} · {s.document_count} docs</p>
                </div>
                <span className="text-2xs uppercase px-2 py-0.5 rounded-md bg-cx-success/10 text-cx-success border border-cx-success/20">{s.connector_status}</span>
              </div>
            ))}
          </div>
          {lims && (
            <div className="mt-4 pt-4 border-t border-cx-border">
              <p className="text-2xs uppercase tracking-wider text-cx-fgDim mb-2">
                LIMS Bridge · {lims.mode === 'api' ? 'Live API' : 'Demo plates'}
              </p>
              <div className="space-y-2">
                {(lims.plates || []).map((plate) => {
                  const id = plate.plate_id || plate.id;
                  return (
                    <div key={id} className="flex items-center justify-between p-3 rounded-xl border border-cx-border bg-white/40 text-xs">
                      <div>
                        <p className="font-medium text-sm">{id}</p>
                        <p className="text-cx-fgDim">{plate.assay} · {plate.wells} wells · {plate.status}</p>
                      </div>
                      <button
                        type="button"
                        onClick={() => handleLimsSync(id)}
                        disabled={limsSyncing === id}
                        className="px-3 py-1.5 rounded-lg border border-cx-accent/30 text-cx-accent hover:bg-cx-accent/5 disabled:opacity-50"
                      >
                        {limsSyncing === id ? 'Importing…' : 'Import'}
                      </button>
                    </div>
                  );
                })}
              </div>
              {limsFeedback && (
                <div className={`mt-3 p-3 rounded-xl border text-xs flex gap-2 ${
                  limsFeedback.type === 'success'
                    ? 'border-cx-success/30 bg-cx-success/5 text-cx-success'
                    : 'border-cx-danger/30 bg-cx-danger/5 text-cx-danger'
                }`}>
                  {limsFeedback.type === 'success'
                    ? <CheckCircle size={14} className="shrink-0 mt-0.5" />
                    : <AlertCircle size={14} className="shrink-0 mt-0.5" />}
                  {limsFeedback.message}
                </div>
              )}
            </div>
          )}
        </GlassPanel>

        <GlassPanel>
          <div className="flex items-center justify-between gap-2 mb-4">
            <div className="flex items-center gap-2">
              <FileSearch size={16} className="text-cx-accent2" />
              <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim">Recent Documents</p>
            </div>
            <span className="text-2xs text-cx-fgDim">{documents.length} total</span>
          </div>
          <div className="space-y-2">
            {recentDocuments.map((d) => (
              <div key={d.id} className="p-3 rounded-xl border border-cx-border bg-white/40">
                <div className="flex items-start justify-between gap-3">
                  <p className="text-sm font-medium leading-snug break-words min-w-0 flex-1">{d.title}</p>
                  <span className={`text-2xs uppercase shrink-0 px-1.5 py-0.5 rounded ${
                    d.status === 'indexed' ? 'text-cx-success bg-cx-success/5' :
                    d.status === 'processing' ? 'text-cx-accent bg-cx-accent/5' :
                    d.status === 'failed' ? 'text-cx-danger bg-cx-danger/5' : 'text-cx-fgDim'
                  }`}>{d.status}</span>
                </div>
                <p className="text-xs text-cx-fgDim mt-1">
                  {d.source_type} · {d.file_format} · {d.metadata_json?.chunk_count ?? '—'} chunks
                  {d.metadata_json?.original_filename && (
                    <span className="block mt-0.5 font-mono text-2xs truncate">{d.metadata_json.original_filename}</span>
                  )}
                </p>
              </div>
            ))}
          </div>
          {documents.length > 0 && (
            <div className="mt-3 pt-3 border-t border-cx-border flex items-center justify-between gap-2">
              <p className="text-2xs text-cx-fgDim">
                {olderDocumentCount > 0
                  ? `Showing ${RECENT_DOC_LIMIT} most recent · ${olderDocumentCount} older in index`
                  : `${documents.length} document${documents.length === 1 ? '' : 's'} indexed`}
              </p>
              {documents.length > RECENT_DOC_LIMIT && (
                <Link
                  to="/documents"
                  className="inline-flex items-center gap-1 text-2xs font-medium text-cx-accent hover:text-cx-accent2 transition-colors shrink-0"
                >
                  View all
                  <ArrowRight size={12} />
                </Link>
              )}
            </div>
          )}
        </GlassPanel>
      </div>

      <GlassPanel>
        <div className="flex items-center gap-2 mb-4">
          <Database size={16} className="text-cx-accent" />
          <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim">Extracted Entities</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {entities.map((e) => (
            <span key={e.id} className="px-3 py-1.5 rounded-lg border border-cx-border bg-white/50 text-xs">
              <span className="font-medium text-cx-fg">{e.name}</span>
              <span className="text-cx-fgDim ml-2">{e.entity_type}</span>
            </span>
          ))}
        </div>
      </GlassPanel>
    </div>
  );
}
