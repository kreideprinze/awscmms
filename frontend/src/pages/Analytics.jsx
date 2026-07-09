import React, { useEffect, useState } from 'react';
import {
  BarChart, Bar, LineChart, Line, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip as RTooltip, ResponsiveContainer,
} from 'recharts';
import { api } from '@/lib/api';
import { useApp } from '@/context/AppContext';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
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

export default function Analytics() {
  const { openMachine } = useApp();
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
            className={`rounded-md border px-3 py-1.5 text-xs ${level === l.key ? 'border-[hsl(var(--primary))] bg-[rgba(46,168,255,0.12)]' : 'border-border text-muted-foreground hover:text-foreground'}`}>
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
            <KpiCard testId="analytics-kpi-failures" label="Failures" value={kpis.failures_total} accent={kpis.failures_total ? 'text-red-400' : ''} />
            <KpiCard testId="analytics-kpi-downtime" label="Downtime" value={`${kpis.downtime_hours_total}h`} />
          </div>

          <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
            <div className="rounded-lg border border-border bg-[hsl(var(--panel-1))] p-4">
              <div className="mb-3 text-xs font-semibold uppercase tracking-widest text-muted-foreground">Downtime Trend (hours / month)</div>
              {kpis.downtime_trend.length === 0 ? <div className="py-10 text-center text-sm text-muted-foreground">No downtime recorded</div> : (
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={kpis.downtime_trend}>
                    <CartesianGrid stroke={chartTheme.grid} vertical={false} />
                    <XAxis dataKey="month" tick={chartTheme.tick} />
                    <YAxis tick={chartTheme.tick} width={35} />
                    <RTooltip contentStyle={chartTheme.tooltip} />
                    <Bar dataKey="downtime_hours" fill="hsl(0 84% 58%)" radius={[3, 3, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
            <div className="rounded-lg border border-border bg-[hsl(var(--panel-1))] p-4">
              <div className="mb-3 text-xs font-semibold uppercase tracking-widest text-muted-foreground">Failure Trend (count / month)</div>
              {kpis.failure_trend.length === 0 ? <div className="py-10 text-center text-sm text-muted-foreground">No failures recorded</div> : (
                <ResponsiveContainer width="100%" height={220}>
                  <LineChart data={kpis.failure_trend}>
                    <CartesianGrid stroke={chartTheme.grid} vertical={false} />
                    <XAxis dataKey="month" tick={chartTheme.tick} />
                    <YAxis tick={chartTheme.tick} width={35} allowDecimals={false} />
                    <RTooltip contentStyle={chartTheme.tooltip} />
                    <Line type="monotone" dataKey="failures" stroke="hsl(24 95% 55%)" strokeWidth={2} dot />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>
            <div className="rounded-lg border border-border bg-[hsl(var(--panel-1))] p-4">
              <div className="mb-3 text-xs font-semibold uppercase tracking-widest text-muted-foreground">Availability Trend (%)</div>
              {kpis.availability_trend.length === 0 ? <div className="py-10 text-center text-sm text-muted-foreground">No runtime data yet</div> : (
                <ResponsiveContainer width="100%" height={220}>
                  <AreaChart data={kpis.availability_trend}>
                    <CartesianGrid stroke={chartTheme.grid} vertical={false} />
                    <XAxis dataKey="month" tick={chartTheme.tick} />
                    <YAxis tick={chartTheme.tick} width={35} domain={[0, 100]} />
                    <RTooltip contentStyle={chartTheme.tooltip} />
                    <Area type="monotone" dataKey="availability" stroke="hsl(205 100% 58%)" fill="rgba(46,168,255,0.15)" strokeWidth={2} />
                  </AreaChart>
                </ResponsiveContainer>
              )}
            </div>
            <div className="rounded-lg border border-border bg-[hsl(var(--panel-1))] p-4">
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
            <div className="rounded-lg border border-border bg-[hsl(var(--panel-1))] p-4 xl:col-span-2">
              <div className="mb-3 text-xs font-semibold uppercase tracking-widest text-muted-foreground">Failure Modes Distribution</div>
              {kpis.failure_modes.length === 0 ? <div className="py-10 text-center text-sm text-muted-foreground">No failures recorded</div> : (
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={kpis.failure_modes} layout="vertical">
                    <CartesianGrid stroke={chartTheme.grid} horizontal={false} />
                    <XAxis type="number" tick={chartTheme.tick} allowDecimals={false} />
                    <YAxis type="category" dataKey="mode" tick={chartTheme.tick} width={160} />
                    <RTooltip contentStyle={chartTheme.tooltip} />
                    <Bar dataKey="count" fill="hsl(205 100% 58%)" radius={[0, 3, 3, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
