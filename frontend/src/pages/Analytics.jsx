import React, { useEffect, useState, useCallback, useMemo } from 'react';
import {
  BarChart, Bar, LineChart, Line, AreaChart, Area, ComposedChart, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip as RTooltip, ResponsiveContainer,
} from 'recharts';
import { ShieldCheck, Trophy, X, Timer, Medal } from 'lucide-react';
import { api } from '@/lib/api';
import { useApp } from '@/context/AppContext';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { KpiCard, MachineSelect } from '@/components/Shared';

const chartTheme = {
  grid: 'rgba(255,255,255,0.08)',
  tick: { fill: 'rgba(229,231,235,0.7)', fontSize: 11 },
  tooltip: { backgroundColor: 'hsl(220 16% 10%)', border: '1px solid hsl(220 12% 18%)', borderRadius: 8, fontSize: 12 },
};

const LEVELS = [
  { key: 'plant', label: 'Plant' },
  { key: 'department', label: 'Department' },
  { key: 'line', label: 'Line' },
  { key: 'process_group', label: 'Process Group' },
  { key: 'machine', label: 'Machine' },
];

const WO_TYPES = ['all', 'Corrective', 'Preventive', 'Inspection', 'RCA'];
const fmtMin = (v) => (v == null ? '—' : `${v} min`);
const fmtPct = (v) => (v == null ? '—' : `${v}%`);
const minToH = (m) => `${((m || 0) / 60).toFixed(1)}h`;

// Time Utilization buckets — where maintenance minutes were actually invested.
const TU_SLICES = [
  { key: 'breakdown_minutes', name: 'Breakdown / Corrective', color: '#ff2e63' },
  { key: 'preventive_minutes', name: 'PM / Preventive', color: '#05ffa1' },
  { key: 'predictive_minutes', name: 'AWS / Predictive', color: '#00fff5' },
];

// Breakdown-type pie — same category colors as the AWS health pools.
const BT_META = {
  MECHANICAL: { label: 'Mechanical', color: '#00fff5' },
  ELECTRICAL: { label: 'Electrical', color: '#f9f871' },
  CONTROL_PLC: { label: 'PLC / Control', color: '#ff2e63' },
};

// Leaderboard ranking modes (admin choice: metric tabs + Overall composite)
const LB_METRICS = [
  { key: 'overall', label: 'Overall', hint: 'composite score' },
  { key: 'breakdowns', label: 'Breakdowns Closed', hint: 'most resolved' },
  { key: 'mttr', label: 'Best Avg MTTR', hint: 'fastest repairs' },
  { key: 'pm', label: 'PM Compliance', hint: 'on-time PMs' },
  { key: 'ontime', label: 'WO On-Time', hint: 'within target' },
];
const lbValue = (r, metric) => (
  metric === 'overall' ? r.overall_score
  : metric === 'breakdowns' ? r.breakdowns_resolved
  : metric === 'mttr' ? r.avg_repair_minutes
  : metric === 'pm' ? r.pm_compliance_rate
  : r.wo_on_time_rate);
const lbDisplay = (r, metric) => (
  metric === 'overall' ? (r.overall_score != null ? `${r.overall_score}` : '—')
  : metric === 'breakdowns' ? `${r.breakdowns_resolved}`
  : metric === 'mttr' ? fmtMin(r.avg_repair_minutes)
  : metric === 'pm' ? fmtPct(r.pm_compliance_rate)
  : fmtPct(r.wo_on_time_rate));

// Admin-only technician performance section. The API itself is role-guarded (403 for non-admins).
function TechnicianAnalytics({ hierarchy }) {
  const [rows, setRows] = useState([]);
  const [target, setTarget] = useState(30);
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState({ date_from: '', date_to: '', line: 'all', department: 'all', wo_type: 'all' });
  const [metric, setMetric] = useState('overall'); // leaderboard ranking mode
  const [cardTech, setCardTech] = useState(null);  // drill-down technician card

  const load = useCallback(() => {
    setLoading(true);
    const params = new URLSearchParams();
    if (filters.date_from) params.set('date_from', filters.date_from);
    if (filters.date_to) params.set('date_to', filters.date_to);
    if (filters.line !== 'all') params.set('line', filters.line);
    if (filters.department !== 'all') params.set('department', filters.department);
    if (filters.wo_type !== 'all') params.set('wo_type', filters.wo_type);
    api.get(`/analytics/technicians?${params}`).then((r) => {
      setRows(r.data.technicians || []);
      setTarget(r.data.on_time_target_minutes);
    }).finally(() => setLoading(false));
  }, [filters]);
  useEffect(() => { load(); }, [load]);

  const top = rows[0];

  // Leaderboard ordering — lower is better ONLY for Avg MTTR; techs without data
  // for the chosen metric sink to the bottom (never unfairly ranked).
  const ranked = useMemo(() => {
    const active = rows.filter((r) => r.breakdowns_resolved || r.wo_completed || r.pm_completed);
    const asc = metric === 'mttr';
    return [...active].sort((a, b) => {
      const va = lbValue(a, metric), vb = lbValue(b, metric);
      if (va == null && vb == null) return 0;
      if (va == null) return 1;
      if (vb == null) return -1;
      return asc ? va - vb : vb - va;
    });
  }, [rows, metric]);
  const bestVal = ranked.length ? lbValue(ranked[0], metric) : null;
  const barPct = (r) => {
    const v = lbValue(r, metric);
    if (v == null || bestVal == null || bestVal === 0) return v === 0 && bestVal === 0 ? 100 : 0;
    return Math.max(Math.min(metric === 'mttr' ? (bestVal / v) * 100 : (v / bestVal) * 100, 100), 3);
  };
  const medalColor = (i) => (i === 0 ? '#f9f871' : i === 1 ? '#9ca3af' : i === 2 ? '#ff9e1c' : null);

  return (
    <div className="mt-8" data-testid="technician-analytics-section">
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <ShieldCheck className="h-5 w-5 text-[hsl(var(--primary))]" />
        <h2 className="text-lg font-semibold tracking-tight">Technician Analytics</h2>
        <span className="border border-[#ff9e1c]/50 px-1.5 py-px font-mono text-[9px] uppercase tracking-widest text-[#ff9e1c]">Admin Only</span>
      </div>

      <div className="mb-4 flex flex-wrap items-end gap-3">
        <div>
          <Label className="text-[10px] uppercase tracking-wide text-muted-foreground">From</Label>
          <Input type="date" data-testid="tech-filter-from" value={filters.date_from} onChange={(e) => setFilters({ ...filters, date_from: e.target.value })} className="w-40 bg-[hsl(var(--panel-2))]" />
        </div>
        <div>
          <Label className="text-[10px] uppercase tracking-wide text-muted-foreground">To</Label>
          <Input type="date" data-testid="tech-filter-to" value={filters.date_to} onChange={(e) => setFilters({ ...filters, date_to: e.target.value })} className="w-40 bg-[hsl(var(--panel-2))]" />
        </div>
        <div>
          <Label className="text-[10px] uppercase tracking-wide text-muted-foreground">Line</Label>
          <Select value={filters.line} onValueChange={(v) => setFilters({ ...filters, line: v })}>
            <SelectTrigger data-testid="tech-filter-line" className="w-44 bg-[hsl(var(--panel-2))]"><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="all">All Lines</SelectItem>{hierarchy.lines.map((l) => <SelectItem key={l.name} value={l.name}>{l.name}</SelectItem>)}</SelectContent>
          </Select>
        </div>
        <div>
          <Label className="text-[10px] uppercase tracking-wide text-muted-foreground">Department</Label>
          <Select value={filters.department} onValueChange={(v) => setFilters({ ...filters, department: v })}>
            <SelectTrigger data-testid="tech-filter-department" className="w-44 bg-[hsl(var(--panel-2))]"><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="all">All Departments</SelectItem>{[...new Set(hierarchy.departments.map((d) => d.name))].map((d) => <SelectItem key={d} value={d}>{d}</SelectItem>)}</SelectContent>
          </Select>
        </div>
        <div>
          <Label className="text-[10px] uppercase tracking-wide text-muted-foreground">WO Type</Label>
          <Select value={filters.wo_type} onValueChange={(v) => setFilters({ ...filters, wo_type: v })}>
            <SelectTrigger data-testid="tech-filter-wo-type" className="w-36 bg-[hsl(var(--panel-2))]"><SelectValue /></SelectTrigger>
            <SelectContent>{WO_TYPES.map((t) => <SelectItem key={t} value={t}>{t === 'all' ? 'All Types' : t}</SelectItem>)}</SelectContent>
          </Select>
        </div>
      </div>

      {top && (
        <div className="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
          <KpiCard testId="tech-kpi-top" label="Top Breakdown Handler" value={top.name} accent="text-[hsl(var(--primary))]" sub={`${top.breakdowns_resolved} resolved`} />
          <KpiCard testId="tech-kpi-active" label="Technicians Active" value={rows.filter((r) => r.breakdowns_resolved || r.wo_completed || r.pm_completed).length} />
          <KpiCard testId="tech-kpi-total-hours" label="Total Logged Effort" value={`${rows.reduce((n, r) => n + (r.total_hours || 0), 0).toFixed(1)}h`} />
          <KpiCard testId="tech-kpi-target" label="On-Time Target" value={`≤ ${target} min`} sub="per work order" />
        </div>
      )}

      {/* LEADERBOARD — rank all technicians against each other on a chosen metric */}
      <div className="cyber-panel mb-4 p-4" data-testid="tech-leaderboard">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
            <Medal className="h-4 w-4 text-[#f9f871]" /> Leaderboard
            <span className="font-mono text-[9px] normal-case tracking-normal">({LB_METRICS.find((m) => m.key === metric)?.hint})</span>
          </div>
          <div className="flex flex-wrap gap-1">
            {LB_METRICS.map((m) => (
              <button key={m.key} data-testid={`lb-metric-${m.key}`} onClick={() => setMetric(m.key)}
                className={`cyber-chamfer-sm border px-2.5 py-1 font-mono text-[10px] uppercase tracking-wide transition-colors ${metric === m.key ? 'power-on border-[hsl(var(--primary))] bg-transparent text-[hsl(var(--primary))] shadow-[0_0_8px_rgba(var(--accent-rgb),0.25)]' : 'border-border text-muted-foreground hover:text-foreground'}`}>
                {m.label}
              </button>
            ))}
          </div>
        </div>
        {ranked.length === 0 ? (
          <div className="py-8 text-center text-sm text-muted-foreground" data-testid="lb-empty">No technician activity in the selected window</div>
        ) : (
          <div className="space-y-1.5">
            {ranked.map((r, i) => (
              <button key={r.technician} data-testid={`lb-row-${r.technician}`} onClick={() => setCardTech(r)}
                className="group flex w-full items-center gap-3 border border-border bg-[hsl(var(--panel-2))] px-3 py-2 text-left transition-colors hover:border-[hsl(var(--primary))]/60">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center border font-mono text-[11px]"
                  style={medalColor(i) ? { borderColor: `${medalColor(i)}99`, color: medalColor(i) } : { borderColor: 'hsl(var(--border))', color: 'inherit' }}>
                  {i === 0 ? <Trophy className="h-3.5 w-3.5" /> : i + 1}
                </span>
                <div className="w-40 shrink-0 truncate">
                  <div className="text-sm font-medium group-hover:text-[hsl(var(--primary))]">{r.name}</div>
                  <div className="font-mono text-[9px] text-muted-foreground">{r.technician}</div>
                </div>
                <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-[hsl(var(--panel-3))]">
                  <div className="h-full bg-[hsl(var(--primary))]/70" style={{ width: `${barPct(r)}%` }} />
                </div>
                <span className="w-20 shrink-0 text-right font-mono text-xs tabular-nums" data-testid={`lb-value-${r.technician}`}>{lbDisplay(r, metric)}</span>
              </button>
            ))}
          </div>
        )}
        <p className="mt-2 text-[10px] text-muted-foreground">Overall = composite score (0–100) blending breakdowns resolved, WOs completed, avg repair time (inverted), WO on-time and PM compliance — normalized across peers. Click a technician for their full card.</p>
      </div>

      <div className="overflow-hidden border border-border">
        <Table data-testid="technician-analytics-table">
          <TableHeader>
            <TableRow className="border-border bg-[hsl(var(--panel-1))] hover:bg-[hsl(var(--panel-1))]">
              <TableHead className="text-xs uppercase">#</TableHead>
              <TableHead className="text-xs uppercase">Technician</TableHead>
              <TableHead className="text-xs uppercase">Breakdowns Resolved</TableHead>
              <TableHead className="text-xs uppercase">Avg Repair</TableHead>
              <TableHead className="text-xs uppercase">WO Completed</TableHead>
              <TableHead className="text-xs uppercase">WO Avg Time</TableHead>
              <TableHead className="text-xs uppercase">WO On-Time</TableHead>
              <TableHead className="text-xs uppercase">PM Completed</TableHead>
              <TableHead className="text-xs uppercase">PM Compliance</TableHead>
              <TableHead className="text-xs uppercase">Total Time</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading && <TableRow><TableCell colSpan={10} className="py-10 text-center text-muted-foreground">Computing technician metrics…</TableCell></TableRow>}
            {!loading && rows.length === 0 && <TableRow><TableCell colSpan={10} className="py-10 text-center text-muted-foreground">No technician activity in the selected window</TableCell></TableRow>}
            {!loading && rows.map((r) => (
              <TableRow key={r.technician} data-testid={`tech-row-${r.technician}`} onClick={() => setCardTech(r)}
                className="cursor-pointer border-border hover:bg-white/[0.03]">
                <TableCell className="font-mono text-xs">
                  {r.rank === 1 ? <Trophy className="h-3.5 w-3.5 text-[#f9f871]" /> : r.rank}
                </TableCell>
                <TableCell><div className="text-sm font-medium">{r.name}</div><div className="font-mono text-[10px] text-muted-foreground">{r.technician}</div></TableCell>
                <TableCell className="tabular-nums text-sm text-[#ff2e63]">{r.breakdowns_resolved}</TableCell>
                <TableCell className="tabular-nums text-sm">{fmtMin(r.avg_repair_minutes)}</TableCell>
                <TableCell className="tabular-nums text-sm">{r.wo_completed}</TableCell>
                <TableCell className="tabular-nums text-sm">{fmtMin(r.wo_avg_minutes)}</TableCell>
                <TableCell className={`tabular-nums text-sm ${r.wo_on_time_rate != null ? (r.wo_on_time_rate >= 80 ? 'text-[#05ffa1]' : r.wo_on_time_rate >= 50 ? 'text-[#f9f871]' : 'text-[#ff2e63]') : ''}`}>{fmtPct(r.wo_on_time_rate)}</TableCell>
                <TableCell className="tabular-nums text-sm">{r.pm_completed}</TableCell>
                <TableCell className={`tabular-nums text-sm ${r.pm_compliance_rate != null ? (r.pm_compliance_rate >= 80 ? 'text-[#05ffa1]' : 'text-[#f9f871]') : ''}`}>{fmtPct(r.pm_compliance_rate)}</TableCell>
                <TableCell className="tabular-nums text-sm">{r.total_hours}h</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <p className="mt-2 text-[11px] text-muted-foreground">WO On-Time = completed within the configured {target}-minute target (Reliability Rules → Root Cause threshold). PM Compliance = completions within the ± reminder-offset window around the due date. Click any row for the technician's card.</p>

      {/* Individual TECHNICIAN CARD — drill-down from leaderboard or table (admin-only section) */}
      <Dialog open={!!cardTech} onOpenChange={(v) => { if (!v) setCardTech(null); }}>
        <DialogContent data-testid="tech-card-modal" className="max-w-md border-border bg-[hsl(var(--panel-1))]">
          <DialogHeader>
            <DialogTitle className="flex flex-wrap items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-[hsl(var(--primary))]" />
              <span data-testid="tech-card-name">{cardTech?.name}</span>
              <span className="font-mono text-[10px] text-muted-foreground">@{cardTech?.technician}</span>
              {cardTech?.overall_score != null && (
                <span className="border border-[hsl(var(--primary))]/50 px-1.5 py-px font-mono text-[10px] text-[hsl(var(--primary))]" data-testid="tech-card-score">
                  Overall {cardTech.overall_score}
                </span>
              )}
            </DialogTitle>
          </DialogHeader>
          {cardTech && (
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                {[
                  ['Breakdowns Resolved', cardTech.breakdowns_resolved, 'text-[#ff2e63]'],
                  ['Avg MTTR', fmtMin(cardTech.avg_repair_minutes)],
                  ['Total Repair Time', minToH(cardTech.total_repair_minutes)],
                  ['WOs Completed', cardTech.wo_completed],
                  ['Avg Time / Task', fmtMin(cardTech.wo_avg_minutes)],
                  ['WO On-Time', fmtPct(cardTech.wo_on_time_rate), cardTech.wo_on_time_rate >= 80 ? 'text-[#05ffa1]' : ''],
                  ['PM Completed', cardTech.pm_completed],
                  ['PM Compliance', fmtPct(cardTech.pm_compliance_rate), cardTech.pm_compliance_rate >= 80 ? 'text-[#05ffa1]' : ''],
                  ['RCA Completed', cardTech.rca_completed, 'text-[#ff2e63]'],
                ].map(([label, val, accent]) => (
                  <div key={label} className="border border-border bg-[hsl(var(--panel-2))] p-2.5" data-testid={`tech-card-${label.toLowerCase().replace(/[^a-z]+/g, '-')}`}>
                    <div className="text-[9px] uppercase tracking-widest text-muted-foreground">{label}</div>
                    <div className={`mt-0.5 font-mono text-lg tabular-nums ${accent || ''}`}>{val ?? '—'}</div>
                  </div>
                ))}
              </div>
              <div className="flex items-center justify-between border border-[hsl(var(--primary))]/30 bg-[hsl(var(--primary))]/[0.04] px-3 py-2">
                <span className="text-[10px] uppercase tracking-widest text-muted-foreground">Total Logged Effort</span>
                <span className="font-mono text-sm tabular-nums text-[hsl(var(--primary))]" data-testid="tech-card-total-hours">{cardTech.total_hours}h</span>
              </div>
              <p className="text-[10px] text-muted-foreground">Metrics respect the filters above (date range / line / department / WO type). Admin-only visibility.</p>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default function Analytics() {
  const { openMachine, isAdmin } = useApp();
  const [level, setLevel] = useState('plant');
  const [value, setValue] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [hierarchy, setHierarchy] = useState({ departments: [], lines: [], process_groups: [] });
  const [kpis, setKpis] = useState(null);
  const [loading, setLoading] = useState(false);
  const [paretoExpanded, setParetoExpanded] = useState(false); // top 15 by default, expandable
  const [btMode, setBtMode] = useState('downtime'); // breakdown-type pie: 'downtime' | 'count'

  useEffect(() => { api.get('/hierarchy').then((r) => setHierarchy(r.data)); }, []);

  useEffect(() => {
    if (level !== 'plant' && !value) return;
    setLoading(true);
    const params = new URLSearchParams({ level });
    if (value) params.set('value', value);
    if (dateFrom) params.set('date_from', dateFrom);
    if (dateTo) params.set('date_to', dateTo);
    api.get(`/analytics/kpis?${params}`).then((r) => setKpis(r.data)).finally(() => setLoading(false));
  }, [level, value, dateFrom, dateTo]);

  // Departments repeat per line in the Line-first hierarchy — dedupe names
  const options = level === 'department' ? [...new Set(hierarchy.departments.map((d) => d.name))]
    : level === 'line' ? hierarchy.lines.map((l) => l.name)
    : level === 'process_group' ? [...new Set(hierarchy.process_groups.map((p) => p.name))] : [];

  return (
    <div className="p-6" data-testid="analytics-page">
      <div className="mb-5">
        <h1 className="text-2xl font-semibold tracking-tight">Analytics</h1>
        <p className="text-sm text-muted-foreground">MTBF · MTTR · Availability · Failure Rate · PM Compliance · Trends — at every hierarchy level</p>
      </div>

      <div className="mb-5 flex flex-wrap items-center gap-2">
        {LEVELS.map((l) => (
          <button key={l.key} data-testid={`analytics-level-${l.key}`} onClick={() => { setLevel(l.key); setValue(''); setKpis(l.key === 'plant' ? kpis : null); }}
            className={`cyber-chamfer-sm border px-3 py-1.5 font-mono text-[11px] uppercase tracking-wide transition-colors ${level === l.key ? 'power-on border-[hsl(var(--primary))] bg-transparent text-[hsl(var(--primary))] shadow-[0_0_8px_rgba(var(--accent-rgb),0.25)]' : 'border-border text-muted-foreground hover:text-foreground'}`}>
            {l.label}
          </button>
        ))}
        {level !== 'plant' && level !== 'machine' && (
          <Select value={value} onValueChange={setValue}>
            <SelectTrigger className="w-64 bg-[hsl(var(--panel-2))]" data-testid="analytics-value-select"><SelectValue placeholder={`Select ${level.replace('_', ' ')}`} /></SelectTrigger>
            <SelectContent>{options.map((o) => <SelectItem key={o} value={o}>{o}</SelectItem>)}</SelectContent>
          </Select>
        )}
        {level === 'machine' && (
          <div className="w-80"><MachineSelect value={value} onChange={(id) => setValue(id)} testId="analytics-machine-select" /></div>
        )}
        {/* Global date range slicer — slices EVERY KPI and chart on this page */}
        <div className="ml-auto flex items-end gap-2" data-testid="analytics-date-slicer">
          <div>
            <Label className="text-[10px] uppercase tracking-wide text-muted-foreground">From</Label>
            <Input type="date" data-testid="analytics-date-from" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)}
              onClick={(e) => { try { e.currentTarget.showPicker && e.currentTarget.showPicker(); } catch {} }}
              className="h-8 w-36 cursor-pointer bg-[hsl(var(--panel-2))] font-mono text-xs" />
          </div>
          <div>
            <Label className="text-[10px] uppercase tracking-wide text-muted-foreground">To</Label>
            <Input type="date" data-testid="analytics-date-to" value={dateTo} onChange={(e) => setDateTo(e.target.value)}
              onClick={(e) => { try { e.currentTarget.showPicker && e.currentTarget.showPicker(); } catch {} }}
              className="h-8 w-36 cursor-pointer bg-[hsl(var(--panel-2))] font-mono text-xs" />
          </div>
          {(dateFrom || dateTo) && (
            <button data-testid="analytics-date-clear" onClick={() => { setDateFrom(''); setDateTo(''); }} title="Clear date range"
              className="cyber-chamfer-sm mb-0.5 border border-border p-1.5 text-muted-foreground transition-colors hover:border-[#ff2e63]/60 hover:text-[#ff2e63]">
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </div>

      {loading && <div className="py-10 text-center text-muted-foreground">Computing KPIs…</div>}
      {!loading && !kpis && level !== 'plant' && <div className="py-10 text-center text-muted-foreground">Select a {level.replace('_', ' ')} to view analytics</div>}

      {!loading && kpis && (
        <>
          <div className="mb-5 grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-5">
            <KpiCard testId="analytics-kpi-mtbf" label="MTBF" value={kpis.mtbf_hours != null ? `${kpis.mtbf_hours}h` : '—'} />
            <KpiCard testId="analytics-kpi-mttr" label="MTTR" value={kpis.mttr_hours != null ? `${kpis.mttr_hours}h` : '—'} />
            <KpiCard testId="analytics-kpi-availability" label="Availability" value={kpis.availability != null ? `${kpis.availability}%` : '—'} accent="text-[hsl(var(--primary))]" />
            <KpiCard testId="analytics-kpi-failure-rate" label="Failure Rate" value={kpis.failure_rate_per_1000h != null ? kpis.failure_rate_per_1000h : '—'} sub="per 1000 run-h" />
            <KpiCard testId="analytics-kpi-pm-compliance" label="PM Compliance"
              value={kpis.pm_compliance != null ? `${kpis.pm_compliance}%` : 'N/A'}
              accent={kpis.pm_compliance != null ? (kpis.pm_compliance >= 80 ? 'text-[#05ffa1]' : kpis.pm_compliance >= 50 ? 'text-[#f9f871]' : 'text-[#ff2e63]') : ''}
              sub={kpis.pm_scheduled_count ? `${kpis.pm_completed_count}/${kpis.pm_scheduled_count} scheduled PMs completed` : 'No PMs scheduled in range'} />
            <KpiCard testId="analytics-kpi-am-compliance" label="AM Compliance"
              value={kpis.am_compliance != null ? `${kpis.am_compliance}%` : 'N/A'}
              accent={kpis.am_compliance != null ? (kpis.am_compliance >= 80 ? 'text-[#05ffa1]' : kpis.am_compliance >= 50 ? 'text-[#f9f871]' : 'text-[#ff2e63]') : ''}
              sub={kpis.am_scheduled_count ? `${kpis.am_submitted_count}/${kpis.am_scheduled_count} scheduled shift checks submitted` : 'No AM shifts scheduled in range'} />
            <KpiCard testId="analytics-kpi-closure-rate" label="Closure Rate" value={kpis.closure_rate != null ? `${kpis.closure_rate}%` : '—'}
              accent={kpis.closure_rate != null ? (kpis.closure_rate >= 80 ? 'text-[#05ffa1]' : kpis.closure_rate >= 50 ? 'text-[#f9f871]' : 'text-[#ff2e63]') : ''}
              sub={`${kpis.breakdowns_closed ?? 0}/${kpis.breakdowns_reported ?? 0} closed`} />
            <KpiCard testId="analytics-kpi-failures" label="Failures" value={kpis.failures_total} accent={kpis.failures_total ? 'text-[#ff2e63]' : ''} />
            <KpiCard testId="analytics-kpi-downtime" label="Downtime" value={`${kpis.downtime_hours_total}h`} />
          </div>

          <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
            <div className="cyber-panel p-4">
              <div className="mb-3 text-xs font-semibold uppercase tracking-widest text-muted-foreground">Downtime Trend (hours / month)</div>
              {kpis.downtime_trend.length === 0 ? <div className="py-10 text-center text-sm text-muted-foreground">No downtime recorded</div> : (
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={kpis.downtime_trend}>
                    <CartesianGrid stroke={chartTheme.grid} vertical={false} />
                    <XAxis dataKey="month" tick={chartTheme.tick} />
                    <YAxis tick={chartTheme.tick} width={35} />
                    <RTooltip contentStyle={chartTheme.tooltip} />
                    <Bar dataKey="downtime_hours" fill="#ff2e63" radius={[3, 3, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
            <div className="cyber-panel p-4">
              <div className="mb-3 text-xs font-semibold uppercase tracking-widest text-muted-foreground">Failure Trend (count / month)</div>
              {kpis.failure_trend.length === 0 ? <div className="py-10 text-center text-sm text-muted-foreground">No failures recorded</div> : (
                <ResponsiveContainer width="100%" height={220}>
                  <LineChart data={kpis.failure_trend}>
                    <CartesianGrid stroke={chartTheme.grid} vertical={false} />
                    <XAxis dataKey="month" tick={chartTheme.tick} />
                    <YAxis tick={chartTheme.tick} width={35} allowDecimals={false} />
                    <RTooltip contentStyle={chartTheme.tooltip} />
                    <Line type="monotone" dataKey="failures" stroke="#ff9e1c" strokeWidth={2} dot />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>
            <div className="cyber-panel p-4">
              <div className="mb-3 text-xs font-semibold uppercase tracking-widest text-muted-foreground">Availability Trend (%)</div>
              {kpis.availability_trend.length === 0 ? <div className="py-10 text-center text-sm text-muted-foreground">No runtime data yet</div> : (
                <ResponsiveContainer width="100%" height={220}>
                  <AreaChart data={kpis.availability_trend}>
                    <CartesianGrid stroke={chartTheme.grid} vertical={false} />
                    <XAxis dataKey="month" tick={chartTheme.tick} />
                    <YAxis tick={chartTheme.tick} width={35} domain={[0, 100]} />
                    <RTooltip contentStyle={chartTheme.tooltip} />
                    <Area type="monotone" dataKey="availability" stroke="#00fff5" fill="rgba(var(--accent-rgb),0.12)" strokeWidth={2} />
                  </AreaChart>
                </ResponsiveContainer>
              )}
            </div>
            <div className="cyber-panel p-4">
              <div className="mb-3 text-xs font-semibold uppercase tracking-widest text-muted-foreground">Top Failing Machines</div>
              {kpis.top_failing_machines.length === 0 ? <div className="py-10 text-center text-sm text-muted-foreground">No failures recorded</div> : (
                <div className="space-y-1.5">
                  {kpis.top_failing_machines.map((m) => (
                    <button key={m.machine_id} onClick={() => openMachine(m.machine_id)} className="flex w-full items-center justify-between rounded-md border border-border bg-[hsl(var(--panel-2))] px-3 py-2 text-sm hover:border-white/25">
                      <span>{m.machine_name}</span>
                      <span className="tabular-nums text-xs text-muted-foreground">{m.failures} failures · {m.downtime_hours}h down</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
            {/* Breakdown-type share — Mechanical / Electrical / PLC (count or downtime-weighted) */}
            <div className="cyber-panel p-4" data-testid="analytics-breakdown-types">
              <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                <div className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Breakdowns by Type</div>
                <div className="flex gap-1">
                  {[['downtime', 'Downtime'], ['count', 'Count']].map(([k, lbl]) => (
                    <button key={k} data-testid={`bt-mode-${k}`} onClick={() => setBtMode(k)}
                      className={`cyber-chamfer-sm border px-2.5 py-1 font-mono text-[10px] uppercase tracking-wide transition-colors ${btMode === k ? 'power-on border-[hsl(var(--primary))] bg-transparent text-[hsl(var(--primary))] shadow-[0_0_8px_rgba(var(--accent-rgb),0.25)]' : 'border-border text-muted-foreground hover:text-foreground'}`}>
                      {lbl}
                    </button>
                  ))}
                </div>
              </div>
              {(() => {
                const valKey = btMode === 'count' ? 'count' : 'downtime_minutes';
                const data = (kpis.breakdown_types || [])
                  .map((b) => ({ ...b, ...(BT_META[b.type] || { label: b.type, color: '#9ca3af' }), value: b[valKey] || 0 }))
                  .filter((b) => b.value > 0);
                const total = data.reduce((n, b) => n + b.value, 0);
                const fmtVal = (v) => (btMode === 'count' ? `${v} breakdown${v === 1 ? '' : 's'}` : minToH(v));
                if (!total) {
                  return <div className="py-10 text-center text-sm text-muted-foreground" data-testid="breakdown-types-empty">No breakdowns in the selected range</div>;
                }
                return (
                  <div className="flex flex-wrap items-center gap-4">
                    <div className="relative h-[200px] w-[200px] shrink-0">
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                          <Pie data={data} dataKey="value" nameKey="label" cx="50%" cy="50%" innerRadius={58} outerRadius={88}
                            paddingAngle={3} stroke="hsl(220 16% 8%)" strokeWidth={2}>
                            {data.map((d) => <Cell key={d.type} fill={d.color} />)}
                          </Pie>
                          <RTooltip contentStyle={chartTheme.tooltip} formatter={(v, name) => [`${fmtVal(v)} (${Math.round((v / total) * 100)}%)`, name]} />
                        </PieChart>
                      </ResponsiveContainer>
                      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
                        <span className="font-mono text-lg font-semibold tabular-nums" data-testid="breakdown-types-total">{btMode === 'count' ? total : minToH(total)}</span>
                        <span className="text-[9px] uppercase tracking-widest text-muted-foreground">{btMode === 'count' ? 'Breakdowns' : 'Downtime'}</span>
                      </div>
                    </div>
                    <div className="min-w-[180px] flex-1 space-y-1.5">
                      {Object.keys(BT_META).map((t) => {
                        const row = (kpis.breakdown_types || []).find((b) => b.type === t);
                        const v = row ? row[valKey] || 0 : 0;
                        return (
                          <div key={t} data-testid={`breakdown-type-${t}`} className="flex items-center justify-between border border-border bg-[hsl(var(--panel-2))] px-3 py-2">
                            <span className="flex items-center gap-2 text-xs"><span className="h-2 w-2" style={{ backgroundColor: BT_META[t].color }} />{BT_META[t].label}</span>
                            <span className="tabular-nums font-mono text-xs">{btMode === 'count' ? v : minToH(v)} <span className="text-muted-foreground">· {total ? Math.round((v / total) * 100) : 0}%</span></span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })()}
              <p className="mt-2 text-[10px] text-muted-foreground">{btMode === 'count' ? 'Share of breakdown occurrences' : 'Downtime-weighted share (consistent with the Pareto metric)'} · respects the date range and scope above.</p>
            </div>

            <div className="cyber-panel p-4" data-testid="analytics-time-utilization">
              <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                <Timer className="h-3.5 w-3.5 text-[hsl(var(--primary))]" /> Time Utilization — maintenance time invested
              </div>
              {(() => {
                const tu = kpis.time_utilization || {};
                const total = tu.total_minutes || 0;
                const data = TU_SLICES.map((s) => ({ ...s, minutes: tu[s.key] || 0 })).filter((d) => d.minutes > 0);
                if (!total || data.length === 0) {
                  return <div className="py-10 text-center text-sm text-muted-foreground" data-testid="time-utilization-empty">No maintenance time logged in the selected range</div>;
                }
                return (
                  <div className="flex flex-wrap items-center gap-4">
                    <div className="relative h-[200px] w-[200px] shrink-0">
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                          <Pie data={data} dataKey="minutes" nameKey="name" cx="50%" cy="50%" innerRadius={58} outerRadius={88}
                            paddingAngle={3} stroke="hsl(220 16% 8%)" strokeWidth={2}>
                            {data.map((d) => <Cell key={d.key} fill={d.color} />)}
                          </Pie>
                          <RTooltip contentStyle={chartTheme.tooltip} formatter={(v, name) => [`${minToH(v)} (${Math.round((v / total) * 100)}%)`, name]} />
                        </PieChart>
                      </ResponsiveContainer>
                      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
                        <span className="font-mono text-lg font-semibold tabular-nums" data-testid="time-utilization-total">{minToH(total)}</span>
                        <span className="text-[9px] uppercase tracking-widest text-muted-foreground">Total</span>
                      </div>
                    </div>
                    <div className="min-w-[180px] flex-1 space-y-1.5">
                      {TU_SLICES.map((s) => {
                        const mins = tu[s.key] || 0;
                        return (
                          <div key={s.key} data-testid={`time-utilization-${s.key}`} className="flex items-center justify-between border border-border bg-[hsl(var(--panel-2))] px-3 py-2">
                            <span className="flex items-center gap-2 text-xs"><span className="h-2 w-2" style={{ backgroundColor: s.color }} />{s.name}</span>
                            <span className="tabular-nums font-mono text-xs">{minToH(mins)} <span className="text-muted-foreground">· {total ? Math.round((mins / total) * 100) : 0}%</span></span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })()}
              <p className="mt-2 text-[10px] text-muted-foreground">Breakdown = actual repair minutes on closed breakdowns (+ standalone corrective WOs) · PM / AWS = completed work-order durations. Respects the date range and hierarchy scope above.</p>
            </div>
            <div className="cyber-panel p-4 xl:col-span-2">
              <div className="mb-3 flex items-center justify-between">
                <div className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Downtime Pareto — by Machine (cumulative %)</div>
                {(kpis.pareto || []).length > 15 && (
                  <button data-testid="analytics-pareto-expand" onClick={() => setParetoExpanded((v) => !v)}
                    className="border border-border px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide text-muted-foreground transition-colors hover:border-[hsl(var(--primary))] hover:text-[hsl(var(--primary))]">
                    {paretoExpanded ? 'Show Top 15' : `Show All ${kpis.pareto_total_machines || kpis.pareto.length}`}
                  </button>
                )}
              </div>
              {(kpis.pareto || []).length === 0 ? <div className="py-10 text-center text-sm text-muted-foreground">No downtime recorded</div> : (
                <ResponsiveContainer width="100%" height={260}>
                  <ComposedChart data={paretoExpanded ? kpis.pareto : kpis.pareto.slice(0, 15)} data-testid="analytics-pareto-chart">
                    <CartesianGrid stroke={chartTheme.grid} vertical={false} />
                    <XAxis dataKey="machine" tick={{ ...chartTheme.tick, fontSize: 9 }} interval={0} angle={-25} textAnchor="end" height={60} />
                    <YAxis yAxisId="downtime" tick={chartTheme.tick} width={45} unit="h" />
                    <YAxis yAxisId="pct" orientation="right" domain={[0, 100]} tick={chartTheme.tick} width={40} unit="%" />
                    <RTooltip contentStyle={chartTheme.tooltip} formatter={(v, name) => name === 'cumulative_pct' ? [`${v}%`, 'Cumulative downtime'] : name === 'downtime_hours' ? [`${v}h`, 'Downtime'] : [v, name === 'count' ? 'Breakdowns' : name]} />
                    <Bar yAxisId="downtime" dataKey="downtime_hours" fill="#00fff5" radius={[3, 3, 0, 0]} maxBarSize={42} />
                    <Line yAxisId="pct" type="monotone" dataKey="cumulative_pct" stroke="#ff9e1c" strokeWidth={2} dot={{ r: 3 }} />
                  </ComposedChart>
                </ResponsiveContainer>
              )}
              <p className="mt-1 text-[10px] text-muted-foreground">80/20 view — bars are each MACHINE's total downtime (hours, worst first{paretoExpanded ? '' : ', top 15 shown'}); the line is the cumulative share of all downtime across machines.</p>
            </div>
          </div>
        </>
      )}

      {isAdmin && <TechnicianAnalytics hierarchy={hierarchy} />}
    </div>
  );
}
