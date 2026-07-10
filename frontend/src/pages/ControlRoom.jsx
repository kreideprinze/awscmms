import React, { useEffect, useMemo, useState, useCallback } from 'react';
import { Search, PanelRightClose, PanelRightOpen, Activity, Rows3, Network } from 'lucide-react';
import { api } from '@/lib/api';
import { useApp } from '@/context/AppContext';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { StatusDot, HealthBadge, STATUS_META, fmtDate } from '@/components/StatusBits';
import { KpiCard } from '@/components/Shared';
import { PlantClock } from '@/components/PlantClock';
import { LineKpiRibbon } from '@/components/LineKpiRibbon';

const STATUS_FILTERS = ['all', 'running', 'watch', 'inspection_due', 'repair', 'failed', 'idle'];
const LINE_ORDER = ['PC21', 'PC32', 'PC36', 'KKR', 'TWZ', 'BCP'];

const MachineTile = React.memo(function MachineTile({ machine, onOpen }) {
  const meta = STATUS_META[machine.status] || STATUS_META.idle;
  const critical = machine.status === 'failed';
  return (
    <button
      data-testid={`machine-tile-${machine.code}`}
      onClick={() => onOpen(machine.id)}
      className={`cyber-chamfer-sm relative w-[200px] border border-border bg-[hsl(var(--panel-1))] p-3 text-left transition-all duration-150 hover:-translate-y-0.5 hover:border-[hsl(var(--primary))]/60 hover:shadow-[0_0_14px_rgba(var(--accent-rgb),0.2)] ${critical ? 'glow-critical border-[#ff2e63]/50' : ''}`}
    >
      <span className="absolute left-0 top-0 h-full w-1" style={{ backgroundColor: meta.color, boxShadow: `0 0 8px ${meta.color}66` }} />
      <div className="flex items-start justify-between gap-1">
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold leading-5">{machine.name}</div>
          <div className="font-mono text-[10px] text-muted-foreground">{machine.code}</div>
        </div>
        <StatusDot status={machine.status} pulse />
      </div>
      <div className="mt-2 flex items-center justify-between">
        <span data-testid={`machine-tile-status-${machine.code}`} className="font-mono text-[10px] uppercase tracking-wider" style={{ color: meta.color }}>{meta.label}</span>
        <HealthBadge health={machine.health} />
      </div>
      <div className="mt-1.5 flex items-center justify-between text-[10px] text-muted-foreground">
        <span className="font-mono tabular-nums">{Math.round(machine.total_run_hours || 0)}h run</span>
        <span className="uppercase tracking-wide">{(machine.reliability_state || 'no_data').replace('_', ' ')}</span>
      </div>
    </button>
  );
});

export default function ControlRoom() {
  const { openMachine, machineUpdates, liveFeed } = useApp();
  const [machines, setMachines] = useState([]);
  const [hierarchy, setHierarchy] = useState({ departments: [], lines: [], process_groups: [] });
  const [summary, setSummary] = useState(null);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [deptFilter, setDeptFilter] = useState('all');
  const [lineFilter, setLineFilter] = useState('all');
  const [groupMode, setGroupMode] = useState('hierarchy'); // hierarchy | line
  const [showFeed, setShowFeed] = useState(true);
  const [showPlantTotals, setShowPlantTotals] = useState(false);
  const [feed, setFeed] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const [m, h, s, t] = await Promise.all([
        api.get('/machines?limit=10000'),
        api.get('/hierarchy'),
        api.get('/control-room/summary'),
        api.get('/timeline?limit=30'),
      ]);
      setMachines(m.data);
      setHierarchy(h.data);
      setSummary(s.data);
      setFeed(t.data);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    const ids = Object.keys(machineUpdates);
    if (!ids.length) return;
    setMachines((prev) => prev.map((m) => (machineUpdates[m.id] ? { ...m, ...machineUpdates[m.id] } : m)));
    api.get('/control-room/summary').then((r) => setSummary(r.data)).catch(() => {});
  }, [machineUpdates]);

  const combinedFeed = useMemo(() => {
    const seen = new Set();
    return [...liveFeed, ...feed].filter((e) => (seen.has(e.id) ? false : seen.add(e.id))).slice(0, 40);
  }, [liveFeed, feed]);

  const lineNames = useMemo(() => {
    const names = hierarchy.lines.map((l) => l.name);
    return names.sort((a, b) => {
      const ia = LINE_ORDER.indexOf(a); const ib = LINE_ORDER.indexOf(b);
      return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib) || a.localeCompare(b);
    });
  }, [hierarchy.lines]);

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return machines.filter((m) => {
      if (statusFilter !== 'all' && m.status !== statusFilter) return false;
      if (deptFilter !== 'all' && m.department !== deptFilter) return false;
      if (lineFilter !== 'all' && m.line !== lineFilter) return false;
      if (q && !(m.name.toLowerCase().includes(q) || m.code.toLowerCase().includes(q) || (m.line || '').toLowerCase().includes(q) || (m.process_group || '').toLowerCase().includes(q))) return false;
      return true;
    });
  }, [machines, search, statusFilter, deptFilter, lineFilter]);

  // ---- Twin layout: grouped by full hierarchy OR flat sections per line ----
  const twin = useMemo(() => {
    const deptOrder = hierarchy.departments.map((d) => d.name);
    const pgOrder = hierarchy.process_groups.reduce((acc, pg) => { acc[`${pg.line}::${pg.name}`] = pg.order; return acc; }, {});
    if (groupMode === 'line') {
      const byLine = {};
      for (const m of filtered) {
        byLine[m.line] = byLine[m.line] || [];
        byLine[m.line].push(m);
      }
      return Object.entries(byLine)
        .sort((a, b) => lineNames.indexOf(a[0]) - lineNames.indexOf(b[0]))
        .map(([line, ms]) => ({
          dept: null,
          lines: [{
            line,
            pgs: [{
              pg: null,
              machines: ms.sort((x, y) => (pgOrder[`${line}::${x.process_group}`] ?? 99) - (pgOrder[`${line}::${y.process_group}`] ?? 99) || (x.position_x || 0) - (y.position_x || 0)),
            }],
          }],
        }));
    }
    const byDept = {};
    for (const m of filtered) {
      byDept[m.department] = byDept[m.department] || {};
      byDept[m.department][m.line] = byDept[m.department][m.line] || {};
      byDept[m.department][m.line][m.process_group] = byDept[m.department][m.line][m.process_group] || [];
      byDept[m.department][m.line][m.process_group].push(m);
    }
    return Object.entries(byDept)
      .sort((a, b) => deptOrder.indexOf(a[0]) - deptOrder.indexOf(b[0]))
      .map(([dept, linesObj]) => ({
        dept,
        lines: Object.entries(linesObj)
          .sort((a, b) => lineNames.indexOf(a[0]) - lineNames.indexOf(b[0]))
          .map(([line, pgsObj]) => ({
            line,
            pgs: Object.entries(pgsObj)
              .sort((a, b) => (pgOrder[`${line}::${a[0]}`] ?? 99) - (pgOrder[`${line}::${b[0]}`] ?? 99))
              .map(([pg, ms]) => ({ pg, machines: ms.sort((x, y) => (x.position_x || 0) - (y.position_x || 0)) })),
          })),
      }));
  }, [filtered, hierarchy, groupMode, lineNames]);

  return (
    <div className="flex h-full flex-col" data-testid="control-room-page">
      {/* KPI ribbon — primary: line/section availability + downtime */}
      <div
        className="border-b border-border px-4 py-3"
        style={{ backgroundImage: 'radial-gradient(900px 500px at 20% 10%, rgba(var(--accent-rgb),0.05), transparent 60%), radial-gradient(700px 400px at 85% 0%, rgba(255,46,99,0.04), transparent 55%)' }}
      >
        <LineKpiRibbon
          refreshSignal={machineUpdates}
          selectedLine={lineFilter}
          onSelectLine={(line) => { setLineFilter(line); setDeptFilter('all'); }}
        />

        {/* Secondary: plant-wide totals, collapsible */}
        <button
          data-testid="plant-totals-toggle"
          onClick={() => setShowPlantTotals(!showPlantTotals)}
          className="mt-2 flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground transition-colors hover:text-foreground"
        >
          {showPlantTotals ? '▾' : '▸'} Plant totals
          {!showPlantTotals && summary && (
            <span className="ml-2 normal-case tracking-normal">
              {summary.total_machines} machines · {summary.by_status?.running || 0} running · {summary.open_breakdowns} open BD · {summary.open_work_orders} open WO
            </span>
          )}
        </button>
        {showPlantTotals && (
          <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4 xl:grid-cols-8" data-testid="plant-totals-strip">
            <KpiCard testId="kpi-total-machines" label="Machines" value={summary?.total_machines} />
            <KpiCard testId="kpi-running" label="Running" value={summary?.by_status?.running || 0} accent="text-[#05ffa1]" />
            <KpiCard testId="kpi-failed" label="Failed" value={summary?.by_status?.failed || 0} accent={summary?.by_status?.failed ? 'text-[#ff2e63]' : ''} />
            <KpiCard testId="kpi-repair" label="In Repair" value={summary?.by_status?.repair || 0} accent="text-[hsl(var(--primary))]" />
            <KpiCard testId="kpi-open-breakdowns" label="Open Breakdowns" value={summary?.open_breakdowns} accent={summary?.open_breakdowns ? 'text-[#ff2e63]' : ''} />
            <KpiCard testId="kpi-open-wos" label="Open WOs" value={summary?.open_work_orders} />
            <KpiCard testId="kpi-watchlist" label="Watchlist" value={summary?.watchlist} accent={summary?.watchlist ? 'text-[#f9f871]' : ''} />
            <KpiCard testId="kpi-availability" label="Availability" value={summary?.availability != null ? `${summary.availability}%` : '—'} />
          </div>
        )}
        {/* Filters */}
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <div className="relative">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              data-testid="control-room-search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search machine, code, line, group..."
              className="w-64 bg-[hsl(var(--panel-2))] pl-8"
            />
          </div>
          {STATUS_FILTERS.map((s) => (
            <button
              key={s}
              data-testid={`status-filter-${s}`}
              onClick={() => setStatusFilter(s)}
              className={`cyber-chamfer-sm border px-3 py-1 text-[11px] font-mono uppercase tracking-wide transition-colors ${
                statusFilter === s ? 'power-on border-[hsl(var(--primary))] bg-transparent text-[hsl(var(--primary))] shadow-[0_0_8px_rgba(var(--accent-rgb),0.25)]' : 'border-border text-muted-foreground hover:text-foreground'
              }`}
            >
              {s === 'all' ? 'All' : (STATUS_META[s]?.label || s)}
            </button>
          ))}
          {['all', ...hierarchy.departments.map((d) => d.name)].map((d) => (
            <button
              key={d}
              data-testid={`dept-filter-${d}`}
              onClick={() => { setDeptFilter(d); setLineFilter('all'); }}
              className={`cyber-chamfer-sm border px-3 py-1 text-[11px] uppercase tracking-wide transition-colors ${
                deptFilter === d ? 'power-on border-[hsl(var(--primary))] bg-transparent text-[hsl(var(--primary))] shadow-[0_0_8px_rgba(var(--accent-rgb),0.25)]' : 'border-border text-muted-foreground hover:text-foreground'
              }`}
            >
              {d === 'all' ? 'All Depts' : d}
            </button>
          ))}
          {/* Line sort/group controls */}
          <Select value={lineFilter} onValueChange={setLineFilter}>
            <SelectTrigger className="h-8 w-36 bg-[hsl(var(--panel-2))] text-xs" data-testid="line-filter-select">
              <SelectValue placeholder="Line" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Lines</SelectItem>
              {lineNames.map((l) => <SelectItem key={l} value={l}>{l}</SelectItem>)}
            </SelectContent>
          </Select>
          <button
            data-testid="group-mode-toggle"
            onClick={() => setGroupMode(groupMode === 'hierarchy' ? 'line' : 'hierarchy')}
            title="Toggle grouping"
            className="cyber-chamfer-sm flex items-center gap-1.5 border border-[hsl(var(--primary))]/40 px-3 py-1 text-[11px] uppercase tracking-wide text-[hsl(var(--primary))] transition-colors hover:bg-[hsl(var(--primary))]/10"
          >
            {groupMode === 'hierarchy' ? <Network className="h-3.5 w-3.5" /> : <Rows3 className="h-3.5 w-3.5" />}
            {groupMode === 'hierarchy' ? 'Grouped: Hierarchy' : 'Grouped: By Line'}
          </button>
          <div className="ml-auto flex items-center gap-1">
            <span className="mr-2 font-mono text-xs text-muted-foreground">{filtered.length} machines</span>
            <Button variant="ghost" size="icon" onClick={() => setShowFeed(!showFeed)} data-testid="toggle-live-feed" title="Toggle live feed">
              {showFeed ? <PanelRightClose className="h-4 w-4" /> : <PanelRightOpen className="h-4 w-4" />}
            </Button>
          </div>
        </div>
      </div>

      {/* Twin canvas + feed */}
      <div className="flex min-h-0 flex-1">
        <div className="relative min-w-0 flex-1 overflow-hidden" data-testid="digital-twin-canvas">
          {loading ? (
            <div className="flex h-full flex-col items-center justify-center gap-3 text-muted-foreground">
              <div className="cyber-loading w-64" />
              <span className="font-mono text-xs uppercase tracking-widest">Loading digital twin…</span>
            </div>
          ) : (
            <>
              {/* Plant wall-clock — fixed corner, never scrolls away */}
              <div className="absolute bottom-3 right-3 z-20">
                <PlantClock />
              </div>
              {/* Legend */}
              <div className="absolute bottom-3 left-3 z-20 flex flex-wrap items-center gap-3 border border-border bg-[hsl(var(--panel-1))]/95 px-3 py-2" data-testid="twin-legend">
                {Object.entries(STATUS_META).map(([k, v]) => (
                  <span key={k} className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
                    <span className="h-2 w-2 rounded-full" style={{ backgroundColor: v.color, boxShadow: `0 0 5px ${v.color}` }} /> {v.label}
                  </span>
                ))}
              </div>
              {/* Fixed-size twin: vertical scrolling, no zoom */}
              <div className="h-full overflow-y-auto overflow-x-hidden p-6 pb-20" data-testid="digital-twin-scroll">
                <div className="space-y-8">
                  {twin.length === 0 && <div className="p-10 text-muted-foreground">No machines match filters</div>}
                  {twin.map(({ dept, lines }) => (
                    <section key={dept || lines[0]?.line}>
                      {dept && <h2 className="mb-3 text-lg font-bold uppercase tracking-[0.25em] text-[hsl(var(--primary))]" style={{ textShadow: '0 0 12px rgba(var(--accent-rgb),0.35)' }}>{dept}</h2>}
                      <div className="space-y-6">
                        {lines.map(({ line, pgs }) => (
                          <div key={line} className="cyber-panel p-4" data-testid={`twin-line-${line.replace(/\s+/g, '-')}`}>
                            <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold uppercase tracking-[0.2em]">
                              <Activity className="h-4 w-4 text-[hsl(var(--primary))]" /> {line}
                              <span className="font-mono text-[10px] font-normal normal-case tracking-normal text-muted-foreground">{pgs.reduce((n, p) => n + p.machines.length, 0)} machines</span>
                            </h3>
                            <div className="space-y-4">
                              {pgs.map(({ pg, machines: ms }) => (
                                <div key={pg || 'flat'}>
                                  {pg && <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.2em] text-muted-foreground">{pg}</div>}
                                  <div className="flex flex-wrap gap-2.5">
                                    {ms.map((m) => <MachineTile key={m.id} machine={m} onOpen={openMachine} />)}
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        ))}
                      </div>
                    </section>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>

        {/* Live feed rail */}
        {showFeed && (
          <aside className="w-80 shrink-0 border-l border-border bg-[hsl(var(--panel-1))]" data-testid="live-feed-rail">
            <div className="flex h-10 items-center gap-2 border-b border-border px-3 font-mono text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
              <span className="h-1.5 w-1.5 rounded-full bg-[#05ffa1] alarm-pulse" style={{ boxShadow: '0 0 6px #05ffa1' }} /> Live Event Feed
            </div>
            <ScrollArea className="h-[calc(100%-2.5rem)]">
              {combinedFeed.length === 0 && <div className="p-4 text-xs text-muted-foreground">No events yet. Actions across the plant appear here in real time.</div>}
              {combinedFeed.map((e) => {
                const rail = e.event_type === 'warning_created' ? '#f9f871' : e.event_type === 'breakdown_created' ? '#ff2e63' : e.event_type === 'wo_completed' || e.event_type === 'breakdown_closed' ? '#05ffa1' : 'transparent';
                return (
                <button key={e.id} onClick={() => e.machine_id && openMachine(e.machine_id)} className="block w-full border-b border-border/50 border-l-2 px-3 py-2 text-left hover:bg-white/5" style={{ borderLeftColor: rail }}>
                  <div className="text-xs font-medium" style={e.event_type === 'warning_created' ? { color: '#f9f871' } : undefined}>{e.title}</div>
                  <div className="mt-0.5 text-[11px] text-muted-foreground">{e.machine_name} {e.line ? `· ${e.line}` : ''}</div>
                  <div className="mt-0.5 font-mono text-[10px] text-muted-foreground">{fmtDate(e.created_at)} · {e.user}</div>
                </button>
                );
              })}
            </ScrollArea>
          </aside>
        )}
      </div>
    </div>
  );
}
