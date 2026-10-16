import { useEffect, useState } from 'react';
import GlassPanel from '../../components/ui/GlassPanel';
import { fetchVicellFixtureFile, getLabIngestion, ingestLabFile, labError } from '../../api/lab';
import { LabNotice, StatusPill, useLab } from './LabShell';

export default function IngestionMonitor() {
  const { experimentId } = useLab();
  const [report, setReport] = useState(null);
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState('');

  const load = () => {
    if (!experimentId) return;
    getLabIngestion(experimentId).then((response) => setReport(response.data)).catch((err) => setError(labError(err)));
  };

  useEffect(() => { load(); }, [experimentId]);

  const upload = async (file) => {
    setError('');
    try {
      const response = await ingestLabFile(experimentId, file);
      setSummary(response.data);
      load();
    } catch (err) {
      setError(labError(err));
    }
  };

  const useFixture = async () => {
    const file = await fetchVicellFixtureFile();
    await upload(file);
  };

  const viability = (report?.measurements || []).filter((row) => row.readout_key === 'viability_percent');

  return (
    <div className="space-y-5">
      <LabNotice />
      <GlassPanel>
        <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim">Moment 3 — instrument data capture</p>
        <h2 className="font-display text-xl mt-1">Vi-CELL XR landing zone</h2>
        <p className="mt-2 text-sm text-cx-fgMuted">The fixture uses publicly documented Vi-CELL XR export columns. Its numbers are synthetic, including one unmatched sample identifier.</p>
        <div className="mt-4 flex flex-wrap gap-2">
          <button type="button" onClick={useFixture} disabled={!experimentId} className="rounded-xl bg-cx-accent text-white px-3 py-2 text-sm disabled:opacity-50">Ingest synthetic Vi-CELL fixture</button>
          <label className="rounded-xl border border-cx-border px-3 py-2 text-sm cursor-pointer">
            Upload CSV
            <input type="file" accept=".csv,text/csv" className="hidden" onChange={(event) => event.target.files?.[0] && upload(event.target.files[0])} />
          </label>
        </div>
        {error && <p className="mt-3 text-sm text-rose-700">{error}</p>}
        {summary && (
          <dl className="mt-4 grid md:grid-cols-3 gap-3 text-sm">
            <div><dt className="text-cx-fgDim">SHA-256</dt><dd className="break-all font-mono text-xs">{summary.sha256}</dd></div>
            <div><dt className="text-cx-fgDim">Landing</dt><dd>{summary.landing_mode} · external {String(summary.landing_external)} · simulation {String(summary.simulation)}</dd></div>
            <div><dt className="text-cx-fgDim">Completeness</dt><dd>{summary.completeness_percent}% · parser {summary.parser_id} {summary.parser_version}</dd></div>
          </dl>
        )}
      </GlassPanel>
      <GlassPanel>
        <p className="text-sm font-medium mb-3">Quality flags</p>
        <div className="flex flex-wrap gap-2">
          {(report?.flags || []).map((flag) => <StatusPill key={flag.id} value={`${flag.code} ${flag.sample_code || ''}`} />)}
          {!report?.flags?.length && <p className="text-sm text-cx-fgMuted">No flags yet.</p>}
        </div>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-cx-fgDim"><tr><th className="py-2">Sample</th><th>Readout</th><th>Value</th><th>Ontology</th><th>Confidence</th><th>Origin</th></tr></thead>
            <tbody>
              {viability.map((row) => (
                <tr key={row.id} className="border-t border-cx-line">
                  <td className="py-2">{row.sample_code_observed}</td>
                  <td>{row.readout_key}</td>
                  <td>{row.value} {row.unit}</td>
                  <td>{row.ontology_id || 'unconfirmed'}</td>
                  <td>{row.mapping_confidence}</td>
                  <td>{row.data_origin}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </GlassPanel>
    </div>
  );
}
