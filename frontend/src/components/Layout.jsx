import React, { useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import {
  Radar, Flame, ClipboardList, CalendarCheck, BarChart3, Timer, Package, Settings2, Siren,
  Bell, LogOut, Pin, PinOff, Factory,
} from 'lucide-react';
import { useApp } from '@/context/AppContext';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { fmtDate } from '@/components/StatusBits';
import { MachineDrawer } from '@/components/MachineDrawer';

const MODULES = [
  { key: 'control-room', path: '/', label: 'Control Room', icon: Radar, roles: ['admin', 'technician', 'operator'] },
  { key: 'breakdowns', path: '/breakdowns', label: 'Breakdowns', icon: Flame, roles: ['admin', 'technician', 'operator'] },
  { key: 'work-orders', path: '/work-orders', label: 'Work Orders', icon: ClipboardList, roles: ['admin', 'technician'] },
  { key: 'pm', path: '/preventive-maintenance', label: 'Preventive Maintenance', icon: CalendarCheck, roles: ['admin', 'technician'] },
  { key: 'analytics', path: '/analytics', label: 'Analytics', icon: BarChart3, roles: ['admin', 'technician', 'operator'] },
  { key: 'runtime', path: '/runtime', label: 'Runtime', icon: Timer, roles: ['admin', 'technician', 'operator'] },
  { key: 'inventory', path: '/inventory', label: 'Inventory (Spares)', icon: Package, roles: ['admin', 'technician'] },
  { key: 'admin', path: '/administration', label: 'Administration', icon: Settings2, roles: ['admin'] },
  { key: 'aws', path: '/aws', label: 'AWS — Advance Warning', icon: Siren, roles: ['admin', 'technician'] },
];

const SEVERITY_CLS = {
  critical: 'border-l-red-500',
  warning: 'border-l-yellow-500',
  success: 'border-l-green-500',
  info: 'border-l-[hsl(var(--primary))]',
};

export function Layout({ children }) {
  const { user, logout, unreadCount, notifications, markAllRead, branding, openMachine } = useApp();
  const [pinned, setPinned] = useState(false);
  const [hovered, setHovered] = useState(false);
  const navigate = useNavigate();
  const expanded = pinned || hovered;
  const visible = MODULES.filter((m) => m.roles.includes(user?.role));

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      {/* Sidebar */}
      <aside
        data-testid="app-sidebar"
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        className={`relative z-30 flex flex-col border-r border-border bg-[hsl(var(--panel-1))] transition-[width] duration-200 ${expanded ? 'w-64' : 'w-14'}`}
      >
        <div className="flex h-14 items-center gap-3 border-b border-border px-3">
          <Factory className="h-6 w-6 shrink-0 text-[hsl(var(--primary))]" />
          {expanded && (
            <div className="overflow-hidden">
              <div className="truncate text-sm font-semibold tracking-wide">{branding.app_name || 'ForgeOps'}</div>
              <div className="truncate text-[10px] uppercase tracking-widest text-muted-foreground">Factory Operations</div>
            </div>
          )}
        </div>
        <nav className="flex-1 space-y-1 overflow-y-auto px-2 py-3">
          {visible.map((m) => (
            <NavLink
              key={m.key}
              to={m.path}
              data-testid={`sidebar-nav-item-${m.key}`}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-md px-2.5 py-2 text-sm transition-colors ${
                  isActive
                    ? 'border-l-2 border-[hsl(var(--primary))] bg-[rgba(46,168,255,0.10)] text-foreground'
                    : 'text-muted-foreground hover:bg-white/5 hover:text-foreground'
                }`
              }
            >
              <m.icon className="h-4.5 w-4.5 h-[18px] w-[18px] shrink-0" />
              {expanded && <span className="truncate">{m.label}</span>}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-border p-2">
          <button
            data-testid="sidebar-collapse-toggle"
            onClick={() => setPinned(!pinned)}
            className="flex w-full items-center gap-3 rounded-md px-2.5 py-2 text-sm text-muted-foreground hover:bg-white/5 hover:text-foreground"
          >
            {pinned ? <PinOff className="h-[18px] w-[18px] shrink-0" /> : <Pin className="h-[18px] w-[18px] shrink-0" />}
            {expanded && <span>{pinned ? 'Unpin sidebar' : 'Pin sidebar'}</span>}
          </button>
        </div>
      </aside>

      {/* Main */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center justify-between border-b border-border bg-[hsl(var(--panel-1))] px-4">
          <div className="flex items-center gap-3">
            <span className="text-xs uppercase tracking-widest text-muted-foreground">{branding.plant_name || 'Plant'}</span>
            <span className="hidden items-center gap-1.5 rounded-full border border-green-500/30 bg-green-500/10 px-2 py-0.5 text-[10px] uppercase tracking-wide text-green-300 sm:flex">
              <span className="h-1.5 w-1.5 rounded-full bg-green-400 alarm-pulse" /> Live
            </span>
          </div>
          <div className="flex items-center gap-2">
            {/* Notification bell */}
            <Popover>
              <PopoverTrigger asChild>
                <Button variant="ghost" size="icon" data-testid="notification-center-bell" className="relative">
                  <Bell className="h-5 w-5" />
                  {unreadCount > 0 && (
                    <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-semibold text-white">
                      {unreadCount > 99 ? '99+' : unreadCount}
                    </span>
                  )}
                </Button>
              </PopoverTrigger>
              <PopoverContent align="end" className="w-96 p-0" data-testid="notification-center-panel">
                <div className="flex items-center justify-between border-b border-border px-3 py-2">
                  <span className="text-sm font-semibold">Notifications</span>
                  <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={markAllRead} data-testid="notifications-mark-all-read">Mark all read</Button>
                </div>
                <ScrollArea className="h-96">
                  {notifications.length === 0 && <div className="p-4 text-sm text-muted-foreground">No notifications yet</div>}
                  {notifications.map((n) => (
                    <button
                      key={n.id}
                      className={`block w-full border-b border-border/50 border-l-2 px-3 py-2 text-left hover:bg-white/5 ${SEVERITY_CLS[n.severity] || SEVERITY_CLS.info}`}
                      onClick={() => n.machine_id && openMachine(n.machine_id)}
                    >
                      <div className="text-xs font-semibold">{n.title}</div>
                      <div className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">{n.message}</div>
                      <div className="mt-1 font-mono text-[10px] text-muted-foreground">{fmtDate(n.created_at)}</div>
                    </button>
                  ))}
                </ScrollArea>
              </PopoverContent>
            </Popover>
            <div className="hidden text-right sm:block">
              <div className="text-xs font-semibold">{user?.name}</div>
              <div className="text-[10px] uppercase tracking-wide text-[hsl(var(--primary))]">{user?.role}</div>
            </div>
            <Button variant="ghost" size="icon" onClick={logout} data-testid="logout-button" title="Logout">
              <LogOut className="h-4 w-4" />
            </Button>
          </div>
        </header>
        <main className="min-h-0 flex-1 overflow-y-auto">{children}</main>
      </div>

      {/* Global machine drawer */}
      <MachineDrawer />
    </div>
  );
}
