import axios from 'axios';

const BASE = '/api/v1';

export const fetchHealth  = () => axios.get('/health').then(r => r.data);
export const fetchMetrics = () => axios.get(`${BASE}/metrics`).then(r => r.data);
export const fetchDrift   = (agentType) => axios.get(`${BASE}/drift`, { params: agentType ? { agent_type: agentType } : {} }).then(r => r.data);
export const fetchErrors  = (category)  => axios.get(`${BASE}/errors`, { params: category ? { category } : {} }).then(r => r.data);
export const fetchErrorsByCategory = (category) => axios.get(`${BASE}/errors/${category}`).then(r => r.data);
export const sendQuery    = (query, agentType) => axios.post(`${BASE}/query`, { query, agent_type: agentType }).then(r => r.data);
