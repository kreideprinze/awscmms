import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { toast } from 'sonner';
import { Plus, Upload, ChevronLeft, ChevronRight, CalendarDays, Rows3, Trash2 } from 'lucide-react';
import { api, errMsg } from '@/lib/api';
import { useApp } from '@/context/AppContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { KpiCard } from '@/components/Shared';

// Runtime is logged PER LINE (one entry per line per day). Line availability = run/calendar.
// Machines inherit their line's runtime automatically for Weibull/reliability computations.
// The calendar view makes logged vs missing line-days visually obvious.

const iso = (d) => d.toISOString().slice(0, 10);
const monthLabel = (d) => d.toLocaleDateString('en-GB', { month: 'long', year: 'numeric' });

// Per-day per-line editor inside the day dialog. Admin: full CRUD; others: view-only.
function DayLineRow({ line, date, log, isAdmin, onSaved }) {
  const [cal, setCal] = useState(log ? String(log.calendar_hours) : '24');
  const [run, setRun] = useState(log ? String(log.run_hours) : '');
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    setCal(log ? String(log.calendar_hours) : '24');
    setRun(log ? String(log.run_hours) : '');
  }, [log]);

  const save = async () => {
    if (run === '' || cal === '') { toast.error('Calendar and run hours required'); return; }
    setBusy(true);
    try {
      await api.post('/runtime-logs', { line, date, calendar_hours: parseFloat(cal), run_hours: parseFloat(run) });
      toast.success(`${line} · ${date} runtime saved`);
      onSaved();
    } catch (e) { toast.error(errMsg(e)); }
    setBusy(false);
  };

  const remove = async () => {
    setBusy(true);
    try {
      await api.delete(`/line-runtime-logs?line=${encodeURIComponent(line)}&date=${date}`);
      toast.success(`${line} · ${date} runtime removed`);
      onSaved();
    } catch (e) { toast.error(errMsg(e)); }
    setBusy(false);
  };

  const avail = log ? log.availability : (cal && run !== '' && parseFloat(cal) > 0 ? Math.round((parseFloat(run) / parseFloat(cal)) * 1000) / 10 : null);

  return (
    <div className={`flex flex-wrap items-center gap-2 border px-3 py-2 ${log ? 'border-[#05ffa1]/30 bg-[#05ffa1]/[0.03]' : 'border-border bg-[hsl(var(--panel-2))]/40'}`}
      data-testid={`day-line-row-${line}`}>
      <div className="w-28 shrink-0">
        <div className="text-sm font-medium">{line}</div>
        <div className={`font-mono text-[9px] uppercase tracking-wide ${log ? 'text-[#05ffa1]' : 'text-muted-foreground'}`}>{log ? 'logged' : 'missing'}</div>
      </div>
      {isAdmin ? (
        <>
          <div className="w-20"><Label className="text-[9px] uppercase text-muted-foreground">Cal h</Label>
            <Input type="number" min="0.1" value={cal} onChange={(e) => setCal(e.target.value)} data-testid={`day-cal-${line}`} className="h-7 bg-[hsl(var(--panel-1))] text-xs" /></div>
          <div className="w-20"><Label className="text-[9px] uppercase text-muted-foreground">Run h</Label>
            <Input type="number" min="0" value={run} onChange={(e) => setRun(e.target.value)} data-testid={`day-run-${line}`} className="h-7 bg-[hsl(var(--panel-1))] text-xs" /></div>
          <div className="w-16 text-center">
            <div className="text-[9px] uppercase text-muted-foreground">Avail</div>
            <div className="tabular-nums text-xs text-[hsl(var(--primary))]">{avail != null ? `${avail}%` : '—'}</div>
          </div>
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
        </>
      ) : (
        <div className="ml-auto flex gap-4 font-mono text-xs">
          {log ? (
            <>
              <span>Cal {log.calendar_hours}h</span>
              <span className="text-[#05ffa1]">Run {log.run_hours}h</span>
              <span>Dark {log.dark_hours}h</span>
              <span className="text-[hsl(var(--primary))]">{log.availability}%</span>
            </>
          ) : <span className="text-muted-foreground">not logged</span>}
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
  const [form, setForm] = useState({ line: '', date: new Date().toISOString().slice(0, 10), calendar_hours: 24, run_hours: '' });
  const [csvText, setCsvText] = useState('');
  const [preview, setPreview] = useState(null);
  const [summary, setSummary] = useState({ run: 0, cal: 0 });
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
      const run = r.data.items.reduce((n, x) => n + x.run_hours, 0);
      const cal = r.data.items.reduce((n, x) => n + x.calendar_hours, 0);
      setSummary({ run: Math.round(run), cal: Math.round(cal) });
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
    if (!form.line || form.run_hours === '') { toast.error('Line and run hours required'); return; }
    try {
      const res = await api.post('/runtime-logs', { ...form, calendar_hours: parseFloat(form.calendar_hours), run_hours: parseFloat(form.run_hours) });
      toast.success(`Line runtime saved — ${res.data.machines_count} machines inherit ${res.data.run_hours}h`);
      setEntryOpen(false); setForm({ ...form, run_hours: '' });
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
      toast.success(`Imported ${res.data.imported} line runtime rows (${res.data.machines_affected} machines updated)`);
      setImportOpen(false); setPreview(null); setCsvText('');
      refreshAll();
    } catch (e) { toast.error(errMsg(e)); }
  };

  const avail = summary.cal ? Math.round((summary.run / summary.cal) * 1000) / 10 : null;
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
          <h1 className="text-2xl font-semibold tracking-tight">Runtime Tracking — Per Line</h1>
          <p className="text-sm text-muted-foreground">One entry per line per day · Availability = Run ÷ Calendar × 100 · Machines inherit line runtime for reliability</p>
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
                <Plus className="mr-1 h-4 w-4" /> Log Line Runtime
              </Button>
            </>
          )}
        </div>
      </div>

      <div className="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
        <KpiCard testId="runtime-kpi-records" label="Line Records" value={data.total} />
        <KpiCard testId="runtime-kpi-run" label="Run Hours" value={`${summary.run}h`} accent="text-[#05ffa1]" />
        <KpiCard testId="runtime-kpi-dark" label="Dark Hours" value={`${summary.cal - summary.run}h`} />
        <KpiCard testId="runtime-kpi-availability" label="Availability" value={avail != null ? `${avail}%` : '—'} accent="text-[hsl(var(--primary))]" />
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
              <span className="flex items-center gap-1"><span className="h-2.5 w-2.5 border border-border" /> missing</span>
            </div>
          </div>
          <div className="grid grid-cols-7 gap-1.5">
            {['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN'].map((d) => (
              <div key={d} className="pb-1 text-center font-mono text-[10px] uppercase tracking-widest text-muted-foreground">{d}</div>
            ))}
            {cells.map((date, i) => {
              if (!date) return <div key={`empty-${i}`} />;
              const logged = Object.keys(logsByDate[date] || {}).length;
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
                  <span className="font-mono text-xs">{parseInt(date.slice(8), 10)}</span>
                  {!isFuture && (
                    <span className={`font-mono text-[9px] ${logged >= total ? 'text-[#05ffa1]' : logged > 0 ? 'text-[#f9f871]' : 'text-muted-foreground/60'}`}>
                      {logged}/{total} lines
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
                  <TableHead className="text-xs uppercase">Calendar h</TableHead>
                  <TableHead className="text-xs uppercase">Run h</TableHead>
                  <TableHead className="text-xs uppercase">Dark h</TableHead>
                  <TableHead className="text-xs uppercase">Availability</TableHead>
                  <TableHead className="text-xs uppercase">Source</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.items.length === 0 && <TableRow><TableCell colSpan={9} className="py-10 text-center text-muted-foreground">No line runtime logs yet. Admins can log manually or import CSV.</TableCell></TableRow>}
                {data.items.map((r) => (
                  <TableRow key={r.id} data-testid={`runtime-row-${r.line}-${r.date}`} className="border-border hover:bg-white/[0.03]">
                    <TableCell className="font-mono text-xs">{r.date}</TableCell>
                    <TableCell className="text-sm font-medium">{r.line}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">{r.department}</TableCell>
                    <TableCell className="tabular-nums text-xs text-muted-foreground">{r.machines_count ?? '—'}</TableCell>
                    <TableCell className="tabular-nums text-sm">{r.calendar_hours}</TableCell>
                    <TableCell className="tabular-nums text-sm text-[#05ffa1]">{r.run_hours}</TableCell>
                    <TableCell className="tabular-nums text-sm">{r.dark_hours}</TableCell>
                    <TableCell className="tabular-nums text-sm">{r.availability}%</TableCell>
                    <TableCell className="text-xs text-muted-foreground">{r.source}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </>
      )}

      {/* Day detail — per-line log/edit (Admin CRUD; others view-only) */}
      <Dialog open={!!dayOpen} onOpenChange={(o) => !o && setDayOpen(null)}>
        <DialogContent className="max-h-[85vh] max-w-xl overflow-y-auto border-border bg-[hsl(var(--panel-1))]" data-testid="runtime-day-dialog">
          <DialogHeader>
            <DialogTitle className="font-mono text-sm uppercase tracking-widest">
              Line Runtime — <span className="text-[hsl(var(--primary))]">{dayOpen}</span>
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-2">
            {!isAdmin && <p className="text-[11px] text-muted-foreground">View-only — runtime entries are managed by Admins.</p>}
            {lines.map((l) => (
              <DayLineRow key={l} line={l} date={dayOpen} log={(logsByDate[dayOpen] || {})[l]} isAdmin={isAdmin} onSaved={refreshAll} />
            ))}
          </div>
        </DialogContent>
      </Dialog>

      {/* Manual line entry */}
      <Dialog open={entryOpen} onOpenChange={setEntryOpen}>
        <DialogContent className="border-border bg-[hsl(var(--panel-1))]">
          <DialogHeader><DialogTitle>Log Line Runtime</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div>
              <Label className="text-xs">Line</Label>
              <Select value={form.line} onValueChange={(v) => setForm({ ...form, line: v })}>
                <SelectTrigger data-testid="runtime-line-select" className="bg-[hsl(var(--panel-2))]"><SelectValue placeholder="Select line" /></SelectTrigger>
                <SelectContent>{lines.map((l) => <SelectItem key={l} value={l}>{l}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div><Label className="text-xs">Date</Label><Input type="date" data-testid="runtime-date-input" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} className="bg-[hsl(var(--panel-2))]" /></div>
              <div><Label className="text-xs">Calendar h</Label><Input type="number" min="0.1" data-testid="runtime-calendar-input" value={form.calendar_hours} onChange={(e) => setForm({ ...form, calendar_hours: e.target.value })} className="bg-[hsl(var(--panel-2))]" /></div>
              <div><Label className="text-xs">Run h</Label><Input type="number" min="0" data-testid="runtime-run-input" value={form.run_hours} onChange={(e) => setForm({ ...form, run_hours: e.target.value })} className="bg-[hsl(var(--panel-2))]" /></div>
            </div>
            <p className="text-[11px] text-muted-foreground">All machines in the selected line inherit this runtime for reliability (Weibull) calculations.</p>
            <Button onClick={submit} data-testid="runtime-submit" className="w-full bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))]">Save Line Runtime</Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* CSV import */}
      <Dialog open={importOpen} onOpenChange={(o) => { setImportOpen(o); if (!o) setPreview(null); }}>
        <DialogContent className="max-h-[85vh] max-w-2xl overflow-y-auto border-border bg-[hsl(var(--panel-1))]">
          <DialogHeader><DialogTitle>Line Runtime CSV Import</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <p className="text-xs text-muted-foreground">Columns: <span className="font-mono">line,date,run_hours[,calendar_hours]</span> — e.g. <span className="font-mono">Fry Line 1,2025-01-15,22</span></p>
            <Textarea data-testid="runtime-csv-textarea" value={csvText} onChange={(e) => setCsvText(e.target.value)} rows={8}
              placeholder={'line,date,run_hours,calendar_hours\nFry Line 1,2025-01-15,22,24'} className="bg-[hsl(var(--panel-2))] font-mono text-xs" />
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
                    <thead className="bg-[hsl(var(--panel-2))]"><tr><th className="p-1.5 text-left">Line</th><th className="p-1.5">Date</th><th className="p-1.5">Run</th><th className="p-1.5">Cal</th><th className="p-1.5">Avail</th><th className="p-1.5">Machines</th></tr></thead>
                    <tbody>
                      {preview.rows.map((r, i) => (
                        <tr key={i} className="border-t border-border"><td className="p-1.5">{r.line}</td><td className="p-1.5 text-center font-mono">{r.date}</td><td className="p-1.5 text-center">{r.run_hours}</td><td className="p-1.5 text-center">{r.calendar_hours}</td><td className="p-1.5 text-center">{r.availability}%</td><td className="p-1.5 text-center">{r.machines_count}</td></tr>
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
