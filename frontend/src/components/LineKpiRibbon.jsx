import React, { useEffect, useMemo, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChevronDown, ChevronRight, Gauge, CalendarRange, X } from 'lucide-react';
import { api } from '@/lib/api';
import { Input } from '@/components/ui/input';

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

// Live HH:MM:SS ticking timer for an active breakdown on a line
function BreakdownTimer({ since }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const iv = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(iv);
  }, []);
  const secs = Math.max(0, Math.floor((now - new Date(since).getTime()) / 1000));
  const h = String(Math.floor(secs / 3600)).padStart(2, '0');
  const m = String(Math.floor((secs % 3600) / 60)).padStart(2, '0');
  const s = String(secs % 60).padStart(2, '0');
  return <span className="font-mono tabular-nums">{h}:{m}:{s}</span>;
}

// Primary Control Room ribbon: availability + downtime per Line, expandable to
// per-Section (process group) breakdown. KPIs only — no narrative text.
export function LineKpiRibbon({ onSelectLine, selectedLine, refreshSignal }) {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [windowH, setWindowH] = useState(24);
  const [customOpen, setCustomOpen] = useState(false);
  const [customRange, setCustomRange] = useState(null); // {from, to} applied
  const [draftFrom, setDraftFrom] = useState('');
  const [draftTo, setDraftTo] = useState('');
  const [expandedLine, setExpandedLine] = useState(null);

  const load = useCallback(async () => {
    try {
      const params = customRange
        ? `date_from=${customRange.from}${customRange.to ? `&date_to=${customRange.to}` : ''}`
        : `hours=${windowH}`;
      const res = await api.get(`/control-room/line-kpis?${params}`);
      setData(res.data);
    } catch {}
  }, [windowH, customRange]);

  useEffect(() => {
    load();
    const iv = setInterval(load, 60000);
    return () => clearInterval(iv);
  }, [load, refreshSignal]);

  const expanded = useMemo(
    () => data?.lines?.find((l) => l.line === expandedLine) || null,
    [data, expandedLine],
  );

  const applyCustom = () => {
    if (!draftFrom) return;
    setCustomRange({ from: draftFrom, to: draftTo || '' });
  };
  const clearCustom = () => {
    setCustomRange(null);
    setCustomOpen(false);
    setDraftFrom('');
    setDraftTo('');
  };

  return (
    <div data-testid="line-kpi-ribbon">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <span className="flex items-center gap-1.5 font-mono text-[10px] font-semibold uppercase tracking-[0.25em] text-muted-foreground">
          <Gauge className="h-3.5 w-3.5 text-[hsl(var(--primary))]" /> Line Availability · Downtime
        </span>
        <div className="ml-auto flex flex-wrap items-center gap-1">
          {WINDOWS.map((w) => (
            <button
              key={w.key}
              data-testid={`kpi-window-${w.key}`}
              onClick={() => { setWindowH(w.key); setCustomRange(null); setCustomOpen(false); }}
              className={`cyber-chamfer-sm border px-2.5 py-0.5 font-mono text-[10px] uppercase tracking-wide transition-colors ${
                !customRange && windowH === w.key
                  ? 'power-on border-[hsl(var(--primary))] bg-transparent text-[hsl(var(--primary))] shadow-[0_0_8px_rgba(var(--accent-rgb),0.25)]'
                  : 'border-border bg-transparent text-muted-foreground hover:border-muted-foreground hover:text-foreground'
              }`}
            >
              {w.label}
            </button>
          ))}
          <button
            data-testid="kpi-window-custom"
            onClick={() => setCustomOpen(!customOpen)}
            className={`cyber-chamfer-sm flex items-center gap-1 border px-2.5 py-0.5 font-mono text-[10px] uppercase tracking-wide transition-colors ${
              customRange
                ? 'power-on border-[hsl(var(--primary))] bg-transparent text-[hsl(var(--primary))] shadow-[0_0_8px_rgba(var(--accent-rgb),0.25)]'
                : 'border-border bg-transparent text-muted-foreground hover:border-muted-foreground hover:text-foreground'
            }`}
          >
            <CalendarRange className="h-3 w-3" />
            {customRange ? `${customRange.from} → ${customRange.to || 'now'}` : 'Custom'}
          </button>
          {customRange && (
            <button data-testid="kpi-window-custom-clear" onClick={clearCustom} title="Clear custom range"
              className="cyber-chamfer-sm border border-border px-1.5 py-0.5 text-muted-foreground transition-colors hover:border-[#ff2e63]/60 hover:text-[#ff2e63]">
              <X className="h-3 w-3" />
            </button>
          )}
        </div>
      </div>

      {/* Custom date range slicer */}
      {customOpen && (
        <div className="mb-2 flex flex-wrap items-end gap-2 border border-[hsl(var(--primary))]/30 bg-transparent p-2" data-testid="kpi-custom-range-panel">
          <div>
            <div className="mb-0.5 font-mono text-[9px] uppercase tracking-widest text-muted-foreground">From</div>
            <Input type="date" data-testid="kpi-custom-from" value={draftFrom} onChange={(e) => setDraftFrom(e.target.value)}
              onClick={(e) => { try { e.currentTarget.showPicker && e.currentTarget.showPicker(); } catch {} }}
              className="h-7 w-36 cursor-pointer bg-[hsl(var(--panel-2))] font-mono text-xs" />
          </div>
          <div>
            <div className="mb-0.5 font-mono text-[9px] uppercase tracking-widest text-muted-foreground">To (optional)</div>
            <Input type="date" data-testid="kpi-custom-to" value={draftTo} onChange={(e) => setDraftTo(e.target.value)}
              onClick={(e) => { try { e.currentTarget.showPicker && e.currentTarget.showPicker(); } catch {} }}
              className="h-7 w-36 cursor-pointer bg-[hsl(var(--panel-2))] font-mono text-xs" />
          </div>
          <button
            data-testid="kpi-custom-apply"
            onClick={applyCustom}
            disabled={!draftFrom}
            className="cyber-chamfer-sm border border-[hsl(var(--primary))]/60 px-3 py-1 font-mono text-[10px] uppercase tracking-wide text-[hsl(var(--primary))] transition-colors hover:bg-[hsl(var(--primary))]/10 disabled:opacity-40"
          >
            Apply Range
          </button>
        </div>
      )}

      {/* Line cards */}
      <div className="flex gap-2 overflow-x-auto pb-1">
        {!data && <div className="cyber-loading w-full" />}
        {data?.lines?.map((l) => {
          const isOpen = expandedLine === l.line;
          const isSelected = selectedLine === l.line;
          const hasActiveBd = !!l.active_breakdown_since;
          return (
            <div
              key={l.line}
              role="button"
              tabIndex={0}
              data-testid={`line-kpi-${l.line.replace(/\s+/g, '-')}`}
              onClick={() => {
                // card click = expand sections AND filter the Digital Twin to this line (toggle)
                if (isSelected) {
                  setExpandedLine(null);
                  onSelectLine && onSelectLine('all');
                } else {
                  setExpandedLine(l.line);
                  onSelectLine && onSelectLine(l.line);
                }
              }}
              onKeyDown={(e) => { if (e.key === 'Enter') e.currentTarget.click(); }}
              className={`cyber-chamfer-sm min-w-[170px] shrink-0 cursor-pointer border bg-transparent px-3 pt-2 text-left transition-all duration-150 hover:-translate-y-0.5 ${hasActiveBd ? 'pb-0' : 'pb-2'} ${
                isSelected || isOpen
                  ? 'border-[hsl(var(--primary))] shadow-[0_0_12px_rgba(var(--accent-rgb),0.2)]'
                  : hasActiveBd
                    ? 'border-[#ff2e63]/50 hover:border-[#ff2e63]'
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
              {/* Live breakdown ribbon — HH:MM:SS ticking; CLICK jumps to the exact breakdown */}
              {hasActiveBd && (
                <button
                  type="button"
                  data-testid={`line-bd-timer-${l.line.replace(/\s+/g, '-')}`}
                  title={`Jump to breakdown ${l.active_breakdown_ticket || ''}`.trim()}
                  onClick={(e) => {
                    e.stopPropagation();
                    if (l.active_breakdown_id) navigate(`/breakdowns?bd=${l.active_breakdown_id}`);
                    else navigate('/breakdowns');
                  }}
                  className="-mx-3 mt-1.5 flex w-[calc(100%+1.5rem)] items-center justify-between gap-2 border-t border-[#ff2e63]/50 bg-[#ff2e63]/10 px-3 py-1 transition-colors hover:bg-[#ff2e63]/25"
                >
                  <span className="flex items-center gap-1 font-mono text-[8px] uppercase tracking-[0.2em] text-[#ff2e63]">
                    <span className="h-1.5 w-1.5 rounded-full bg-[#ff2e63] alarm-pulse" style={{ boxShadow: '0 0 6px #ff2e63' }} /> Down
                  </span>
                  <span className="flex items-center gap-1 text-[11px] text-[#ff2e63]" style={{ textShadow: '0 0 8px rgba(255,46,99,0.5)' }}>
                    <BreakdownTimer since={l.active_breakdown_since} />
                    <span className="font-mono text-[9px]">↗</span>
                  </span>
                </button>
              )}
            </div>
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
