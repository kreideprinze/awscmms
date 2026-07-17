import React, { useEffect, useMemo, useState, useRef } from 'react';
import { NavLink, useSearchParams, useNavigate } from 'react-router-dom';
import {
  Radar, ClipboardList, CalendarCheck, BarChart3, Timer, Package, Settings2, ClipboardCheck,
  Bell, LogOut, Pin, PinOff, Factory, Paintbrush, GripVertical, Check,
} from 'lucide-react';
import { useApp } from '@/context/AppContext';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { fmtDate, CrackedGear, EwacsIcon } from '@/components/StatusBits';
import { MachineDrawer } from '@/components/MachineDrawer';
import { WorkOrderModal } from '@/components/WorkOrderModal';

const MODULES = [
  { key: 'control-room', path: '/', label: 'Control Room', icon: Radar, roles: ['admin', 'technician', 'operator'] },
  { key: 'breakdowns', path: '/breakdowns', label: 'Breakdowns', icon: CrackedGear, roles: ['admin', 'technician', 'operator'] },
  { key: 'work-orders', path: '/work-orders', label: 'Work Orders', icon: ClipboardList, roles: ['admin', 'technician'] },
  { key: 'pm', path: '/preventive-maintenance', label: 'Preventive Maintenance', icon: CalendarCheck, roles: ['admin', 'technician'] },
  { key: 'am', path: '/am-checklists', label: 'AM Checklists', icon: ClipboardCheck, roles: ['admin', 'technician', 'operator'] },
  { key: 'analytics', path: '/analytics', label: 'Analytics', icon: BarChart3, roles: ['admin', 'technician', 'operator'] },
  { key: 'runtime', path: '/runtime', label: 'Runtime', icon: Timer, roles: ['admin', 'technician', 'operator'] },
  { key: 'inventory', path: '/inventory', label: 'Inventory (Spares)', icon: Package, roles: ['admin', 'technician'] },
  { key: 'admin', path: '/administration', label: 'Administration', icon: Settings2, roles: ['admin'] },
  { key: 'aws', path: '/aws', label: 'eWACS-90', icon: EwacsIcon, roles: ['admin', 'technician'] },
];

const SEVERITY_CLS = {
  critical: 'border-l-[#ff2e63]',
  warning: 'border-l-[#f9f871]',
  success: 'border-l-[#05ffa1]',
  info: 'border-l-[hsl(var(--primary))]',
};

export function Layout({ children }) {
  const { user, logout, unreadCount, notifications, markAllRead, branding, openMachine, openWorkOrder, isTech, uiPrefs, saveUiPrefs } = useApp();
  const [pinned, setPinned] = useState(false);
  const [hovered, setHovered] = useState(false);
  const [customizing, setCustomizing] = useState(false);
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const dragKey = useRef(null);
  const expanded = pinned || hovered || customizing;

  // Universal deep-link: any URL carrying ?wo=<id> opens the exact Work Order popout
  useEffect(() => {
    const woId = searchParams.get('wo');
    if (woId && isTech) {
      openWorkOrder(woId);
      const next = new URLSearchParams(searchParams);
      next.delete('wo');
      setSearchParams(next, { replace: true });
    }
  }, [searchParams, isTech, openWorkOrder, setSearchParams]);

  // Apply per-user order, then append any modules not in the saved order
  const ordered = useMemo(() => {
    const visible = MODULES.filter((m) => m.roles.includes(user?.role));
    const order = uiPrefs?.sidebar_order || [];
    if (!order.length) return visible;
    const byKey = Object.fromEntries(visible.map((m) => [m.key, m]));
    const sorted = order.map((k) => byKey[k]).filter(Boolean);
    for (const m of visible) if (!order.includes(m.key)) sorted.push(m);
    return sorted;
  }, [user, uiPrefs]);

  const iconColors = uiPrefs?.icon_colors || {};

  const onDrop = (targetKey) => {
    const src = dragKey.current;
    dragKey.current = null;
    if (!src || src === targetKey) return;
    const keys = ordered.map((m) => m.key);
    const from = keys.indexOf(src);
    const to = keys.indexOf(targetKey);
    if (from === -1 || to === -1) return;
    keys.splice(to, 0, keys.splice(from, 1)[0]);
    saveUiPrefs({ sidebar_order: keys });
  };

  const setColor = (key, color) => {
    saveUiPrefs({ icon_colors: { ...iconColors, [key]: color } });
  };

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
          {branding.logo_data ? (
            <img src={branding.logo_data} alt="logo" data-testid="app-logo-custom" className="h-7 w-7 shrink-0 object-contain" />
          ) : (
            <Factory data-testid="app-logo-default" className="h-6 w-6 shrink-0 text-[hsl(var(--primary))]" />
          )}
          {expanded && (
            <div className="overflow-hidden">
              <div className="truncate text-sm font-semibold tracking-wide">{branding.app_name || 'ForgeOps'}</div>
              <div className="truncate text-[10px] uppercase tracking-widest text-muted-foreground">Factory Operations</div>
            </div>
          )}
        </div>
        <nav className="flex-1 space-y-1 overflow-y-auto px-2 py-3">
          {ordered.map((m) => {
            const color = iconColors[m.key];
            return (
              <div
                key={m.key}
                draggable={customizing}
                onDragStart={() => { dragKey.current = m.key; }}
                onDragOver={(e) => customizing && e.preventDefault()}
                onDrop={() => customizing && onDrop(m.key)}
                className={customizing ? 'cursor-grab active:cursor-grabbing' : ''}
              >
                <NavLink
                  to={m.path}
                  data-testid={`sidebar-nav-item-${m.key}`}
                  onClick={(e) => customizing && e.preventDefault()}
                  className={({ isActive }) =>
                    `flex items-center gap-3 border border-transparent px-2.5 py-2 text-sm transition-colors ${
                      isActive && !customizing
                        ? 'border-l-2 border-l-[hsl(var(--primary))] text-foreground'
                        : 'text-muted-foreground hover:border-border hover:text-foreground'
                    }`
                  }
                >
                  {customizing && <GripVertical className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />}
                  <m.icon className="h-[18px] w-[18px] shrink-0" style={color ? { color } : undefined} />
                  {expanded && <span className="truncate" style={color ? { color } : undefined}>{m.label}</span>}
                  {customizing && expanded && (
                    <input
                      type="color"
                      value={color || '#00fff5'}
                      data-testid={`sidebar-color-${m.key}`}
                      onClick={(e) => e.stopPropagation()}
                      onChange={(e) => setColor(m.key, e.target.value)}
                      className="ml-auto h-5 w-6 shrink-0 cursor-pointer border-0 bg-transparent p-0"
                      title={`Icon color for ${m.label}`}
                    />
                  )}
                </NavLink>
              </div>
            );
          })}
        </nav>
        <div className="space-y-1 border-t border-border p-2">
          <button
            data-testid="sidebar-customize-toggle"
            onClick={() => setCustomizing(!customizing)}
            className={`flex w-full items-center gap-3 border border-transparent px-2.5 py-2 text-sm transition-colors ${customizing ? 'border-[hsl(var(--primary))]/60 text-[hsl(var(--primary))]' : 'text-muted-foreground hover:border-border hover:text-foreground'}`}
            title="Customize sidebar: drag to reorder, pick icon colors"
          >
            {customizing ? <Check className="h-[18px] w-[18px] shrink-0" /> : <Paintbrush className="h-[18px] w-[18px] shrink-0" />}
            {expanded && <span>{customizing ? 'Done customizing' : 'Customize sidebar'}</span>}
          </button>
          <button
            data-testid="sidebar-collapse-toggle"
            onClick={() => setPinned(!pinned)}
            className="flex w-full items-center gap-3 border border-transparent px-2.5 py-2 text-sm text-muted-foreground transition-colors hover:border-border hover:text-foreground"
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
            <span className="hidden items-center gap-1.5 rounded-full border border-[#05ffa1]/40 bg-transparent px-2 py-0.5 text-[10px] uppercase tracking-wide text-[#05ffa1] sm:flex">
              <span className="h-1.5 w-1.5 rounded-full bg-[#05ffa1] alarm-pulse" /> Live
            </span>
          </div>
          <div className="flex items-center gap-2">
            {/* Notification bell */}
            <Popover>
              <PopoverTrigger asChild>
                <Button variant="ghost" size="icon" data-testid="notification-center-bell" className="relative">
                  <Bell className="h-5 w-5" />
                  {unreadCount > 0 && (
                    <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full border border-[#ff2e63] bg-transparent px-1 text-[10px] font-semibold text-[#ff2e63]">
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
                      data-testid={`notification-item-${n.id}`}
                      className={`block w-full border-b border-border/50 border-l-2 px-3 py-2 text-left hover:bg-white/5 ${SEVERITY_CLS[n.severity] || SEVERITY_CLS.info}`}
                      onClick={() => {
                        // Every notification deep-links to ITS exact source record
                        const rid = n.reference_id;
                        if (rid && n.reference_type === 'work_order' && isTech) openWorkOrder(rid);
                        else if (rid && n.reference_type === 'breakdown') navigate(`/breakdowns?bd=${rid}`);
                        else if (rid && n.reference_type === 'warning') navigate(`/breakdowns?warning=${rid}`);
                        else if (rid && n.reference_type === 'pm_task') navigate(`/preventive-maintenance?task=${rid}`);
                        else if (n.machine_id) openMachine(n.machine_id);
                      }}
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
      {/* Universal work-order popout (deep-linkable from anywhere via ?wo=<id>) */}
      <WorkOrderModal />
    </div>
  );
}
