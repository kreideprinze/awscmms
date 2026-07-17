import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { Hand } from 'lucide-react';
import { api, errMsg } from '@/lib/api';
import { useApp } from '@/context/AppContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { LifecycleBadge, CritBadge, fmtDate } from '@/components/StatusBits';
import { SpareRows, DateTimeField, TechnicianSelect, TransferControl, toLocalInput, toIsoUtc } from '@/components/Shared';

// Closure governance (mirrors backend ADMIN_CLOSURE_TYPES):
//   Corrective / Inspection / Predictive (AWS) — technician closes DIRECTLY
//   Preventive (PM) / RCA — complete → PENDING_ADMIN_CLOSURE → admin closes
export const needsAdminClosure = (woType) => ['Preventive', 'RCA'].includes(woType);

const AWS_CAT_LABEL = { MECHANICAL: 'Mechanical', ELECTRICAL: 'Electrical', CONTROL_PLC: 'PLC / Control' };

function Row({ label, value, testId }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-widest text-muted-foreground">{label}</div>
      <div className="font-mono text-xs text-foreground" data-testid={testId}>{value || '—'}</div>
    </div>
  );
}

// Embedded complete form (for Corrective / Inspection / Predictive — non-navigating types)
function CompleteForm({ wo, onDone, onCancel }) {
  const [actionTaken, setActionTaken] = useState('');
  const [spares, setSpares] = useState([]);
  const [checklist, setChecklist] = useState(() => (wo.checklist ? Object.fromEntries(wo.checklist.map((c) => [c, false])) : {}));
  const [startT, setStartT] = useState(toLocalInput(wo.started_at || wo.created_at));
  const [endT, setEndT] = useState(toLocalInput(new Date().toISOString()));
  const [busy, setBusy] = useState(false);
  const [triedSubmit, setTriedSubmit] = useState(false); // inline required-field flag for Action Taken *

  const submit = async () => {
    // MANDATORY FIELD: Action Taken must be entered before completing (Corrective /
    // Inspection / Predictive — the types where it's captured in this form)
    if (!actionTaken.trim()) { setTriedSubmit(true); toast.error('Action Taken is required to complete this work order'); return; }
    if (startT && endT && new Date(endT) < new Date(startT)) { toast.error('End time cannot be before start time'); return; }
    setBusy(true);
    try {
      await api.put(`/work-orders/${wo.id}`, {
        action: 'complete', action_taken: actionTaken.trim(),
        started_at: startT ? toIsoUtc(startT) : undefined,
        completed_at: endT ? toIsoUtc(endT) : undefined,
        spare_parts: spares.filter((s) => s.sap_code && s.quantity > 0).map((s) => ({ sap_code: s.sap_code, quantity: parseFloat(s.quantity) })),
        checklist_results: Object.keys(checklist).length ? checklist : undefined,
      });
      toast.success(`${wo.wo_number} ${needsAdminClosure(wo.wo_type) ? 'completed — awaiting admin closure' : 'completed & closed'}`);
      onDone();
    } catch (e) { toast.error(errMsg(e)); }
    setBusy(false);
  };

  return (
    <div className="space-y-3 border border-[#05ffa1]/30 bg-[#05ffa1]/[0.03] p-3" data-testid="wo-modal-complete-form">
      <Label className="text-[10px] uppercase tracking-widest text-[#05ffa1]">Complete {wo.wo_number}</Label>
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
      <div className="grid grid-cols-2 gap-3">
        <DateTimeField label="Start Time" value={startT} onChange={setStartT} testId="wo-complete-start-time" />
        <DateTimeField label="End Time" value={endT} onChange={setEndT} testId="wo-complete-end-time" />
      </div>
      <div>
        <Label className="text-xs">Action Taken <span className="text-[#ff2e63]">*</span></Label>
        <Textarea data-testid="wo-complete-action-taken" value={actionTaken} onChange={(e) => setActionTaken(e.target.value)}
          placeholder="Describe the work performed (required)"
          className={`bg-[hsl(var(--panel-2))] ${triedSubmit && !actionTaken.trim() ? 'border-[#ff2e63] focus-visible:ring-[#ff2e63]' : ''}`} />
        {triedSubmit && !actionTaken.trim() && (
          <p className="mt-1 font-mono text-[10px] uppercase tracking-wide text-[#ff2e63]" data-testid="wo-complete-action-taken-error">
            Action Taken is required to complete this work order *
          </p>
        )}
      </div>
      <SpareRows rows={spares} setRows={setSpares} />
      <div className="flex gap-2">
        <Button onClick={submit} disabled={busy} data-testid="wo-complete-confirm" className="flex-1 border border-[#05ffa1]/60 bg-transparent text-[#05ffa1] hover:bg-[#05ffa1]/10">
          {busy ? 'Submitting…' : needsAdminClosure(wo.wo_type) ? 'Complete → Admin Closure' : 'Complete & Close'}
        </Button>
        <Button variant="outline" onClick={onCancel} data-testid="wo-complete-cancel" className="border-border bg-[hsl(var(--panel-2))]">Cancel</Button>
      </div>
    </div>
  );
}

/**
 * Universal Work Order popout — mounted once in Layout, opened from ANYWHERE via
 * openWorkOrder(woId) or the ?wo=<id> deep-link. Fetches the exact WO record and
 * offers the full role/type-aware action set (claim / start / complete / admin close).
 */
export function WorkOrderModal() {
  const { woModalId, closeWorkOrder, bumpWoVersion, user, isAdmin } = useApp();
  const navigate = useNavigate();
  const [wo, setWo] = useState(null);
  const [notFound, setNotFound] = useState(false);
  const [completing, setCompleting] = useState(false);
  const [assignTech, setAssignTech] = useState('');
  const [startT, setStartT] = useState('');
  const [endT, setEndT] = useState('');
  const [saving, setSaving] = useState(false);
  const [rejecting, setRejecting] = useState(false);
  const [rejectReason, setRejectReason] = useState('');

  const fetchWo = useCallback(async () => {
    if (!woModalId) return;
    try {
      const r = await api.get(`/work-orders/${woModalId}`);
      setWo(r.data);
      setNotFound(false);
      setStartT(toLocalInput(r.data.started_at));
      setEndT(toLocalInput(r.data.completed_at));
    } catch {
      setNotFound(true);
      setWo(null);
    }
  }, [woModalId]);

  useEffect(() => {
    setWo(null); setCompleting(false); setNotFound(false); setAssignTech('');
    setRejecting(false); setRejectReason('');
    if (woModalId) fetchWo();
  }, [woModalId, fetchWo]);

  const refresh = useCallback(async () => {
    await fetchWo();
    bumpWoVersion();
  }, [fetchWo, bumpWoVersion]);

  const act = async (action, extra = {}) => {
    try {
      await api.put(`/work-orders/${wo.id}`, { action, ...extra });
      const msg = action === 'claim' ? `claimed by ${user.username}`
        : action === 'assign' ? `${wo.assigned_to ? 'transferred' : 'assigned'} to ${extra.assigned_to}`
        : `${action}ed`;
      toast.success(`${wo.wo_number} ${msg}`);
      await refresh();
    } catch (e) { toast.error(errMsg(e)); }
  };

  // PM WOs close via the structured PM page; RCA WOs via the 5-Why form
  const startComplete = () => {
    if (wo.wo_type === 'RCA') { closeWorkOrder(); navigate(`/work-orders/rca/${wo.id}`); return; }
    if (wo.wo_type === 'Preventive' && wo.pm_task_id) { closeWorkOrder(); navigate(`/preventive-maintenance/close/${wo.pm_task_id}`); return; }
    setCompleting(true);
  };

  const saveTimes = async () => {
    setSaving(true);
    try {
      await api.put(`/work-orders/${wo.id}`, { action: 'update', started_at: toIsoUtc(startT), completed_at: toIsoUtc(endT) });
      toast.success(`${wo.wo_number} times updated`);
      await refresh();
    } catch (e) { toast.error(errMsg(e)); }
    setSaving(false);
  };

  // ADMIN: reject a submitted RCA — reopens it back to the SAME locked technician
  const rejectRca = async () => {
    if (!rejectReason.trim()) return;
    try {
      await api.put(`/work-orders/${wo.id}/rca-reject`, { reason: rejectReason.trim() });
      toast.warning(`${wo.wo_number} rejected — returned to ${wo.assigned_to} for resubmission`);
      setRejecting(false); setRejectReason('');
      await refresh();
    } catch (e) { toast.error(errMsg(e)); }
  };

  const open = !!woModalId;
  if (!open) return null;

  const canEditTimes = wo && (isAdmin || wo.assigned_to === user?.username);
  const dirty = wo && (startT !== toLocalInput(wo.started_at) || endT !== toLocalInput(wo.completed_at));
  const isUnassigned = wo && !wo.assigned_to && ['OPEN', 'ASSIGNED'].includes(wo.status);
  const adminGated = wo && needsAdminClosure(wo.wo_type);
  // ENFORCEMENT: an assigned WO can only be worked (start/complete) by its current
  // assignee or an admin — other technicians must claim/receive a transfer first.
  const canWork = wo && (isAdmin || !wo.assigned_to || wo.assigned_to === user?.username);

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) closeWorkOrder(); }}>
      <DialogContent data-testid="wo-detail-modal" className="max-h-[88vh] max-w-lg overflow-y-auto border-border bg-[hsl(var(--panel-1))]">
        <DialogHeader>
          <DialogTitle className="flex flex-wrap items-center gap-2">
            {wo ? (
              <>
                <span className="font-mono text-sm text-[hsl(var(--primary))]" data-testid="wo-detail-number">{wo.wo_number}</span>
                <LifecycleBadge status={isUnassigned ? 'OPEN' : wo.status} />
                <CritBadge level={wo.priority} />
                {isUnassigned && <span className="border border-[#f9f871]/60 px-1.5 py-px font-mono text-[9px] uppercase tracking-widest text-[#f9f871]" data-testid="wo-detail-unassigned-badge">Unassigned</span>}
                {wo.wo_type === 'Predictive' && <span className="border border-[#ff9e1c]/60 px-1.5 py-px font-mono text-[9px] uppercase tracking-widest text-[#ff9e1c]" data-testid="wo-detail-aws-badge">eWACS-90 {AWS_CAT_LABEL[wo.aws_category] || wo.aws_category || ''}</span>}
              </>
            ) : <span className="font-mono text-sm text-muted-foreground">Work Order</span>}
          </DialogTitle>
        </DialogHeader>

        {notFound && <div className="py-8 text-center text-sm text-muted-foreground" data-testid="wo-detail-not-found">Work order not found — it may have been removed.</div>}
        {!wo && !notFound && <div className="cyber-loading my-8 w-full" />}

        {wo && (
        <div className="space-y-4">
          <div className="text-sm font-medium leading-snug" data-testid="wo-detail-title">{wo.title}</div>

          {/* Active RCA rejection — the analysis was returned for resubmission */}
          {wo.wo_type === 'RCA' && wo.rca_rejection && (
            <div className="border border-[#ff2e63]/50 bg-[#ff2e63]/[0.06] p-2.5 text-xs text-[#ff2e63]" data-testid="wo-detail-rca-rejected-banner">
              <span className="font-semibold uppercase tracking-widest">RCA Rejected</span> by {wo.rca_rejection.rejected_by} · {fmtDate(wo.rca_rejection.rejected_at)}
              <p className="mt-1 whitespace-pre-wrap text-foreground/90">“{wo.rca_rejection.reason}” — {wo.assigned_to} must update and resubmit the 5-Why analysis.</p>
            </div>
          )}

          <div className="grid grid-cols-2 gap-x-4 gap-y-2 rounded-md border border-border bg-[hsl(var(--panel-2))] p-3">
            <Row label="Machine" value={wo.machine_name} testId="wo-detail-machine" />
            <Row label="Type" value={`${wo.wo_type}${wo.auto_generated ? ' (auto)' : ''}`} testId="wo-detail-type" />
            <Row label="Assigned To" value={wo.assigned_to || 'UNASSIGNED'} testId="wo-detail-assigned" />
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

          {/* Origin references */}
          {wo.origin_breakdown && (
            <div className="flex items-center justify-between border border-border bg-[hsl(var(--panel-2))] px-3 py-2">
              <div>
                <div className="text-[10px] uppercase tracking-widest text-muted-foreground">Origin Breakdown</div>
                <div className="font-mono text-xs text-[#ff2e63]" data-testid="wo-detail-origin-bd">{wo.origin_breakdown.ticket_number} · {wo.origin_breakdown.status}</div>
              </div>
              {wo.status !== 'CLOSED' && (
                <Button size="sm" variant="outline" data-testid="wo-detail-repair-page-btn" className="h-7 border-border bg-transparent text-xs"
                  onClick={() => { closeWorkOrder(); navigate(`/breakdowns/repair/${wo.origin_breakdown.id}`); }}>Open Repair Page</Button>
              )}
            </div>
          )}

          {/* Mid-repair handoff trail — every transfer with a Pass-On Note */}
          {(wo.handoffs || []).length > 0 && (
            <div className="rounded-md border border-[#ff9e1c]/40 bg-[hsl(var(--panel-2))] p-3" data-testid="wo-detail-handoffs">
              <Label className="text-[10px] uppercase tracking-widest text-[#ff9e1c]">Pass-On Notes ({wo.handoffs.length} handoff{wo.handoffs.length > 1 ? 's' : ''})</Label>
              <div className="mt-1.5 space-y-2">
                {wo.handoffs.map((h, i) => (
                  <div key={i} className="border-l-2 border-[#ff9e1c]/50 pl-2" data-testid={`wo-handoff-${i}`}>
                    <div className="font-mono text-[10px] text-muted-foreground">{h.from} → <span className="text-foreground">{h.to}</span> · {fmtDate(h.at)}{h.mid_repair ? ' · mid-repair' : ''}</div>
                    <p className="mt-0.5 whitespace-pre-wrap text-xs text-foreground/90">{h.note}</p>
                  </div>
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
                  onClick={(e) => { try { e.currentTarget.showPicker && e.currentTarget.showPicker(); } catch {} }}
                  onChange={(e) => setStartT(e.target.value)} className="mt-0.5 bg-[hsl(var(--panel-1))] font-mono text-xs" />
              </div>
              <div>
                <Label className="text-[10px] text-muted-foreground">End Time</Label>
                <Input type="datetime-local" data-testid="wo-detail-end-time" value={endT} disabled={!canEditTimes}
                  onClick={(e) => { try { e.currentTarget.showPicker && e.currentTarget.showPicker(); } catch {} }}
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

          {/* Embedded complete form */}
          {completing && <CompleteForm wo={wo} onDone={async () => { setCompleting(false); await refresh(); }} onCancel={() => setCompleting(false)} />}

          {/* Workflow actions — role + type aware */}
          {!completing && (
            <div className="flex flex-wrap gap-2 border-t border-border pt-3">
              {isUnassigned && (wo.wo_type === 'RCA' ? (
                <span className="text-[10px] text-[#ff2e63]" data-testid="wo-detail-rca-unassignable">RCA tasks cannot be claimed or assigned — locked to the closing technician</span>
              ) : (
                <div className="w-full space-y-2" data-testid="wo-detail-assign-row">
                  {/* Technicians get BOTH options: claim it themselves OR hand it to a colleague.
                      Admins must pick a technician from the dropdown (no self-claim). */}
                  {!isAdmin && (
                    <Button size="sm" data-testid="wo-detail-claim-btn"
                      className="h-8 w-full border border-[#f9f871]/60 bg-transparent text-xs text-[#f9f871] hover:bg-[#f9f871]/10"
                      onClick={() => act('claim')}>
                      <Hand className="mr-1 h-3 w-3" /> Claim for Me
                    </Button>
                  )}
                  <div className="flex w-full flex-wrap items-center gap-2">
                    <div className="min-w-[220px] flex-1">
                      <TechnicianSelect value={assignTech} onChange={setAssignTech} testId="wo-detail-assign-select" placeholder="Assign To…" />
                    </div>
                    <Button size="sm" disabled={!assignTech} data-testid="wo-detail-assign-btn"
                      className="h-9 border border-[#f9f871]/60 bg-transparent text-xs text-[#f9f871] hover:bg-[#f9f871]/10 disabled:opacity-40"
                      onClick={() => act('assign', { assigned_to: assignTech })}>
                      Assign Technician
                    </Button>
                  </div>
                </div>
              ))}
              {/* Transfer: an assigned, still-active task can be handed to another technician
                  by its CURRENT HOLDER or an admin. RCA tasks are locked — no transfer ever. */}
              {!isUnassigned && wo.assigned_to && ['OPEN', 'ASSIGNED', 'IN_PROGRESS'].includes(wo.status) && (
                wo.wo_type === 'RCA' ? (
                  <span className="w-full border border-[#ff2e63]/40 bg-[#ff2e63]/5 px-2 py-1.5 text-[10px] text-[#ff2e63]" data-testid="wo-detail-rca-locked">
                    RCA locked to {wo.assigned_to} — cannot be transferred or reassigned
                  </span>
                ) : (isAdmin || wo.assigned_to === user?.username) && (
                  <TransferControl current={wo.assigned_to} testId="wo-detail-transfer"
                    requireNote={wo.status === 'IN_PROGRESS'}
                    onTransfer={(t, note) => act('assign', { assigned_to: t, pass_on_note: note })} />
                )
              )}
              {['OPEN', 'ASSIGNED'].includes(wo.status) && !isUnassigned && canWork && (
                <Button size="sm" variant="outline" data-testid="wo-detail-start-btn" className="h-7 border-border bg-[hsl(var(--panel-2))] text-xs"
                  onClick={() => act('start')}>Start</Button>
              )}
              {['OPEN', 'ASSIGNED', 'IN_PROGRESS'].includes(wo.status) && !isUnassigned && canWork && (
                <Button size="sm" data-testid="wo-detail-complete-btn" className="h-7 border border-[#05ffa1]/60 bg-transparent text-xs text-[#05ffa1] hover:bg-[#05ffa1]/10"
                  onClick={startComplete}>{adminGated ? 'Complete' : 'Complete & Close'}</Button>
              )}
              {['OPEN', 'ASSIGNED', 'IN_PROGRESS'].includes(wo.status) && !isUnassigned && !canWork && (
                <span className="w-full border border-[#ff9e1c]/40 bg-[#ff9e1c]/5 px-2 py-1.5 text-[10px] text-[#ff9e1c]" data-testid="wo-detail-locked-note">
                  Assigned to {wo.assigned_to} — only they or an admin can start/complete this work order. Ask {wo.assigned_to} or an admin to transfer it to you.
                </span>
              )}
              {wo.status === 'PENDING_ADMIN_CLOSURE' && (isAdmin ? (
                <div className="w-full space-y-2">
                  <div className="flex flex-wrap gap-2">
                    <Button size="sm" data-testid="wo-detail-admin-close-btn" className="h-7 border border-[#ff9e1c]/60 bg-transparent text-xs text-[#ff9e1c] hover:bg-[#ff9e1c]/10"
                      onClick={() => act('close')}>Admin Close</Button>
                    {wo.wo_type === 'RCA' && (
                      <Button size="sm" data-testid="wo-detail-rca-reject-btn" className="h-7 border border-[#ff2e63]/60 bg-transparent text-xs text-[#ff2e63] hover:bg-[#ff2e63]/10"
                        onClick={() => setRejecting((v) => !v)}>{rejecting ? 'Cancel Reject' : 'Reject RCA'}</Button>
                    )}
                  </div>
                  {rejecting && wo.wo_type === 'RCA' && (
                    <div className="border border-[#ff2e63]/40 bg-[#ff2e63]/[0.04] p-2.5" data-testid="wo-detail-rca-reject-form">
                      <Label className="text-[10px] uppercase tracking-widest text-[#ff2e63]">Rejection Reason <span>*</span></Label>
                      <Textarea data-testid="wo-detail-rca-reject-reason" value={rejectReason} onChange={(e) => setRejectReason(e.target.value)} rows={2}
                        placeholder="Required — tell the technician what must be corrected before resubmission"
                        className="mt-0.5 bg-[hsl(var(--panel-2))] text-xs" />
                      <Button size="sm" disabled={!rejectReason.trim()} data-testid="wo-detail-rca-reject-confirm"
                        className="mt-2 h-7 w-full border border-[#ff2e63]/60 bg-transparent text-xs text-[#ff2e63] hover:bg-[#ff2e63]/10 disabled:opacity-40"
                        onClick={rejectRca}>Reject & Return to {wo.assigned_to}</Button>
                    </div>
                  )}
                </div>
              ) : (
                <span className="self-center text-[10px] text-[#ff9e1c]" data-testid="wo-detail-awaiting-admin">awaiting admin closure</span>
              ))}
              {wo.wo_type === 'Preventive' && wo.pm_task_id && wo.status !== 'CLOSED' && (
                <Button size="sm" variant="outline" data-testid="wo-detail-pm-page-btn" className="h-7 border-border bg-[hsl(var(--panel-2))] text-xs"
                  onClick={() => { closeWorkOrder(); navigate(`/preventive-maintenance/close/${wo.pm_task_id}`); }}>PM Closeout Page</Button>
              )}
              {wo.wo_type === 'RCA' && (
                <Button size="sm" data-testid="wo-detail-rca-form-btn" className="h-7 border border-[#ff2e63]/60 bg-transparent text-xs text-[#ff2e63] hover:bg-[#ff2e63]/10"
                  onClick={() => { closeWorkOrder(); navigate(`/work-orders/rca/${wo.id}`); }}>Open 5-Why RCA Form</Button>
              )}
              {wo.rca_task_id && (
                <Button size="sm" variant="outline" data-testid="wo-detail-view-rca-btn" className="h-7 border-[#ff2e63]/40 bg-[hsl(var(--panel-2))] text-xs text-[#ff2e63]"
                  onClick={() => { closeWorkOrder(); navigate(`/work-orders/rca/${wo.rca_task_id}`); }}>View Linked RCA</Button>
              )}
            </div>
          )}
        </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
