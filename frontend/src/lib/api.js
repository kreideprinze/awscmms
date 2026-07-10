import axios from 'axios';

// Backend origin: explicit env var in dev/preview; falls back to same-origin
// in production deployments where nginx serves the app and proxies /api.
const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || window.location.origin;
export const API_BASE = `${BACKEND_URL}/api`;
export const WS_URL = `${BACKEND_URL.replace(/^http/, 'ws')}/api/ws`;

export const api = axios.create({ baseURL: API_BASE });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('fops_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401 && window.location.pathname !== '/login') {
      localStorage.removeItem('fops_token');
      localStorage.removeItem('fops_user');
      window.location.href = '/login';
    }
    return Promise.reject(err);
  }
);

export const errMsg = (e) => e?.response?.data?.detail || e?.message || 'Something went wrong';
