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
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { MachineSelect, KpiCard } from '@/components/Shared';

export default function Runtime() {
  const { isAdmin, openMachine } = useApp();
  const [data, setData] = useState({ items: [], total: 0 });
  const [entryOpen, setEntryOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [form, setForm] = useState({ machine_id: '', date: new Date().toISOString().slice(0, 10), calendar_hours: 24, run_hours: '' });
  const [csvText, setCsvText] = useState('');
  const [preview, setPreview] = useState(null);
  const [summary, setSummary] = useState({ run: 0, cal: 0 });

  const load = useCallback(() => {
    api.get('/runtime-logs?limit=500').then((r) => {
      setData(r.data);
      const run = r.data.items.reduce((n, x) => n + x.run_hours, 0);
      const cal = r.data.items.reduce((n, x) => n + x.calendar_hours, 0);
      setSummary({ run: Math.round(run), cal: Math.round(cal) });
    });
  }, []);
  useEffect(() => { load(); }, [load]);

  const submit = async () => {
    if (!form.machine_id || form.run_hours === '') { toast.error('Machine and run hours required'); return; }
    try {
      await api.post('/runtime-logs', { ...form, calendar_hours: parseFloat(form.calendar_hours), run_hours: parseFloat(form.run_hours) });
      toast.success('Runtime log saved');
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
      toast.success(`Imported ${res.data.imported} runtime rows`);
      setImportOpen(false); setPreview(null); setCsvText('');
      load();
    } catch (e) { toast.error(errMsg(e)); }
  };

  const avail = summary.cal ? Math.round((summary.run / summary.cal) * 1000) / 10 : null;

  return (
    <div className="p-6" data-testid="runtime-page">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Runtime Tracking</h1>
          <p className="text-sm text-muted-foreground">Calendar Hours · Run Hours · Dark Hours · Availability = Run ÷ Calendar × 100</p>
        </div>
        {isAdmin && (
          <div className="flex gap-2">
            <Button variant="outline" data-testid="runtime-import-button" onClick={() => setImportOpen(true)} className="border-border bg-[hsl(var(--panel-2))]">
              <Upload className="mr-1 h-4 w-4" /> CSV Import
            </Button>
            <Button data-testid="runtime-entry-button" onClick={() => setEntryOpen(true)} className="bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))]">
              <Plus className="mr-1 h-4 w-4" /> Log Runtime
            </Button>
          </div>
        )}
      </div>

      <div className="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
        <KpiCard testId="runtime-kpi-records" label="Records" value={data.total} />
        <KpiCard testId="runtime-kpi-run" label="Run Hours" value={`${summary.run}h`} accent="text-green-400" />
        <KpiCard testId="runtime-kpi-dark" label="Dark Hours" value={`${summary.cal - summary.run}h`} />
        <KpiCard testId="runtime-kpi-availability" label="Availability" value={avail != null ? `${avail}%` : '—'} accent="text-[hsl(var(--primary))]" />
      </div>

      <div className="overflow-hidden rounded-lg border border-border">
        <Table data-testid="runtime-table">
          <TableHeader>
            <TableRow className="border-border bg-[hsl(var(--panel-1))] hover:bg-[hsl(var(--panel-1))]">
              <TableHead className="text-xs uppercase">Date</TableHead>
              <TableHead className="text-xs uppercase">Machine</TableHead>
              <TableHead className="text-xs uppercase">Line</TableHead>
              <TableHead className="text-xs uppercase">Calendar h</TableHead>
              <TableHead className="text-xs uppercase">Run h</TableHead>
              <TableHead className="text-xs uppercase">Dark h</TableHead>
              <TableHead className="text-xs uppercase">Availability</TableHead>
              <TableHead className="text-xs uppercase">Source</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.items.length === 0 && <TableRow><TableCell colSpan={8} className="py-10 text-center text-muted-foreground">No runtime logs yet. Admins can log manually or import CSV.</TableCell></TableRow>}
            {data.items.map((r) => (
              <TableRow key={r.id} className="border-border hover:bg-white/[0.03]">
                <TableCell className="font-mono text-xs">{r.date}</TableCell>
                <TableCell><button className="text-sm hover:text-[hsl(var(--primary))]" onClick={() => openMachine(r.machine_id)}>{r.machine_name}</button></TableCell>
                <TableCell className="text-xs">{r.line}</TableCell>
                <TableCell className="tabular-nums text-sm">{r.calendar_hours}</TableCell>
                <TableCell className="tabular-nums text-sm text-green-400">{r.run_hours}</TableCell>
                <TableCell className="tabular-nums text-sm">{r.dark_hours}</TableCell>
                <TableCell className="tabular-nums text-sm">{r.availability}%</TableCell>
                <TableCell className="text-xs text-muted-foreground">{r.source}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {/* Manual entry */}
      <Dialog open={entryOpen} onOpenChange={setEntryOpen}>
        <DialogContent className="border-border bg-[hsl(var(--panel-1))]">
          <DialogHeader><DialogTitle>Log Runtime</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div><Label className="text-xs">Machine</Label><MachineSelect value={form.machine_id} onChange={(id) => setForm({ ...form, machine_id: id })} testId="runtime-machine-select" /></div>
            <div className="grid grid-cols-3 gap-3">
              <div><Label className="text-xs">Date</Label><Input type="date" data-testid="runtime-date-input" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} className="bg-[hsl(var(--panel-2))]" /></div>
              <div><Label className="text-xs">Calendar h</Label><Input type="number" min="0.1" data-testid="runtime-calendar-input" value={form.calendar_hours} onChange={(e) => setForm({ ...form, calendar_hours: e.target.value })} className="bg-[hsl(var(--panel-2))]" /></div>
              <div><Label className="text-xs">Run h</Label><Input type="number" min="0" data-testid="runtime-run-input" value={form.run_hours} onChange={(e) => setForm({ ...form, run_hours: e.target.value })} className="bg-[hsl(var(--panel-2))]" /></div>
            </div>
            <Button onClick={submit} data-testid="runtime-submit" className="w-full bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))]">Save Runtime Log</Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* CSV import */}
      <Dialog open={importOpen} onOpenChange={(o) => { setImportOpen(o); if (!o) setPreview(null); }}>
        <DialogContent className="max-h-[85vh] max-w-2xl overflow-y-auto border-border bg-[hsl(var(--panel-1))]">
          <DialogHeader><DialogTitle>Runtime CSV Import</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <p className="text-xs text-muted-foreground">Columns: <span className="font-mono">machine_code,date,run_hours[,calendar_hours]</span> — e.g. <span className="font-mono">PC21-FRY-002,2025-01-15,22</span></p>
            <Textarea data-testid="runtime-csv-textarea" value={csvText} onChange={(e) => setCsvText(e.target.value)} rows={8}
              placeholder={'machine_code,date,run_hours,calendar_hours\nPC21-FRY-001,2025-01-15,22,24'} className="bg-[hsl(var(--panel-2))] font-mono text-xs" />
            <div className="flex gap-2">
              <Button variant="outline" onClick={doPreview} data-testid="runtime-csv-preview" className="border-border bg-[hsl(var(--panel-2))]">Preview</Button>
              {preview && preview.errors.length === 0 && preview.valid_rows > 0 && (
                <Button onClick={doApply} data-testid="runtime-csv-apply" className="bg-green-500/20 text-green-200 hover:bg-green-500/30">Apply {preview.valid_rows} rows</Button>
              )}
            </div>
            {preview && (
              <div className="space-y-2">
                {preview.errors.length > 0 && (
                  <div className="rounded-md border border-red-500/30 bg-red-500/10 p-2 text-xs text-red-300" data-testid="runtime-csv-errors">
                    {preview.errors.map((e, i) => <div key={i}>{e}</div>)}
                  </div>
                )}
                <div className="max-h-48 overflow-y-auto rounded-md border border-border">
                  <table className="w-full text-xs">
                    <thead className="bg-[hsl(var(--panel-2))]"><tr><th className="p-1.5 text-left">Machine</th><th className="p-1.5">Date</th><th className="p-1.5">Run</th><th className="p-1.5">Cal</th><th className="p-1.5">Avail</th></tr></thead>
                    <tbody>
                      {preview.rows.map((r, i) => (
                        <tr key={i} className="border-t border-border"><td className="p-1.5">{r.machine_name}</td><td className="p-1.5 text-center font-mono">{r.date}</td><td className="p-1.5 text-center">{r.run_hours}</td><td className="p-1.5 text-center">{r.calendar_hours}</td><td className="p-1.5 text-center">{r.availability}%</td></tr>
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
