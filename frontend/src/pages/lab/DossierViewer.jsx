import { useEffect, useState } from 'react';
import GlassPanel from '../../components/ui/GlassPanel';
import { createLabDossier, downloadLabDossier, getLabDossier, labError } from '../../api/lab';
import { StatusPill, useLab } from './LabShell';

export default function DossierViewer() {
  const { experimentId, dossierId, setDossierId } = useLab();
  const [dossier, setDossier] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!dossierId) return;
    getLabDossier(dossierId).then((response) => setDossier(response.data)).catch((err) => setError(labError(err)));
  }, [dossierId]);

  const generate = async () => {
    setError('');
    try {
      const response = await createLabDossier(experimentId);
      setDossierId(response.data.id);
      setDossier(response.data);
    } catch (err) {
      setError(labError(err));
    }
  };

  const narrative = dossier?.narrative_json;

  return (
    <div className="space-y-5">
      <GlassPanel>
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="font-display text-xl">Experiment dossier</h2>
          {dossier && <StatusPill value={dossier.publishable ? 'publishable' : dossier.status} />}
        </div>
        <button type="button" onClick={generate} disabled={!experimentId} className="mt-4 rounded-xl bg-cx-accent text-white px-3 py-2 text-sm disabled:opacity-50">Generate draft dossier</button>
        {error && <p className="mt-3 text-sm text-rose-700">{error}</p>}
        {narrative && (
          <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm">
            <p className="font-medium">{narrative.label}</p>
            <p className="mt-1 text-xs">Model {narrative.model_version}. LLM called: {String(narrative.llm_called)}. Approval required: {String(narrative.requires_scientist_approval)}.</p>
            <div className="mt-3 space-y-3">
              {(narrative.paragraphs || []).map((paragraph) => (
                <div key={paragraph.text}>
                  <p>{paragraph.text}</p>
                  <p className="text-xs text-cx-fgDim mt-1">Citations: {(paragraph.citations || []).map((item) => `${item.entity_type}:${item.id}`).join(', ')}</p>
                </div>
              ))}
            </div>
          </div>
        )}
        {dossier && (
          <div className="mt-4 flex gap-2">
            <button type="button" onClick={() => downloadLabDossier(dossier.id, 'pdf')} className="rounded-xl border border-cx-border px-3 py-2 text-sm">Download PDF</button>
            <button type="button" onClick={() => downloadLabDossier(dossier.id, 'docx')} className="rounded-xl border border-cx-border px-3 py-2 text-sm">Download DOCX</button>
          </div>
        )}
        {dossier?.eln && <p className="mt-3 text-sm text-cx-fgMuted">{dossier.eln.message}</p>}
      </GlassPanel>
    </div>
  );
}
