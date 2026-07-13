import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { toast } from 'sonner';
import { Plus, Upload, ChevronLeft, ChevronRight, CalendarDays, Rows3, Trash2, AlertTriangle } from 'lucide-react';
import { api, errMsg } from '@/lib/api';
import { useApp } from '@/context/AppContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Tooltip, TooltipContent, TooltipTrigger, TooltipProvider } from '@/components/ui/tooltip';
import { KpiCard } from '@/components/Shared';

// PLANNED-RUNTIME MODEL — one manual value per Line x Date: Planned Runtime (hours).
// Downtime is derived automatically from that line's Breakdowns (Warnings NEVER count).
// Availability = ((Planned − Downtime) ÷ Planned) × 100, clamped at 0% with a visible
// data-quality flag when downtime exceeds planned. Unlogged days are marked missing.

const iso = (d) => d.toISOString().slice(0, 10);
const monthLabel = (d) => d.toLocaleDateString('en-GB', { month: 'long', year: 'numeric' });

const CLAMP_MSG = 'Downtime exceeds Planned Runtime — check breakdown records for this day';

function ClampFlag({ testId }) {
  return (
    <TooltipProvider delayDuration={150}>
      <Tooltip>
        <TooltipTrigger asChild>
          <span data-testid={testId} className="inline-flex cursor-help items-center text-[#ff2e63]">
            <AlertTriangle className="h-3.5 w-3.5" />
          </span>
        </TooltipTrigger>
        <TooltipContent className="max-w-56 border-[#ff2e63]/50 bg-[hsl(var(--panel-1))] text-xs text-[#ff2e63]">
          {CLAMP_MSG}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

// Per-day per-line editor inside the day dialog. Admin: full CRUD; others: view-only.
function DayLineRow({ line, date, log, isAdmin, onSaved }) {
  const [planned, setPlanned] = useState(log ? String(log.planned_hours) : '');
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    setPlanned(log ? String(log.planned_hours) : '');
  }, [log]);

  const save = async () => {
    const p = parseFloat(planned);
    if (!planned || isNaN(p) || p <= 0 || p > 24) { toast.error('Planned Runtime must be between 0 and 24 hours'); return; }
    setBusy(true);
    try {
      await api.post('/runtime-logs', { line, date, planned_hours: p });
      toast.success(`${line} · ${date} planned runtime saved`);
      onSaved();
    } catch (e) { toast.error(errMsg(e)); }
    setBusy(false);
  };

  const remove = async () => {
    setBusy(true);
    try {
      await api.delete(`/line-runtime-logs?line=${encodeURIComponent(line)}&date=${date}`);
      toast.success(`${line} · ${date} planned runtime removed`);
      onSaved();
    } catch (e) { toast.error(errMsg(e)); }
    setBusy(false);
  };

  return (
    <div className={`flex flex-wrap items-center gap-2 border px-3 py-2 ${log ? (log.clamped ? 'border-[#ff2e63]/40 bg-[#ff2e63]/[0.03]' : 'border-[#05ffa1]/30 bg-[#05ffa1]/[0.03]') : 'border-border bg-[hsl(var(--panel-2))]/40'}`}
      data-testid={`day-line-row-${line}`}>
      <div className="w-28 shrink-0">
        <div className="text-sm font-medium">{line}</div>
        <div className={`font-mono text-[9px] uppercase tracking-wide ${log ? 'text-[#05ffa1]' : 'text-muted-foreground'}`}>{log ? 'logged' : 'unlogged'}</div>
      </div>
      {isAdmin && (
        <div className="w-24"><Label className="text-[9px] uppercase text-muted-foreground">Planned h</Label>
          <Input type="number" min="0.5" max="24" step="0.5" value={planned} onChange={(e) => setPlanned(e.target.value)}
            data-testid={`day-planned-${line}`} className="h-7 bg-[hsl(var(--panel-1))] text-xs" placeholder="—" /></div>
      )}
      {log ? (
        <div className="flex items-center gap-3 font-mono text-xs">
          {!isAdmin && <span data-testid={`day-planned-view-${line}`}>Planned {log.planned_hours}h</span>}
          <span className="text-[#ff9e1c]" data-testid={`day-downtime-${line}`}>Down {log.downtime_hours}h</span>
          <span className="text-[#05ffa1]" data-testid={`day-run-${line}`}>Run {log.run_hours}h</span>
          <span className="text-[hsl(var(--primary))]" data-testid={`day-avail-${line}`}>{log.availability != null ? `${log.availability}%` : '—'}</span>
          {log.clamped && <ClampFlag testId={`day-clamped-${line}`} />}
        </div>
      ) : (
        !isAdmin && <span className="font-mono text-xs text-muted-foreground">not logged — no availability figure</span>
      )}
      {isAdmin && (
        <div className="ml-auto flex gap-1.5">
          <Button size="sm" onClick={save} disabled={busy} data-testid={`day-save-${line}`}
            className="h-7 border border-[hsl(var(--primary))]/60 bg-transparent px-2 text-[10px] text-[hsl(var(--primary))] hover:bg-[hsl(var(--primary))]/10">
            {log ? 'Update' : 'Log'}
          </Button>
          {log && (
            <Button size="sm" onClick={remove} disabled={busy} data-testid={`day-delete-${line}`}
              className="h-7 border border-[#ff2e63]/50 bg-transparent px-2 text-[10px] text-[#ff2e63] hover:bg-[#ff2e63]/10">
              <Trash2 className="h-3 w-3" />
            </Button>
          )}
        </div>
      )}
    </div>
  );
}

export default function Runtime() {
  const { isAdmin } = useApp();
  const [view, setView] = useState('calendar'); // calendar is the primary view
  const [data, setData] = useState({ items: [], total: 0 });
  const [lines, setLines] = useState([]);
  const [lineFilter, setLineFilter] = useState('all');
  const [entryOpen, setEntryOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [form, setForm] = useState({ line: '', date: new Date().toISOString().slice(0, 10), planned_hours: '' });
  const [csvText, setCsvText] = useState('');
  const [preview, setPreview] = useState(null);
  const [summary, setSummary] = useState({ planned: 0, down: 0, run: 0 });
  // calendar state
  const [month, setMonth] = useState(() => { const d = new Date(); return new Date(d.getFullYear(), d.getMonth(), 1); });
  const [monthLogs, setMonthLogs] = useState([]);
  const [dayOpen, setDayOpen] = useState(null); // 'YYYY-MM-DD' | null

  useEffect(() => {
    api.get('/hierarchy').then((r) => setLines((r.data.lines || []).map((l) => l.name)));
  }, []);

  const load = useCallback(() => {
    const q = lineFilter !== 'all' ? `&line=${encodeURIComponent(lineFilter)}` : '';
    api.get(`/line-runtime-logs?limit=500${q}`).then((r) => {
      setData(r.data);
      const planned = r.data.items.reduce((n, x) => n + (x.planned_hours || 0), 0);
      const down = r.data.items.reduce((n, x) => n + (x.downtime_hours || 0), 0);
      const run = r.data.items.reduce((n, x) => n + (x.run_hours || 0), 0);
      setSummary({ planned: Math.round(planned), down: Math.round(down * 10) / 10, run: Math.round(run) });
    });
  }, [lineFilter]);
  useEffect(() => { load(); }, [load]);

  const loadMonth = useCallback(() => {
    const from = iso(month);
    const to = iso(new Date(month.getFullYear(), month.getMonth() + 1, 0));
    api.get(`/line-runtime-logs?date_from=${from}&date_to=${to}&limit=2000`).then((r) => setMonthLogs(r.data.items));
  }, [month]);
  useEffect(() => { loadMonth(); }, [loadMonth]);

  const logsByDate = useMemo(() => {
    const map = {};
    for (const lg of monthLogs) {
      (map[lg.date] = map[lg.date] || {})[lg.line] = lg;
    }
    return map;
  }, [monthLogs]);

  const refreshAll = () => { load(); loadMonth(); };

  const submit = async () => {
    const p = parseFloat(form.planned_hours);
    if (!form.line || !form.planned_hours || isNaN(p) || p <= 0 || p > 24) {
      toast.error('Line and Planned Runtime (0–24h) required'); return;
    }
    try {
      const res = await api.post('/runtime-logs', { line: form.line, date: form.date, planned_hours: p });
      toast.success(`Planned runtime saved — availability derives from breakdowns (${res.data.availability != null ? res.data.availability + '%' : 'no downtime yet'})`);
      setEntryOpen(false); setForm({ ...form, planned_hours: '' });
      refreshAll();
    } catch (e) { toast.error(errMsg(e)); }
  };

  const doPreview = async () => {
    try {
      const res = await api.post('/runtime-logs/import', { csv_text: csvText, apply: false });
      setPreview(res.data);
    } catch (e) { toast.error(errMsg(e)); }
  };

  const doApply = async () => {
    try {
      const res = await api.post('/runtime-logs/import', { csv_text: csvText, apply: true });
      toast.success(`Imported ${res.data.imported} planned runtime rows (${res.data.machines_affected} machines updated)`);
      setImportOpen(false); setPreview(null); setCsvText('');
      refreshAll();
    } catch (e) { toast.error(errMsg(e)); }
  };

  const avail = summary.planned ? Math.round(((summary.planned - summary.down) / summary.planned) * 1000) / 10 : null;
  const todayStr = iso(new Date());

  // Build calendar cells (Mon-first grid)
  const cells = useMemo(() => {
    const first = new Date(month.getFullYear(), month.getMonth(), 1);
    const daysInMonth = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate();
    const lead = (first.getDay() + 6) % 7; // Monday-first offset
    const out = [];
    for (let i = 0; i < lead; i++) out.push(null);
    for (let d = 1; d <= daysInMonth; d++) out.push(iso(new Date(Date.UTC(month.getFullYear(), month.getMonth(), d))));
    return out;
  }, [month]);

  return (
    <div className="p-6" data-testid="runtime-page">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Runtime Tracking — Planned Runtime Per Line</h1>
          <p className="text-sm text-muted-foreground">One Planned Runtime entry per line per day · Downtime auto-derived from Breakdowns (Warnings excluded) · Availability = (Planned − Downtime) ÷ Planned × 100</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" data-testid="runtime-view-toggle" onClick={() => setView(view === 'calendar' ? 'table' : 'calendar')} className="border-border bg-[hsl(var(--panel-2))]">
            {view === 'calendar' ? <Rows3 className="mr-1 h-4 w-4" /> : <CalendarDays className="mr-1 h-4 w-4" />} {view === 'calendar' ? 'Table' : 'Calendar'}
          </Button>
          {isAdmin && (
            <>
              <Button variant="outline" data-testid="runtime-import-button" onClick={() => setImportOpen(true)} className="border-border bg-[hsl(var(--panel-2))]">
                <Upload className="mr-1 h-4 w-4" /> CSV Import
              </Button>
              <Button data-testid="runtime-entry-button" onClick={() => setEntryOpen(true)} className="bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))]">
                <Plus className="mr-1 h-4 w-4" /> Log Planned Runtime
              </Button>
            </>
          )}
        </div>
      </div>

      <div className="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
        <KpiCard testId="runtime-kpi-records" label="Line Records" value={data.total} />
        <KpiCard testId="runtime-kpi-planned" label="Planned Hours" value={`${summary.planned}h`} />
        <KpiCard testId="runtime-kpi-downtime" label="Downtime (derived)" value={`${summary.down}h`} accent="text-[#ff9e1c]" />
        <KpiCard testId="runtime-kpi-availability" label="Availability" value={avail != null ? `${Math.max(avail, 0)}%` : '—'} accent="text-[hsl(var(--primary))]" />
      </div>

      {view === 'calendar' ? (
        <div className="cyber-panel p-4" data-testid="runtime-calendar">
          <div className="mb-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <button data-testid="runtime-cal-prev" onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() - 1, 1))}
                className="border border-border p-1 text-muted-foreground transition-colors hover:border-[hsl(var(--primary))] hover:text-[hsl(var(--primary))]"><ChevronLeft className="h-4 w-4" /></button>
              <span className="w-44 text-center font-mono text-sm uppercase tracking-widest" data-testid="runtime-cal-month">{monthLabel(month)}</span>
              <button data-testid="runtime-cal-next" onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() + 1, 1))}
                className="border border-border p-1 text-muted-foreground transition-colors hover:border-[hsl(var(--primary))] hover:text-[hsl(var(--primary))]"><ChevronRight className="h-4 w-4" /></button>
            </div>
            <div className="flex items-center gap-3 font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
              <span className="flex items-center gap-1"><span className="h-2.5 w-2.5 border border-[#05ffa1] bg-[#05ffa1]/20" /> all lines</span>
              <span className="flex items-center gap-1"><span className="h-2.5 w-2.5 border border-[#f9f871] bg-[#f9f871]/15" /> partial</span>
              <span className="flex items-center gap-1"><span className="h-2.5 w-2.5 border border-border" /> unlogged</span>
              <span className="flex items-center gap-1"><AlertTriangle className="h-2.5 w-2.5 text-[#ff2e63]" /> downtime &gt; planned</span>
            </div>
          </div>
          <div className="grid grid-cols-7 gap-1.5">
            {['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN'].map((d) => (
              <div key={d} className="pb-1 text-center font-mono text-[10px] uppercase tracking-widest text-muted-foreground">{d}</div>
            ))}
            {cells.map((date, i) => {
              if (!date) return <div key={`empty-${i}`} />;
              const dayLogs = logsByDate[date] || {};
              const logged = Object.keys(dayLogs).length;
              const clamped = Object.values(dayLogs).some((l) => l.clamped);
              const total = lines.length || 1;
              const isFuture = date > todayStr;
              const cls = isFuture
                ? 'border-border/30 text-muted-foreground/40'
                : logged === 0 ? 'border-border text-muted-foreground hover:border-muted-foreground'
                : logged >= total ? 'border-[#05ffa1]/60 bg-[#05ffa1]/[0.06] text-foreground shadow-[0_0_6px_rgba(5,255,161,0.15)]'
                : 'border-[#f9f871]/60 bg-[#f9f871]/[0.05] text-foreground';
              return (
                <button key={date} data-testid={`runtime-day-${date}`} disabled={isFuture}
                  onClick={() => setDayOpen(date)}
                  className={`flex h-16 flex-col items-start justify-between border p-1.5 text-left transition-colors ${cls} ${!isFuture ? 'cursor-pointer' : 'cursor-default'}`}>
                  <span className="flex w-full items-center justify-between font-mono text-xs">
                    {parseInt(date.slice(8), 10)}
                    {clamped && <AlertTriangle className="h-3 w-3 text-[#ff2e63]" data-testid={`runtime-day-clamped-${date}`} />}
                  </span>
                  {!isFuture && (
                    <span className={`font-mono text-[9px] ${logged >= total ? 'text-[#05ffa1]' : logged > 0 ? 'text-[#f9f871]' : 'text-muted-foreground/60'}`}>
                      {logged === 0 ? 'unlogged' : `${logged}/${total} lines`}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      ) : (
        <>
          <div className="mb-4 flex flex-wrap gap-2">
            {['all', ...lines].map((l) => (
              <button key={l} onClick={() => setLineFilter(l)} data-testid={`runtime-line-filter-${l}`}
                className={`cyber-chamfer-sm border px-3 py-1 font-mono text-[11px] uppercase tracking-wide transition-colors ${lineFilter === l ? 'power-on border-[hsl(var(--primary))] bg-transparent text-[hsl(var(--primary))] shadow-[0_0_8px_rgba(var(--accent-rgb),0.25)]' : 'border-border text-muted-foreground hover:text-foreground'}`}>
                {l === 'all' ? 'All Lines' : l}
              </button>
            ))}
          </div>
          <div className="overflow-hidden border border-border">
            <Table data-testid="runtime-table">
              <TableHeader>
                <TableRow className="border-border bg-[hsl(var(--panel-1))] hover:bg-[hsl(var(--panel-1))]">
                  <TableHead className="text-xs uppercase">Date</TableHead>
                  <TableHead className="text-xs uppercase">Line</TableHead>
                  <TableHead className="text-xs uppercase">Department</TableHead>
                  <TableHead className="text-xs uppercase">Machines</TableHead>
                  <TableHead className="text-xs uppercase">Planned h</TableHead>
                  <TableHead className="text-xs uppercase">Downtime h (derived)</TableHead>
                  <TableHead className="text-xs uppercase">Run h</TableHead>
                  <TableHead className="text-xs uppercase">Availability</TableHead>
                  <TableHead className="text-xs uppercase">Source</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.items.length === 0 && <TableRow><TableCell colSpan={9} className="py-10 text-center text-muted-foreground">No planned runtime logged yet. Admins can log manually or import CSV.</TableCell></TableRow>}
                {data.items.map((r) => (
                  <TableRow key={r.id} data-testid={`runtime-row-${r.line}-${r.date}`} className="border-border hover:bg-white/[0.03]">
                    <TableCell className="font-mono text-xs">{r.date}</TableCell>
                    <TableCell className="text-sm font-medium">{r.line}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">{r.department}</TableCell>
                    <TableCell className="tabular-nums text-xs text-muted-foreground">{r.machines_count ?? '—'}</TableCell>
                    <TableCell className="tabular-nums text-sm">{r.planned_hours}</TableCell>
                    <TableCell className="tabular-nums text-sm text-[#ff9e1c]">{r.downtime_hours}</TableCell>
                    <TableCell className="tabular-nums text-sm text-[#05ffa1]">{r.run_hours}</TableCell>
                    <TableCell className="tabular-nums text-sm">
                      <span className="inline-flex items-center gap-1.5">
                        {r.availability != null ? `${r.availability}%` : '—'}
                        {r.clamped && <ClampFlag testId={`runtime-clamped-${r.line}-${r.date}`} />}
                      </span>
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">{r.source}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </>
      )}

      {/* Day detail — per-line planned entry (Admin CRUD; others view-only) */}
      <Dialog open={!!dayOpen} onOpenChange={(o) => !o && setDayOpen(null)}>
        <DialogContent className="max-h-[85vh] max-w-2xl overflow-y-auto border-border bg-[hsl(var(--panel-1))]" data-testid="runtime-day-dialog">
          <DialogHeader>
            <DialogTitle className="font-mono text-sm uppercase tracking-widest">
              Planned Runtime — <span className="text-[hsl(var(--primary))]">{dayOpen}</span>
            </DialogTitle>
          </DialogHeader>
          <p className="text-[11px] text-muted-foreground">
            {isAdmin ? 'Enter the scheduled production hours per line. ' : 'View-only — planned runtime is managed by Admins. '}
            Downtime and Availability are derived automatically from Breakdowns (Warnings never count).
          </p>
          <div className="space-y-2">
            {lines.map((l) => (
              <DayLineRow key={l} line={l} date={dayOpen} log={(logsByDate[dayOpen] || {})[l]} isAdmin={isAdmin} onSaved={refreshAll} />
            ))}
          </div>
        </DialogContent>
      </Dialog>

      {/* Manual planned-runtime entry */}
      <Dialog open={entryOpen} onOpenChange={setEntryOpen}>
        <DialogContent className="border-border bg-[hsl(var(--panel-1))]">
          <DialogHeader><DialogTitle>Log Planned Runtime</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div>
              <Label className="text-xs">Line</Label>
              <Select value={form.line} onValueChange={(v) => setForm({ ...form, line: v })}>
                <SelectTrigger data-testid="runtime-line-select" className="bg-[hsl(var(--panel-2))]"><SelectValue placeholder="Select line" /></SelectTrigger>
                <SelectContent>{lines.map((l) => <SelectItem key={l} value={l}>{l}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label className="text-xs">Date</Label><Input type="date" data-testid="runtime-date-input" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} className="bg-[hsl(var(--panel-2))]" /></div>
              <div><Label className="text-xs">Planned Runtime (h)</Label><Input type="number" min="0.5" max="24" step="0.5" data-testid="runtime-planned-input" value={form.planned_hours} onChange={(e) => setForm({ ...form, planned_hours: e.target.value })} className="bg-[hsl(var(--panel-2))]" placeholder="e.g. 16" /></div>
            </div>
            <p className="text-[11px] text-muted-foreground">Scheduled production hours for this line on this date (varies with production planning — e.g. lower on a maintenance shutdown day). Downtime is summed automatically from Breakdowns; Availability = (Planned − Downtime) ÷ Planned × 100.</p>
            <Button onClick={submit} data-testid="runtime-submit" className="w-full bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))]">Save Planned Runtime</Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* CSV import */}
      <Dialog open={importOpen} onOpenChange={(o) => { setImportOpen(o); if (!o) setPreview(null); }}>
        <DialogContent className="max-h-[85vh] max-w-2xl overflow-y-auto border-border bg-[hsl(var(--panel-1))]">
          <DialogHeader><DialogTitle>Planned Runtime CSV Import</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <p className="text-xs text-muted-foreground">Columns: <span className="font-mono">line,date,planned_hours</span> — e.g. <span className="font-mono">PC21,2026-01-15,16</span></p>
            <Textarea data-testid="runtime-csv-textarea" value={csvText} onChange={(e) => setCsvText(e.target.value)} rows={8}
              placeholder={'line,date,planned_hours\nPC21,2026-01-15,16'} className="bg-[hsl(var(--panel-2))] font-mono text-xs" />
            <div className="flex gap-2">
              <Button variant="outline" onClick={doPreview} data-testid="runtime-csv-preview" className="border-border bg-[hsl(var(--panel-2))]">Preview</Button>
              {preview && preview.errors.length === 0 && preview.valid_rows > 0 && (
                <Button onClick={doApply} data-testid="runtime-csv-apply" className="border border-[#05ffa1]/60 bg-transparent text-[#05ffa1] hover:bg-[#05ffa1]/10">Apply {preview.valid_rows} rows</Button>
              )}
            </div>
            {preview && (
              <div className="space-y-2">
                {preview.errors.length > 0 && (
                  <div className="rounded-md border border-[#ff2e63]/40 bg-[#ff2e63]/10 p-2 text-xs text-[#ff2e63]" data-testid="runtime-csv-errors">
                    {preview.errors.map((e, i) => <div key={i}>{e}</div>)}
                  </div>
                )}
                <div className="max-h-48 overflow-y-auto rounded-md border border-border">
                  <table className="w-full text-xs">
                    <thead className="bg-[hsl(var(--panel-2))]"><tr><th className="p-1.5 text-left">Line</th><th className="p-1.5">Date</th><th className="p-1.5">Planned h</th><th className="p-1.5">Machines</th></tr></thead>
                    <tbody>
                      {preview.rows.map((r, i) => (
                        <tr key={i} className="border-t border-border"><td className="p-1.5">{r.line}</td><td className="p-1.5 text-center font-mono">{r.date}</td><td className="p-1.5 text-center">{r.planned_hours}</td><td className="p-1.5 text-center">{r.machines_count}</td></tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
