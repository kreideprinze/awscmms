import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
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

// Lifecycle: OPEN -> ASSIGNED -> IN_PROGRESS -> (tech completes) PENDING_ADMIN_CLOSURE -> (admin) CLOSED
const LIFE = ['OPEN', 'ASSIGNED', 'IN_PROGRESS', 'PENDING_ADMIN_CLOSURE', 'CLOSED'];
const COL_LABEL = { PENDING_ADMIN_CLOSURE: 'ADMIN CLOSURE' };
const TYPES = ['all', 'Corrective', 'Preventive', 'Inspection', 'RCA'];

// ISO <-> datetime-local input helpers (local timezone aware)
const toLocalInput = (iso) => {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
};
const toIso = (local) => (local ? new Date(local).toISOString() : '');

// Kanban card detail popout — full WO inspection + editable Start/End times.
// Times editable by Admins or the assigned Technician (enforced server-side too).
function WODetailModal({ wo, open, setOpen, onDone, onAct, onStartComplete }) {
  const { user, isAdmin } = useApp();
  const navigate = useNavigate();
  const [startT, setStartT] = useState('');
  const [endT, setEndT] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (wo) { setStartT(toLocalInput(wo.started_at)); setEndT(toLocalInput(wo.completed_at)); }
  }, [wo]);

  if (!wo) return null;
  const canEditTimes = isAdmin || wo.assigned_to === user?.username;
  const dirty = startT !== toLocalInput(wo.started_at) || endT !== toLocalInput(wo.completed_at);

  const saveTimes = async () => {
    setSaving(true);
    try {
      await api.put(`/work-orders/${wo.id}`, { action: 'update', started_at: toIso(startT), completed_at: toIso(endT) });
      toast.success(`${wo.wo_number} times updated`);
      onDone();
    } catch (e) { toast.error(errMsg(e)); }
    setSaving(false);
  };

  const Row = ({ label, value, testId }) => (
    <div>
      <div className="text-[10px] uppercase tracking-widest text-muted-foreground">{label}</div>
      <div className="font-mono text-xs text-foreground" data-testid={testId}>{value || '—'}</div>
    </div>
  );

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent data-testid="wo-detail-modal" className="max-h-[88vh] max-w-lg overflow-y-auto border-border bg-[hsl(var(--panel-1))]">
        <DialogHeader>
          <DialogTitle className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-sm text-[hsl(var(--primary))]" data-testid="wo-detail-number">{wo.wo_number}</span>
            <LifecycleBadge status={wo.status} />
            <CritBadge level={wo.priority} />
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="text-sm font-medium leading-snug" data-testid="wo-detail-title">{wo.title}</div>

          <div className="grid grid-cols-2 gap-x-4 gap-y-2 rounded-md border border-border bg-[hsl(var(--panel-2))] p-3">
            <Row label="Machine" value={wo.machine_name} testId="wo-detail-machine" />
            <Row label="Type" value={`${wo.wo_type}${wo.auto_generated ? ' (auto)' : ''}`} testId="wo-detail-type" />
            <Row label="Assigned To" value={wo.assigned_to} testId="wo-detail-assigned" />
            <Row label="Created" value={fmtDate(wo.created_at)} testId="wo-detail-created" />
            <Row label="Duration" value={wo.duration_minutes != null ? `${wo.duration_minutes} min` : null} testId="wo-detail-duration" />
            <Row label="Closed By" value={wo.closed_by} testId="wo-detail-closed-by" />
          </div>

          {wo.description && (
            <div>
              <Label className="text-[10px] uppercase tracking-widest text-muted-foreground">Description</Label>
              <p className="mt-0.5 whitespace-pre-wrap text-xs text-foreground/90" data-testid="wo-detail-description">{wo.description}</p>
            </div>
          )}
          {wo.root_cause && (
            <div>
              <Label className="text-[10px] uppercase tracking-widest text-muted-foreground">Root Cause</Label>
              <p className="mt-0.5 whitespace-pre-wrap text-xs text-foreground/90" data-testid="wo-detail-root-cause">{wo.root_cause}</p>
            </div>
          )}
          {wo.action_taken && (
            <div>
              <Label className="text-[10px] uppercase tracking-widest text-muted-foreground">Action Taken</Label>
              <p className="mt-0.5 whitespace-pre-wrap text-xs text-foreground/90" data-testid="wo-detail-action-taken">{wo.action_taken}</p>
            </div>
          )}
          {(wo.spare_parts || []).length > 0 && (
            <div>
              <Label className="text-[10px] uppercase tracking-widest text-muted-foreground">Spare Parts Consumed</Label>
              <div className="mt-1 space-y-0.5">
                {wo.spare_parts.map((s, i) => (
                  <div key={i} className="font-mono text-[11px] text-foreground/80">{s.sap_code} × {s.quantity}{s.name ? ` — ${s.name}` : ''}</div>
                ))}
              </div>
            </div>
          )}

          {/* 5-Why RCA summary (RCA work orders with a submitted analysis) */}
          {wo.wo_type === 'RCA' && wo.rca && (
            <div className="rounded-md border border-[#ff2e63]/40 bg-[hsl(var(--panel-2))] p-3" data-testid="wo-detail-rca-summary">
              <Label className="text-[10px] uppercase tracking-widest text-[#ff2e63]">5-Why Analysis</Label>
              <ol className="mt-1.5 space-y-1">
                {(wo.rca.whys || []).map((w, i) => (
                  <li key={i} className="flex gap-2 text-xs text-foreground/90">
                    <span className="font-mono text-[10px] text-[#ff2e63]">W{i + 1}</span>{w}
                  </li>
                ))}
              </ol>
              <div className="mt-2 text-xs"><span className="text-[10px] uppercase tracking-widest text-muted-foreground">Root Cause: </span>{wo.rca.root_cause}</div>
              <div className="mt-1 text-xs"><span className="text-[10px] uppercase tracking-widest text-muted-foreground">Corrective Action: </span>{wo.rca.corrective_action}</div>
              <div className="mt-1 text-[10px] text-muted-foreground">Submitted by {wo.rca.submitted_by} · {fmtDate(wo.rca.submitted_at)}</div>
            </div>
          )}

          {/* Editable Start / End times */}
          <div className="rounded-md border border-[hsl(var(--primary))]/30 bg-[hsl(var(--panel-2))] p-3">
            <div className="mb-2 flex items-center justify-between">
              <Label className="text-[10px] uppercase tracking-widest text-[hsl(var(--primary))]">Execution Times</Label>
              {!canEditTimes && <span className="text-[9px] text-muted-foreground">read-only (admin / assignee)</span>}
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-[10px] text-muted-foreground">Start Time</Label>
                <Input type="datetime-local" data-testid="wo-detail-start-time" value={startT} disabled={!canEditTimes}
                  onChange={(e) => setStartT(e.target.value)} className="mt-0.5 bg-[hsl(var(--panel-1))] font-mono text-xs" />
              </div>
              <div>
                <Label className="text-[10px] text-muted-foreground">End Time</Label>
                <Input type="datetime-local" data-testid="wo-detail-end-time" value={endT} disabled={!canEditTimes}
                  onChange={(e) => setEndT(e.target.value)} className="mt-0.5 bg-[hsl(var(--panel-1))] font-mono text-xs" />
              </div>
            </div>
            {canEditTimes && (
              <Button size="sm" onClick={saveTimes} disabled={!dirty || saving} data-testid="wo-detail-save-times"
                className="mt-3 w-full border border-[hsl(var(--primary))]/60 bg-transparent text-xs text-[hsl(var(--primary))] hover:bg-[hsl(var(--primary))]/10 disabled:opacity-40">
                {saving ? 'Saving…' : 'Save Times'}
              </Button>
            )}
          </div>

          {/* Workflow actions */}
          <div className="flex flex-wrap gap-2 border-t border-border pt-3">
            {['OPEN', 'ASSIGNED'].includes(wo.status) && (
              <Button size="sm" variant="outline" data-testid="wo-detail-start-btn" className="h-7 border-border bg-[hsl(var(--panel-2))] text-xs"
                onClick={() => { onAct(wo, 'start'); setOpen(false); }}>Start</Button>
            )}
            {['OPEN', 'ASSIGNED', 'IN_PROGRESS'].includes(wo.status) && (
              <Button size="sm" data-testid="wo-detail-complete-btn" className="h-7 border border-[#05ffa1]/60 bg-transparent text-xs text-[#05ffa1] hover:bg-[#05ffa1]/10"
                onClick={() => { setOpen(false); onStartComplete(wo); }}>Complete</Button>
            )}
            {wo.status === 'PENDING_ADMIN_CLOSURE' && (isAdmin ? (
              <Button size="sm" data-testid="wo-detail-admin-close-btn" className="h-7 border border-[#ff9e1c]/60 bg-transparent text-xs text-[#ff9e1c] hover:bg-[#ff9e1c]/10"
                onClick={() => { onAct(wo, 'close'); setOpen(false); }}>Admin Close</Button>
            ) : (
              <span className="self-center text-[10px] text-[#ff9e1c]">awaiting admin closure</span>
            ))}
            {(wo.breakdown_id || wo.source_breakdown_id) && wo.status !== 'CLOSED' && (
              <Button size="sm" variant="outline" data-testid="wo-detail-repair-page-btn" className="h-7 border-border bg-[hsl(var(--panel-2))] text-xs"
                onClick={() => navigate(`/breakdowns/repair/${wo.breakdown_id || wo.source_breakdown_id}`)}>Open Repair Page</Button>
            )}
            {wo.wo_type === 'Preventive' && wo.pm_task_id && wo.status !== 'CLOSED' && (
              <Button size="sm" variant="outline" data-testid="wo-detail-pm-page-btn" className="h-7 border-border bg-[hsl(var(--panel-2))] text-xs"
                onClick={() => navigate(`/preventive-maintenance/close/${wo.pm_task_id}`)}>PM Closeout Page</Button>
            )}
            {wo.wo_type === 'RCA' && (
              <Button size="sm" data-testid="wo-detail-rca-form-btn" className="h-7 border border-[#ff2e63]/60 bg-transparent text-xs text-[#ff2e63] hover:bg-[#ff2e63]/10"
                onClick={() => navigate(`/work-orders/rca/${wo.id}`)}>Open 5-Why RCA Form</Button>
            )}
            {wo.rca_task_id && (
              <Button size="sm" variant="outline" data-testid="wo-detail-view-rca-btn" className="h-7 border-[#ff2e63]/40 bg-[hsl(var(--panel-2))] text-xs text-[#ff2e63]"
                onClick={() => navigate(`/work-orders/rca/${wo.rca_task_id}`)}>View Linked RCA</Button>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

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
      toast.success(`${wo.wo_number} completed — awaiting admin closure`);
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
          <div><Label className="text-xs">Root Cause (optional)</Label><Textarea data-testid="wo-complete-root-cause" value={rootCause} onChange={(e) => setRootCause(e.target.value)} className="bg-[hsl(var(--panel-2))]" /></div>
          <div><Label className="text-xs">Action Taken</Label><Textarea data-testid="wo-complete-action-taken" value={actionTaken} onChange={(e) => setActionTaken(e.target.value)} className="bg-[hsl(var(--panel-2))]" /></div>
          <SpareRows rows={spares} setRows={setSpares} />
          <Button onClick={submit} data-testid="wo-complete-confirm" className="w-full border border-[#05ffa1]/60 bg-transparent text-[#05ffa1] hover:bg-[#05ffa1]/10">Complete Work Order</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default function WorkOrders() {
  const { isAdmin } = useApp();
  const navigate = useNavigate();
  const [data, setData] = useState({ items: [], total: 0 });
  const [view, setView] = useState('kanban'); // kanban is the default view
  const [status, setStatus] = useState('all');
  const [woType, setWoType] = useState('all');
  const [createOpen, setCreateOpen] = useState(false);
  const [completeWo, setCompleteWo] = useState(null);
  const [completeOpen, setCompleteOpen] = useState(false);
  const [detailWo, setDetailWo] = useState(null);
  const [detailOpen, setDetailOpen] = useState(false);
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

  const openDetail = (wo) => { setDetailWo(wo); setDetailOpen(true); };

  // Refresh the board AND the WO currently open in the detail modal (after time edits)
  const refreshDetail = useCallback(async () => {
    load();
    if (detailWo) {
      try {
        const r = await api.get(`/work-orders?search=${encodeURIComponent(detailWo.wo_number)}`);
        const fresh = (r.data.items || []).find((w) => w.id === detailWo.id);
        if (fresh) setDetailWo(fresh);
      } catch {}
    }
  }, [load, detailWo]);

  // Compact kanban card — click anywhere on the card to open the detail popout
  const WOCard = ({ wo }) => (
    <div role="button" tabIndex={0} onClick={() => openDetail(wo)} onKeyDown={(e) => e.key === 'Enter' && openDetail(wo)}
      className="cursor-pointer border border-border bg-[hsl(var(--panel-1))] p-2 transition-colors hover:border-[hsl(var(--primary))]/60 hover:shadow-[0_0_8px_rgba(var(--accent-rgb),0.15)]"
      data-testid={`wo-card-${wo.wo_number}`}>
      <div className="flex items-center justify-between gap-1">
        <span className="font-mono text-[10px] text-[hsl(var(--primary))]">{wo.wo_number}</span>
        <div className="flex items-center gap-1">
          {wo.wo_type === 'RCA' && <span className="border border-[#ff2e63]/60 px-1 py-px font-mono text-[8px] uppercase tracking-wide text-[#ff2e63]">RCA</span>}
          <CritBadge level={wo.priority} />
        </div>
      </div>
      <div className="mt-0.5 line-clamp-2 text-xs font-medium leading-snug" title={wo.title}>{wo.title}</div>
      <div className="mt-0.5 truncate text-[10px] text-muted-foreground" data-testid={`wo-card-machine-${wo.wo_number}`}>{wo.machine_name}</div>
      <div className="text-[9px] text-muted-foreground">{wo.wo_type} · {wo.assigned_to || 'unassigned'} · {fmtDate(wo.created_at)}</div>
      <div className="mt-1.5 flex flex-wrap gap-1">
        {['OPEN', 'ASSIGNED'].includes(wo.status) && <Button size="sm" variant="outline" className="h-5 border-border bg-[hsl(var(--panel-2))] px-1.5 text-[9px]" onClick={(e) => { e.stopPropagation(); act(wo, 'start'); }}>Start</Button>}
        {['OPEN', 'ASSIGNED', 'IN_PROGRESS'].includes(wo.status) && <Button size="sm" className="h-5 border border-[#05ffa1]/60 bg-transparent px-1.5 text-[9px] text-[#05ffa1] hover:bg-[#05ffa1]/10" onClick={(e) => { e.stopPropagation(); startComplete(wo); }}>Complete</Button>}
        {wo.status === 'PENDING_ADMIN_CLOSURE' && (isAdmin ? (
          <Button size="sm" className="h-5 border border-[#ff9e1c]/60 bg-transparent px-1.5 text-[9px] text-[#ff9e1c] hover:bg-[#ff9e1c]/10" data-testid={`wo-admin-close-${wo.wo_number}`} onClick={(e) => { e.stopPropagation(); act(wo, 'close'); }}>Admin Close</Button>
        ) : (
          <span className="text-[9px] text-[#ff9e1c]">awaiting admin</span>
        ))}
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
            className={`cyber-chamfer-sm border px-3 py-1 font-mono text-[11px] uppercase tracking-wide transition-colors ${status === s ? 'power-on border-[hsl(var(--primary))] bg-transparent text-[hsl(var(--primary))] shadow-[0_0_8px_rgba(var(--accent-rgb),0.25)]' : 'border-border text-muted-foreground hover:text-foreground'}`}>
            {s === 'all' ? 'All' : s}
          </button>
        ))}
        <span className="mx-1 text-border">|</span>
        {TYPES.map((t) => (
          <button key={t} onClick={() => setWoType(t)} data-testid={`wo-type-filter-${t}`}
            className={`cyber-chamfer-sm border px-3 py-1 font-mono text-[11px] uppercase tracking-wide transition-colors ${woType === t ? 'power-on border-[hsl(var(--primary))] bg-transparent text-[hsl(var(--primary))] shadow-[0_0_8px_rgba(var(--accent-rgb),0.25)]' : 'border-border text-muted-foreground hover:text-foreground'}`}>
            {t === 'all' ? 'All Types' : t}
          </button>
        ))}
      </div>

      {view === 'kanban' ? (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3 xl:grid-cols-5" data-testid="work-orders-kanban">
          {LIFE.map((col) => (
            <div key={col} className="rounded-lg border border-border bg-[hsl(var(--panel-1))]/50">
              <div className="border-b border-border px-3 py-1.5 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
                {COL_LABEL[col] || col} <span className="ml-1 text-[hsl(var(--primary))]">{data.items.filter((w) => w.status === col).length}</span>
              </div>
              <ScrollArea className="h-[62vh]">
                <div className="space-y-1.5 p-1.5">
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
                  <TableCell className="text-sm" data-testid={`wo-machine-${wo.wo_number}`}>{wo.machine_name}</TableCell>
                  <TableCell><CritBadge level={wo.priority} /></TableCell>
                  <TableCell><LifecycleBadge status={wo.status} /></TableCell>
                  <TableCell className="text-sm">{wo.assigned_to || '—'}</TableCell>
                  <TableCell>
                    <div className="flex gap-1">
                      {['OPEN', 'ASSIGNED'].includes(wo.status) && <Button size="sm" variant="outline" className="h-6 border-border bg-[hsl(var(--panel-2))] text-[10px]" data-testid={`wo-start-${wo.wo_number}`} onClick={() => act(wo, 'start')}>Start</Button>}
                      {['OPEN', 'ASSIGNED', 'IN_PROGRESS'].includes(wo.status) && <Button size="sm" className="h-6 border border-[#05ffa1]/60 bg-transparent text-[10px] text-[#05ffa1] hover:bg-[#05ffa1]/10" data-testid={`wo-complete-${wo.wo_number}`} onClick={() => startComplete(wo)}>Complete</Button>}
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
      <WODetailModal wo={detailWo} open={detailOpen} setOpen={setDetailOpen} onDone={refreshDetail} onAct={act} onStartComplete={startComplete} />
    </div>
  );
}
