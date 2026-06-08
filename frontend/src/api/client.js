import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('scinova_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  const projectId = localStorage.getItem('scinova_project_id');
  if (projectId) config.headers['X-Project-Id'] = projectId;
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && !error.config?.url?.includes('/auth/login')) {
      localStorage.removeItem('scinova_token');
      localStorage.removeItem('scinova_user');
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  },
);

export default api;

export const getDashboardStats = () => api.get('/dashboard/stats');
export const getDocuments = (params) => api.get('/documents', { params });
export const getEntities = (params) => api.get('/entities', { params });
export const getDataSources = () => api.get('/data-sources');
export const uploadDocument = (formData) => api.post('/ingest/upload', formData, {
  headers: { 'Content-Type': 'multipart/form-data' },
});
export const getIngestionStatus = (jobId) => api.get(`/ingest/status/${jobId}`);
export const retryIngestion = (jobId) => api.post(`/ingest/retry/${jobId}`);
export const getIngestionStages = () => api.get('/ingest/stages');
export const getFabricStats = () => api.get('/fabric/stats');
export const fabricSearch = (data) => api.post('/fabric/search', data);
export const getDocumentChunks = (docId) => api.get(`/documents/${docId}/chunks`);

export const searchGraph = (params) => api.get('/graph/search', { params });
export const getFullGraph = (params) => api.get('/graph/full', { params });
export const getGraphStats = () => api.get('/graph/stats');
export const getNeighborhood = (entityId, params) => api.get(`/graph/neighborhood/${entityId}`, { params });
export const syncGraphToNeo4j = () => api.post('/graph/sync');

export const getAgents = (params) => api.get('/agents', { params });
export const getAgent = (id) => api.get(`/agents/${id}`);
export const runAgent = (id, data) => api.post(`/agents/${id}/run`, data);
export const ragQuery = (data) => api.post('/rag/query', data);
export const getAgentRuns = (id) => api.get(`/agents/${id}/runs`);

export const getWorkflowTemplates = () => api.get('/workflows/templates');
export const getWorkflowPipelines = () => api.get('/workflows/pipelines');
export const runWorkflow = (data) => api.post('/workflows/run', data);
export const getWorkflowStatus = (id) => api.get(`/workflows/${id}/status`);
export const getWorkflowRuns = () => api.get('/workflows/runs');
export const resumeWorkflow = (id, approved = true) => api.post(`/workflows/${id}/resume`, null, { params: { approved } });

export const downloadWorkflowExport = (workflowId, format = 'markdown') =>
  api.get(`/workflows/${workflowId}/export`, { params: { format }, responseType: 'blob' });

export const downloadWorkflowStepExport = (workflowId, stepIndex) =>
  api.get(`/workflows/${workflowId}/steps/${stepIndex}/export`, { params: { format: 'markdown' }, responseType: 'blob' });

function saveBlob(blob, filename) {
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  window.URL.revokeObjectURL(url);
}

export async function triggerWorkflowDownload(workflowId, format = 'markdown') {
  const res = await downloadWorkflowExport(workflowId, format);
  const ext = format === 'json' ? 'json' : 'md';
  const disposition = res.headers['content-disposition'] || '';
  const match = disposition.match(/filename="([^"]+)"/);
  saveBlob(res.data, match?.[1] || `workflow-export.${ext}`);
}

export async function triggerWorkflowStepDownload(workflowId, stepIndex) {
  const res = await downloadWorkflowStepExport(workflowId, stepIndex);
  const disposition = res.headers['content-disposition'] || '';
  const match = disposition.match(/filename="([^"]+)"/);
  saveBlob(res.data, match?.[1] || `workflow-step-${stepIndex + 1}.md`);
}

export const getSLMProfiles = () => api.get('/models/slm');
export const routeModel = (data) => api.post('/models/route', data);
export const evaluateSLM = (data) => api.post('/models/evaluate', data);

export const getAuditEvents = () => api.get('/audit');
export const getRiskAlerts = () => api.get('/risk-alerts');
export const getApprovals = () => api.get('/approvals');
export const processApproval = (data) => api.post('/approval', data);
export const getGxpCheck = () => api.get('/governance/gxp-check');
export const acknowledgeRiskAlert = (id) => api.post(`/risk-alerts/${id}/acknowledge`);

export const getReports = (params) => api.get('/reports', { params });
export const getReport = (id) => api.get(`/reports/${id}`);
export const generateReport = (data) => api.post('/reports/generate', data);
export const updateReportStatus = (id, status) => api.patch(`/reports/${id}/status`, { status });

export const exportScientificReport = (reportId, format = 'markdown') =>
  api.get(`/reports/${reportId}/export`, { params: { format }, responseType: 'blob' });

export async function triggerReportDownload(reportId, format = 'markdown') {
  const res = await exportScientificReport(reportId, format);
  const disposition = res.headers['content-disposition'] || '';
  const match = disposition.match(/filename="([^"]+)"/);
  const ext = format === 'pdf' ? 'pdf' : format === 'docx' ? 'docx' : 'md';
  saveBlob(res.data, match?.[1] || `report.${ext}`);
}
export const getIntegrationsStatus = () => api.get('/integrations/status');

export const getAgentTaskSettings = () => api.get('/settings/agent-tasks');
export const updateAgentTaskSettings = (data) => api.put('/settings/agent-tasks', data);
export const getToolFabricCatalog = () => api.get('/settings/tool-fabric');
export const getAgentToolFabricDefaults = (agentId) => api.get(`/agents/${agentId}/tool-fabric/defaults`);
export const getAgentToolFabricBindings = (agentId) => api.get(`/agents/${agentId}/tool-fabric/bindings`);

export const login = (data) => api.post('/auth/login', data);
export const getMe = () => api.get('/auth/me');

export const getAccountQuotas = () => api.get('/account/quotas');
export const listAdminUsers = () => api.get('/admin/users');
export const createAdminUser = (data) => api.post('/admin/users', data);
export const deleteAdminUser = (userId) => api.delete(`/admin/users/${userId}`);

export const listAdminCustomTools = () => api.get('/admin/tool-fabric');
export const listAdminToolFabricRoles = () => api.get('/admin/tool-fabric/roles');
export const createAdminCustomTool = (data) => api.post('/admin/tool-fabric', data);
export const updateAdminCustomTool = (rowId, data) => api.put(`/admin/tool-fabric/${rowId}`, data);
export const deleteAdminCustomTool = (rowId) => api.delete(`/admin/tool-fabric/${rowId}`);
export const testAdminCustomTool = (rowId, data) => api.post(`/admin/tool-fabric/${rowId}/test`, data);

export const getCollaborationActivity = () => api.get('/collaboration/activity');
export const generateMeetingBrief = (data) => api.post('/collaboration/meeting-brief', data);
export const getDocumentQC = (docId) => api.get(`/documents/${docId}/qc`);
export const getChemoinformaticsStatus = () => api.get('/collaboration/chemoinformatics/status');

export const listProjects = () => api.get('/projects');
export const createProject = (data) => api.post('/projects', data);
export const getProjectMembers = (projectId) => api.get(`/projects/${projectId}/members`);
export const addProjectMember = (projectId, data) => api.post(`/projects/${projectId}/members`, data);

export const getLimsPlates = () => api.get('/integrations/lims/plates');
export const syncLimsPlate = (plateId) => api.post(`/integrations/lims/sync/${encodeURIComponent(plateId)}`);

export const runDocking = (data) => api.post('/chemoinformatics/dock', data);

export const exportMeetingBrief = (reportId, format = 'markdown') =>
  api.get(`/collaboration/meeting-brief/${reportId}/export`, { params: { format }, responseType: 'blob' });

export async function triggerBriefDownload(reportId, format = 'markdown') {
  const res = await exportMeetingBrief(reportId, format);
  const disposition = res.headers['content-disposition'] || '';
  const match = disposition.match(/filename="([^"]+)"/);
  const ext = format === 'pdf' ? 'pdf' : format === 'docx' ? 'docx' : 'md';
  saveBlob(res.data, match?.[1] || `meeting-brief.${ext}`);
}
