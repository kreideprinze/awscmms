import React, { useEffect, useMemo, useState, useCallback } from 'react';
import { ChevronDown, ChevronRight, Gauge } from 'lucide-react';
import { api } from '@/lib/api';

const WINDOWS = [
  { key: 8, label: 'Shift (8h)' },
  { key: 24, label: 'Day (24h)' },
  { key: 168, label: 'Week (7d)' },
];

export function fmtDowntime(mins) {
  if (mins == null) return '—';
  const m = Math.round(mins);
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  return `${h}h ${String(m % 60).padStart(2, '0')}m`;
}

function availColor(a) {
  if (a == null) return 'text-muted-foreground';
  if (a >= 95) return 'text-[#05ffa1]';
  if (a >= 85) return 'text-[#f9f871]';
  return 'text-[#ff2e63]';
}

function availGlow(a) {
  if (a == null) return {};
  if (a >= 95) return { textShadow: '0 0 8px rgba(5,255,161,0.4)' };
  if (a >= 85) return { textShadow: '0 0 8px rgba(249,248,113,0.4)' };
  return { textShadow: '0 0 8px rgba(255,46,99,0.5)' };
}

// Primary Control Room ribbon: availability + downtime per Line, expandable to
// per-Section (process group) breakdown. This is the primary at-a-glance info.
export function LineKpiRibbon({ onSelectLine, refreshSignal }) {
  const [data, setData] = useState(null);
  const [windowH, setWindowH] = useState(24);
  const [expandedLine, setExpandedLine] = useState(null);

  const load = useCallback(async () => {
    try {
      const res = await api.get(`/control-room/line-kpis?hours=${windowH}`);
      setData(res.data);
    } catch {}
  }, [windowH]);

  useEffect(() => {
    load();
    const iv = setInterval(load, 60000);
    return () => clearInterval(iv);
  }, [load, refreshSignal]);

  const expanded = useMemo(
    () => data?.lines?.find((l) => l.line === expandedLine) || null,
    [data, expandedLine],
  );

  return (
    <div data-testid="line-kpi-ribbon">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <span className="flex items-center gap-1.5 font-mono text-[10px] font-semibold uppercase tracking-[0.25em] text-muted-foreground">
          <Gauge className="h-3.5 w-3.5 text-[hsl(var(--primary))]" /> Line Availability · Downtime
        </span>
        <div className="ml-auto flex items-center gap-1">
          {WINDOWS.map((w) => (
            <button
              key={w.key}
              data-testid={`kpi-window-${w.key}`}
              onClick={() => setWindowH(w.key)}
              className={`cyber-chamfer-sm border px-2.5 py-0.5 font-mono text-[10px] uppercase tracking-wide transition-colors ${
                windowH === w.key
                  ? 'power-on border-[hsl(var(--primary))] bg-transparent text-[hsl(var(--primary))] shadow-[0_0_8px_rgba(var(--accent-rgb),0.25)]'
                  : 'border-border bg-transparent text-muted-foreground hover:border-muted-foreground hover:text-foreground'
              }`}
            >
              {w.label}
            </button>
          ))}
        </div>
      </div>

      {/* Line cards */}
      <div className="flex gap-2 overflow-x-auto pb-1">
        {!data && <div className="cyber-loading w-full" />}
        {data?.lines?.map((l) => {
          const isOpen = expandedLine === l.line;
          return (
            <button
              key={l.line}
              data-testid={`line-kpi-${l.line.replace(/\s+/g, '-')}`}
              onClick={() => setExpandedLine(isOpen ? null : l.line)}
              className={`cyber-chamfer-sm min-w-[170px] shrink-0 border bg-transparent px-3 py-2 text-left transition-all duration-150 ${
                isOpen
                  ? 'border-[hsl(var(--primary))] shadow-[0_0_12px_rgba(var(--accent-rgb),0.2)]'
                  : 'border-border hover:border-[hsl(var(--primary))]/60'
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs font-bold uppercase tracking-[0.15em]">{l.line}</span>
                <span className="flex items-center gap-1 font-mono text-[9px] text-muted-foreground">
                  {l.failed > 0 && <span className="text-[#ff2e63]" style={{ textShadow: '0 0 6px rgba(255,46,99,0.5)' }}>{l.failed}▼</span>}
                  {isOpen ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                </span>
              </div>
              <div className="mt-1 flex items-baseline gap-2">
                <span data-testid={`line-avail-${l.line.replace(/\s+/g, '-')}`} className={`font-mono text-xl tabular-nums ${availColor(l.availability)}`} style={availGlow(l.availability)}>
                  {l.availability != null ? `${l.availability}%` : '—'}
                </span>
                <span className="font-mono text-[10px] tabular-nums text-muted-foreground" title="Total downtime in window">
                  {fmtDowntime(l.downtime_minutes)} down
                </span>
              </div>
              <div className="mt-0.5 font-mono text-[9px] uppercase tracking-wide text-muted-foreground">
                {l.department} · {l.machines} mach · {l.running} run
              </div>
            </button>
          );
        })}
      </div>

      {/* Expanded: per-section breakdown */}
      {expanded && (
        <div className="mt-2 border border-[hsl(var(--primary))]/30 bg-transparent p-3" data-testid="section-kpi-panel">
          <div className="mb-2 flex items-center justify-between">
            <span className="font-mono text-[10px] font-semibold uppercase tracking-[0.25em] text-[hsl(var(--primary))]">
              {expanded.line} — Sections ({fmtDowntime(expanded.downtime_minutes)} total down)
            </span>
            <button
              data-testid="section-filter-twin"
              onClick={() => onSelectLine && onSelectLine(expanded.line)}
              className="cyber-chamfer-sm border border-border bg-transparent px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide text-muted-foreground transition-colors hover:border-[hsl(var(--primary))] hover:text-[hsl(var(--primary))]"
            >
              Filter twin to {expanded.line}
            </button>
          </div>
          <div className="grid grid-cols-2 gap-1.5 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
            {expanded.sections.map((s) => (
              <div
                key={s.process_group}
                data-testid={`section-kpi-${s.process_group.replace(/\s+/g, '-')}`}
                className={`border bg-transparent px-2.5 py-1.5 ${s.downtime_minutes > 0 ? 'border-[#ff2e63]/40' : 'border-border/60'}`}
              >
                <div className="truncate text-[10px] font-semibold uppercase tracking-wide text-muted-foreground" title={s.process_group}>{s.process_group}</div>
                <div className="flex items-baseline justify-between gap-1">
                  <span className={`font-mono text-sm tabular-nums ${availColor(s.availability)}`}>{s.availability != null ? `${s.availability}%` : '—'}</span>
                  <span className={`font-mono text-[9px] tabular-nums ${s.downtime_minutes > 0 ? 'text-[#ff2e63]' : 'text-muted-foreground'}`}>{fmtDowntime(s.downtime_minutes)}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
