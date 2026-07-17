import React from 'react';
import { Badge } from '@/components/ui/badge';

// Cracked gear — the platform's breakdown icon (lucide-style 24x24 stroke icon)
/* eWACS-90 module icon — radar sweep with plane silhouette + "90" badge (fallback custom SVG). */
export const EwacsIcon = ({ className = 'h-4 w-4', style }) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
    strokeLinecap="round" strokeLinejoin="round" className={className} style={style} aria-hidden="true">
    {/* radar rings (open at top-right for the badge) */}
    <path d="M20.8 13.5A9 9 0 1 1 10.5 3.2" />
    <path d="M12 7.5a4.5 4.5 0 1 0 4.5 4.5" />
    {/* sweep line */}
    <path d="M12 12 6.6 6.6" />
    <path d="m12 12 3.4 7.2" opacity="0.4" />
    {/* plane silhouette */}
    <path d="m15.2 6.4 3-1.2-1.1 3-1-0.8z" fill="currentColor" strokeWidth="0.6" />
    {/* 90 badge */}
    <text x="19.2" y="6.4" fontSize="6.5" fontFamily="ui-monospace, monospace" fontWeight="bold"
      fill="currentColor" stroke="none" textAnchor="middle">90</text>
  </svg>
);

export const CrackedGear = ({ className = 'h-4 w-4', style }) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
    strokeLinecap="round" strokeLinejoin="round" className={className} style={style} aria-hidden="true">
    <path d="M12 20a8 8 0 1 1 8-8" />
    <path d="M12 2v2" /><path d="M12 20v2" /><path d="m4.93 4.93 1.41 1.41" />
    <path d="m17.66 17.66 1.41 1.41" /><path d="M2 12h2" /><path d="M20 12h2" />
    <path d="m6.34 17.66-1.41 1.41" /><path d="m19.07 4.93-1.41 1.41" />
    {/* crack */}
    <path d="M20 12l-2.5 2.2 1.8 2.4" />
    <path d="M12 9.5a2.5 2.5 0 1 0 2.5 2.5" />
    <path d="M14.5 12 13 10.4l1-1.6" />
  </svg>
);

// Cyberpunk neon status palette — functionally distinct, reskinned from traffic-light colors
export const STATUS_META = {
  running: { label: 'Running', color: '#05ffa1', cls: 'bg-[#05ffa1]/10 text-[#05ffa1] border-[#05ffa1]/40' },
  watch: { label: 'Watch', color: '#f9f871', cls: 'bg-[#f9f871]/10 text-[#f9f871] border-[#f9f871]/40' },
  inspection_due: { label: 'Inspection Due', color: '#ff9e1c', cls: 'bg-[#ff9e1c]/10 text-[#ff9e1c] border-[#ff9e1c]/40' },
  repair: { label: 'Repair', color: '#00fff5', cls: 'bg-[#00fff5]/10 text-[#00fff5] border-[#00fff5]/40' },
  failed: { label: 'Failed', color: '#ff2e63', cls: 'bg-[#ff2e63]/10 text-[#ff2e63] border-[#ff2e63]/40' },
  idle: { label: 'Idle', color: '#7b84a8', cls: 'bg-[#7b84a8]/10 text-[#9aa2c0] border-[#7b84a8]/40' },
};

export const HEALTH_META = {
  healthy: { label: 'Healthy', cls: 'bg-[#05ffa1]/10 text-[#05ffa1] border-[#05ffa1]/40' },
  watch: { label: 'Watch', cls: 'bg-[#f9f871]/10 text-[#f9f871] border-[#f9f871]/40' },
  inspection_due: { label: 'Inspection Due', cls: 'bg-[#ff9e1c]/10 text-[#ff9e1c] border-[#ff9e1c]/40' },
  overdue: { label: 'OVERDUE', cls: 'bg-[#ff2e63]/10 text-[#ff2e63] border-[#ff2e63]/40' },
};

export const LIFECYCLE_META = {
  OPEN: 'bg-[#ff2e63]/10 text-[#ff2e63] border-[#ff2e63]/40',
  ASSIGNED: 'bg-[#00fff5]/10 text-[#00fff5] border-[#00fff5]/40',
  IN_PROGRESS: 'bg-[#f9f871]/10 text-[#f9f871] border-[#f9f871]/40',
  COMPLETED: 'bg-[#05ffa1]/10 text-[#05ffa1] border-[#05ffa1]/40',
  PENDING_ADMIN_CLOSURE: 'bg-[#ff9e1c]/10 text-[#ff9e1c] border-[#ff9e1c]/40',
  CLOSED: 'bg-[#7b84a8]/10 text-[#9aa2c0] border-[#7b84a8]/40',
  PENDING_REVIEW: 'bg-[#f9f871]/10 text-[#f9f871] border-[#f9f871]/40',
  ACKNOWLEDGED: 'bg-[#00fff5]/10 text-[#00fff5] border-[#00fff5]/40',
  CONVERTED: 'bg-[#ff9e1c]/10 text-[#ff9e1c] border-[#ff9e1c]/40',
  DISMISSED: 'bg-[#7b84a8]/10 text-[#9aa2c0] border-[#7b84a8]/40',
};

export const BREAKDOWN_TYPE_META = {
  MECHANICAL: 'bg-[#00fff5]/10 text-[#00fff5] border-[#00fff5]/40',
  ELECTRICAL: 'bg-[#f9f871]/10 text-[#f9f871] border-[#f9f871]/40',
  CONTROL_PLC: 'bg-[#ff2e63]/10 text-[#ff2e63] border-[#ff2e63]/40',
};

export const StatusBadge = ({ status }) => {
  const meta = STATUS_META[status] || STATUS_META.idle;
  return <Badge variant="outline" className={`${meta.cls} text-[10px] uppercase tracking-wider font-mono`}>{meta.label}</Badge>;
};

export const HealthBadge = ({ health }) => {
  const meta = HEALTH_META[health] || HEALTH_META.healthy;
  return <Badge variant="outline" className={`${meta.cls} text-[10px] uppercase tracking-wider font-mono`}>{meta.label}</Badge>;
};

export const LifecycleBadge = ({ status }) => (
  <Badge variant="outline" className={`${LIFECYCLE_META[status] || LIFECYCLE_META.CLOSED} text-[10px] tracking-wider font-mono`}>{status}</Badge>
);

export const TypeBadge = ({ type }) => type ? (
  <Badge variant="outline" className={`${BREAKDOWN_TYPE_META[type] || BREAKDOWN_TYPE_META.MECHANICAL} text-[10px] tracking-wider font-mono`}>{type.replace('_', ' ')}</Badge>
) : null;

export const StatusDot = ({ status, pulse }) => {
  const meta = STATUS_META[status] || STATUS_META.idle;
  return (
    <span
      className={`inline-block h-2 w-2 rounded-full ${pulse && status === 'failed' ? 'alarm-pulse' : ''}`}
      style={{ backgroundColor: meta.color, boxShadow: `0 0 6px ${meta.color}` }}
    />
  );
};

export const fmtDate = (iso) => {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  } catch { return iso; }
};

export const CRIT_META = {
  critical: 'bg-[#ff2e63]/10 text-[#ff2e63] border-[#ff2e63]/40',
  high: 'bg-[#ff9e1c]/10 text-[#ff9e1c] border-[#ff9e1c]/40',
  medium: 'bg-[#00fff5]/10 text-[#00fff5] border-[#00fff5]/40',
  low: 'bg-[#7b84a8]/10 text-[#9aa2c0] border-[#7b84a8]/40',
};

export const CritBadge = ({ level }) => (
  <Badge variant="outline" className={`${CRIT_META[level] || CRIT_META.medium} text-[10px] uppercase tracking-wider font-mono`}>{level}</Badge>
);
