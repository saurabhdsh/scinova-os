import { useCallback, useEffect, useState } from 'react';
import {
  CheckCircle,
  FlaskConical,
  Loader2,
  Plug,
  Trash2,
  Wrench,
  Zap,
} from 'lucide-react';
import GlassPanel from '../ui/GlassPanel';
import {
  createAdminCustomTool,
  deleteAdminCustomTool,
  listAdminCustomTools,
  listAdminToolFabricRoles,
  testAdminCustomTool,
  updateAdminCustomTool,
} from '../../api/client';
import { apiErrorMessage } from '../../lib/auth';

const AUTH_TYPES = [
  { value: 'none', label: 'None' },
  { value: 'bearer', label: 'Bearer token' },
  { value: 'api_key_header', label: 'API key header' },
];

const HTTP_METHODS = ['POST', 'GET', 'PUT'];

const emptyForm = () => ({
  tool_id: '',
  label: '',
  description: '',
  role_id: 'property_prediction',
  endpoint_url: '',
  http_method: 'POST',
  auth_type: 'none',
  auth_header_name: 'X-API-Key',
  auth_secret: '',
  request_template: '{}',
  status: 'active',
});

function parseTemplate(text) {
  if (!text.trim()) return {};
  return JSON.parse(text);
}

export default function AdminToolFabricPanel() {
  const [tools, setTools] = useState([]);
  const [roles, setRoles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState(emptyForm);
  const [creating, setCreating] = useState(false);
  const [deletingId, setDeletingId] = useState(null);
  const [testingId, setTestingId] = useState(null);
  const [testResult, setTestResult] = useState(null);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [editingId, setEditingId] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [toolsRes, rolesRes] = await Promise.all([
        listAdminCustomTools(),
        listAdminToolFabricRoles(),
      ]);
      setTools(toolsRes.data);
      setRoles(rolesRes.data);
      if (rolesRes.data.length && !form.role_id) {
        setForm((f) => ({ ...f, role_id: rolesRes.data[0].id }));
      }
    } catch (err) {
      setError(apiErrorMessage(err, 'Failed to load custom tools'));
    } finally {
      setLoading(false);
    }
  }, [form.role_id]);

  useEffect(() => {
    load();
  }, [load]);

  const resetForm = () => {
    setForm(emptyForm());
    setEditingId(null);
    setTestResult(null);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setCreating(true);
    setError('');
    setSuccess('');
    setTestResult(null);
    try {
      let requestTemplate = {};
      try {
        requestTemplate = parseTemplate(form.request_template);
      } catch {
        throw new Error('Request template must be valid JSON');
      }

      const payload = {
        tool_id: form.tool_id.trim(),
        label: form.label.trim(),
        description: form.description.trim() || null,
        role_id: form.role_id,
        endpoint_url: form.endpoint_url.trim(),
        http_method: form.http_method,
        auth_type: form.auth_type,
        auth_header_name: form.auth_type === 'api_key_header' ? form.auth_header_name.trim() : null,
        auth_secret: form.auth_secret.trim() || null,
        request_template: requestTemplate,
        status: form.status,
      };

      if (editingId) {
        const updatePayload = { ...payload };
        delete updatePayload.tool_id;
        if (!updatePayload.auth_secret) delete updatePayload.auth_secret;
        await updateAdminCustomTool(editingId, updatePayload);
        setSuccess('Custom tool updated.');
      } else {
        await createAdminCustomTool(payload);
        setSuccess('Custom tool registered — assign it in Agent Tasks.');
        resetForm();
      }
      await load();
    } catch (err) {
      setError(err.message || apiErrorMessage(err, 'Failed to save custom tool'));
    } finally {
      setCreating(false);
    }
  };

  const handleEdit = (tool) => {
    setEditingId(tool.id);
    setForm({
      tool_id: tool.tool_id.replace(/^custom_/, ''),
      label: tool.label,
      description: tool.description || '',
      role_id: tool.role_id,
      endpoint_url: tool.endpoint_url,
      http_method: tool.http_method || 'POST',
      auth_type: tool.auth_type || 'none',
      auth_header_name: tool.auth_header_name || 'X-API-Key',
      auth_secret: '',
      request_template: JSON.stringify(tool.request_template || {}, null, 2),
      status: tool.status || 'active',
    });
    setSuccess('');
    setError('');
    setTestResult(null);
  };

  const handleDelete = async (tool) => {
    const message = [
      `Delete custom tool "${tool.label}" (${tool.tool_id})?`,
      '',
      'Agents bound to this tool will fall back to platform defaults.',
    ].join('\n');
    if (!window.confirm(message)) return;

    setDeletingId(tool.id);
    setError('');
    try {
      await deleteAdminCustomTool(tool.id);
      if (editingId === tool.id) resetForm();
      setSuccess(`Deleted "${tool.label}".`);
      await load();
    } catch (err) {
      setError(apiErrorMessage(err, 'Failed to delete custom tool'));
    } finally {
      setDeletingId(null);
    }
  };

  const handleTest = async (tool) => {
    setTestingId(tool.id);
    setTestResult(null);
    setError('');
    try {
      const r = await testAdminCustomTool(tool.id, {});
      setTestResult({ toolId: tool.id, ...r.data });
    } catch (err) {
      setError(apiErrorMessage(err, 'Connection test failed'));
    } finally {
      setTestingId(null);
    }
  };

  if (loading && tools.length === 0) {
    return (
      <div className="flex items-center justify-center min-h-[30vh] text-cx-fgMuted">
        <Loader2 className="animate-spin mr-2" size={20} />
        Loading Tool Fabric Registry…
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <GlassPanel hero>
        <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim flex items-center gap-2">
          <Wrench size={14} /> Administration
        </p>
        <h2 className="font-display text-xl font-semibold mt-1">Tool Fabric Registry</h2>
        <p className="text-sm text-cx-fgMuted mt-2 max-w-2xl">
          Register your organization&apos;s scientific tools (REST APIs, internal QSAR services, ELN connectors).
          Once registered, they appear in <strong>Agent Tasks</strong> tool dropdowns for all users.
        </p>
        {(error || success) && (
          <div className={`mt-3 p-3 rounded-xl text-sm border ${
            error
              ? 'border-cx-danger/30 bg-cx-danger/5 text-cx-danger'
              : 'border-cx-success/30 bg-cx-success/5 text-cx-success'
          }`}>
            {error || success}
          </div>
        )}
      </GlassPanel>

      <div className="grid lg:grid-cols-2 gap-6">
        <GlassPanel>
          <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim mb-4 flex items-center gap-2">
            <Plug size={12} /> {editingId ? 'Edit custom tool' : 'Register custom tool'}
          </p>
          <form onSubmit={handleSubmit} className="space-y-3">
            <div className="grid sm:grid-cols-2 gap-3">
              <div>
                <label className="text-2xs uppercase tracking-wider text-cx-fgDim">Tool ID (slug)</label>
                <input
                  value={form.tool_id}
                  onChange={(e) => setForm((f) => ({ ...f, tool_id: e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, '') }))}
                  required
                  disabled={Boolean(editingId)}
                  placeholder="acme_qsar_v3"
                  className="mt-1 w-full px-3 py-2 rounded-xl border border-cx-border bg-white/60 text-sm font-mono disabled:opacity-60 focus:outline-none focus:border-cx-accent/40"
                />
                <p className="text-2xs text-cx-fgDim mt-1">Stored as custom_{form.tool_id || '…'}</p>
              </div>
              <div>
                <label className="text-2xs uppercase tracking-wider text-cx-fgDim">Display label</label>
                <input
                  value={form.label}
                  onChange={(e) => setForm((f) => ({ ...f, label: e.target.value }))}
                  required
                  placeholder="Acme QSAR v3"
                  className="mt-1 w-full px-3 py-2 rounded-xl border border-cx-border bg-white/60 text-sm focus:outline-none focus:border-cx-accent/40"
                />
              </div>
            </div>

            <div>
              <label className="text-2xs uppercase tracking-wider text-cx-fgDim">Tool role</label>
              <select
                value={form.role_id}
                onChange={(e) => setForm((f) => ({ ...f, role_id: e.target.value }))}
                className="mt-1 w-full px-3 py-2 rounded-xl border border-cx-border bg-white/60 text-sm focus:outline-none focus:border-cx-accent/40"
              >
                {roles.map((r) => (
                  <option key={r.id} value={r.id}>{r.label}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="text-2xs uppercase tracking-wider text-cx-fgDim">Endpoint URL</label>
              <input
                value={form.endpoint_url}
                onChange={(e) => setForm((f) => ({ ...f, endpoint_url: e.target.value }))}
                required
                placeholder="https://tools.yourcompany.com/api/predict"
                className="mt-1 w-full px-3 py-2 rounded-xl border border-cx-border bg-white/60 text-sm font-mono focus:outline-none focus:border-cx-accent/40"
              />
            </div>

            <div className="grid sm:grid-cols-2 gap-3">
              <div>
                <label className="text-2xs uppercase tracking-wider text-cx-fgDim">HTTP method</label>
                <select
                  value={form.http_method}
                  onChange={(e) => setForm((f) => ({ ...f, http_method: e.target.value }))}
                  className="mt-1 w-full px-3 py-2 rounded-xl border border-cx-border bg-white/60 text-sm focus:outline-none focus:border-cx-accent/40"
                >
                  {HTTP_METHODS.map((m) => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-2xs uppercase tracking-wider text-cx-fgDim">Auth type</label>
                <select
                  value={form.auth_type}
                  onChange={(e) => setForm((f) => ({ ...f, auth_type: e.target.value }))}
                  className="mt-1 w-full px-3 py-2 rounded-xl border border-cx-border bg-white/60 text-sm focus:outline-none focus:border-cx-accent/40"
                >
                  {AUTH_TYPES.map((a) => (
                    <option key={a.value} value={a.value}>{a.label}</option>
                  ))}
                </select>
              </div>
            </div>

            {form.auth_type === 'api_key_header' && (
              <div>
                <label className="text-2xs uppercase tracking-wider text-cx-fgDim">Auth header name</label>
                <input
                  value={form.auth_header_name}
                  onChange={(e) => setForm((f) => ({ ...f, auth_header_name: e.target.value }))}
                  className="mt-1 w-full px-3 py-2 rounded-xl border border-cx-border bg-white/60 text-sm font-mono focus:outline-none focus:border-cx-accent/40"
                />
              </div>
            )}

            {form.auth_type !== 'none' && (
              <div>
                <label className="text-2xs uppercase tracking-wider text-cx-fgDim">
                  {form.auth_type === 'bearer' ? 'Bearer token' : 'API key'}
                  {editingId && ' (leave blank to keep existing)'}
                </label>
                <input
                  type="password"
                  value={form.auth_secret}
                  onChange={(e) => setForm((f) => ({ ...f, auth_secret: e.target.value }))}
                  required={!editingId && form.auth_type !== 'none'}
                  className="mt-1 w-full px-3 py-2 rounded-xl border border-cx-border bg-white/60 text-sm font-mono focus:outline-none focus:border-cx-accent/40"
                />
              </div>
            )}

            <div>
              <label className="text-2xs uppercase tracking-wider text-cx-fgDim">Description</label>
              <textarea
                value={form.description}
                onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                rows={2}
                placeholder="Internal ADMET model served on VPC"
                className="mt-1 w-full px-3 py-2 rounded-xl border border-cx-border bg-white/60 text-sm resize-y focus:outline-none focus:border-cx-accent/40"
              />
            </div>

            <div>
              <label className="text-2xs uppercase tracking-wider text-cx-fgDim">Request template (JSON)</label>
              <textarea
                value={form.request_template}
                onChange={(e) => setForm((f) => ({ ...f, request_template: e.target.value }))}
                rows={4}
                className="mt-1 w-full px-3 py-2 rounded-xl border border-cx-border bg-white/60 text-xs font-mono resize-y focus:outline-none focus:border-cx-accent/40"
              />
              <p className="text-2xs text-cx-fgDim mt-1">
                Merged with agent context (query, compounds, SMILES). For ADMET tools, return JSON with a
                {' '}
                <code className="text-cx-accent">predictions</code>
                {' '}
                array.
              </p>
            </div>

            <div className="flex gap-2">
              <button
                type="submit"
                disabled={creating}
                className="flex-1 py-2.5 rounded-xl text-sm font-medium border border-cx-accent/30 bg-cx-accent/5 text-cx-accent hover:bg-cx-accent/10 disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {creating ? <Loader2 size={16} className="animate-spin" /> : <FlaskConical size={16} />}
                {creating ? 'Saving…' : editingId ? 'Update tool' : 'Register tool'}
              </button>
              {editingId && (
                <button
                  type="button"
                  onClick={resetForm}
                  className="px-4 py-2.5 rounded-xl text-sm border border-cx-border text-cx-fgMuted hover:text-cx-fg"
                >
                  Cancel
                </button>
              )}
            </div>
          </form>
        </GlassPanel>

        <GlassPanel>
          <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim mb-4">
            Registered tools ({tools.length})
          </p>
          <div className="space-y-2 max-h-[520px] overflow-y-auto pr-1">
            {tools.length === 0 && (
              <p className="text-sm text-cx-fgMuted p-4 rounded-xl border border-dashed border-cx-border">
                No custom tools yet. Register your first integration to extend the Tool Fabric.
              </p>
            )}
            {tools.map((tool) => {
              const isDeleting = deletingId === tool.id;
              const isTesting = testingId === tool.id;
              const showTest = testResult?.toolId === tool.id;
              return (
                <div
                  key={tool.id}
                  className={`p-3 rounded-xl border bg-white/40 ${
                    editingId === tool.id ? 'border-cx-accent/30' : 'border-cx-border'
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-sm font-medium truncate">{tool.label}</p>
                      <p className="text-2xs font-mono text-cx-fgDim">{tool.tool_id}</p>
                      <p className="text-2xs text-cx-fgMuted mt-1">{tool.role_label || tool.role_id}</p>
                      <p className="text-2xs text-cx-fgDim truncate mt-0.5">{tool.endpoint_url}</p>
                    </div>
                    <div className="shrink-0 flex flex-col items-end gap-1">
                      <span className={`text-2xs px-2 py-0.5 rounded-full border capitalize ${
                        tool.status === 'active'
                          ? 'border-cx-success/30 text-cx-success'
                          : 'border-cx-border text-cx-fgDim'
                      }`}
                      >
                        {tool.status}
                      </span>
                      {tool.auth_secret_configured && (
                        <span className="text-2xs text-cx-fgDim">Auth configured</span>
                      )}
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2 mt-3">
                    <button
                      type="button"
                      onClick={() => handleEdit(tool)}
                      className="text-2xs px-2 py-1 rounded-lg border border-cx-border hover:border-cx-accent/30"
                    >
                      Edit
                    </button>
                    <button
                      type="button"
                      onClick={() => handleTest(tool)}
                      disabled={isTesting}
                      className="text-2xs px-2 py-1 rounded-lg border border-cx-border hover:border-cx-accent/30 inline-flex items-center gap-1"
                    >
                      {isTesting ? <Loader2 size={10} className="animate-spin" /> : <Zap size={10} />}
                      Test
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDelete(tool)}
                      disabled={isDeleting}
                      className="text-2xs px-2 py-1 rounded-lg border border-cx-danger/30 text-cx-danger hover:bg-cx-danger/5 inline-flex items-center gap-1"
                    >
                      {isDeleting ? <Loader2 size={10} className="animate-spin" /> : <Trash2 size={10} />}
                      Delete
                    </button>
                  </div>
                  {showTest && (
                    <div className={`mt-2 p-2 rounded-lg text-2xs border ${
                      testResult.ok
                        ? 'border-cx-success/30 bg-cx-success/5 text-cx-success'
                        : 'border-cx-danger/30 bg-cx-danger/5 text-cx-danger'
                    }`}
                    >
                      {testResult.ok ? (
                        <span className="inline-flex items-center gap-1">
                          <CheckCircle size={12} />
                          HTTP {testResult.status_code} · {testResult.latency_ms}ms
                        </span>
                      ) : (
                        testResult.error
                      )}
                      {testResult.response_preview && (
                        <pre className="mt-1 text-cx-fgDim whitespace-pre-wrap break-all max-h-20 overflow-y-auto">
                          {testResult.response_preview}
                        </pre>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </GlassPanel>
      </div>
    </div>
  );
}
