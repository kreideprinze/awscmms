import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { toast } from 'sonner';
import { Siren, RefreshCw } from 'lucide-react';
import { api, errMsg } from '@/lib/api';
import { useApp } from '@/context/AppContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { HealthBadge, fmtDate } from '@/components/StatusBits';
import { KpiCard } from '@/components/Shared';

const HEALTH_FILTERS = ['all', 'healthy', 'watch', 'inspection_due', 'overdue'];
const CATEGORY_FILTERS = [
  { key: 'all', label: 'All Pools' },
  { key: 'MECHANICAL', label: 'Mechanical' },
  { key: 'ELECTRICAL', label: 'Electrical' },
  { key: 'CONTROL_PLC', label: 'PLC / Control' },
];
const CAT_COLOR = { MECHANICAL: '#00fff5', ELECTRICAL: '#f9f871', CONTROL_PLC: '#ff2e63' };
const CAT_SHORT = { MECHANICAL: 'MEC', ELECTRICAL: 'ELE', CONTROL_PLC: 'PLC' };
const POOL_ORDER = ['MECHANICAL', 'ELECTRICAL', 'CONTROL_PLC'];

const lifeBarColor = (pct) => (pct >= 100 ? 'bg-[#ff2e63]' : pct >= 80 ? 'bg-[#ff9e1c]' : pct >= 70 ? 'bg-[#f9f871]' : 'bg-[#05ffa1]');

// Three independent health pools per machine — Mechanical / Electrical / PLC.
// Each pool has its own MTBF, predicted life and life %; the DRIVING pool (▲) is the riskiest.
// When a category filter is active, ONLY that pool renders (others are hidden entirely).
function PoolBars({ m, category = 'all' }) {
  const cats = m.categories || {};
  const present = POOL_ORDER.filter((c) => cats[c] && (category === 'all' || c === category));
  if (!present.length) return <span className="text-xs text-muted-foreground">—</span>;
  return (
    <div className="min-w-[180px] space-y-1" data-testid={`aws-pools-${m.machine_id}`}>
      {present.map((c) => {
        const p = cats[c];
        const driving = m.driving_category === c;
        return (
          <div key={c} className={`flex items-center gap-1.5 ${driving || category !== 'all' ? '' : 'opacity-60'}`} title={`${p.label}: ${p.life_pct}% of ${p.predicted_failure_life}h predicted life · MTBF ${p.mtbf}h · ${p.health.replace('_', ' ')}`}>
            <span className="w-7 font-mono text-[9px] font-semibold" style={{ color: CAT_COLOR[c] }}>{CAT_SHORT[c]}</span>
            <div className="h-1.5 w-16 overflow-hidden rounded-full bg-[hsl(var(--panel-3))]">
              <div className={`h-full ${lifeBarColor(p.life_pct)}`} style={{ width: `${Math.min(p.life_pct, 100)}%` }} />
            </div>
            <span className="w-10 tabular-nums text-right text-[10px]">{p.life_pct}%</span>
            {driving && category === 'all' && <span className="font-mono text-[9px] text-[#ff9e1c]" title="Driving pool (riskiest)">▲</span>}
          </div>
        );
      })}
    </div>
  );
}

export default function AWSPage() {
  const { openMachine, isAdmin } = useApp();
  const [metrics, setMetrics] = useState([]);
  const [health, setHealth] = useState('all');
  const [category, setCategory] = useState('all');
  const [settings, setSettings] = useState(null);
  const [savingSettings, setSavingSettings] = useState(false);

  const load = useCallback(() => {
    const params = new URLSearchParams();
    // With a category selected, the health filter is applied CLIENT-SIDE against
    // that pool's own health — the server-side `health` param matches the blended
    // (worst-pool) machine health, which would leak other pools' states in.
    if (health !== 'all' && category === 'all') params.set('health', health);
    if (category !== 'all') params.set('category', category);
    api.get(`/reliability/metrics?${params}`).then((r) => setMetrics(r.data));
    api.get('/reliability/settings').then((r) => setSettings(r.data));
  }, [health, category]);
  useEffect(() => { load(); }, [load]);

  const recompute = async () => {
    try {
      await api.post('/reliability/recompute');
      toast.success('Reliability metrics recomputed');
      load();
    } catch (e) { toast.error(errMsg(e)); }
  };

  const saveSettings = async () => {
    setSavingSettings(true);
    try {
      const payload = {};
      ['predictive_trigger_pct', 'healthy_threshold_pct', 'watch_threshold_pct', 'inspection_threshold_pct', 'alert_trigger_pct', 'level2_min_failures', 'level3_min_failures', 'rolling_window', 'root_cause_downtime_minutes'].forEach((k) => {
        if (settings[k] !== undefined && settings[k] !== null && settings[k] !== '') payload[k] = parseFloat(settings[k]);
      });
      await api.put('/reliability/settings', payload);
      toast.success('Reliability rules updated');
    } catch (e) { toast.error(errMsg(e)); } finally { setSavingSettings(false); }
  };

  // STRICT category scoping — selecting a pool hides machines without it and
  // re-reads EVERY table figure + KPI card from that pool alone (never the
  // blended machine-level state). 'All Pools' keeps the blended behaviour.
  const rows = useMemo(() => {
    if (category === 'all') return metrics;
    return metrics
      .filter((m) => (m.categories || {})[category])
      .map((m) => {
        const p = m.categories[category];
        return {
          ...m,
          level: p.level, failures_count: p.failures_count, tier: p.tier,
          mtbf: p.mtbf, predicted_failure_life: p.predicted_failure_life,
          hours_since_last_failure: p.hours_since_last_failure,
          health: p.health, weibull: p.weibull,
        };
      })
      .filter((m) => health === 'all' || m.health === health);
  }, [metrics, category, health]);

  const counts = {
    watch: rows.filter((m) => m.health === 'watch').length,
    inspection: rows.filter((m) => m.health === 'inspection_due').length,
    overdue: rows.filter((m) => m.health === 'overdue').length,
    weibull: rows.filter((m) => m.weibull).length,
  };
  const catLabel = CATEGORY_FILTERS.find((c) => c.key === category)?.label;

  return (
    <div className="p-6" data-testid="aws-page">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight"><Siren className="h-6 w-6 text-[#ff9e1c]" /> AWS — Advance Warning System</h1>
          <p className="text-sm text-muted-foreground">3 independent health pools per machine (Mechanical · Electrical · PLC) — statistical reliability, not AI. A Predictive WO fires when any pool crosses {settings?.predictive_trigger_pct ?? 80}%.</p>
        </div>
        {isAdmin && (
          <Button variant="outline" onClick={recompute} data-testid="aws-recompute-button" className="border-border bg-[hsl(var(--panel-2))]">
            <RefreshCw className="mr-1 h-4 w-4" /> Recompute All
          </Button>
        )}
      </div>

      <div className="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-5">
        <KpiCard testId="aws-kpi-tracked" label={category === 'all' ? 'Machines Tracked' : `Machines Tracked — ${catLabel}`} value={rows.length} />
        <KpiCard testId="aws-kpi-watch" label="Watch (70–80%)" value={counts.watch} accent={counts.watch ? 'text-[#f9f871]' : ''} />
        <KpiCard testId="aws-kpi-inspection" label="Inspection Due (80–100%)" value={counts.inspection} accent={counts.inspection ? 'text-[#ff9e1c]' : ''} />
        <KpiCard testId="aws-kpi-overdue" label="Overdue (100%+)" value={counts.overdue} accent={counts.overdue ? 'text-[#ff2e63]' : ''} />
        <KpiCard testId="aws-kpi-weibull" label="Weibull Active (L3)" value={counts.weibull} accent="text-[hsl(var(--primary))]" />
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-2">
        {HEALTH_FILTERS.map((h) => (
          <button key={h} data-testid={`aws-health-filter-${h}`} onClick={() => setHealth(h)}
            className={`cyber-chamfer-sm border px-3 py-1 font-mono text-[11px] uppercase tracking-wide transition-colors capitalize ${health === h ? 'power-on border-[hsl(var(--primary))] bg-transparent text-[hsl(var(--primary))] shadow-[0_0_8px_rgba(var(--accent-rgb),0.25)]' : 'border-border text-muted-foreground hover:text-foreground'}`}>
            {h.replace('_', ' ')}
          </button>
        ))}
        <span className="mx-1 text-border">|</span>
        {CATEGORY_FILTERS.map((c) => (
          <button key={c.key} data-testid={`aws-category-filter-${c.key}`} onClick={() => setCategory(c.key)}
            className={`cyber-chamfer-sm border px-3 py-1 font-mono text-[11px] uppercase tracking-wide transition-colors ${category === c.key ? 'power-on border-[hsl(var(--primary))] bg-transparent text-[hsl(var(--primary))] shadow-[0_0_8px_rgba(var(--accent-rgb),0.25)]' : 'border-border text-muted-foreground hover:text-foreground'}`}>
            {c.label}
          </button>
        ))}
      </div>

      <div className="overflow-hidden border border-border">
        <Table data-testid="aws-metrics-table">
          <TableHeader>
            <TableRow className="border-border bg-[hsl(var(--panel-1))] hover:bg-[hsl(var(--panel-1))]">
              <TableHead className="text-xs uppercase">Machine</TableHead>
              <TableHead className="text-xs uppercase">{category === 'all' ? 'Health Pools (life %)' : `${catLabel} Pool (life %)`}</TableHead>
              <TableHead className="text-xs uppercase">Level</TableHead>
              <TableHead className="text-xs uppercase">Tier</TableHead>
              <TableHead className="text-xs uppercase">MTBF {category === 'all' ? '▲' : ''}</TableHead>
              <TableHead className="text-xs uppercase">Predicted Life {category === 'all' ? '▲' : ''}</TableHead>
              <TableHead className="text-xs uppercase">Hours Since Failure {category === 'all' ? '▲' : ''}</TableHead>
              <TableHead className="text-xs uppercase">Health</TableHead>
              <TableHead className="text-xs uppercase">Weibull β/η {category === 'all' ? '▲' : ''}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.length === 0 && (
              <TableRow><TableCell colSpan={10} className="py-10 text-center text-muted-foreground">
                {category === 'all' ? 'No reliability data yet. Metrics appear immediately after the first recorded breakdown.' : `No machines with an active ${catLabel} health pool${health !== 'all' ? ` in “${health.replace('_', ' ')}” state` : ''}.`}
              </TableCell></TableRow>
            )}
            {rows.map((m) => (
              <TableRow key={m.machine_id} data-testid={`aws-row-${m.machine_id}`} className="border-border hover:bg-white/[0.03]">
                <TableCell>
                  <button className="text-sm font-medium hover:text-[hsl(var(--primary))]" onClick={() => openMachine(m.machine_id)}>{m.machine_name}</button>
                  <div className="text-[10px] text-muted-foreground">{m.line} / {m.process_group}</div>
                </TableCell>
                <TableCell><PoolBars m={m} category={category} /></TableCell>
                <TableCell className="text-sm">L{m.level} <span className="text-[10px] text-muted-foreground">({m.failures_count}f)</span></TableCell>
                <TableCell className="text-xs capitalize">{m.tier}</TableCell>
                <TableCell className="tabular-nums text-sm">{m.mtbf}h</TableCell>
                <TableCell className="tabular-nums text-sm">{m.predicted_failure_life}h</TableCell>
                <TableCell className="tabular-nums text-sm">{m.hours_since_last_failure}h</TableCell>
                <TableCell><HealthBadge health={m.health} /></TableCell>
                <TableCell className="font-mono text-xs">{m.weibull ? `${m.weibull.beta} / ${m.weibull.eta}h` : '—'}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {isAdmin && settings && (
        <div className="mt-6 cyber-panel p-4" data-testid="aws-settings-panel">
          <div className="mb-3 text-xs font-semibold uppercase tracking-widest text-muted-foreground">Reliability Rules (Admin)</div>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[['predictive_trigger_pct', 'Predictive WO Trigger %'], ['healthy_threshold_pct', 'Healthy < %'], ['watch_threshold_pct', 'Watch < %'], ['root_cause_downtime_minutes', 'Root Cause > min'],
              ['level2_min_failures', 'Level 2 min failures'], ['level3_min_failures', 'Level 3 min failures'], ['rolling_window', 'Rolling MTBF window']].map(([k, label]) => (
              <div key={k}>
                <Label className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</Label>
                <Input type="number" data-testid={`aws-setting-${k}`} value={settings[k] ?? ''} onChange={(e) => setSettings({ ...settings, [k]: e.target.value })} className="bg-[hsl(var(--panel-2))]" />
              </div>
            ))}
          </div>
          <p className="mt-2 text-[11px] text-muted-foreground">Predictive WO Trigger — a pool crossing this % of predicted failure life auto-dispatches one UNASSIGNED Predictive work order per cycle (default 80%). Applies independently to the Mechanical, Electrical and PLC pools.</p>
          <Button onClick={saveSettings} disabled={savingSettings} data-testid="aws-settings-save" className="mt-3 bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))]">Save Rules</Button>
        </div>
      )}
    </div>
  );
}
