import { useCallback, useEffect, useState } from 'react';
import { CheckCircle, Copy, Loader2, Trash2, UserPlus, Users } from 'lucide-react';
import GlassPanel from '../ui/GlassPanel';
import { createAdminUser, deleteAdminUser, listAdminUsers } from '../../api/client';
import { apiErrorMessage } from '../../lib/auth';
import { useUser } from '../../context/UserContext';

const ROLES = [
  { value: 'scientist', label: 'Scientist' },
  { value: 'reviewer', label: 'Reviewer' },
  { value: 'admin', label: 'Admin' },
];

const emptyForm = () => ({
  username: '',
  password: '',
  full_name: '',
  role: 'scientist',
});

export default function AdminUsersPanel() {
  const { user: currentUser } = useUser();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState(emptyForm);
  const [creating, setCreating] = useState(false);
  const [deletingId, setDeletingId] = useState(null);
  const [error, setError] = useState('');
  const [deleteMessage, setDeleteMessage] = useState('');
  const [success, setSuccess] = useState(null);
  const [copied, setCopied] = useState(false);

  const loadUsers = useCallback(async () => {
    setLoading(true);
    try {
      const r = await listAdminUsers();
      setUsers(r.data);
      return r.data;
    } catch (err) {
      setError(apiErrorMessage(err, 'Failed to load users'));
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadUsers();
  }, [loadUsers]);

  const handleCreate = async (e) => {
    e.preventDefault();
    setCreating(true);
    setError('');
    setSuccess(null);
    try {
      const payload = {
        username: form.username.trim(),
        password: form.password,
        role: form.role,
        full_name: form.full_name.trim() || form.username.trim(),
      };
      const r = await createAdminUser(payload);
      setSuccess({
        username: r.data.username,
        password: form.password,
        role: r.data.role,
      });
      setForm(emptyForm());
      loadUsers();
    } catch (err) {
      setError(apiErrorMessage(err, 'Failed to create user'));
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (target) => {
    const isSelf = target.id === currentUser?.user_id;
    if (isSelf) {
      setError('You cannot delete your own account.');
      return;
    }

    const message = [
      `Delete user "${target.username}"?`,
      '',
      'This permanently removes their account, uploads, workflows, reports, and any projects they own.',
      'This cannot be undone.',
    ].join('\n');

    if (!window.confirm(message)) return;

    setDeletingId(target.id);
    setError('');
    setDeleteMessage('');
    try {
      await deleteAdminUser(target.id);
      setUsers((prev) => prev.filter((u) => u.id !== target.id));
      setDeleteMessage(`User "${target.username}" deleted.`);
      await loadUsers();
    } catch (err) {
      setError(apiErrorMessage(err, 'Failed to delete user'));
    } finally {
      setDeletingId(null);
    }
  };

  const copyCredentials = async () => {
    if (!success) return;
    const text = `SciNova OS login\nUsername: ${success.username}\nPassword: ${success.password}\nRole: ${success.role}`;
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  };

  if (loading && users.length === 0) {
    return (
      <div className="flex items-center justify-center min-h-[30vh] text-cx-fgMuted">
        <Loader2 className="animate-spin mr-2" size={20} />
        Loading users…
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <GlassPanel hero>
        <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim flex items-center gap-2">
          <Users size={14} /> Administration
        </p>
        <h2 className="font-display text-xl font-semibold mt-1">User Administration</h2>
        <p className="text-sm text-cx-fgMuted mt-2 max-w-2xl">
          Create or remove team accounts. Share usernames and passwords securely — there is no self-registration.
          Deleting a user removes their workspace data and owned shared projects.
        </p>
        {(error || deleteMessage) && (
          <div className={`mt-3 p-3 rounded-xl text-sm border ${
            error
              ? 'border-cx-danger/30 bg-cx-danger/5 text-cx-danger'
              : 'border-cx-success/30 bg-cx-success/5 text-cx-success'
          }`}>
            {error || deleteMessage}
          </div>
        )}
      </GlassPanel>

      <div className="grid lg:grid-cols-2 gap-6">
        <GlassPanel>
          <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim mb-4 flex items-center gap-2">
            <UserPlus size={12} /> Create user
          </p>
          <form onSubmit={handleCreate} className="space-y-4">
            <div>
              <label className="text-2xs uppercase tracking-wider text-cx-fgDim">Username</label>
              <input
                value={form.username}
                onChange={(e) => setForm((f) => ({ ...f, username: e.target.value }))}
                required
                minLength={2}
                className="mt-1 w-full px-3 py-2 rounded-xl border border-cx-border bg-white/60 text-sm focus:outline-none focus:border-cx-accent/40"
              />
            </div>
            <div>
              <label className="text-2xs uppercase tracking-wider text-cx-fgDim">Full name</label>
              <input
                value={form.full_name}
                onChange={(e) => setForm((f) => ({ ...f, full_name: e.target.value }))}
                placeholder="Optional display name"
                className="mt-1 w-full px-3 py-2 rounded-xl border border-cx-border bg-white/60 text-sm focus:outline-none focus:border-cx-accent/40"
              />
            </div>
            <div>
              <label className="text-2xs uppercase tracking-wider text-cx-fgDim">Password</label>
              <input
                type="text"
                value={form.password}
                onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
                required
                minLength={6}
                placeholder="Share this password with the user"
                className="mt-1 w-full px-3 py-2 rounded-xl border border-cx-border bg-white/60 text-sm font-mono focus:outline-none focus:border-cx-accent/40"
              />
            </div>
            <div>
              <label className="text-2xs uppercase tracking-wider text-cx-fgDim">Role</label>
              <select
                value={form.role}
                onChange={(e) => setForm((f) => ({ ...f, role: e.target.value }))}
                className="mt-1 w-full px-3 py-2 rounded-xl border border-cx-border bg-white/60 text-sm focus:outline-none focus:border-cx-accent/40"
              >
                {ROLES.map((r) => (
                  <option key={r.value} value={r.value}>{r.label}</option>
                ))}
              </select>
            </div>
            {error && <p className="text-sm text-cx-danger">{error}</p>}
            {deleteMessage && !error && (
              <p className="text-sm text-cx-success">{deleteMessage}</p>
            )}
            <button
              type="submit"
              disabled={creating}
              className="w-full py-2.5 rounded-xl text-sm font-medium border border-cx-accent/30 bg-cx-accent/5 text-cx-accent hover:bg-cx-accent/10 disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {creating ? <Loader2 size={16} className="animate-spin" /> : <UserPlus size={16} />}
              {creating ? 'Creating…' : 'Create user'}
            </button>
          </form>

          {success && (
            <div className="mt-4 p-4 rounded-xl border border-cx-success/30 bg-cx-success/5 text-sm">
              <p className="flex items-center gap-2 text-cx-success font-medium">
                <CheckCircle size={16} /> User created: {success.username}
              </p>
              <p className="mt-2 text-cx-fgMuted text-xs">
                Password: <span className="font-mono text-cx-fg">{success.password}</span>
              </p>
              <button
                type="button"
                onClick={copyCredentials}
                className="mt-3 inline-flex items-center gap-1.5 text-xs text-cx-accent hover:underline"
              >
                <Copy size={12} />
                {copied ? 'Copied!' : 'Copy credentials to share'}
              </button>
            </div>
          )}
        </GlassPanel>

        <GlassPanel>
          <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim mb-4">All users ({users.length})</p>
          <div className="space-y-2 max-h-[420px] overflow-y-auto pr-1">
            {users.map((user) => {
              const isSelf = user.id === currentUser?.user_id;
              const isDeleting = deletingId === user.id;
              return (
              <div
                key={user.id}
                className="p-3 rounded-xl border border-cx-border bg-white/40 flex items-start justify-between gap-3"
              >
                <div className="min-w-0">
                  <p className="text-sm font-medium truncate">
                    {user.full_name || user.username}
                    {isSelf && (
                      <span className="ml-2 text-2xs text-cx-accent">(you)</span>
                    )}
                  </p>
                  <p className="text-2xs text-cx-fgDim font-mono">@{user.username}</p>
                </div>
                <div className="text-right shrink-0 flex flex-col items-end gap-2">
                  <span className="text-2xs px-2 py-0.5 rounded-full border border-cx-border capitalize">
                    {user.role}
                  </span>
                  <p className="text-2xs text-cx-fgMuted">
                    {user.document_count} uploads · {user.workflow_count} workflows
                  </p>
                  <button
                    type="button"
                    onClick={() => handleDelete(user)}
                    disabled={isSelf || isDeleting}
                    title={isSelf ? 'You cannot delete your own account' : 'Delete user'}
                    className="inline-flex items-center gap-1 text-2xs px-2 py-1 rounded-lg border border-cx-danger/30 text-cx-danger hover:bg-cx-danger/5 disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    {isDeleting ? (
                      <Loader2 size={12} className="animate-spin" />
                    ) : (
                      <Trash2 size={12} />
                    )}
                    Delete
                  </button>
                </div>
              </div>
            );
            })}
          </div>
        </GlassPanel>
      </div>
    </div>
  );
}
