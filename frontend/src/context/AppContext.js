import React, { createContext, useContext, useState, useEffect, useRef, useCallback } from 'react';
import { toast } from 'sonner';
import { api, WS_URL } from '@/lib/api';

const AppContext = createContext(null);
export const useApp = () => useContext(AppContext);

// Apply the admin-configured brand accent (hex) as runtime CSS variables so the
// entire neon accent system (borders, buttons, glows, charts) re-themes instantly.
export function applyAccent(hex) {
  if (!/^#[0-9a-fA-F]{6}$/.test(hex || '')) return;
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  const r1 = r / 255, g1 = g / 255, b1 = b / 255;
  const max = Math.max(r1, g1, b1), min = Math.min(r1, g1, b1);
  let h = 0, s = 0;
  const l = (max + min) / 2;
  if (max !== min) {
    const d = max - min;
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    if (max === r1) h = (g1 - b1) / d + (g1 < b1 ? 6 : 0);
    else if (max === g1) h = (b1 - r1) / d + 2;
    else h = (r1 - g1) / d + 4;
    h *= 60;
  }
  const hsl = `${Math.round(h)} ${Math.round(s * 100)}% ${Math.round(l * 100)}%`;
  const root = document.documentElement.style;
  root.setProperty('--primary', hsl);
  root.setProperty('--accent', hsl);
  root.setProperty('--ring', hsl);
  root.setProperty('--neon-cyan', hsl);
  root.setProperty('--chart-1', hsl);
  root.setProperty('--status-repair', hsl);
  root.setProperty('--accent-rgb', `${r}, ${g}, ${b}`);
}

export function AppProvider({ children }) {
  const [user, setUser] = useState(() => {
    try { return JSON.parse(localStorage.getItem('fops_user')); } catch { return null; }
  });
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [machineUpdates, setMachineUpdates] = useState({});
  const [liveFeed, setLiveFeed] = useState([]);
  const [drawerMachineId, setDrawerMachineId] = useState(null);
  const [branding, setBranding] = useState({ app_name: 'ForgeOps', plant_name: '' });
  const [uiPrefs, setUiPrefs] = useState({});
  const wsRef = useRef(null);
  const reconnectRef = useRef(null);

  const login = async (username, password) => {
    const res = await api.post('/auth/login', { username, password });
    localStorage.setItem('fops_token', res.data.token);
    localStorage.setItem('fops_user', JSON.stringify(res.data.user));
    setUser(res.data.user);
    return res.data.user;
  };

  const logout = useCallback(() => {
    localStorage.removeItem('fops_token');
    localStorage.removeItem('fops_user');
    setUser(null);
    if (wsRef.current) { try { wsRef.current.close(); } catch {} }
    window.location.href = '/login';
  }, []);

  const refreshNotifications = useCallback(async () => {
    try {
      const res = await api.get('/notifications?limit=50');
      setNotifications(res.data);
      const uname = JSON.parse(localStorage.getItem('fops_user') || '{}')?.username;
      setUnreadCount(res.data.filter((n) => !(n.read_by || []).includes(uname)).length);
    } catch {}
  }, []);

  const refreshBranding = useCallback(async () => {
    try {
      const res = await api.get('/branding');
      setBranding((b) => ({ ...b, ...res.data }));
      if (res.data.accent) applyAccent(res.data.accent);
    } catch {}
  }, []);

  const saveUiPrefs = useCallback(async (prefs) => {
    setUiPrefs((p) => ({ ...p, ...prefs }));
    try {
      const res = await api.put('/users/me/ui-prefs', prefs);
      setUiPrefs(res.data || {});
    } catch {}
  }, []);

  // Branding applies even on the login screen
  useEffect(() => { refreshBranding(); }, [refreshBranding]);

  // WebSocket live connection + per-user prefs
  useEffect(() => {
    if (!user) return undefined;
    let closed = false;
    const connect = () => {
      const token = localStorage.getItem('fops_token');
      if (!token) return;
      const ws = new WebSocket(`${WS_URL}?token=${token}`);
      wsRef.current = ws;
      ws.onmessage = (evt) => {
        try {
          const msg = JSON.parse(evt.data);
          if (msg.type === 'notification') {
            const n = msg.data;
            setNotifications((prev) => [n, ...prev].slice(0, 100));
            setUnreadCount((c) => c + 1);
            const fn = n.severity === 'critical' ? toast.error : n.severity === 'warning' ? toast.warning : n.severity === 'success' ? toast.success : toast.info;
            fn(n.title, { description: n.message });
          } else if (msg.type === 'machine_update') {
            setMachineUpdates((prev) => ({ ...prev, [msg.data.id]: msg.data }));
          } else if (msg.type === 'timeline_event') {
            setLiveFeed((prev) => [msg.data, ...prev].slice(0, 50));
          }
        } catch {}
      };
      ws.onclose = () => {
        if (!closed) reconnectRef.current = setTimeout(connect, 3000);
      };
    };
    connect();
    refreshNotifications();
    api.get('/users/me/ui-prefs').then((r) => setUiPrefs(r.data || {})).catch(() => {});
    return () => {
      closed = true;
      clearTimeout(reconnectRef.current);
      if (wsRef.current) { try { wsRef.current.close(); } catch {} }
    };
  }, [user, refreshNotifications]);

  const markAllRead = async () => {
    try {
      await api.put('/notifications/read-all');
      setUnreadCount(0);
      refreshNotifications();
    } catch {}
  };

  const isAdmin = user?.role === 'admin';
  const isTech = user?.role === 'technician' || isAdmin;

  return (
    <AppContext.Provider value={{
      user, login, logout, isAdmin, isTech,
      notifications, unreadCount, markAllRead, refreshNotifications,
      machineUpdates, liveFeed, branding, refreshBranding,
      uiPrefs, saveUiPrefs,
      drawerMachineId, openMachine: setDrawerMachineId, closeMachine: () => setDrawerMachineId(null),
    }}>
      {children}
    </AppContext.Provider>
  );
}
