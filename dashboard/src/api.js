import axios from 'axios';

const BASE = '/api/v1';

// Create axios instance with interceptors
const api = axios.create();

// Token storage (set from AuthProvider)
let accessToken = null;

export const setAccessToken = (token) => {
  accessToken = token;
};

// Add auth header to requests when token is available
api.interceptors.request.use((config) => {
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }
  return config;
});

// API calls
export const fetchHealth = () => api.get('/health').then(r => r.data);
export const fetchMetrics = (agentType) => api.get(`${BASE}/metrics`, { params: agentType ? { agent_type: agentType } : {} }).then(r => r.data);
export const fetchDrift = (agentType) => api.get(`${BASE}/drift`, { params: agentType ? { agent_type: agentType } : {} }).then(r => r.data);
export const fetchErrors = (category, agentType) => api.get(`${BASE}/errors`, { params: { ...(category ? { category } : {}), ...(agentType ? { agent_type: agentType } : {}) } }).then(r => r.data);
export const fetchErrorsByCategory = (category) => api.get(`${BASE}/errors/${category}`).then(r => r.data);
export const fetchUserInfo = () => api.get(`${BASE}/auth/me`).then(r => r.data);
export const fetchHistory = (limit = 50, agentType) => api.get(`${BASE}/history`, { params: { limit, ...(agentType ? { agent_type: agentType } : {}) } }).then(r => r.data);
export const fetchAlerts = () => api.get(`${BASE}/alerts`).then(r => r.data);
export const fetchRunDetails = (queryId) => api.get(`${BASE}/monitor/runs/${queryId}`).then(r => r.data);

// Dashboard is monitoring-only — queries go directly to agents via SDK
export const sendQuery = () => Promise.resolve({ status: "info", error: "Send queries directly to your agent. SDK handles telemetry automatically." });
export const executeSql = () => Promise.resolve({ status: "error", results: [] });

// Agent management
export const fetchAgents = () => api.get(`${BASE}/agents`).then(r => r.data);
export const registerAgent = (data) => api.post(`${BASE}/agents/register`, data).then(r => r.data);
export const deleteAgent = (agentId) => api.delete(`${BASE}/agents/${agentId}`).then(r => r.data);
export const refreshAgent = (agentId) => api.post(`${BASE}/agents/${agentId}/refresh`).then(r => r.data);
export const regenerateAgentKey = (agentId) => api.post(`${BASE}/agents/${agentId}/regenerate-key`).then(r => r.data);
export const fetchAgentsHealth = () => api.get(`${BASE}/agents/health`).then(r => r.data);
export const retryGroundTruth = (agentId) => api.post(`${BASE}/agents/${agentId}/retry-ground-truth`).then(r => r.data);
export const fetchGroundTruthStatus = (agentId) => api.get(`${BASE}/agents/${agentId}/ground-truth-status`).then(r => r.data);

// Schema Monitoring
export const scanSchemaChanges = (agentId) => api.post(`${BASE}/agents/${agentId}/scan-schema-changes`).then(r => r.data);
export const fetchSchemaChanges = (agentId, limit = 50) => api.get(`${BASE}/agents/${agentId}/schema-changes`, { params: { limit } }).then(r => r.data);
export const fetchSchemaStatus = (agentId) => api.get(`${BASE}/agents/${agentId}/schema-status`).then(r => r.data);

// Data Quality
export const fetchDataQuality = (agentId) => api.get(`${BASE}/agents/${agentId}/data-quality`).then(r => r.data);
export const revalidateDataQuality = (agentId) => api.post(`${BASE}/agents/${agentId}/revalidate`).then(r => r.data);
