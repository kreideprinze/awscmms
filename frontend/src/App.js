import React from 'react';
import '@/App.css';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from '@/components/ui/sonner';
import { AppProvider, useApp } from '@/context/AppContext';
import { Layout } from '@/components/Layout';
import Login from '@/pages/Login';
import ControlRoom from '@/pages/ControlRoom';
import Breakdowns from '@/pages/Breakdowns';
import WorkOrders from '@/pages/WorkOrders';
import PreventiveMaintenance from '@/pages/PreventiveMaintenance';
import ClosePMTask from '@/pages/ClosePMTask';
import Analytics from '@/pages/Analytics';
import Runtime from '@/pages/Runtime';
import Inventory from '@/pages/Inventory';
import Administration from '@/pages/Administration';
import AWSPage from '@/pages/AWSPage';

function Protected({ children, roles }) {
  const { user } = useApp();
  if (!user) return <Navigate to="/login" replace />;
  if (roles && !roles.includes(user.role)) return <Navigate to="/" replace />;
  return <Layout>{children}</Layout>;
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<Protected><ControlRoom /></Protected>} />
      <Route path="/breakdowns" element={<Protected><Breakdowns /></Protected>} />
      <Route path="/work-orders" element={<Protected roles={['admin', 'technician']}><WorkOrders /></Protected>} />
      <Route path="/preventive-maintenance" element={<Protected roles={['admin', 'technician']}><PreventiveMaintenance /></Protected>} />
      <Route path="/preventive-maintenance/close/:taskId" element={<Protected roles={['admin', 'technician']}><ClosePMTask /></Protected>} />
      <Route path="/analytics" element={<Protected><Analytics /></Protected>} />
      <Route path="/runtime" element={<Protected><Runtime /></Protected>} />
      <Route path="/inventory" element={<Protected roles={['admin', 'technician']}><Inventory /></Protected>} />
      <Route path="/administration" element={<Protected roles={['admin']}><Administration /></Protected>} />
      <Route path="/aws" element={<Protected roles={['admin', 'technician']}><AWSPage /></Protected>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

function App() {
  return (
    <AppProvider>
      <BrowserRouter>
        <AppRoutes />
        <Toaster position="top-right" richColors closeButton theme="dark" />
      </BrowserRouter>
    </AppProvider>
  );
}

export default App;
