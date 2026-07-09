import React, { createContext, useContext, useState, useEffect, useRef, useCallback } from 'react';
import { toast } from 'sonner';
import { api, WS_URL } from '@/lib/api';

const AppContext = createContext(null);
export const useApp = () => useContext(AppContext);

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

  // WebSocket live connection
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
    api.get('/branding').then((r) => setBranding((b) => ({ ...b, ...r.data }))).catch(() => {});
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
      machineUpdates, liveFeed, branding,
      drawerMachineId, openMachine: setDrawerMachineId, closeMachine: () => setDrawerMachineId(null),
    }}>
      {children}
    </AppContext.Provider>
  );
}
