import { useEffect, useState } from 'react';
import GlassPanel from '../../components/ui/GlassPanel';
import { decideLabDossier, getLabDossier, labError } from '../../api/lab';
import { StatusPill, useLab } from './LabShell';

export default function ApprovalWorkspace() {
  const { dossierId } = useLab();
  const [dossier, setDossier] = useState(null);
  const [comment, setComment] = useState('Reviewed measurements, criteria, and citations.');
  const [error, setError] = useState('');

  const load = () => {
    if (!dossierId) return;
    getLabDossier(dossierId).then((response) => setDossier(response.data)).catch((err) => setError(labError(err)));
  };

  useEffect(() => { load(); }, [dossierId]);

  const decide = async (decision) => {
    setError('');
    try {
      const response = await decideLabDossier(dossierId, { decision, comment });
      setDossier(response.data);
    } catch (err) {
      setError(labError(err));
    }
  };

  return (
    <div className="space-y-5">
      <GlassPanel>
        <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim">Gate G6 — scientist dossier approval</p>
        <h2 className="font-display text-xl mt-1">Nothing here is approved automatically</h2>
        {!dossierId && <p className="mt-3 text-sm text-cx-fgMuted">Generate a dossier before recording a decision.</p>}
        {dossier && (
          <div className="mt-4 text-sm space-y-2">
            <p>Version {dossier.version} · <StatusPill value={dossier.status} /></p>
            <p className="text-cx-fgMuted">Publishable: {String(dossier.publishable)}. Actor on record: {dossier.approval_json?.actor || 'pending'}.</p>
          </div>
        )}
        <textarea value={comment} onChange={(event) => setComment(event.target.value)} className="mt-4 w-full rounded-xl border border-cx-border p-3 text-sm" rows={3} />
        <div className="mt-3 flex flex-wrap gap-2">
          <button type="button" onClick={() => decide('approve')} disabled={!dossierId} className="rounded-xl bg-emerald-700 text-white px-3 py-2 text-sm disabled:opacity-50">Approve</button>
          <button type="button" onClick={() => decide('revision_requested')} disabled={!dossierId} className="rounded-xl border border-cx-border px-3 py-2 text-sm disabled:opacity-50">Request revision</button>
          <button type="button" onClick={() => decide('reject')} disabled={!dossierId} className="rounded-xl border border-rose-300 text-rose-800 px-3 py-2 text-sm disabled:opacity-50">Reject</button>
        </div>
        {error && <p className="mt-3 text-sm text-rose-700">{error}</p>}
      </GlassPanel>
    </div>
  );
}
