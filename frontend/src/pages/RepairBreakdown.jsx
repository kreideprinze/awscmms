import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { ArrowLeft, CheckCircle2, Timer, GitBranch } from 'lucide-react';
import { api, errMsg } from '@/lib/api';
import { useApp } from '@/context/AppContext';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { LifecycleBadge, TypeBadge, fmtDate, CrackedGear } from '@/components/StatusBits';
import { SpareRows, DateTimeField, TechnicianSelect, toLocalInput, toIsoUtc } from '@/components/Shared';
import { RcaFormBody } from '@/pages/RcaForm';

function Elapsed({ since }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const iv = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(iv);
  }, []);
  if (!since) return null;
  const mins = Math.max(0, Math.floor((now - new Date(since).getTime()) / 60000));
  const h = Math.floor(mins / 60);
  return <span className="font-mono tabular-nums">{h > 0 ? `${h}h ${String(mins % 60).padStart(2, '0')}m` : `${mins}m`}</span>;
}

// Dedicated Repair page — technicians record progress, root cause, spares and
// completion here (consistent with the PM close-out page pattern).
export default function RepairBreakdown() {
  const { breakdownId } = useParams();
  const navigate = useNavigate();
  const { isTech, isAdmin, user } = useApp();
  const [bd, setBd] = useState(null);
  const [notFound, setNotFound] = useState(false);
  const [actionTaken, setActionTaken] = useState('');
  const [spares, setSpares] = useState([]);
  const [assignTech, setAssignTech] = useState('');
  const [startT, setStartT] = useState('');
  const [endT, setEndT] = useState('');
  const [submitting, setSubmitting] = useState(false);
  // IMMEDIATE RCA FLOW: when closure downtime exceeds the threshold, the backend
  // returns the freshly created RCA task id — we pop the 5-Why form right here,
  // in-flow, for the closing technician (it stays locked to them regardless).
  const [rcaTaskId, setRcaTaskId] = useState(null);

  const load = useCallback(() => {
    api.get(`/breakdowns/${breakdownId}`).then((r) => {
      setBd(r.data);
      setActionTaken((v) => v || r.data.action_taken || '');
      setStartT((v) => v || toLocalInput(r.data.start_time));
      setEndT((v) => v || toLocalInput(r.data.end_time || new Date().toISOString()));
    }).catch(() => setNotFound(true));
  }, [breakdownId]);
  useEffect(() => { load(); }, [load]);

  const act = async (payload, msg) => {
    setSubmitting(true);
    try {
      const res = await api.put(`/breakdowns/${bd.id}`, payload);
      toast.success(msg);
      load();
      return res.data || true;
    } catch (e) {
      toast.error(errMsg(e));
      return false;
    } finally {
      setSubmitting(false);
    }
  };

  const completeRepair = async () => {
    if (!actionTaken.trim()) { toast.error('Action Taken is required to complete the repair'); return; }
    if (startT && endT && new Date(endT) < new Date(startT)) { toast.error('End time cannot be before start time'); return; }
    // A breakdown can never be closed without a technician on record:
    // technicians auto-assign themselves; admins must pick from the dropdown.
    if (!bd.assigned_to && isAdmin && !assignTech) {
      toast.error('Select the technician who performed this repair before completing');
      return;
    }
    const res = await act({
      action: 'complete',
      action_taken: actionTaken,
      assigned_to: bd.assigned_to ? undefined : (assignTech || undefined),
      start_time: startT ? toIsoUtc(startT) : undefined,
      end_time: endT ? toIsoUtc(endT) : undefined,
      consumed_spares: spares.filter((s) => s.sap_code && s.quantity > 0).map((s) => ({ sap_code: s.sap_code, quantity: parseFloat(s.quantity) })),
    }, 'Repair completed — machine restored');
    if (!res) return;
    if (res.rca_required && res.rca_task_id) {
      // Downtime exceeded the RCA threshold — the 5-Why form pops up IMMEDIATELY,
      // in-flow, instead of leaving a task to be found later on the board.
      toast.warning(`Downtime ${Math.round(res.downtime_minutes)} min exceeded the RCA threshold — complete the 5-Why analysis now`);
      setRcaTaskId(res.rca_task_id);
    } else {
      navigate('/breakdowns');
    }
  };

  const dismissRca = () => {
    // Dismissing does NOT unassign anything — the RCA remains a locked pending
    // task under the closing technician's name until they complete it.
    setRcaTaskId(null);
    toast.warning('RCA is still pending — it stays locked to you until the 5-Why analysis is completed');
    navigate('/breakdowns');
  };

  if (notFound) {
    return (
      <div className="p-10 text-center text-muted-foreground" data-testid="repair-not-found">
        Breakdown not found.
        <Button variant="ghost" className="ml-2" onClick={() => navigate('/breakdowns')}>Back to Breakdowns</Button>
      </div>
    );
  }
  if (!bd) return <div className="p-10"><div className="cyber-loading w-64" /></div>;

  const active = ['OPEN', 'ASSIGNED', 'IN_PROGRESS'].includes(bd.status);
  // ENFORCEMENT: only the current assignee (or an admin) may work an assigned breakdown
  const canWork = isAdmin || !bd.assigned_to || bd.assigned_to === user?.username;

  return (
    <div className="mx-auto max-w-4xl p-6" data-testid="repair-page">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => navigate('/breakdowns')} data-testid="repair-back"><ArrowLeft className="h-4 w-4" /></Button>
          <div>
            <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
              <CrackedGear className="h-5 w-5 text-[#ff2e63]" /> Repair — {bd.ticket_number}
            </h1>
            <p className="text-xs text-muted-foreground">Record progress, root cause and spares, then complete to restore the machine.</p>
          </div>
        </div>
        <LifecycleBadge status={bd.status} />
      </div>

      {/* Breakdown context */}
      <div className="cyber-panel mb-4 grid grid-cols-2 gap-x-6 gap-y-2 p-4 sm:grid-cols-4" data-testid="repair-context">
        <div>
          <div className="font-mono text-[9px] uppercase tracking-[0.2em] text-muted-foreground">Machine</div>
          <div className="text-sm font-semibold">{bd.machine_name}</div>
          <div className="text-[10px] text-muted-foreground">{bd.line} / {bd.process_group}</div>
        </div>
        <div>
          <div className="font-mono text-[9px] uppercase tracking-[0.2em] text-muted-foreground">Type</div>
          <div className="mt-0.5"><TypeBadge type={bd.breakdown_type} /></div>
        </div>
        <div>
          <div className="font-mono text-[9px] uppercase tracking-[0.2em] text-muted-foreground">Down since</div>
          <div className="font-mono text-sm">{fmtDate(bd.start_time)}</div>
        </div>
        <div>
          <div className="font-mono text-[9px] uppercase tracking-[0.2em] text-muted-foreground">Elapsed downtime</div>
          <div className="flex items-center gap-1.5 text-sm text-[#ff2e63]" data-testid="repair-elapsed">
            <Timer className="h-3.5 w-3.5" />
            {bd.end_time ? `${Math.round(bd.downtime_minutes)} min (ended)` : <Elapsed since={bd.start_time} />}
          </div>
        </div>
        <div className="col-span-2 sm:col-span-4">
          <div className="font-mono text-[9px] uppercase tracking-[0.2em] text-muted-foreground">Reported problem</div>
          <div className="text-sm">{bd.description}</div>
          <div className="mt-0.5 text-[11px] text-muted-foreground">
            Reported by {bd.reporter}{bd.work_order_number ? ` · WO ${bd.work_order_number}` : ''}{bd.assigned_to ? ` · assigned to ${bd.assigned_to}` : ''}
          </div>
        </div>
      </div>

      {!isTech && <div className="mb-4 border border-[#f9f871]/40 p-3 text-xs text-[#f9f871]">Read-only — repairs are recorded by technicians/admins.</div>}

      {/* ENFORCEMENT (P0): only the assigned technician or an admin can complete this
          repair. Other technicians see a locked notice instead of the completion form. */}
      {active && isTech && !canWork && (
        <div className="mb-4 border border-[#ff9e1c]/50 bg-[#ff9e1c]/5 p-3 text-xs text-[#ff9e1c]" data-testid="repair-locked-banner">
          This breakdown is assigned to <span className="font-semibold">{bd.assigned_to}</span> — only {bd.assigned_to} or an admin can start or complete the repair.
          Ask {bd.assigned_to} or an admin to transfer it to you first; completion controls are disabled.
        </div>
      )}

      {active && isTech && canWork ? (
        <div className="space-y-4">
          <div className="cyber-panel space-y-3 p-4">
            <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">Repair record</div>
            {/* Repairing technician — mandatory: closures always carry a technician name */}
            {!bd.assigned_to && (
              isAdmin ? (
                <div data-testid="repair-assign-section">
                  <Label className="text-xs">Repairing Technician *</Label>
                  <div className="mt-1"><TechnicianSelect value={assignTech} onChange={setAssignTech} testId="repair-assign-select" /></div>
                  <p className="mt-1 text-[11px] text-[#f9f871]">This breakdown is unassigned — select the technician who performed the repair. It cannot be closed without one.</p>
                </div>
              ) : (
                <p className="text-[11px] text-[#f9f871]" data-testid="repair-self-assign-note">
                  Unassigned — completing this repair records you ({user?.username}) as the repairing technician.
                </p>
              )
            )}
            {/* Corrected times: downtime + the 30-min RCA trigger evaluate against these, not the raw timer */}
            <div className="grid grid-cols-2 gap-3">
              <DateTimeField label="Breakdown Start Time" value={startT} onChange={setStartT} testId="repair-start-time" />
              <DateTimeField label="Repair End Time" value={endT} onChange={setEndT} testId="repair-end-time" />
            </div>
            <p className="text-[11px] text-muted-foreground">
              Downtime is calculated from the times above — correct them if the timer doesn't reflect reality.
              If downtime exceeds the threshold, a dedicated 5-Why RCA work order is auto-assigned (root cause is captured there, not here).
            </p>
            <div>
              <Label className="text-xs">Action Taken *</Label>
              <Textarea data-testid="repair-action-taken" value={actionTaken} onChange={(e) => setActionTaken(e.target.value)} rows={2}
                placeholder="e.g. Replaced bearing 6205 ZZ, realigned shaft" className="bg-[hsl(var(--panel-2))]" />
            </div>
            <SpareRows rows={spares} setRows={setSpares} />
            <Button data-testid="repair-complete-button" disabled={submitting} onClick={completeRepair}
              className="w-full border border-[#05ffa1]/60 bg-transparent font-semibold text-[#05ffa1] hover:bg-[#05ffa1]/10">
              <CheckCircle2 className="mr-1 h-4 w-4" /> Complete Repair — Restore Machine
            </Button>
          </div>
        </div>
      ) : (
        <div className="cyber-panel space-y-2 p-4" data-testid="repair-summary">
          <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">Repair summary</div>
          {bd.root_cause && <div className="text-sm"><span className="text-muted-foreground">Root cause:</span> {bd.root_cause}</div>}
          {bd.action_taken && <div className="text-sm"><span className="text-muted-foreground">Action taken:</span> {bd.action_taken}</div>}
          {bd.consumed_spares?.length > 0 && (
            <div className="text-sm"><span className="text-muted-foreground">Spares:</span> {bd.consumed_spares.map((s) => `${s.material_name || s.sap_code} ×${s.quantity}`).join(', ')}</div>
          )}
          {!bd.root_cause && !bd.action_taken && <div className="text-sm text-muted-foreground">No repair details recorded.</div>}
        </div>
      )}

      {/* IMMEDIATE 5-Why RCA — pops up right after a >threshold breakdown closure.
          Dismissing keeps the RCA pending & locked to the closing technician. */}
      <Dialog open={!!rcaTaskId} onOpenChange={(v) => { if (!v) dismissRca(); }}>
        <DialogContent data-testid="immediate-rca-dialog" className="max-h-[88vh] max-w-2xl overflow-y-auto border-[#ff2e63]/40 bg-[hsl(var(--panel-1))]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <GitBranch className="h-5 w-5 text-[#ff2e63]" />
              <span className="text-[#ff2e63]">5-Why RCA Required — Complete Now</span>
            </DialogTitle>
          </DialogHeader>
          {rcaTaskId && (
            <RcaFormBody woId={rcaTaskId} immediate
              onDone={() => { setRcaTaskId(null); navigate('/breakdowns'); }} />
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
