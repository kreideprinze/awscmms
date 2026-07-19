import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { Plus, LayoutGrid, Rows3, Hand, UserRound, Trash2 } from 'lucide-react';
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
import { MachineSelect, TechnicianSelect, SpareRows, DateTimeField, toLocalInput, toIsoUtc } from '@/components/Shared';
import { needsAdminClosure } from '@/components/WorkOrderModal';

// Kanban lifecycle: UNASSIGNED (claimable) -> ASSIGNED -> IN_PROGRESS -> [type-gated] -> CLOSED
const COLUMNS = ['UNASSIGNED', 'ASSIGNED', 'IN_PROGRESS', 'PENDING_ADMIN_CLOSURE', 'CLOSED'];
const COL_LABEL = { PENDING_ADMIN_CLOSURE: 'ADMIN CLOSURE' };
const TYPES = ['all', 'Corrective', 'Preventive', 'Inspection', 'Predictive', 'RCA'];

const inColumn = (wo, col) => {
  if (col === 'UNASSIGNED') return !wo.assigned_to && ['OPEN', 'ASSIGNED'].includes(wo.status);
  if (col === 'ASSIGNED') return !!wo.assigned_to && ['OPEN', 'ASSIGNED'].includes(wo.status);
  return wo.status === col;
};

function TypeChip({ wo }) {
  if (wo.wo_type === 'RCA') return <span className="border border-[#ff2e63]/60 px-1 py-px font-mono text-[8px] uppercase tracking-wide text-[#ff2e63]">RCA</span>;
  if (wo.wo_type === 'Predictive') return <span className="border border-[#ff9e1c]/60 px-1 py-px font-mono text-[8px] uppercase tracking-wide text-[#ff9e1c]" title={`eWACS-90 Predictive — ${wo.aws_category || ''}`}>eWACS-90</span>;
  return null;
}

function CompleteDialog({ wo, open, setOpen, onDone }) {
  const [actionTaken, setActionTaken] = useState('');
  const [spares, setSpares] = useState([]);
  const [checklist, setChecklist] = useState({});
  const [startT, setStartT] = useState('');
  const [endT, setEndT] = useState('');

  useEffect(() => {
    if (wo?.checklist) setChecklist(Object.fromEntries(wo.checklist.map((c) => [c, false])));
    if (wo) {
      setStartT(toLocalInput(wo.started_at || wo.created_at));
      setEndT(toLocalInput(new Date().toISOString()));
    }
  }, [wo]);

  if (!wo) return null;
  const submit = async () => {
    if (startT && endT && new Date(endT) < new Date(startT)) { toast.error('End time cannot be before start time'); return; }
    try {
      await api.put(`/work-orders/${wo.id}`, {
        action: 'complete', action_taken: actionTaken || undefined,
        started_at: startT ? toIsoUtc(startT) : undefined,
        completed_at: endT ? toIsoUtc(endT) : undefined,
        spare_parts: spares.filter((s) => s.sap_code && s.quantity > 0).map((s) => ({ sap_code: s.sap_code, quantity: parseFloat(s.quantity) })),
        checklist_results: Object.keys(checklist).length ? checklist : undefined,
      });
      toast.success(`${wo.wo_number} ${needsAdminClosure(wo.wo_type) ? 'completed — awaiting admin closure' : 'completed & closed'}`);
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
                  <input type="checkbox" checked={!!checklist[c]} onChange={(e) => setChecklist({ ...checklist, [c]: e.target.checked })} className="accent-[#00fff5]" />
                  {c}
                </label>
              ))}
            </div>
          )}
          {/* Corrected execution times: duration + RCA trigger evaluate against these */}
          <div className="grid grid-cols-2 gap-3">
            <DateTimeField label="Start Time" value={startT} onChange={setStartT} testId="wo-complete-start-time" />
            <DateTimeField label="End Time" value={endT} onChange={setEndT} testId="wo-complete-end-time" />
          </div>
          <div><Label className="text-xs">Action Taken</Label><Textarea data-testid="wo-complete-action-taken" value={actionTaken} onChange={(e) => setActionTaken(e.target.value)} className="bg-[hsl(var(--panel-2))]" /></div>
          <SpareRows rows={spares} setRows={setSpares} />
          <Button onClick={submit} data-testid="wo-complete-confirm" className="w-full border border-[#05ffa1]/60 bg-transparent text-[#05ffa1] hover:bg-[#05ffa1]/10">
            {needsAdminClosure(wo.wo_type) ? 'Complete → Admin Closure' : 'Complete & Close'}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default function WorkOrders() {
  const { user, isAdmin, openWorkOrder, woVersion } = useApp();
  const navigate = useNavigate();
  const isTechRole = user?.role === 'technician';
  const [data, setData] = useState({ items: [], total: 0 });
  const [view, setView] = useState('kanban'); // kanban is the default view
  const [status, setStatus] = useState('all');
  const [woType, setWoType] = useState('all');
  const [myTasks, setMyTasks] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [completeWo, setCompleteWo] = useState(null);
  const [completeOpen, setCompleteOpen] = useState(false);
  const [form, setForm] = useState({ machine_id: '', title: '', description: '', wo_type: 'Corrective', priority: 'medium', assigned_to: '' });

  const load = useCallback(() => {
    const params = new URLSearchParams();
    if (woType !== 'all') params.set('wo_type', woType);
    api.get(`/work-orders?${params}`).then((r) => setData(r.data));
  }, [woType]);
  useEffect(() => { load(); }, [load, woVersion]);

  // Client-side status + My Tasks filtering (UNASSIGNED is a derived state)
  const items = useMemo(() => {
    let list = data.items;
    if (myTasks) list = list.filter((w) => w.assigned_to === user?.username);
    if (status !== 'all') list = list.filter((w) => inColumn(w, status));
    return list;
  }, [data.items, myTasks, status, user]);

  const create = async () => {
    if (!form.machine_id || !form.title) { toast.error('Machine and title are required'); return; }
    try {
      const res = await api.post('/work-orders', { ...form, assigned_to: form.assigned_to || undefined });
      toast.success(`${res.data.wo_number} created — ${form.assigned_to ? `assigned to ${form.assigned_to}` : 'UNASSIGNED (any technician can claim)'}`);
      setCreateOpen(false);
      setForm({ machine_id: '', title: '', description: '', wo_type: 'Corrective', priority: 'medium', assigned_to: '' });
      load();
    } catch (e) { toast.error(errMsg(e)); }
  };

  const act = async (wo, action, extra = {}) => {
    try {
      await api.put(`/work-orders/${wo.id}`, { action, ...extra });
      toast.success(`${wo.wo_number} ${action === 'claim' ? `claimed by ${user.username}` : `${action}ed`}`);
      load();
    } catch (e) { toast.error(errMsg(e)); }
  };

  // PM-type WOs open the structured PM close page; RCA WOs open the 5-Why form; others use the complete dialog
  const startComplete = (wo) => {
    if (wo.wo_type === 'RCA') {
      navigate(`/work-orders/rca/${wo.id}`);
      return;
    }
    if (wo.wo_type === 'Preventive' && wo.pm_task_id) {
      navigate(`/preventive-maintenance/close/${wo.pm_task_id}`);
      return;
    }
    setCompleteWo(wo);
    setCompleteOpen(true);
  };

  const clearClosed = async () => {
    try {
      const r = await api.post('/work-orders/clear-closed');
      toast.success(`${r.data.cleared} closed work order(s) cleared from the board — still available in the Table view`);
      load();
    } catch (e) { toast.error(errMsg(e)); }
  };

  const deleteWo = async (wo) => {
    if (!window.confirm(`Permanently delete ${wo.wo_number}? This cannot be undone.`)) return;
    try {
      await api.delete(`/work-orders/${wo.id}`);
      toast.success(`${wo.wo_number} deleted`);
      load();
    } catch (e) { toast.error(errMsg(e)); }
  };

  const deleteAllUnassigned = async (count) => {
    if (!window.confirm(`Permanently delete ALL ${count} unassigned work order(s)? This cannot be undone.`)) return;
    try {
      const r = await api.delete('/work-orders/unassigned');
      toast.success(`${r.data.deleted} unassigned work order(s) deleted`);
      load();
    } catch (e) { toast.error(errMsg(e)); }
  };

  const isUnassigned = (wo) => !wo.assigned_to && ['OPEN', 'ASSIGNED'].includes(wo.status);

  // Compact kanban card — click anywhere on the card to open the universal detail popout
  const WOCard = ({ wo }) => (
    <div role="button" tabIndex={0} onClick={() => openWorkOrder(wo.id)} onKeyDown={(e) => e.key === 'Enter' && openWorkOrder(wo.id)}
      className={`cursor-pointer border bg-[hsl(var(--panel-1))] p-2 transition-colors hover:border-[hsl(var(--primary))]/60 hover:shadow-[0_0_8px_rgba(var(--accent-rgb),0.15)] ${isUnassigned(wo) ? 'border-[#f9f871]/40' : 'border-border'}`}
      data-testid={`wo-card-${wo.wo_number}`}>
      <div className="flex items-center justify-between gap-1">
        <span className="font-mono text-[10px] text-[hsl(var(--primary))]">{wo.wo_number}</span>
        <div className="flex items-center gap-1">
          <TypeChip wo={wo} />
          <CritBadge level={wo.priority} />
        </div>
      </div>
      <div className="mt-0.5 line-clamp-2 text-xs font-medium leading-snug" title={wo.title}>{wo.title}</div>
      <div className="mt-0.5 truncate text-[10px] text-muted-foreground" data-testid={`wo-card-machine-${wo.wo_number}`}>{wo.machine_name}</div>
      <div className="text-[9px] text-muted-foreground">{wo.wo_type} · {wo.assigned_to || 'unassigned'} · {fmtDate(wo.created_at)}</div>
      <div className="mt-1.5 flex flex-wrap gap-1">
        {isUnassigned(wo) ? (
          isAdmin ? (
            <Button size="sm" data-testid={`wo-assign-${wo.wo_number}`}
              className="h-5 border border-[#f9f871]/60 bg-transparent px-1.5 text-[9px] text-[#f9f871] hover:bg-[#f9f871]/10"
              onClick={(e) => { e.stopPropagation(); openWorkOrder(wo.id); }}
              title="Open the work order to assign a technician">
              <UserRound className="mr-0.5 h-2.5 w-2.5" /> Assign Tech
            </Button>
          ) : (
            <Button size="sm" data-testid={`wo-claim-${wo.wo_number}`}
              className="h-5 border border-[#f9f871]/60 bg-transparent px-1.5 text-[9px] text-[#f9f871] hover:bg-[#f9f871]/10"
              onClick={(e) => { e.stopPropagation(); act(wo, 'claim'); }}>
              <Hand className="mr-0.5 h-2.5 w-2.5" /> Claim
            </Button>
          )
        ) : (
          <>
            {['OPEN', 'ASSIGNED'].includes(wo.status) && <Button size="sm" variant="outline" className="h-5 border-border bg-[hsl(var(--panel-2))] px-1.5 text-[9px]" onClick={(e) => { e.stopPropagation(); act(wo, 'start'); }}>Start</Button>}
            {['OPEN', 'ASSIGNED', 'IN_PROGRESS'].includes(wo.status) && <Button size="sm" className="h-5 border border-[#05ffa1]/60 bg-transparent px-1.5 text-[9px] text-[#05ffa1] hover:bg-[#05ffa1]/10" onClick={(e) => { e.stopPropagation(); startComplete(wo); }}>Complete</Button>}
          </>
        )}
        {wo.status === 'PENDING_ADMIN_CLOSURE' && (isAdmin ? (
          <Button size="sm" className="h-5 border border-[#ff9e1c]/60 bg-transparent px-1.5 text-[9px] text-[#ff9e1c] hover:bg-[#ff9e1c]/10" data-testid={`wo-admin-close-${wo.wo_number}`} onClick={(e) => { e.stopPropagation(); act(wo, 'close'); }}>Admin Close</Button>
        ) : (
          <span className="text-[9px] text-[#ff9e1c]">awaiting admin</span>
        ))}
        {isAdmin && <Button size="sm" variant="ghost" data-testid={`wo-delete-${wo.wo_number}`}
          className="ml-auto h-5 px-1 text-[#ff2e63]/70 hover:bg-[#ff2e63]/10 hover:text-[#ff2e63]"
          title="Permanently delete this work order"
          onClick={(e) => { e.stopPropagation(); deleteWo(wo); }}><Trash2 className="h-3 w-3" /></Button>}
      </div>
    </div>
  );

  return (
    <div className="p-6" data-testid="work-orders-page">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Work Orders</h1>
          <p className="text-sm text-muted-foreground">{data.total} total · Corrective / Preventive / Inspection / eWACS-90-Predictive / RCA</p>
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

      <div className="mb-4 flex flex-wrap items-center gap-2">
        {isTechRole && (
          <button
            data-testid="wo-my-tasks-toggle"
            onClick={() => setMyTasks(!myTasks)}
            className={`cyber-chamfer-sm flex items-center gap-1 border px-3 py-1 font-mono text-[11px] uppercase tracking-wide transition-colors ${myTasks ? 'power-on border-[#05ffa1] bg-transparent text-[#05ffa1] shadow-[0_0_8px_rgba(5,255,161,0.25)]' : 'border-border text-muted-foreground hover:text-foreground'}`}>
            <UserRound className="h-3 w-3" /> My Tasks
          </button>
        )}
        {isTechRole && <span className="mx-1 text-border">|</span>}
        {['all', ...COLUMNS].map((s) => (
          <button key={s} onClick={() => setStatus(s)} data-testid={`wo-filter-${s}`}
            className={`cyber-chamfer-sm border px-3 py-1 font-mono text-[11px] uppercase tracking-wide transition-colors ${status === s ? 'power-on border-[hsl(var(--primary))] bg-transparent text-[hsl(var(--primary))] shadow-[0_0_8px_rgba(var(--accent-rgb),0.25)]' : 'border-border text-muted-foreground hover:text-foreground'}`}>
            {s === 'all' ? 'All' : (COL_LABEL[s] || s)}
          </button>
        ))}
        <span className="mx-1 text-border">|</span>
        {TYPES.map((t) => (
          <button key={t} onClick={() => setWoType(t)} data-testid={`wo-type-filter-${t}`}
            className={`cyber-chamfer-sm border px-3 py-1 font-mono text-[11px] uppercase tracking-wide transition-colors ${woType === t ? 'power-on border-[hsl(var(--primary))] bg-transparent text-[hsl(var(--primary))] shadow-[0_0_8px_rgba(var(--accent-rgb),0.25)]' : 'border-border text-muted-foreground hover:text-foreground'}`}>
            {t === 'all' ? 'All Types' : t === 'Predictive' ? 'eWACS-90 / Predictive' : t}
          </button>
        ))}
      </div>

      {view === 'kanban' ? (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-5" data-testid="work-orders-kanban">
          {COLUMNS.map((col) => {
            const colItems = items.filter((w) => inColumn(w, col) && !w.kanban_cleared);
            return (
              <div key={col} className={`rounded-lg border bg-[hsl(var(--panel-1))]/50 ${col === 'UNASSIGNED' ? 'border-[#f9f871]/30' : 'border-border'}`} data-testid={`wo-kanban-col-${col}`}>
                <div className={`flex items-center justify-between border-b px-3 py-1.5 text-[10px] font-semibold uppercase tracking-widest ${col === 'UNASSIGNED' ? 'border-[#f9f871]/30 text-[#f9f871]' : 'border-border text-muted-foreground'}`}>
                  <span>{COL_LABEL[col] || col} <span className="ml-1 text-[hsl(var(--primary))]">{colItems.length}</span></span>
                  {col === 'UNASSIGNED' && isAdmin && colItems.length > 0 && (
                    <button data-testid="wo-delete-all-unassigned" onClick={() => deleteAllUnassigned(colItems.length)}
                      className="flex items-center gap-1 border border-[#ff2e63]/50 px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-wide text-[#ff2e63] transition-colors hover:bg-[#ff2e63]/10"
                      title="Permanently delete ALL unassigned work orders">
                      Delete All
                    </button>
                  )}
                  {col === 'CLOSED' && colItems.length > 0 && (
                    <button data-testid="wo-clear-closed" onClick={clearClosed}
                      className="flex items-center gap-1 border border-border px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-wide text-muted-foreground transition-colors hover:border-[hsl(var(--primary))] hover:text-[hsl(var(--primary))]"
                      title="Clear closed work orders off the board (they remain in the Table view)">
                      Clear List
                    </button>
                  )}
                </div>
                <ScrollArea className="h-[62vh]">
                  <div className="space-y-1.5 p-1.5">
                    {colItems.map((wo) => <WOCard key={wo.id} wo={wo} />)}
                  </div>
                </ScrollArea>
              </div>
            );
          })}
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
              {items.length === 0 && <TableRow><TableCell colSpan={8} className="py-10 text-center text-muted-foreground">No work orders match filters</TableCell></TableRow>}
              {items.map((wo) => (
                <TableRow key={wo.id} data-testid={`wo-row-${wo.wo_number}`} className="border-border hover:bg-white/[0.03]">
                  <TableCell>
                    <button className="font-mono text-xs text-[hsl(var(--primary))] hover:underline" data-testid={`wo-open-${wo.wo_number}`} onClick={() => openWorkOrder(wo.id)}>
                      {wo.wo_number}
                    </button>
                  </TableCell>
                  <TableCell className="text-xs">
                    {wo.wo_type === 'Predictive' ? <span className="text-[#ff9e1c]">eWACS-90 / Predictive</span> : wo.wo_type}
                    {wo.auto_generated && <span className="ml-1 text-[9px] text-muted-foreground">(auto)</span>}
                  </TableCell>
                  <TableCell className="max-w-64 truncate text-sm">{wo.title}</TableCell>
                  <TableCell className="text-sm" data-testid={`wo-machine-${wo.wo_number}`}>{wo.machine_name}</TableCell>
                  <TableCell><CritBadge level={wo.priority} /></TableCell>
                  <TableCell>{isUnassigned(wo) ? <span className="border border-[#f9f871]/50 px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wide text-[#f9f871]">Unassigned</span> : <LifecycleBadge status={wo.status} />}</TableCell>
                  <TableCell className="text-sm">{wo.assigned_to || '—'}</TableCell>
                  <TableCell>
                    <div className="flex gap-1">
                      {isUnassigned(wo) ? (
                        isAdmin ? (
                          <Button size="sm" className="h-6 border border-[#f9f871]/60 bg-transparent text-[10px] text-[#f9f871] hover:bg-[#f9f871]/10" data-testid={`wo-assign-${wo.wo_number}`} onClick={() => openWorkOrder(wo.id)}>Assign Tech</Button>
                        ) : (
                          <Button size="sm" className="h-6 border border-[#f9f871]/60 bg-transparent text-[10px] text-[#f9f871] hover:bg-[#f9f871]/10" data-testid={`wo-claim-${wo.wo_number}`} onClick={() => act(wo, 'claim')}>Claim</Button>
                        )
                      ) : (
                        <>
                          {['OPEN', 'ASSIGNED'].includes(wo.status) && <Button size="sm" variant="outline" className="h-6 border-border bg-[hsl(var(--panel-2))] text-[10px]" data-testid={`wo-start-${wo.wo_number}`} onClick={() => act(wo, 'start')}>Start</Button>}
                          {['OPEN', 'ASSIGNED', 'IN_PROGRESS'].includes(wo.status) && <Button size="sm" className="h-6 border border-[#05ffa1]/60 bg-transparent text-[10px] text-[#05ffa1] hover:bg-[#05ffa1]/10" data-testid={`wo-complete-${wo.wo_number}`} onClick={() => startComplete(wo)}>Complete</Button>}
                        </>
                      )}
                      {wo.status === 'PENDING_ADMIN_CLOSURE' && (isAdmin ? (
                        <Button size="sm" className="h-6 border border-[#ff9e1c]/60 bg-transparent text-[10px] text-[#ff9e1c] hover:bg-[#ff9e1c]/10" data-testid={`wo-close-${wo.wo_number}`} onClick={() => act(wo, 'close')}>Admin Close</Button>
                      ) : (
                        <span className="text-[10px] text-[#ff9e1c]">awaiting admin</span>
                      ))}
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
        <DialogContent className="border-border bg-[hsl(var(--panel-1))]" onOpenAutoFocus={(e) => e.preventDefault()}>
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
                  <SelectContent>{['Corrective', 'Preventive', 'Inspection', 'Predictive'].map((t) => <SelectItem key={t} value={t}>{t === 'Predictive' ? 'eWACS-90 / Predictive' : t}</SelectItem>)}</SelectContent>
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
            <div>
              <Label className="text-xs">Assign Technician (optional)</Label>
              <TechnicianSelect value={form.assigned_to} onChange={(v) => setForm({ ...form, assigned_to: v })} testId="wo-create-technician" allowNone />
              <p className="mt-1 text-[11px] text-muted-foreground">Leave empty to create an UNASSIGNED work order that any technician can claim from the board.</p>
            </div>
            <Button onClick={create} data-testid="wo-create-submit" className="w-full bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))]">Create Work Order</Button>
          </div>
        </DialogContent>
      </Dialog>

      <CompleteDialog wo={completeWo} open={completeOpen} setOpen={setCompleteOpen} onDone={load} />
    </div>
  );
}
