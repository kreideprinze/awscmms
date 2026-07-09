import React, { useEffect, useState, useCallback } from 'react';
import { toast } from 'sonner';
import { Plus, CheckCircle2 } from 'lucide-react';
import { api, errMsg } from '@/lib/api';
import { useApp } from '@/context/AppContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { CritBadge, fmtDate } from '@/components/StatusBits';
import { MachineSelect, TechnicianSelect, SpareRows, KpiCard } from '@/components/Shared';

const FREQS = ['daily', 'weekly', 'monthly', 'quarterly', 'yearly'];

function CompletePMDialog({ task, open, setOpen, onDone }) {
  const [remarks, setRemarks] = useState('');
  const [spares, setSpares] = useState([]);
  const [checklist, setChecklist] = useState({});
  useEffect(() => {
    if (task?.checklist) setChecklist(Object.fromEntries(task.checklist.map((c) => [c, false])));
    setRemarks(''); setSpares([]);
  }, [task]);
  if (!task) return null;
  const submit = async () => {
    try {
      await api.post(`/pm-tasks/${task.id}/complete`, {
        remarks: remarks || undefined,
        checklist_results: Object.keys(checklist).length ? checklist : undefined,
        spares_consumed: spares.filter((s) => s.sap_code && s.quantity > 0).map((s) => ({ sap_code: s.sap_code, quantity: parseFloat(s.quantity) })),
      });
      toast.success(`PM “${task.task_name}” completed`);
      setOpen(false); onDone();
    } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="max-h-[85vh] overflow-y-auto border-border bg-[hsl(var(--panel-1))]">
        <DialogHeader><DialogTitle>Complete PM — {task.task_name}</DialogTitle></DialogHeader>
        <div className="space-y-3">
          {task.checklist?.length > 0 && (
            <div className="space-y-1.5 rounded-md border border-border bg-[hsl(var(--panel-2))] p-3">
              <Label className="text-xs uppercase tracking-wide text-muted-foreground">Checklist</Label>
              {task.checklist.map((c) => (
                <label key={c} className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={!!checklist[c]} onChange={(e) => setChecklist({ ...checklist, [c]: e.target.checked })} className="accent-[#2ea8ff]" data-testid={`pm-checklist-item`} />
                  {c}
                </label>
              ))}
            </div>
          )}
          <div><Label className="text-xs">Remarks / Action Taken</Label><Textarea data-testid="pm-complete-remarks" value={remarks} onChange={(e) => setRemarks(e.target.value)} className="bg-[hsl(var(--panel-2))]" /></div>
          <SpareRows rows={spares} setRows={setSpares} />
          <Button onClick={submit} data-testid="pm-complete-confirm" className="w-full bg-green-500/20 text-green-200 hover:bg-green-500/30">Complete PM Task</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default function PreventiveMaintenance() {
  const { openMachine, isAdmin } = useApp();
  const [data, setData] = useState({ items: [], total: 0 });
  const [filter, setFilter] = useState('all');
  const [createOpen, setCreateOpen] = useState(false);
  const [completeTask, setCompleteTask] = useState(null);
  const [completeOpen, setCompleteOpen] = useState(false);
  const [templates, setTemplates] = useState([]);
  const [form, setForm] = useState({ task_name: '', description: '', priority: 'medium', machine_id: '', assigned_to: '', frequency: 'monthly', checklist: '', reminder_offset_days: 1, next_due_date: '' });

  const load = useCallback(() => {
    const q = filter === 'overdue' ? '?due=overdue' : '';
    api.get(`/pm-tasks${q}`).then((r) => setData(r.data));
  }, [filter]);
  useEffect(() => { load(); api.get('/pm-templates').then((r) => setTemplates(r.data)); }, [load]);

  const applyTemplate = (tid) => {
    const t = templates.find((x) => x.id === tid);
    if (t) setForm((f) => ({ ...f, task_name: t.name, frequency: t.frequency, priority: t.priority, checklist: (t.checklist || []).join('\n') }));
  };

  const create = async () => {
    if (!form.machine_id || !form.task_name) { toast.error('Machine and task name are required'); return; }
    try {
      await api.post('/pm-tasks', {
        ...form,
        assigned_to: form.assigned_to || undefined,
        next_due_date: form.next_due_date || undefined,
        reminder_offset_days: parseInt(form.reminder_offset_days, 10) || 0,
        checklist: form.checklist.split('\n').map((s) => s.trim()).filter(Boolean),
      });
      toast.success('PM task created');
      setCreateOpen(false);
      load();
    } catch (e) { toast.error(errMsg(e)); }
  };

  const today = new Date().toISOString().slice(0, 10);
  const overdueCnt = data.items.filter((t) => t.active && t.next_due_date < today).length;

  return (
    <div className="p-6" data-testid="pm-page">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Preventive Maintenance</h1>
          <p className="text-sm text-muted-foreground">Background scheduler generates PM work orders automatically</p>
        </div>
        {isAdmin && (
          <Button data-testid="pm-create-button" onClick={() => setCreateOpen(true)} className="bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))]">
            <Plus className="mr-1 h-4 w-4" /> New PM Task
          </Button>
        )}
      </div>

      <div className="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
        <KpiCard testId="pm-kpi-total" label="Active Tasks" value={data.items.filter((t) => t.active).length} />
        <KpiCard testId="pm-kpi-overdue" label="Overdue" value={overdueCnt} accent={overdueCnt ? 'text-red-400' : ''} />
        <KpiCard testId="pm-kpi-suggested" label="Predictive Suggestions" value={data.items.filter((t) => t.source === 'predictive').length} accent="text-orange-300" />
        <KpiCard testId="pm-kpi-due-week" label="Due in 7 days" value={data.items.filter((t) => t.active && t.next_due_date >= today && new Date(t.next_due_date) - new Date(today) <= 7 * 864e5).length} />
      </div>

      <div className="mb-4 flex gap-2">
        {['all', 'overdue'].map((f) => (
          <button key={f} onClick={() => setFilter(f)} data-testid={`pm-filter-${f}`}
            className={`rounded-full border px-3 py-1 text-xs capitalize ${filter === f ? 'border-[hsl(var(--primary))] bg-[rgba(46,168,255,0.12)]' : 'border-border text-muted-foreground hover:text-foreground'}`}>
            {f}
          </button>
        ))}
      </div>

      <div className="overflow-hidden rounded-lg border border-border">
        <Table data-testid="pm-table">
          <TableHeader>
            <TableRow className="border-border bg-[hsl(var(--panel-1))] hover:bg-[hsl(var(--panel-1))]">
              <TableHead className="text-xs uppercase">Task</TableHead>
              <TableHead className="text-xs uppercase">Machine</TableHead>
              <TableHead className="text-xs uppercase">Frequency</TableHead>
              <TableHead className="text-xs uppercase">Priority</TableHead>
              <TableHead className="text-xs uppercase">Next Due</TableHead>
              <TableHead className="text-xs uppercase">Assigned</TableHead>
              <TableHead className="text-xs uppercase">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.items.length === 0 && <TableRow><TableCell colSpan={7} className="py-10 text-center text-muted-foreground">No PM tasks yet. Create one to start the schedule.</TableCell></TableRow>}
            {data.items.map((t) => (
              <TableRow key={t.id} data-testid={`pm-row-${t.id}`} className="border-border hover:bg-white/[0.03]">
                <TableCell>
                  <div className="text-sm font-medium">{t.task_name} {t.source === 'predictive' && <span className="ml-1 rounded bg-orange-500/15 px-1 text-[9px] uppercase text-orange-300">AWS</span>}</div>
                  {t.checklist?.length > 0 && <div className="text-[10px] text-muted-foreground">{t.checklist.length} checklist items</div>}
                </TableCell>
                <TableCell><button className="text-sm hover:text-[hsl(var(--primary))]" onClick={() => openMachine(t.machine_id)}>{t.machine_name}</button></TableCell>
                <TableCell className="text-xs capitalize">{t.frequency}</TableCell>
                <TableCell><CritBadge level={t.priority} /></TableCell>
                <TableCell className={`font-mono text-xs ${t.next_due_date < today && t.active ? 'text-red-400' : ''}`}>{t.next_due_date}</TableCell>
                <TableCell className="text-sm">{t.assigned_to || '—'}</TableCell>
                <TableCell>
                  {t.active !== false && (
                    <Button size="sm" className="h-6 bg-green-500/20 text-[10px] text-green-200 hover:bg-green-500/30" data-testid={`pm-complete-${t.id}`}
                      onClick={() => { setCompleteTask(t); setCompleteOpen(true); }}>
                      <CheckCircle2 className="mr-1 h-3 w-3" /> Complete
                    </Button>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="max-h-[85vh] overflow-y-auto border-border bg-[hsl(var(--panel-1))]">
          <DialogHeader><DialogTitle>New PM Task</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div>
              <Label className="text-xs">Start from template (optional)</Label>
              <Select onValueChange={applyTemplate}>
                <SelectTrigger data-testid="pm-template-select" className="bg-[hsl(var(--panel-2))]"><SelectValue placeholder="Choose PM template" /></SelectTrigger>
                <SelectContent>{templates.map((t) => <SelectItem key={t.id} value={t.id}>{t.name} ({t.frequency})</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div><Label className="text-xs">Machine</Label><MachineSelect value={form.machine_id} onChange={(id) => setForm({ ...form, machine_id: id })} testId="pm-create-machine-select" /></div>
            <div><Label className="text-xs">Task Name</Label><Input data-testid="pm-create-name" value={form.task_name} onChange={(e) => setForm({ ...form, task_name: e.target.value })} className="bg-[hsl(var(--panel-2))]" /></div>
            <div><Label className="text-xs">Description</Label><Textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className="bg-[hsl(var(--panel-2))]" /></div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs">Frequency</Label>
                <Select value={form.frequency} onValueChange={(v) => setForm({ ...form, frequency: v })}>
                  <SelectTrigger data-testid="pm-create-frequency" className="bg-[hsl(var(--panel-2))]"><SelectValue /></SelectTrigger>
                  <SelectContent>{FREQS.map((f) => <SelectItem key={f} value={f} className="capitalize">{f}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-xs">Priority</Label>
                <Select value={form.priority} onValueChange={(v) => setForm({ ...form, priority: v })}>
                  <SelectTrigger className="bg-[hsl(var(--panel-2))]"><SelectValue /></SelectTrigger>
                  <SelectContent>{['low', 'medium', 'high', 'critical'].map((p) => <SelectItem key={p} value={p}>{p}</SelectItem>)}</SelectContent>
                </Select>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label className="text-xs">First Due Date</Label><Input type="date" data-testid="pm-create-due-date" value={form.next_due_date} onChange={(e) => setForm({ ...form, next_due_date: e.target.value })} className="bg-[hsl(var(--panel-2))]" /></div>
              <div><Label className="text-xs">Reminder Offset (days)</Label><Input type="number" min="0" value={form.reminder_offset_days} onChange={(e) => setForm({ ...form, reminder_offset_days: e.target.value })} className="bg-[hsl(var(--panel-2))]" /></div>
            </div>
            <div><Label className="text-xs">Assign Technician</Label><TechnicianSelect value={form.assigned_to} onChange={(v) => setForm({ ...form, assigned_to: v })} testId="pm-create-technician" /></div>
            <div><Label className="text-xs">Checklist (one item per line)</Label><Textarea data-testid="pm-create-checklist" value={form.checklist} onChange={(e) => setForm({ ...form, checklist: e.target.value })} rows={4} className="bg-[hsl(var(--panel-2))] font-mono text-xs" /></div>
            <Button onClick={create} data-testid="pm-create-submit" className="w-full bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))]">Create PM Task</Button>
          </div>
        </DialogContent>
      </Dialog>

      <CompletePMDialog task={completeTask} open={completeOpen} setOpen={setCompleteOpen} onDone={load} />
    </div>
  );
}
