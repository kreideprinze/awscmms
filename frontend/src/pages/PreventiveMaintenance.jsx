import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { Plus, CheckCircle2, FileDown, UserRound } from 'lucide-react';
import { api, errMsg } from '@/lib/api';
import { useApp } from '@/context/AppContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { CritBadge } from '@/components/StatusBits';
import { MachineSelect, TechnicianSelect, KpiCard } from '@/components/Shared';
import { ChecklistBuilder, downloadPmPdf } from '@/components/ChecklistBuilder';

const FREQS = ['daily', 'weekly', 'monthly', 'quarterly', 'yearly'];
const EMPTY_FORM = { task_name: '', description: '', priority: 'medium', machine_id: '', assigned_to: '', frequency: 'monthly', location: '', reminder_offset_days: 1, next_due_date: '' };

export default function PreventiveMaintenance() {
  const { openMachine, isAdmin, user } = useApp();
  const navigate = useNavigate();
  const isTechRole = user?.role === 'technician';
  const [data, setData] = useState({ items: [], total: 0 });
  const [filter, setFilter] = useState('all');
  const [myTasks, setMyTasks] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [templates, setTemplates] = useState([]);
  const [form, setForm] = useState(EMPTY_FORM);
  const [groups, setGroups] = useState([]);

  const load = useCallback(() => {
    const q = filter === 'overdue' ? '?due=overdue' : '';
    api.get(`/pm-tasks${q}`).then((r) => setData(r.data));
  }, [filter]);
  useEffect(() => { load(); api.get('/pm-templates').then((r) => setTemplates(r.data)); }, [load]);

  const items = myTasks ? data.items.filter((t) => t.assigned_to === user?.username) : data.items;

  const applyTemplate = (tid) => {
    const t = templates.find((x) => x.id === tid);
    if (!t) return;
    setForm((f) => ({ ...f, task_name: t.name, frequency: t.frequency, priority: t.priority }));
    if (t.checklist_groups?.length) setGroups(JSON.parse(JSON.stringify(t.checklist_groups)));
    else setGroups((t.checklist || []).map((c) => ({ description: c, items: [{ checked_for: 'Condition', parameter: '' }] })));
  };

  const create = async () => {
    if (!form.machine_id || !form.task_name) { toast.error('Machine and task name are required'); return; }
    const cleaned = groups
      .map((g) => ({ description: g.description.trim(), items: g.items.filter((i) => i.checked_for.trim()) }))
      .filter((g) => g.description && g.items.length);
    if (!cleaned.length) { toast.error('Add at least one checklist component with a sub-item'); return; }
    try {
      await api.post('/pm-tasks', {
        ...form,
        assigned_to: form.assigned_to || undefined,
        location: form.location || undefined,
        next_due_date: form.next_due_date || undefined,
        reminder_offset_days: parseInt(form.reminder_offset_days, 10) || 0,
        checklist_groups: cleaned,
      });
      toast.success('PM task created with structured checklist');
      setCreateOpen(false);
      setForm(EMPTY_FORM);
      setGroups([]);
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
          <p className="text-sm text-muted-foreground">Structured checklists · printable sheets · background scheduler generates PM work orders</p>
        </div>
        {isAdmin && (
          <Button data-testid="pm-create-button" onClick={() => setCreateOpen(true)}>
            <Plus className="mr-1 h-4 w-4" /> New PM Task
          </Button>
        )}
      </div>

      <div className="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
        <KpiCard testId="pm-kpi-total" label="Active Tasks" value={data.items.filter((t) => t.active).length} />
        <KpiCard testId="pm-kpi-overdue" label="Overdue" value={overdueCnt} accent={overdueCnt ? 'text-[#ff2e63]' : ''} />
        <KpiCard testId="pm-kpi-suggested" label="Predictive Suggestions" value={data.items.filter((t) => t.source === 'predictive').length} accent="text-[#ff9e1c]" />
        <KpiCard testId="pm-kpi-due-week" label="Due in 7 days" value={data.items.filter((t) => t.active && t.next_due_date >= today && new Date(t.next_due_date) - new Date(today) <= 7 * 864e5).length} />
      </div>

      <div className="mb-4 flex gap-2">
        {isTechRole && (
          <button
            data-testid="pm-my-tasks-toggle"
            onClick={() => setMyTasks(!myTasks)}
            className={`cyber-chamfer-sm flex items-center gap-1 border px-3 py-1 font-mono text-[11px] uppercase tracking-wide transition-colors ${myTasks ? 'power-on border-[#05ffa1] bg-transparent text-[#05ffa1] shadow-[0_0_8px_rgba(5,255,161,0.25)]' : 'border-border text-muted-foreground hover:text-foreground'}`}>
            <UserRound className="h-3 w-3" /> My Tasks
          </button>
        )}
        {['all', 'overdue'].map((f) => (
          <button key={f} onClick={() => setFilter(f)} data-testid={`pm-filter-${f}`}
            className={`cyber-chamfer-sm border px-3 py-1 font-mono text-[11px] uppercase tracking-wide transition-colors capitalize ${filter === f ? 'power-on border-[hsl(var(--primary))] bg-transparent text-[hsl(var(--primary))] shadow-[0_0_8px_rgba(var(--accent-rgb),0.25)]' : 'border-border text-muted-foreground hover:text-foreground'}`}>
            {f}
          </button>
        ))}
      </div>

      <div className="overflow-hidden border border-border">
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
            {items.length === 0 && <TableRow><TableCell colSpan={7} className="py-10 text-center text-muted-foreground">No PM tasks match filters. Create one to start the schedule.</TableCell></TableRow>}
            {items.map((t) => {
              const rowCount = t.checklist_groups?.length ? t.checklist_groups.reduce((n, g) => n + g.items.length, 0) : (t.checklist?.length || 0);
              return (
                <TableRow key={t.id} data-testid={`pm-row-${t.id}`} className="border-border hover:bg-white/[0.03]">
                  <TableCell>
                    <div className="text-sm font-medium">{t.task_name} {t.source === 'predictive' && <span className="ml-1 border border-[#ff9e1c]/50 px-1 text-[9px] uppercase text-[#ff9e1c]">AWS</span>}</div>
                    {rowCount > 0 && <div className="text-[10px] text-muted-foreground">{t.checklist_groups?.length ? `${t.checklist_groups.length} components · ` : ''}{rowCount} check rows</div>}
                  </TableCell>
                  <TableCell><button className="text-sm hover:text-[hsl(var(--primary))]" onClick={() => openMachine(t.machine_id)}>{t.machine_name}</button></TableCell>
                  <TableCell className="text-xs capitalize">{t.frequency}</TableCell>
                  <TableCell><CritBadge level={t.priority} /></TableCell>
                  <TableCell className={`font-mono text-xs ${t.next_due_date < today && t.active ? 'text-[#ff2e63]' : ''}`}>{t.next_due_date}</TableCell>
                  <TableCell className="text-sm">{t.assigned_to || '—'}</TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1.5">
                      {t.active !== false && (
                        <Button size="sm" className="h-6 border border-[#05ffa1]/60 bg-transparent text-[10px] text-[#05ffa1] hover:bg-[#05ffa1]/10" data-testid={`pm-complete-${t.id}`}
                          onClick={() => navigate(`/preventive-maintenance/close/${t.id}`)}>
                          <CheckCircle2 className="mr-1 h-3 w-3" /> Complete
                        </Button>
                      )}
                      <Button size="sm" variant="outline" className="h-6 px-1.5 text-[10px]" title="Download blank checklist PDF" data-testid={`pm-pdf-blank-${t.id}`}
                        onClick={() => downloadPmPdf(t.id, null, `PM_${t.task_name}_blank.pdf`).catch(() => toast.error('PDF download failed'))}>
                        <FileDown className="h-3 w-3" />
                      </Button>
                      {t.last_completed_at && (
                        <Button size="sm" variant="ghost" className="h-6 px-1.5 text-[10px] text-muted-foreground" title="Download last completed sheet" data-testid={`pm-pdf-done-${t.id}`}
                          onClick={() => downloadPmPdf(t.id, 'latest', `PM_${t.task_name}_completed.pdf`).catch(() => toast.error('No completion found'))}>
                          <FileDown className="mr-0.5 h-3 w-3" /> last
                        </Button>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="max-h-[88vh] overflow-y-auto border-border bg-[hsl(var(--panel-1))] sm:max-w-3xl">
          <DialogHeader><DialogTitle>New PM Task — Structured Checklist</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div>
              <Label className="text-xs">Start from template (optional)</Label>
              <Select onValueChange={applyTemplate}>
                <SelectTrigger data-testid="pm-template-select" className="bg-[hsl(var(--panel-2))]"><SelectValue placeholder="Choose PM template" /></SelectTrigger>
                <SelectContent>{templates.map((t) => <SelectItem key={t.id} value={t.id}>{t.name} ({t.frequency})</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label className="text-xs">Machine</Label><MachineSelect value={form.machine_id} onChange={(id) => setForm({ ...form, machine_id: id })} testId="pm-create-machine-select" /></div>
              <div><Label className="text-xs">Task Name (PM title)</Label><Input data-testid="pm-create-name" value={form.task_name} onChange={(e) => setForm({ ...form, task_name: e.target.value })} className="bg-[hsl(var(--panel-2))]" /></div>
            </div>
            <div className="grid grid-cols-3 gap-3">
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
              <div><Label className="text-xs">Location / Area</Label><Input data-testid="pm-create-location" value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })} placeholder="e.g. Utility Area" className="bg-[hsl(var(--panel-2))]" /></div>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div><Label className="text-xs">First Due Date</Label><Input type="date" data-testid="pm-create-due-date" value={form.next_due_date} onChange={(e) => setForm({ ...form, next_due_date: e.target.value })} className="bg-[hsl(var(--panel-2))]" /></div>
              <div><Label className="text-xs">Reminder Offset (days)</Label><Input type="number" min="0" value={form.reminder_offset_days} onChange={(e) => setForm({ ...form, reminder_offset_days: e.target.value })} className="bg-[hsl(var(--panel-2))]" /></div>
              <div><Label className="text-xs">Assign Technician</Label><TechnicianSelect value={form.assigned_to} onChange={(v) => setForm({ ...form, assigned_to: v })} testId="pm-create-technician" /></div>
            </div>
            <div><Label className="text-xs">Description (optional)</Label><Textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} rows={2} className="bg-[hsl(var(--panel-2))]" /></div>
            <div>
              <Label className="text-xs">Checklist — components with sub-items (reused every schedule)</Label>
              <div className="mt-1.5"><ChecklistBuilder groups={groups} setGroups={setGroups} /></div>
            </div>
            <Button onClick={create} data-testid="pm-create-submit" className="w-full">Create PM Task</Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
