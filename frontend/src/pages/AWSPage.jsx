import React, { useEffect, useState, useCallback } from 'react';
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

export default function AWSPage() {
  const { openMachine, isAdmin } = useApp();
  const [metrics, setMetrics] = useState([]);
  const [health, setHealth] = useState('all');
  const [settings, setSettings] = useState(null);
  const [savingSettings, setSavingSettings] = useState(false);

  const load = useCallback(() => {
    const q = health === 'all' ? '' : `?health=${health}`;
    api.get(`/reliability/metrics${q}`).then((r) => setMetrics(r.data));
    api.get('/reliability/settings').then((r) => setSettings(r.data));
  }, [health]);
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
      ['healthy_threshold_pct', 'watch_threshold_pct', 'inspection_threshold_pct', 'alert_trigger_pct', 'level2_min_failures', 'level3_min_failures', 'rolling_window', 'root_cause_downtime_minutes'].forEach((k) => {
        if (settings[k] !== undefined && settings[k] !== null && settings[k] !== '') payload[k] = parseFloat(settings[k]);
      });
      await api.put('/reliability/settings', payload);
      toast.success('Reliability rules updated');
    } catch (e) { toast.error(errMsg(e)); } finally { setSavingSettings(false); }
  };

  const counts = {
    watch: metrics.filter((m) => m.health === 'watch').length,
    inspection: metrics.filter((m) => m.health === 'inspection_due').length,
    overdue: metrics.filter((m) => m.health === 'overdue').length,
    weibull: metrics.filter((m) => m.weibull).length,
  };

  return (
    <div className="p-6" data-testid="aws-page">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight"><Siren className="h-6 w-6 text-[#ff9e1c]" /> AWS — Advance Warning System</h1>
          <p className="text-sm text-muted-foreground">Statistical reliability engineering (MTBF → Weighted MTBF → Weibull) — not AI. Calculations begin after the first breakdown.</p>
        </div>
        {isAdmin && (
          <Button variant="outline" onClick={recompute} data-testid="aws-recompute-button" className="border-border bg-[hsl(var(--panel-2))]">
            <RefreshCw className="mr-1 h-4 w-4" /> Recompute All
          </Button>
        )}
      </div>

      <div className="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-5">
        <KpiCard testId="aws-kpi-tracked" label="Machines Tracked" value={metrics.length} />
        <KpiCard testId="aws-kpi-watch" label="Watch (70–80%)" value={counts.watch} accent={counts.watch ? 'text-[#f9f871]' : ''} />
        <KpiCard testId="aws-kpi-inspection" label="Inspection Due (80–100%)" value={counts.inspection} accent={counts.inspection ? 'text-[#ff9e1c]' : ''} />
        <KpiCard testId="aws-kpi-overdue" label="Overdue (100%+)" value={counts.overdue} accent={counts.overdue ? 'text-[#ff2e63]' : ''} />
        <KpiCard testId="aws-kpi-weibull" label="Weibull Active (L3)" value={counts.weibull} accent="text-[hsl(var(--primary))]" />
      </div>

      <div className="mb-4 flex gap-2">
        {HEALTH_FILTERS.map((h) => (
          <button key={h} data-testid={`aws-health-filter-${h}`} onClick={() => setHealth(h)}
            className={`cyber-chamfer-sm border px-3 py-1 font-mono text-[11px] uppercase tracking-wide transition-colors capitalize ${health === h ? 'power-on border-[hsl(var(--primary))] bg-[hsl(var(--primary))]/10 text-[hsl(var(--primary))]' : 'border-border text-muted-foreground hover:text-foreground'}`}>
            {h.replace('_', ' ')}
          </button>
        ))}
      </div>

      <div className="overflow-hidden border border-border">
        <Table data-testid="aws-metrics-table">
          <TableHeader>
            <TableRow className="border-border bg-[hsl(var(--panel-1))] hover:bg-[hsl(var(--panel-1))]">
              <TableHead className="text-xs uppercase">Machine</TableHead>
              <TableHead className="text-xs uppercase">Level</TableHead>
              <TableHead className="text-xs uppercase">Tier</TableHead>
              <TableHead className="text-xs uppercase">MTBF</TableHead>
              <TableHead className="text-xs uppercase">Predicted Life</TableHead>
              <TableHead className="text-xs uppercase">Hours Since Failure</TableHead>
              <TableHead className="text-xs uppercase">Life %</TableHead>
              <TableHead className="text-xs uppercase">Health</TableHead>
              <TableHead className="text-xs uppercase">Weibull β/η</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {metrics.length === 0 && (
              <TableRow><TableCell colSpan={9} className="py-10 text-center text-muted-foreground">No reliability data yet. Metrics appear immediately after the first recorded breakdown.</TableCell></TableRow>
            )}
            {metrics.map((m) => (
              <TableRow key={m.machine_id} data-testid={`aws-row-${m.machine_id}`} className="border-border hover:bg-white/[0.03]">
                <TableCell>
                  <button className="text-sm font-medium hover:text-[hsl(var(--primary))]" onClick={() => openMachine(m.machine_id)}>{m.machine_name}</button>
                  <div className="text-[10px] text-muted-foreground">{m.line} / {m.process_group}</div>
                </TableCell>
                <TableCell className="text-sm">L{m.level} <span className="text-[10px] text-muted-foreground">({m.failures_count}f)</span></TableCell>
                <TableCell className="text-xs capitalize">{m.tier}</TableCell>
                <TableCell className="tabular-nums text-sm">{m.mtbf}h</TableCell>
                <TableCell className="tabular-nums text-sm">{m.predicted_failure_life}h</TableCell>
                <TableCell className="tabular-nums text-sm">{m.hours_since_last_failure}h</TableCell>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <div className="h-1.5 w-16 overflow-hidden rounded-full bg-[hsl(var(--panel-3))]">
                      <div className={`h-full ${m.life_pct >= 100 ? 'bg-[#ff2e63]' : m.life_pct >= 80 ? 'bg-[#ff9e1c]' : m.life_pct >= 70 ? 'bg-[#f9f871]' : 'bg-[#05ffa1]'}`} style={{ width: `${Math.min(m.life_pct, 100)}%` }} />
                    </div>
                    <span className="tabular-nums text-xs">{m.life_pct}%</span>
                  </div>
                </TableCell>
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
            {[['healthy_threshold_pct', 'Healthy < %'], ['watch_threshold_pct', 'Watch < %'], ['alert_trigger_pct', 'Alert Trigger %'], ['root_cause_downtime_minutes', 'Root Cause > min'],
              ['level2_min_failures', 'Level 2 min failures'], ['level3_min_failures', 'Level 3 min failures'], ['rolling_window', 'Rolling MTBF window']].map(([k, label]) => (
              <div key={k}>
                <Label className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</Label>
                <Input type="number" data-testid={`aws-setting-${k}`} value={settings[k] ?? ''} onChange={(e) => setSettings({ ...settings, [k]: e.target.value })} className="bg-[hsl(var(--panel-2))]" />
              </div>
            ))}
          </div>
          <Button onClick={saveSettings} disabled={savingSettings} data-testid="aws-settings-save" className="mt-3 bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))]">Save Rules</Button>
        </div>
      )}
    </div>
  );
}
