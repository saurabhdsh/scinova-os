import api from './client';

function saveBlob(blob, filename) {
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  window.URL.revokeObjectURL(url);
}

export const getLabOverview = () => api.get('/lab/overview');
export const getLabProtocols = () => api.get('/lab/protocols');
export const createLabProtocol = (data) => api.post('/lab/protocols', data);
export const getLabExperiments = () => api.get('/lab/experiments');
export const getLabExperiment = (id) => api.get(`/lab/experiments/${id}`);
export const createLabPlan = (data) => api.post('/lab/plans', data);
export const approveLabPlan = (planId, data) => api.post(`/lab/plans/${planId}/approve`, data);
export const evaluateReadiness = (experimentId) => api.post(`/lab/experiments/${experimentId}/readiness`);
export const getLabIssues = (experimentId) => api.get(`/lab/experiments/${experimentId}/issues`);
export const resolveLabIssue = (issueId, data) => api.post(`/lab/readiness/${issueId}/resolve`, data);
export const getLabIngestion = (experimentId) => api.get(`/lab/experiments/${experimentId}/ingestion`);
export const compileLabResults = (experimentId) => api.post(`/lab/experiments/${experimentId}/results`);
export const getLabResults = (experimentId) => api.get(`/lab/experiments/${experimentId}/results`);
export const createLabDossier = (experimentId) => api.post(`/lab/experiments/${experimentId}/dossier`);
export const getLabDossier = (dossierId) => api.get(`/lab/dossiers/${dossierId}`);
export const decideLabDossier = (dossierId, data) => api.post(`/lab/dossiers/${dossierId}/decision`, data);
export const getLabWhatIf = (experimentId) => api.get(`/lab/experiments/${experimentId}/what-if`);
export const createFollowUp = (experimentId) => api.post(`/lab/experiments/${experimentId}/follow-up`);
export const getLabStoryline = (experimentId) => api.get(`/lab/experiments/${experimentId}/storyline`);
export const getLabLineage = (entityRef) => api.get(`/lab/graph/lineage/${entityRef}`);
export const queryLabGraph = (data) => api.post('/lab/graph/query', data);
export const searchLabDocuments = (q) => api.get('/lab/documents/search', { params: { q } });
export const lookupOntology = (q) => api.get('/lab/ontology/lookup', { params: { q } });
export const getLabAudit = (entityRef) => api.get(`/lab/audit/${entityRef}`);
export const getLabAgents = () => api.get('/lab/agents');
export const getLabAgentHealth = (agentId) => api.get(`/lab/agents/${agentId}/health`);
export const askLabAssistant = (data) => api.post('/lab/assistant/ask', data);
export const draftLabPlanFromIntent = (data) => api.post('/lab/assistant/draft', data);
export const getLabJob = (jobId) => api.get(`/lab/agents/jobs/${jobId}`);
export const invokeLabAgent = (agentId, data, idempotencyKey) => api.post(`/lab/agents/${agentId}/invoke`, data, {
  headers: idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : {},
});

export const ingestLabFile = (experimentId, file) => {
  const form = new FormData();
  form.append('file', file);
  return api.post(`/lab/experiments/${experimentId}/ingest`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
};

export async function fetchVicellFixtureFile(experimentId) {
  const planned = Boolean(experimentId);
  const response = await api.get(planned ? '/lab/fixtures/vicell-planned.csv' : '/lab/fixtures/vicell-current.csv', {
    params: planned ? { experiment_id: experimentId } : undefined,
    responseType: 'blob',
  });
  return new File(
    [response.data],
    planned ? 'vicell-planned-synthetic.csv' : 'vicell-current-synthetic.csv',
    { type: 'text/csv' },
  );
}

export async function downloadLabDossier(dossierId, format = 'pdf') {
  const response = await api.get(`/lab/dossiers/${dossierId}/export`, {
    params: { format },
    responseType: 'blob',
  });
  saveBlob(response.data, `experiment-dossier.${format}`);
  return response.headers['x-dossier-publishable'];
}

export function labError(error) {
  return error?.response?.data?.message || error?.message || 'Request failed';
}
