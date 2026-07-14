import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Plus, Search, Tag, GitBranch, UserRound, ChevronRight } from 'lucide-react';
import { api } from '@/lib/api';
import { useApp } from '@/context/AppContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { LifecycleBadge, TypeBadge, fmtDate } from '@/components/StatusBits';
import { BreakdownActions } from '@/components/MachineDrawer';
import { ReportBreakdownDialog } from '@/components/ReportBreakdownDialog';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { toast } from 'sonner';
import { errMsg } from '@/lib/api';

const STATUSES = ['all', 'OPEN', 'ASSIGNED', 'IN_PROGRESS', 'COMPLETED', 'CLOSED'];

// Warning detail popout: linked WO jump, or generate a WO (assignment optional — unassigned WOs are claimable)
function WarningDialog({ warning, open, setOpen, onDone }) {
  const { openWorkOrder, isTech } = useApp();
  const [technicians, setTechnicians] = useState([]);
  const [tech, setTech] = useState('');
  const [woType] = useState('Inspection'); // warnings always dispatch an Inspection WO
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (open) {
      api.get('/users/technicians').then((r) => setTechnicians((r.data || []).filter((t) => t.role === 'technician'))).catch(() => {});
      setTech('');
    }
  }, [open]);

  if (!warning) return null;
  const hasOpenWo = !!warning.work_order_number && warning.status !== 'CLOSED';

  const generate = async () => {
    setBusy(true);
    try {
      const r = await api.post(`/warnings/${warning.id}/generate-wo`, { assigned_to: tech || undefined, wo_type: woType });
      toast.success(`${r.data.wo_number} generated — ${tech ? `assigned to ${tech}` : 'UNASSIGNED (any technician can claim)'}`);
      setOpen(false); onDone();
    } catch (e) { toast.error(errMsg(e)); }
    setBusy(false);
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent data-testid="warning-detail-dialog" className="border-[#f9f871]/30 bg-[hsl(var(--panel-1))]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Tag className="h-4 w-4 text-[#f9f871]" />
            <span className="font-mono text-sm text-[#f9f871]">{warning.tag_number}</span>
            <span className={`border px-1.5 py-0.5 font-mono text-[10px] uppercase ${warning.status === 'OPEN' ? 'border-[#f9f871]/50 text-[#f9f871]' : 'border-border text-muted-foreground'}`}>{warning.status}</span>
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-x-4 gap-y-2 rounded-md border border-border bg-[hsl(var(--panel-2))] p-3">
            <div><div className="text-[10px] uppercase tracking-widest text-muted-foreground">Machine</div><div className="text-sm font-medium">{warning.machine_name}</div></div>
            <div><div className="text-[10px] uppercase tracking-widest text-muted-foreground">Type</div><div className="mt-0.5"><TypeBadge type={warning.warning_type} /></div></div>
            <div><div className="text-[10px] uppercase tracking-widest text-muted-foreground">Raised</div><div className="font-mono text-xs">{fmtDate(warning.created_at)}</div></div>
            <div><div className="text-[10px] uppercase tracking-widest text-muted-foreground">Reporter</div><div className="text-sm">{warning.reporter}</div></div>
          </div>
          <p className="text-sm" data-testid="warning-dialog-description">{warning.description}</p>

          {warning.work_order_number ? (
            <div className="flex items-center justify-between border border-border bg-[hsl(var(--panel-2))] px-3 py-2">
              <div>
                <div className="text-[10px] uppercase tracking-widest text-muted-foreground">Linked Work Order</div>
                <div className="font-mono text-sm text-[hsl(var(--primary))]">{warning.work_order_number}</div>
              </div>
              {warning.work_order_id && isTech && (
                <Button size="sm" variant="outline" data-testid="warning-open-wo" className="h-7 border-border bg-transparent text-xs"
                  onClick={() => { setOpen(false); openWorkOrder(warning.work_order_id); }}>Open Work Order</Button>
              )}
            </div>
          ) : null}

          {!hasOpenWo && (
            <div className="space-y-2 border border-[#f9f871]/30 bg-[#f9f871]/[0.03] p-3">
              <Label className="text-[10px] uppercase tracking-widest text-[#f9f871]">Generate Work Order</Label>
              <div className="grid grid-cols-1 gap-2">
                <Select value={tech || 'none'} onValueChange={(v) => setTech(v === 'none' ? '' : v)}>
                  <SelectTrigger data-testid="warning-wo-technician" className="bg-[hsl(var(--panel-2))]"><SelectValue placeholder="Unassigned — claimable" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">Unassigned — any technician can claim</SelectItem>
                    {technicians.map((t) => <SelectItem key={t.username} value={t.username}>{t.name} ({t.username})</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <p className="text-[10px] text-muted-foreground" data-testid="warning-wo-type-note">An Inspection work order will be dispatched.</p>
              <Button onClick={generate} disabled={busy} data-testid="warning-generate-wo"
                className="w-full border border-[#f9f871]/60 bg-transparent text-xs text-[#f9f871] hover:bg-[#f9f871]/10 disabled:opacity-40">
                {busy ? 'Generating…' : 'Generate Work Order'}
              </Button>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

function WarningsView({ initialWarningId, onInitialConsumed }) {
  const [data, setData] = useState({ items: [], total: 0 });
  const [selected, setSelected] = useState(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const load = useCallback(() => { api.get('/warnings').then((r) => setData(r.data)); }, []);
  useEffect(() => { load(); }, [load]);

  // Deep-link (?warning=<id>): open the exact warning detail card once the list loads
  useEffect(() => {
    if (!initialWarningId || !data.items.length) return;
    const w = data.items.find((x) => x.id === initialWarningId);
    if (w) { setSelected(w); setDialogOpen(true); }
    onInitialConsumed && onInitialConsumed();
  }, [initialWarningId, data.items]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <div className="overflow-hidden border border-[#f9f871]/25" data-testid="warnings-table">
      <Table>
        <TableHeader>
          <TableRow className="border-border bg-[hsl(var(--panel-1))] hover:bg-[hsl(var(--panel-1))]">
            <TableHead className="text-xs uppercase">Tag</TableHead>
            <TableHead className="text-xs uppercase">Machine</TableHead>
            <TableHead className="text-xs uppercase">Type</TableHead>
            <TableHead className="text-xs uppercase">Description</TableHead>
            <TableHead className="text-xs uppercase">Status</TableHead>
            <TableHead className="text-xs uppercase">Work Order</TableHead>
            <TableHead className="text-xs uppercase">Raised</TableHead>
            <TableHead className="text-xs uppercase">Reporter</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.items.length === 0 && (
            <TableRow><TableCell colSpan={8} className="py-10 text-center text-muted-foreground">No red tags raised yet</TableCell></TableRow>
          )}
          {data.items.map((w) => (
            <TableRow key={w.id} data-testid={`warning-row-${w.tag_number}`} onClick={() => { setSelected(w); setDialogOpen(true); }}
              className="cursor-pointer border-border hover:bg-white/[0.03]">
              <TableCell className="font-mono text-xs text-[#f9f871]">
                <Tag className="mr-1 inline h-3 w-3" />{w.tag_number}
                {w.submitted_via === 'public_kiosk' && (
                  <span className="ml-1.5 border border-[#f9f871]/50 px-1 py-px text-[8px] uppercase tracking-wide text-[#f9f871]">Public</span>
                )}
              </TableCell>
              <TableCell>
                <div className="text-sm font-medium">{w.machine_name}</div>
                <div className="text-[10px] text-muted-foreground">{w.line} / {w.process_group}</div>
              </TableCell>
              <TableCell><TypeBadge type={w.warning_type} /></TableCell>
              <TableCell className="max-w-[320px] truncate text-sm" title={w.description}>{w.description}</TableCell>
              <TableCell>
                <span className={`border px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wide ${w.status === 'OPEN' ? 'border-[#f9f871]/50 text-[#f9f871]' : 'border-border text-muted-foreground'}`}>{w.status}</span>
              </TableCell>
              <TableCell className="font-mono text-xs">{w.work_order_number || '—'}</TableCell>
              <TableCell className="font-mono text-xs">{fmtDate(w.created_at)}</TableCell>
              <TableCell className="text-sm">{w.reporter}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <WarningDialog warning={selected} open={dialogOpen} setOpen={setDialogOpen} onDone={load} />
    </div>
  );
}

export default function Breakdowns() {
  const { openMachine, openWorkOrder, liveFeed, isTech, user } = useApp();
  const navigate = useNavigate();
  const isTechRole = user?.role === 'technician';
  const [data, setData] = useState({ items: [], total: 0 });
  const [status, setStatus] = useState('all');
  const [search, setSearch] = useState('');
  const [myTasks, setMyTasks] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [warningOpen, setWarningOpen] = useState(false);
  const [view, setView] = useState('breakdowns'); // breakdowns | warnings
  const [expanded, setExpanded] = useState(null);
  const [highlightId, setHighlightId] = useState(null);
  const [warningTarget, setWarningTarget] = useState(null);
  const [searchParams, setSearchParams] = useSearchParams();

  const load = useCallback(() => {
    const params = new URLSearchParams();
    if (status !== 'all') params.set('status', status);
    if (search) params.set('search', search);
    api.get(`/breakdowns?${params}`).then((r) => setData(r.data));
  }, [status, search]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { load(); }, [liveFeed.length]); // refresh on live events

  // Deep-link: /breakdowns?bd=<id> (e.g. from the Control Room live DOWN timer)
  // expands + highlights + scrolls to the exact breakdown row
  useEffect(() => {
    const bdId = searchParams.get('bd');
    if (bdId) {
      if (!data.items.length) return;
      const found = data.items.find((b) => b.id === bdId);
      if (found) {
        setView('breakdowns');
        setExpanded(bdId);
        setHighlightId(bdId);
        setTimeout(() => {
          document.getElementById(`bd-row-${bdId}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }, 150);
        setTimeout(() => setHighlightId(null), 5000);
      }
      const next = new URLSearchParams(searchParams);
      next.delete('bd');
      setSearchParams(next, { replace: true });
      return;
    }
    // Deep-link: /breakdowns?warning=<id> (Live Event Feed) — switch to the
    // warnings view and open that exact warning's detail card
    const wId = searchParams.get('warning');
    if (wId) {
      setView('warnings');
      setWarningTarget(wId);
      const next = new URLSearchParams(searchParams);
      next.delete('warning');
      setSearchParams(next, { replace: true });
    }
  }, [searchParams, data.items]); // eslint-disable-line react-hooks/exhaustive-deps

  const items = myTasks ? data.items.filter((bd) => bd.assigned_to === user?.username) : data.items;

  return (
    <div className="p-6" data-testid="breakdowns-page">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Breakdowns</h1>
          <p className="text-sm text-muted-foreground" data-testid="breakdowns-subtitle">{data.open_total ?? 0} open · lifecycle OPEN → ASSIGNED → IN_PROGRESS → COMPLETED → CLOSED</p>
        </div>
        <div className="flex gap-2">
          <Button data-testid="breakdowns-report-warning-button" onClick={() => setWarningOpen(true)} className="border border-[#f9f871]/60 bg-transparent text-[#f9f871] hover:bg-[#f9f871]/10">
            <Tag className="mr-1 h-4 w-4" /> Report Red Tag
          </Button>
          <Button data-testid="breakdowns-create-button" onClick={() => setCreateOpen(true)} className="border border-[#ff2e63]/60 bg-transparent text-[#ff2e63] hover:bg-[#ff2e63]/10">
            <Plus className="mr-1 h-4 w-4" /> Report Breakdown
          </Button>
        </div>
      </div>

      <div className="mb-4 flex gap-2">
        {[['breakdowns', 'Breakdowns'], ['warnings', 'Red Tags']].map(([k, lbl]) => (
          <button key={k} data-testid={`breakdowns-view-${k}`} onClick={() => setView(k)}
            className={`cyber-chamfer-sm border px-3 py-1 font-mono text-[11px] uppercase tracking-wide transition-colors ${view === k
              ? (k === 'warnings' ? 'power-on border-[#f9f871] bg-transparent text-[#f9f871] shadow-[0_0_8px_rgba(249,248,113,0.25)]' : 'power-on border-[hsl(var(--primary))] bg-transparent text-[hsl(var(--primary))] shadow-[0_0_8px_rgba(var(--accent-rgb),0.25)]')
              : 'border-border text-muted-foreground hover:text-foreground'}`}>
            {lbl}
          </button>
        ))}
      </div>

      {view === 'warnings' ? <WarningsView initialWarningId={warningTarget} onInitialConsumed={() => setWarningTarget(null)} /> : (
      <>
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="relative">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input data-testid="breakdowns-search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search ticket / machine / description" className="w-72 bg-[hsl(var(--panel-2))] pl-8" />
        </div>
        {isTechRole && (
          <button
            data-testid="bd-my-tasks-toggle"
            onClick={() => setMyTasks(!myTasks)}
            className={`cyber-chamfer-sm flex items-center gap-1 border px-3 py-1 font-mono text-[11px] uppercase tracking-wide transition-colors ${myTasks ? 'power-on border-[#05ffa1] bg-transparent text-[#05ffa1] shadow-[0_0_8px_rgba(5,255,161,0.25)]' : 'border-border text-muted-foreground hover:text-foreground'}`}>
            <UserRound className="h-3 w-3" /> My Tasks
          </button>
        )}
        {STATUSES.map((s) => (
          <button key={s} data-testid={`breakdowns-filter-${s}`} onClick={() => setStatus(s)}
            className={`cyber-chamfer-sm border px-3 py-1 font-mono text-[11px] uppercase tracking-wide transition-colors ${status === s ? 'power-on border-[hsl(var(--primary))] bg-transparent text-[hsl(var(--primary))] shadow-[0_0_8px_rgba(var(--accent-rgb),0.25)]' : 'border-border text-muted-foreground hover:text-foreground'}`}>
            {s === 'all' ? 'All' : s}
          </button>
        ))}
      </div>

      <div className="overflow-hidden border border-border">
        <Table data-testid="breakdowns-table">
          <TableHeader>
            <TableRow className="border-border bg-[hsl(var(--panel-1))] hover:bg-[hsl(var(--panel-1))]">
              <TableHead className="text-xs uppercase">Ticket</TableHead>
              <TableHead className="text-xs uppercase">Machine</TableHead>
              <TableHead className="text-xs uppercase">Type</TableHead>
              <TableHead className="text-xs uppercase">Failure Mode</TableHead>
              <TableHead className="text-xs uppercase">Status</TableHead>
              <TableHead className="text-xs uppercase">Start</TableHead>
              <TableHead className="text-xs uppercase">Downtime</TableHead>
              <TableHead className="text-xs uppercase">Assigned</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.length === 0 && (
              <TableRow><TableCell colSpan={8} className="py-10 text-center text-muted-foreground">No breakdowns match filters</TableCell></TableRow>
            )}
            {items.map((bd) => (
              <React.Fragment key={bd.id}>
                <TableRow id={`bd-row-${bd.id}`} data-testid={`breakdowns-row-${bd.ticket_number}`} onClick={() => setExpanded(expanded === bd.id ? null : bd.id)}
                  className={`cursor-pointer border-border hover:bg-white/[0.03] ${highlightId === bd.id ? 'bg-[#ff2e63]/10 shadow-[inset_2px_0_0_#ff2e63]' : ''}`}>
                  <TableCell className="font-mono text-xs text-[hsl(var(--primary))]">
                    <span className="flex items-center gap-1">
                      <ChevronRight className={`h-3 w-3 shrink-0 text-muted-foreground transition-transform duration-150 ${expanded === bd.id ? 'rotate-90 text-[hsl(var(--primary))]' : ''}`} data-testid={`breakdown-expand-${bd.ticket_number}`} />
                      {bd.ticket_number}
                    </span>
                    {bd.submitted_via === 'public_kiosk' && (
                      <span className="ml-1.5 border border-[#f9f871]/50 px-1 py-px text-[8px] uppercase tracking-wide text-[#f9f871]" title="Reported without login (public kiosk)" data-testid={`public-badge-${bd.ticket_number}`}>Public</span>
                    )}
                  </TableCell>
                  <TableCell>
                    <button className="text-sm font-medium hover:text-[hsl(var(--primary))]" onClick={(e) => { e.stopPropagation(); openMachine(bd.machine_id); }}>
                      {bd.machine_name}
                    </button>
                    <div className="text-[10px] text-muted-foreground">{bd.line} / {bd.process_group}</div>
                  </TableCell>
                  <TableCell><TypeBadge type={bd.breakdown_type} /></TableCell>
                  <TableCell className="text-sm">{bd.failure_mode}</TableCell>
                  <TableCell><LifecycleBadge status={bd.status} /></TableCell>
                  <TableCell className="font-mono text-xs">{fmtDate(bd.start_time)}</TableCell>
                  <TableCell className="tabular-nums text-sm">{bd.downtime_minutes != null ? `${Math.round(bd.downtime_minutes)} min` : '—'}</TableCell>
                  <TableCell className="text-sm">{bd.assigned_to || '—'}</TableCell>
                </TableRow>
                {expanded === bd.id && (
                  <TableRow className="border-border bg-[hsl(var(--panel-1))]/60 hover:bg-[hsl(var(--panel-1))]/60">
                    <TableCell colSpan={8} className="p-4">
                      <div className="text-sm">{bd.description}</div>
                      <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
                        <span>Reported by {bd.reporter}</span>
                        {bd.work_order_number && (
                          <button
                            data-testid={`breakdown-wo-link-${bd.ticket_number}`}
                            onClick={(e) => { e.stopPropagation(); if (bd.work_order_id && isTech) openWorkOrder(bd.work_order_id); }}
                            className="flex items-center gap-1 border border-[hsl(var(--primary))]/50 px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide text-[hsl(var(--primary))] transition-colors hover:bg-[hsl(var(--primary))]/10"
                            title="Open the linked work order">
                            WO {bd.work_order_number} ↗
                          </button>
                        )}
                      </div>
                      {bd.root_cause && <div className="mt-1 text-xs"><span className="text-muted-foreground">Root cause:</span> {bd.root_cause}</div>}
                      {bd.action_taken && <div className="mt-1 text-xs"><span className="text-muted-foreground">Action taken:</span> {bd.action_taken}</div>}
                      {bd.rca_task_id && isTech && (
                        <button data-testid={`breakdown-rca-link-${bd.ticket_number}`}
                          onClick={(e) => { e.stopPropagation(); navigate(`/work-orders/rca/${bd.rca_task_id}`); }}
                          className="mt-1.5 flex items-center gap-1 border border-[#ff2e63]/50 px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide text-[#ff2e63] transition-colors hover:bg-[#ff2e63]/10">
                          <GitBranch className="h-3 w-3" /> 5-Why RCA Linked — Open
                        </button>
                      )}
                      {bd.consumed_spares?.length > 0 && (
                        <div className="mt-1 text-xs"><span className="text-muted-foreground">Spares:</span> {bd.consumed_spares.map((s) => `${s.material_name || s.sap_code} ×${s.quantity}`).join(', ')}</div>
                      )}
                      <BreakdownActions bd={bd} onDone={load} />
                    </TableCell>
                  </TableRow>
                )}
              </React.Fragment>
            ))}
          </TableBody>
        </Table>
      </div>
      </>
      )}

      <ReportBreakdownDialog open={createOpen} setOpen={setCreateOpen} onCreated={load} />
      <ReportBreakdownDialog open={warningOpen} setOpen={setWarningOpen} mode="warning" onCreated={() => setView('warnings')} />
    </div>
  );
}
