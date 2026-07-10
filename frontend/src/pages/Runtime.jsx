import React, { useEffect, useState, useCallback } from 'react';
import { toast } from 'sonner';
import { Plus, Upload } from 'lucide-react';
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
export default function Runtime() {
  const { isAdmin } = useApp();
  const [data, setData] = useState({ items: [], total: 0 });
  const [lines, setLines] = useState([]);
  const [lineFilter, setLineFilter] = useState('all');
  const [entryOpen, setEntryOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [form, setForm] = useState({ line: '', date: new Date().toISOString().slice(0, 10), calendar_hours: 24, run_hours: '' });
  const [csvText, setCsvText] = useState('');
  const [preview, setPreview] = useState(null);
  const [summary, setSummary] = useState({ run: 0, cal: 0 });

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

  const submit = async () => {
    if (!form.line || form.run_hours === '') { toast.error('Line and run hours required'); return; }
    try {
      const res = await api.post('/runtime-logs', { ...form, calendar_hours: parseFloat(form.calendar_hours), run_hours: parseFloat(form.run_hours) });
      toast.success(`Line runtime saved — ${res.data.machines_count} machines inherit ${res.data.run_hours}h`);
      setEntryOpen(false); setForm({ ...form, run_hours: '' });
      load();
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
      load();
    } catch (e) { toast.error(errMsg(e)); }
  };

  const avail = summary.cal ? Math.round((summary.run / summary.cal) * 1000) / 10 : null;

  return (
    <div className="p-6" data-testid="runtime-page">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Runtime Tracking — Per Line</h1>
          <p className="text-sm text-muted-foreground">One entry per line per day · Availability = Run ÷ Calendar × 100 · Machines inherit line runtime for reliability</p>
        </div>
        {isAdmin && (
          <div className="flex gap-2">
            <Button variant="outline" data-testid="runtime-import-button" onClick={() => setImportOpen(true)} className="border-border bg-[hsl(var(--panel-2))]">
              <Upload className="mr-1 h-4 w-4" /> CSV Import
            </Button>
            <Button data-testid="runtime-entry-button" onClick={() => setEntryOpen(true)} className="bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))]">
              <Plus className="mr-1 h-4 w-4" /> Log Line Runtime
            </Button>
          </div>
        )}
      </div>

      <div className="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
        <KpiCard testId="runtime-kpi-records" label="Line Records" value={data.total} />
        <KpiCard testId="runtime-kpi-run" label="Run Hours" value={`${summary.run}h`} accent="text-[#05ffa1]" />
        <KpiCard testId="runtime-kpi-dark" label="Dark Hours" value={`${summary.cal - summary.run}h`} />
        <KpiCard testId="runtime-kpi-availability" label="Availability" value={avail != null ? `${avail}%` : '—'} accent="text-[hsl(var(--primary))]" />
      </div>

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
