import { useEffect, useState } from 'react';
import GlassPanel from '../../components/ui/GlassPanel';
import { getLabIngestion, getLabLineage, labError, queryLabGraph } from '../../api/lab';
import { useLab } from './LabShell';

export default function LineageExplorer() {
  const { experimentId } = useLab();
  const [lineage, setLineage] = useState(null);
  const [graph, setGraph] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!experimentId) return;
    getLabIngestion(experimentId).then(async (response) => {
      const measurement = (response.data.measurements || []).find((row) => row.readout_key === 'viability_percent' && row.sample_id);
      if (!measurement) return;
      const chain = await getLabLineage(`measurement:${measurement.id}`);
      setLineage(chain.data);
      const queried = await queryLabGraph({ start: measurement.id, depth: 2 });
      setGraph(queried.data);
    }).catch((err) => setError(labError(err)));
  }, [experimentId]);

  return (
    <div className="space-y-5">
      <GlassPanel>
        <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim">Knowledge graph lineage</p>
        <h2 className="font-display text-xl mt-1">Measurement to protocol version</h2>
        {error && <p className="mt-3 text-sm text-rose-700">{error}</p>}
        <ol className="mt-4 space-y-2">
          {(lineage?.chain || []).filter(Boolean).map((item, index) => (
            <li key={item.id} className="rounded-xl border border-cx-border px-3 py-2 text-sm">
              <span className="text-cx-fgDim mr-2">{index + 1}</span>
              <span className="font-medium">{item.entity_type}</span>
              <span className="text-cx-fgMuted"> · {item.sample_code || item.run_code || item.serial_number || item.title || item.code || item.version_label || item.readout_key || item.id}</span>
            </li>
          ))}
        </ol>
        {lineage?.checksum && <p className="mt-3 text-xs font-mono break-all text-cx-fgDim">Raw SHA-256 {lineage.checksum}</p>}
        {graph && <p className="mt-3 text-sm text-cx-fgMuted">Graph query returned {graph.nodes?.length || 0} nodes and {graph.relationships?.length || 0} relationships in the existing knowledge graph.</p>}
      </GlassPanel>
    </div>
  );
}
