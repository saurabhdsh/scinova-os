import { useEffect, useRef, useState } from 'react';
import { FolderPlus, Loader2, X } from 'lucide-react';

export default function NewProjectModal({ open, onClose, onCreate }) {
  const inputRef = useRef(null);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (open) {
      setName('');
      setDescription('');
      setError('');
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  if (!open) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) {
      setError('Project name is required');
      return;
    }
    setSaving(true);
    setError('');
    try {
      await onCreate(trimmed, description.trim());
      onClose();
    } catch (err) {
      setError(err?.response?.data?.detail || 'Failed to create project');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center px-4">
      <button
        type="button"
        aria-label="Close"
        className="absolute inset-0 bg-cx-void/40 backdrop-blur-sm"
        onClick={onClose}
      />
      <form
        onSubmit={handleSubmit}
        className="relative w-full max-w-md rounded-2xl border border-cx-border bg-white/95 shadow-2xl backdrop-blur-xl p-6"
      >
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center gap-2">
            <FolderPlus size={18} className="text-cx-accent" />
            <h3 className="font-display font-semibold text-cx-fg">New shared project</h3>
          </div>
          <button type="button" onClick={onClose} className="p-1 rounded-lg hover:bg-cx-deep/30">
            <X size={16} className="text-cx-fgDim" />
          </button>
        </div>

        <label className="block text-2xs uppercase tracking-wider text-cx-fgDim">Name</label>
        <input
          ref={inputRef}
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="mt-1 w-full px-3 py-2 rounded-xl border border-cx-border bg-white/60 text-sm focus:outline-none focus:border-cx-accent/40"
          placeholder="e.g. JAK1 inhibitor program"
        />

        <label className="block mt-4 text-2xs uppercase tracking-wider text-cx-fgDim">Description (optional)</label>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={2}
          className="mt-1 w-full px-3 py-2 rounded-xl border border-cx-border bg-white/60 text-sm focus:outline-none focus:border-cx-accent/40 resize-none"
          placeholder="Shared workspace for your team"
        />

        {error && <p className="mt-3 text-sm text-cx-danger">{error}</p>}

        <div className="mt-5 flex gap-2 justify-end">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-sm rounded-xl border border-cx-border text-cx-fgMuted hover:bg-white/80"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={saving}
            className="px-4 py-2 text-sm rounded-xl border border-cx-accent/30 bg-cx-accent/5 text-cx-accent hover:bg-cx-accent/10 disabled:opacity-50 flex items-center gap-2"
          >
            {saving && <Loader2 size={14} className="animate-spin" />}
            Create project
          </button>
        </div>
      </form>
    </div>
  );
}
