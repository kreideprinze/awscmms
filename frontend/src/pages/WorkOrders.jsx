import React, { useEffect, useState, useCallback } from 'react';
import { toast } from 'sonner';
import { Plus, LayoutGrid, Rows3 } from 'lucide-react';
import { api, errMsg } from '@/lib/api';
import { useApp } from '@/context/AppContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { ScrollArea } from '@/components/ui/scroll-area';
import { LifecycleBadge, CritBadge, fmtDate } from '@/components/StatusBits';
import { MachineSelect, TechnicianSelect, SpareRows } from '@/components/Shared';

const LIFE = ['OPEN', 'ASSIGNED', 'IN_PROGRESS', 'COMPLETED', 'CLOSED'];
const TYPES = ['all', 'Corrective', 'Preventive', 'Inspection'];

function CompleteDialog({ wo, open, setOpen, onDone }) {
  const [actionTaken, setActionTaken] = useState('');
  const [rootCause, setRootCause] = useState('');
  const [spares, setSpares] = useState([]);
  const [checklist, setChecklist] = useState({});

  useEffect(() => {
    if (wo?.checklist) setChecklist(Object.fromEntries(wo.checklist.map((c) => [c, false])));
  }, [wo]);

  if (!wo) return null;
  const submit = async () => {
    try {
      await api.put(`/work-orders/${wo.id}`, {
        action: 'complete', action_taken: actionTaken || undefined, root_cause: rootCause || undefined,
        spare_parts: spares.filter((s) => s.sap_code && s.quantity > 0).map((s) => ({ sap_code: s.sap_code, quantity: parseFloat(s.quantity) })),
        checklist_results: Object.keys(checklist).length ? checklist : undefined,
      });
      toast.success(`${wo.wo_number} completed — inventory updated`);
      setOpen(false); onDone();
    } catch (e) { toast.error(errMsg(e)); }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="max-h-[85vh] overflow-y-auto border-border bg-[hsl(var(--panel-1))]">
        <DialogHeader><DialogTitle>Complete {wo.wo_number}</DialogTitle></DialogHeader>
        <div className="space-y-3">
          {wo.checklist?.length > 0 && (
            <div className="space-y-1.5 rounded-md border border-border bg-[hsl(var(--panel-2))] p-3">
              <Label className="text-xs uppercase tracking-wide text-muted-foreground">Checklist</Label>
              {wo.checklist.map((c) => (
                <label key={c} className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={!!checklist[c]} onChange={(e) => setChecklist({ ...checklist, [c]: e.target.checked })} className="accent-[#2ea8ff]" />
                  {c}
                </label>
              ))}
            </div>
          )}
          <div><Label className="text-xs">Root Cause (optional)</Label><Textarea data-testid="wo-complete-root-cause" value={rootCause} onChange={(e) => setRootCause(e.target.value)} className="bg-[hsl(var(--panel-2))]" /></div>
          <div><Label className="text-xs">Action Taken</Label><Textarea data-testid="wo-complete-action-taken" value={actionTaken} onChange={(e) => setActionTaken(e.target.value)} className="bg-[hsl(var(--panel-2))]" /></div>
          <SpareRows rows={spares} setRows={setSpares} />
          <Button onClick={submit} data-testid="wo-complete-confirm" className="w-full bg-[#05ffa1]/15 text-[#05ffa1] hover:bg-[#05ffa1]/25">Complete Work Order</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default function WorkOrders() {
  const { openMachine } = useApp();
  const [data, setData] = useState({ items: [], total: 0 });
  const [view, setView] = useState('table');
  const [status, setStatus] = useState('all');
  const [woType, setWoType] = useState('all');
  const [createOpen, setCreateOpen] = useState(false);
  const [completeWo, setCompleteWo] = useState(null);
  const [completeOpen, setCompleteOpen] = useState(false);
  const [form, setForm] = useState({ machine_id: '', title: '', description: '', wo_type: 'Corrective', priority: 'medium', assigned_to: '' });

  const load = useCallback(() => {
    const params = new URLSearchParams();
    if (status !== 'all') params.set('status', status);
    if (woType !== 'all') params.set('wo_type', woType);
    api.get(`/work-orders?${params}`).then((r) => setData(r.data));
  }, [status, woType]);
  useEffect(() => { load(); }, [load]);

  const create = async () => {
    if (!form.machine_id || !form.title) { toast.error('Machine and title are required'); return; }
    try {
      const res = await api.post('/work-orders', { ...form, assigned_to: form.assigned_to || undefined });
      toast.success(`${res.data.wo_number} created`);
      setCreateOpen(false);
      setForm({ machine_id: '', title: '', description: '', wo_type: 'Corrective', priority: 'medium', assigned_to: '' });
      load();
    } catch (e) { toast.error(errMsg(e)); }
  };

  const act = async (wo, action, extra = {}) => {
    try {
      await api.put(`/work-orders/${wo.id}`, { action, ...extra });
      toast.success(`${wo.wo_number} ${action}ed`);
      load();
    } catch (e) { toast.error(errMsg(e)); }
  };

  const WOCard = ({ wo }) => (
    <div className="rounded-md border border-border bg-[hsl(var(--panel-1))] p-3">
      <div className="flex items-center justify-between">
        <span className="font-mono text-xs text-[hsl(var(--primary))]">{wo.wo_number}</span>
        <CritBadge level={wo.priority} />
      </div>
      <div className="mt-1 text-sm font-medium">{wo.title}</div>
      <button className="mt-0.5 text-xs text-muted-foreground hover:text-[hsl(var(--primary))]" onClick={() => openMachine(wo.machine_id)}>{wo.machine_name}</button>
      <div className="mt-1 text-[10px] text-muted-foreground">{wo.wo_type} · {wo.assigned_to || 'unassigned'} · {fmtDate(wo.created_at)}</div>
      <div className="mt-2 flex flex-wrap gap-1">
        {['OPEN', 'ASSIGNED'].includes(wo.status) && <Button size="sm" variant="outline" className="h-6 border-border bg-[hsl(var(--panel-2))] text-[10px]" onClick={() => act(wo, 'start')}>Start</Button>}
        {['OPEN', 'ASSIGNED', 'IN_PROGRESS'].includes(wo.status) && <Button size="sm" className="h-6 bg-[#05ffa1]/15 text-[10px] text-[#05ffa1] hover:bg-[#05ffa1]/25" onClick={() => { setCompleteWo(wo); setCompleteOpen(true); }}>Complete</Button>}
        {wo.status === 'COMPLETED' && <Button size="sm" variant="outline" className="h-6 border-border bg-[hsl(var(--panel-2))] text-[10px]" onClick={() => act(wo, 'close')}>Close</Button>}
      </div>
    </div>
  );

  return (
    <div className="p-6" data-testid="work-orders-page">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Work Orders</h1>
          <p className="text-sm text-muted-foreground">{data.total} total · Corrective / Preventive / Inspection</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" data-testid="work-orders-view-toggle" onClick={() => setView(view === 'table' ? 'kanban' : 'table')} className="border-border bg-[hsl(var(--panel-2))]">
            {view === 'table' ? <LayoutGrid className="mr-1 h-4 w-4" /> : <Rows3 className="mr-1 h-4 w-4" />} {view === 'table' ? 'Kanban' : 'Table'}
          </Button>
          <Button data-testid="wo-create-button" onClick={() => setCreateOpen(true)} className="bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))]">
            <Plus className="mr-1 h-4 w-4" /> New Work Order
          </Button>
        </div>
      </div>

      <div className="mb-4 flex flex-wrap gap-2">
        {['all', ...LIFE].map((s) => (
          <button key={s} onClick={() => setStatus(s)} data-testid={`wo-filter-${s}`}
            className={`cyber-chamfer-sm border px-3 py-1 font-mono text-[11px] uppercase tracking-wide transition-colors ${status === s ? 'power-on border-[hsl(var(--primary))] bg-[hsl(var(--primary))]/10 text-[hsl(var(--primary))]' : 'border-border text-muted-foreground hover:text-foreground'}`}>
            {s === 'all' ? 'All' : s}
          </button>
        ))}
        <span className="mx-1 text-border">|</span>
        {TYPES.map((t) => (
          <button key={t} onClick={() => setWoType(t)} data-testid={`wo-type-filter-${t}`}
            className={`cyber-chamfer-sm border px-3 py-1 font-mono text-[11px] uppercase tracking-wide transition-colors ${woType === t ? 'power-on border-[hsl(var(--primary))] bg-[hsl(var(--primary))]/10 text-[hsl(var(--primary))]' : 'border-border text-muted-foreground hover:text-foreground'}`}>
            {t === 'all' ? 'All Types' : t}
          </button>
        ))}
      </div>

      {view === 'kanban' ? (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3 xl:grid-cols-5" data-testid="work-orders-kanban">
          {LIFE.map((col) => (
            <div key={col} className="rounded-lg border border-border bg-[hsl(var(--panel-1))]/50">
              <div className="border-b border-border px-3 py-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                {col} <span className="ml-1 text-[hsl(var(--primary))]">{data.items.filter((w) => w.status === col).length}</span>
              </div>
              <ScrollArea className="h-[60vh]">
                <div className="space-y-2 p-2">
                  {data.items.filter((w) => w.status === col).map((wo) => <WOCard key={wo.id} wo={wo} />)}
                </div>
              </ScrollArea>
            </div>
          ))}
        </div>
      ) : (
        <div className="overflow-hidden border border-border">
          <Table data-testid="work-orders-table">
            <TableHeader>
              <TableRow className="border-border bg-[hsl(var(--panel-1))] hover:bg-[hsl(var(--panel-1))]">
                <TableHead className="text-xs uppercase">WO #</TableHead>
                <TableHead className="text-xs uppercase">Type</TableHead>
                <TableHead className="text-xs uppercase">Title</TableHead>
                <TableHead className="text-xs uppercase">Machine</TableHead>
                <TableHead className="text-xs uppercase">Priority</TableHead>
                <TableHead className="text-xs uppercase">Status</TableHead>
                <TableHead className="text-xs uppercase">Assigned</TableHead>
                <TableHead className="text-xs uppercase">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.items.length === 0 && <TableRow><TableCell colSpan={8} className="py-10 text-center text-muted-foreground">No work orders match filters</TableCell></TableRow>}
              {data.items.map((wo) => (
                <TableRow key={wo.id} data-testid={`wo-row-${wo.wo_number}`} className="border-border hover:bg-white/[0.03]">
                  <TableCell className="font-mono text-xs text-[hsl(var(--primary))]">{wo.wo_number}</TableCell>
                  <TableCell className="text-xs">{wo.wo_type}{wo.auto_generated && <span className="ml-1 text-[9px] text-muted-foreground">(auto)</span>}</TableCell>
                  <TableCell className="max-w-64 truncate text-sm">{wo.title}</TableCell>
                  <TableCell>
                    <button className="text-sm hover:text-[hsl(var(--primary))]" onClick={() => openMachine(wo.machine_id)}>{wo.machine_name}</button>
                  </TableCell>
                  <TableCell><CritBadge level={wo.priority} /></TableCell>
                  <TableCell><LifecycleBadge status={wo.status} /></TableCell>
                  <TableCell className="text-sm">{wo.assigned_to || '—'}</TableCell>
                  <TableCell>
                    <div className="flex gap-1">
                      {['OPEN', 'ASSIGNED'].includes(wo.status) && <Button size="sm" variant="outline" className="h-6 border-border bg-[hsl(var(--panel-2))] text-[10px]" data-testid={`wo-start-${wo.wo_number}`} onClick={() => act(wo, 'start')}>Start</Button>}
                      {['OPEN', 'ASSIGNED', 'IN_PROGRESS'].includes(wo.status) && <Button size="sm" className="h-6 bg-[#05ffa1]/15 text-[10px] text-[#05ffa1] hover:bg-[#05ffa1]/25" data-testid={`wo-complete-${wo.wo_number}`} onClick={() => { setCompleteWo(wo); setCompleteOpen(true); }}>Complete</Button>}
                      {wo.status === 'COMPLETED' && <Button size="sm" variant="outline" className="h-6 border-border bg-[hsl(var(--panel-2))] text-[10px]" data-testid={`wo-close-${wo.wo_number}`} onClick={() => act(wo, 'close')}>Close</Button>}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Create dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="border-border bg-[hsl(var(--panel-1))]">
          <DialogHeader><DialogTitle>New Work Order</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div><Label className="text-xs">Machine</Label><MachineSelect value={form.machine_id} onChange={(id) => setForm({ ...form, machine_id: id })} testId="wo-create-machine-select" /></div>
            <div><Label className="text-xs">Title</Label><Input data-testid="wo-create-title" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} className="bg-[hsl(var(--panel-2))]" /></div>
            <div><Label className="text-xs">Description</Label><Textarea data-testid="wo-create-description" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className="bg-[hsl(var(--panel-2))]" /></div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs">Type</Label>
                <Select value={form.wo_type} onValueChange={(v) => setForm({ ...form, wo_type: v })}>
                  <SelectTrigger data-testid="wo-create-type" className="bg-[hsl(var(--panel-2))]"><SelectValue /></SelectTrigger>
                  <SelectContent>{['Corrective', 'Preventive', 'Inspection'].map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}</SelectContent>
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
            <div><Label className="text-xs">Assign Technician (optional)</Label><TechnicianSelect value={form.assigned_to} onChange={(v) => setForm({ ...form, assigned_to: v })} testId="wo-create-technician" /></div>
            <Button onClick={create} data-testid="wo-create-submit" className="w-full bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))]">Create Work Order</Button>
          </div>
        </DialogContent>
      </Dialog>

      <CompleteDialog wo={completeWo} open={completeOpen} setOpen={setCompleteOpen} onDone={load} />
    </div>
  );
}
