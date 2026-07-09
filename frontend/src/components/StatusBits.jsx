import React from 'react';
import { Badge } from '@/components/ui/badge';

export const STATUS_META = {
  running: { label: 'Running', color: 'hsl(var(--status-running))', cls: 'bg-green-500/15 text-green-300 border-green-500/30' },
  watch: { label: 'Watch', color: 'hsl(var(--status-watch))', cls: 'bg-yellow-500/15 text-yellow-200 border-yellow-500/30' },
  inspection_due: { label: 'Inspection Due', color: 'hsl(var(--status-inspection))', cls: 'bg-orange-500/15 text-orange-200 border-orange-500/30' },
  repair: { label: 'Repair', color: 'hsl(var(--status-repair))', cls: 'bg-blue-500/15 text-blue-200 border-blue-500/30' },
  failed: { label: 'Failed', color: 'hsl(var(--status-failed))', cls: 'bg-red-500/15 text-red-300 border-red-500/30' },
  idle: { label: 'Idle', color: 'hsl(var(--status-idle))', cls: 'bg-slate-500/15 text-slate-300 border-slate-500/30' },
};

export const HEALTH_META = {
  healthy: { label: 'Healthy', cls: 'bg-green-500/15 text-green-300 border-green-500/30' },
  watch: { label: 'Watch', cls: 'bg-yellow-500/15 text-yellow-200 border-yellow-500/30' },
  inspection_due: { label: 'Inspection Due', cls: 'bg-orange-500/15 text-orange-200 border-orange-500/30' },
  overdue: { label: 'OVERDUE', cls: 'bg-red-500/15 text-red-300 border-red-500/30' },
};

export const LIFECYCLE_META = {
  OPEN: 'bg-red-500/15 text-red-200 border-red-500/30',
  ASSIGNED: 'bg-blue-500/15 text-blue-200 border-blue-500/30',
  IN_PROGRESS: 'bg-yellow-500/15 text-yellow-100 border-yellow-500/30',
  COMPLETED: 'bg-green-500/15 text-green-200 border-green-500/30',
  CLOSED: 'bg-slate-500/15 text-slate-200 border-slate-500/30',
  PENDING_REVIEW: 'bg-yellow-500/15 text-yellow-100 border-yellow-500/30',
  ACKNOWLEDGED: 'bg-blue-500/15 text-blue-200 border-blue-500/30',
  CONVERTED: 'bg-orange-500/15 text-orange-200 border-orange-500/30',
  DISMISSED: 'bg-slate-500/15 text-slate-200 border-slate-500/30',
};

export const StatusBadge = ({ status }) => {
  const meta = STATUS_META[status] || STATUS_META.idle;
  return <Badge variant="outline" className={`${meta.cls} text-[10px] uppercase tracking-wide`}>{meta.label}</Badge>;
};

export const HealthBadge = ({ health }) => {
  const meta = HEALTH_META[health] || HEALTH_META.healthy;
  return <Badge variant="outline" className={`${meta.cls} text-[10px] uppercase tracking-wide`}>{meta.label}</Badge>;
};

export const LifecycleBadge = ({ status }) => (
  <Badge variant="outline" className={`${LIFECYCLE_META[status] || LIFECYCLE_META.CLOSED} text-[10px] tracking-wide`}>{status}</Badge>
);

export const StatusDot = ({ status, pulse }) => {
  const meta = STATUS_META[status] || STATUS_META.idle;
  return <span className={`inline-block h-2 w-2 rounded-full ${pulse && status === 'failed' ? 'alarm-pulse' : ''}`} style={{ backgroundColor: meta.color }} />;
};

export const fmtDate = (iso) => {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  } catch { return iso; }
};

export const CRIT_META = {
  critical: 'bg-red-500/15 text-red-300 border-red-500/30',
  high: 'bg-orange-500/15 text-orange-200 border-orange-500/30',
  medium: 'bg-blue-500/15 text-blue-200 border-blue-500/30',
  low: 'bg-slate-500/15 text-slate-300 border-slate-500/30',
};

export const CritBadge = ({ level }) => (
  <Badge variant="outline" className={`${CRIT_META[level] || CRIT_META.medium} text-[10px] uppercase`}>{level}</Badge>
);
