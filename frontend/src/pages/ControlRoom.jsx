import React, { useEffect, useMemo, useState, useCallback } from 'react';
import { TransformWrapper, TransformComponent } from 'react-zoom-pan-pinch';
import { Search, ZoomIn, ZoomOut, Maximize, PanelRightClose, PanelRightOpen, Activity } from 'lucide-react';
import { api } from '@/lib/api';
import { useApp } from '@/context/AppContext';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { StatusDot, HealthBadge, STATUS_META, fmtDate } from '@/components/StatusBits';
import { KpiCard } from '@/components/Shared';

const STATUS_FILTERS = ['all', 'running', 'watch', 'inspection_due', 'repair', 'failed', 'idle'];

const MachineTile = React.memo(function MachineTile({ machine, onOpen }) {
  const meta = STATUS_META[machine.status] || STATUS_META.idle;
  return (
    <button
      data-testid={`machine-tile-${machine.code}`}
      onClick={() => onOpen(machine.id)}
      className="relative w-[200px] rounded-lg border border-border bg-[hsl(var(--panel-1))] p-3 text-left transition-colors hover:border-white/25 hover:bg-white/[0.04]"
    >
      <span className="absolute left-0 top-0 h-full w-1 rounded-l-lg" style={{ backgroundColor: meta.color }} />
      <div className="flex items-start justify-between gap-1">
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold leading-5">{machine.name}</div>
          <div className="font-mono text-[10px] text-muted-foreground">{machine.code}</div>
        </div>
        <StatusDot status={machine.status} pulse />
      </div>
      <div className="mt-2 flex items-center justify-between">
        <span data-testid={`machine-tile-status-${machine.code}`} className="text-[10px] uppercase tracking-wide" style={{ color: meta.color }}>{meta.label}</span>
        <HealthBadge health={machine.health} />
      </div>
      <div className="mt-1.5 flex items-center justify-between text-[10px] text-muted-foreground">
        <span className="tabular-nums">{Math.round(machine.total_run_hours || 0)}h run</span>
        <span className="uppercase">{(machine.reliability_state || 'no_data').replace('_', ' ')}</span>
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
  const [showFeed, setShowFeed] = useState(true);
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

  // merge live machine updates
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

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return machines.filter((m) => {
      if (statusFilter !== 'all' && m.status !== statusFilter) return false;
      if (deptFilter !== 'all' && m.department !== deptFilter) return false;
      if (q && !(m.name.toLowerCase().includes(q) || m.code.toLowerCase().includes(q) || (m.line || '').toLowerCase().includes(q) || (m.process_group || '').toLowerCase().includes(q))) return false;
      return true;
    });
  }, [machines, search, statusFilter, deptFilter]);

  // digital twin layout: generated purely from hierarchy data
  const twin = useMemo(() => {
    const byDept = {};
    for (const m of filtered) {
      byDept[m.department] = byDept[m.department] || {};
      byDept[m.department][m.line] = byDept[m.department][m.line] || {};
      byDept[m.department][m.line][m.process_group] = byDept[m.department][m.line][m.process_group] || [];
      byDept[m.department][m.line][m.process_group].push(m);
    }
    // order by hierarchy seed order
    const deptOrder = hierarchy.departments.map((d) => d.name);
    const lineOrder = hierarchy.lines.map((l) => l.name);
    const pgOrder = hierarchy.process_groups.reduce((acc, pg) => { acc[`${pg.line}::${pg.name}`] = pg.order; return acc; }, {});
    return Object.entries(byDept)
      .sort((a, b) => deptOrder.indexOf(a[0]) - deptOrder.indexOf(b[0]))
      .map(([dept, linesObj]) => ({
        dept,
        lines: Object.entries(linesObj)
          .sort((a, b) => lineOrder.indexOf(a[0]) - lineOrder.indexOf(b[0]))
          .map(([line, pgsObj]) => ({
            line,
            pgs: Object.entries(pgsObj)
              .sort((a, b) => (pgOrder[`${line}::${a[0]}`] ?? 99) - (pgOrder[`${line}::${b[0]}`] ?? 99))
              .map(([pg, ms]) => ({ pg, machines: ms.sort((x, y) => (x.position_x || 0) - (y.position_x || 0)) })),
          })),
      }));
  }, [filtered, hierarchy]);

  return (
    <div className="flex h-full flex-col" data-testid="control-room-page">
      {/* KPI strip */}
      <div
        className="border-b border-border px-4 py-3"
        style={{ backgroundImage: 'radial-gradient(900px 500px at 20% 10%, rgba(46,168,255,0.08), transparent 60%)' }}
      >
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 xl:grid-cols-8">
          <KpiCard testId="kpi-total-machines" label="Machines" value={summary?.total_machines} />
          <KpiCard testId="kpi-running" label="Running" value={summary?.by_status?.running || 0} accent="text-green-400" />
          <KpiCard testId="kpi-failed" label="Failed" value={summary?.by_status?.failed || 0} accent={summary?.by_status?.failed ? 'text-red-400' : ''} />
          <KpiCard testId="kpi-repair" label="In Repair" value={summary?.by_status?.repair || 0} accent="text-[hsl(var(--primary))]" />
          <KpiCard testId="kpi-open-breakdowns" label="Open Breakdowns" value={summary?.open_breakdowns} accent={summary?.open_breakdowns ? 'text-red-400' : ''} />
          <KpiCard testId="kpi-open-wos" label="Open WOs" value={summary?.open_work_orders} />
          <KpiCard testId="kpi-watchlist" label="Watchlist" value={summary?.watchlist} accent={summary?.watchlist ? 'text-yellow-400' : ''} />
          <KpiCard testId="kpi-availability" label="Availability" value={summary?.availability != null ? `${summary.availability}%` : '—'} />
        </div>
        {/* Filters */}
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <div className="relative">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              data-testid="control-room-search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search machine, code, line, group..."
              className="w-72 bg-[hsl(var(--panel-2))] pl-8"
            />
          </div>
          {STATUS_FILTERS.map((s) => (
            <button
              key={s}
              data-testid={`status-filter-${s}`}
              onClick={() => setStatusFilter(s)}
              className={`rounded-full border px-3 py-1 text-xs capitalize transition-colors ${
                statusFilter === s ? 'border-[hsl(var(--primary))] bg-[rgba(46,168,255,0.12)] text-foreground' : 'border-border text-muted-foreground hover:text-foreground'
              }`}
            >
              {s === 'all' ? 'All' : (STATUS_META[s]?.label || s)}
            </button>
          ))}
          {['all', ...hierarchy.departments.map((d) => d.name)].map((d) => (
            <button
              key={d}
              data-testid={`dept-filter-${d}`}
              onClick={() => setDeptFilter(d)}
              className={`rounded-md border px-3 py-1 text-xs transition-colors ${
                deptFilter === d ? 'border-[hsl(var(--primary))] bg-[rgba(46,168,255,0.12)] text-foreground' : 'border-border text-muted-foreground hover:text-foreground'
              }`}
            >
              {d === 'all' ? 'All Depts' : d}
            </button>
          ))}
          <div className="ml-auto flex items-center gap-1">
            <span className="mr-2 text-xs text-muted-foreground">{filtered.length} machines</span>
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
            <div className="flex h-full items-center justify-center text-muted-foreground">Loading digital twin…</div>
          ) : (
            <TransformWrapper minScale={0.25} maxScale={2} initialScale={0.7} limitToBounds={false} doubleClick={{ disabled: true }} wheel={{ step: 0.08 }}>
              {({ zoomIn, zoomOut, resetTransform }) => (
                <>
                  <div className="absolute right-3 top-3 z-20 flex flex-col gap-1 rounded-md border border-border bg-[hsl(var(--panel-1))]/95 p-1">
                    <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => zoomIn()} data-testid="twin-zoom-in"><ZoomIn className="h-4 w-4" /></Button>
                    <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => zoomOut()} data-testid="twin-zoom-out"><ZoomOut className="h-4 w-4" /></Button>
                    <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => resetTransform()} data-testid="twin-reset"><Maximize className="h-4 w-4" /></Button>
                  </div>
                  {/* Legend */}
                  <div className="absolute bottom-3 left-3 z-20 flex flex-wrap items-center gap-3 rounded-md border border-border bg-[hsl(var(--panel-1))]/95 px-3 py-2" data-testid="twin-legend">
                    {Object.entries(STATUS_META).map(([k, v]) => (
                      <span key={k} className="flex items-center gap-1.5 text-[10px] uppercase tracking-wide text-muted-foreground">
                        <span className="h-2 w-2 rounded-full" style={{ backgroundColor: v.color }} /> {v.label}
                      </span>
                    ))}
                  </div>
                  <TransformComponent wrapperStyle={{ width: '100%', height: '100%' }} contentStyle={{ padding: '24px' }}>
                    <div className="space-y-8">
                      {twin.length === 0 && <div className="p-10 text-muted-foreground">No machines match filters</div>}
                      {twin.map(({ dept, lines }) => (
                        <section key={dept}>
                          <h2 className="mb-3 text-lg font-bold uppercase tracking-[0.2em] text-[hsl(var(--primary))]">{dept}</h2>
                          <div className="space-y-6">
                            {lines.map(({ line, pgs }) => (
                              <div key={line} className="rounded-xl border border-border/70 bg-[hsl(var(--panel-1))]/40 p-4" data-testid={`twin-line-${line.replace(/\s+/g, '-')}`}>
                                <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold uppercase tracking-widest">
                                  <Activity className="h-4 w-4 text-[hsl(var(--primary))]" /> {line}
                                  <span className="text-[10px] font-normal normal-case text-muted-foreground">{pgs.reduce((n, p) => n + p.machines.length, 0)} machines</span>
                                </h3>
                                <div className="space-y-4">
                                  {pgs.map(({ pg, machines: ms }) => (
                                    <div key={pg}>
                                      <div className="mb-2 text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">{pg}</div>
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
                  </TransformComponent>
                </>
              )}
            </TransformWrapper>
          )}
        </div>

        {/* Live feed rail */}
        {showFeed && (
          <aside className="w-80 shrink-0 border-l border-border bg-[hsl(var(--panel-1))]" data-testid="live-feed-rail">
            <div className="flex h-10 items-center gap-2 border-b border-border px-3 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
              <span className="h-1.5 w-1.5 rounded-full bg-green-400 alarm-pulse" /> Live Event Feed
            </div>
            <ScrollArea className="h-[calc(100%-2.5rem)]">
              {combinedFeed.length === 0 && <div className="p-4 text-xs text-muted-foreground">No events yet. Actions across the plant appear here in real time.</div>}
              {combinedFeed.map((e) => (
                <button key={e.id} onClick={() => e.machine_id && openMachine(e.machine_id)} className="block w-full border-b border-border/50 px-3 py-2 text-left hover:bg-white/5">
                  <div className="text-xs font-medium">{e.title}</div>
                  <div className="mt-0.5 text-[11px] text-muted-foreground">{e.machine_name} {e.line ? `· ${e.line}` : ''}</div>
                  <div className="mt-0.5 font-mono text-[10px] text-muted-foreground">{fmtDate(e.created_at)} · {e.user}</div>
                </button>
              ))}
            </ScrollArea>
          </aside>
        )}
      </div>
    </div>
  );
}
