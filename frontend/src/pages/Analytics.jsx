import React, { useEffect, useState, useCallback } from 'react';
import {
  BarChart, Bar, LineChart, Line, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip as RTooltip, ResponsiveContainer,
} from 'recharts';
import { ShieldCheck, Trophy } from 'lucide-react';
import { api } from '@/lib/api';
import { useApp } from '@/context/AppContext';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
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

// Admin-only technician performance section. The API itself is role-guarded (403 for non-admins).
function TechnicianAnalytics({ hierarchy }) {
  const [rows, setRows] = useState([]);
  const [target, setTarget] = useState(30);
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState({ date_from: '', date_to: '', line: 'all', department: 'all', wo_type: 'all' });

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
            <SelectContent><SelectItem value="all">All Departments</SelectItem>{hierarchy.departments.map((d) => <SelectItem key={d.name} value={d.name}>{d.name}</SelectItem>)}</SelectContent>
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
              <TableRow key={r.technician} data-testid={`tech-row-${r.technician}`} className="border-border hover:bg-white/[0.03]">
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
      <p className="mt-2 text-[11px] text-muted-foreground">WO On-Time = completed within the configured {target}-minute target (Reliability Rules → Root Cause threshold). PM Compliance = completions on/before due date.</p>
    </div>
  );
}

export default function Analytics() {
  const { openMachine, isAdmin } = useApp();
  const [level, setLevel] = useState('plant');
  const [value, setValue] = useState('');
  const [hierarchy, setHierarchy] = useState({ departments: [], lines: [], process_groups: [] });
  const [kpis, setKpis] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => { api.get('/hierarchy').then((r) => setHierarchy(r.data)); }, []);

  useEffect(() => {
    if (level !== 'plant' && !value) return;
    setLoading(true);
    const params = new URLSearchParams({ level });
    if (value) params.set('value', value);
    api.get(`/analytics/kpis?${params}`).then((r) => setKpis(r.data)).finally(() => setLoading(false));
  }, [level, value]);

  const options = level === 'department' ? hierarchy.departments.map((d) => d.name)
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
      </div>

      {loading && <div className="py-10 text-center text-muted-foreground">Computing KPIs…</div>}
      {!loading && !kpis && level !== 'plant' && <div className="py-10 text-center text-muted-foreground">Select a {level.replace('_', ' ')} to view analytics</div>}

      {!loading && kpis && (
        <>
          <div className="mb-5 grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-7">
            <KpiCard testId="analytics-kpi-mtbf" label="MTBF" value={kpis.mtbf_hours != null ? `${kpis.mtbf_hours}h` : '—'} />
            <KpiCard testId="analytics-kpi-mttr" label="MTTR" value={kpis.mttr_hours != null ? `${kpis.mttr_hours}h` : '—'} />
            <KpiCard testId="analytics-kpi-availability" label="Availability" value={kpis.availability != null ? `${kpis.availability}%` : '—'} accent="text-[hsl(var(--primary))]" />
            <KpiCard testId="analytics-kpi-failure-rate" label="Failure Rate" value={kpis.failure_rate_per_1000h != null ? kpis.failure_rate_per_1000h : '—'} sub="per 1000 run-h" />
            <KpiCard testId="analytics-kpi-pm-compliance" label="PM Compliance" value={kpis.pm_compliance != null ? `${kpis.pm_compliance}%` : '—'} />
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
            <div className="cyber-panel p-4 xl:col-span-2">
              <div className="mb-3 text-xs font-semibold uppercase tracking-widest text-muted-foreground">Failure Modes Distribution</div>
              {kpis.failure_modes.length === 0 ? <div className="py-10 text-center text-sm text-muted-foreground">No failures recorded</div> : (
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={kpis.failure_modes} layout="vertical">
                    <CartesianGrid stroke={chartTheme.grid} horizontal={false} />
                    <XAxis type="number" tick={chartTheme.tick} allowDecimals={false} />
                    <YAxis type="category" dataKey="mode" tick={chartTheme.tick} width={160} />
                    <RTooltip contentStyle={chartTheme.tooltip} />
                    <Bar dataKey="count" fill="#00fff5" radius={[0, 3, 3, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>
        </>
      )}

      {isAdmin && <TechnicianAnalytics hierarchy={hierarchy} />}
    </div>
  );
}
