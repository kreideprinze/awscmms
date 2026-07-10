import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { ArrowLeft, Wrench, CheckCircle2, Timer } from 'lucide-react';
import { api, errMsg } from '@/lib/api';
import { useApp } from '@/context/AppContext';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { LifecycleBadge, TypeBadge, fmtDate, CrackedGear } from '@/components/StatusBits';
import { SpareRows } from '@/components/Shared';

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
  const { isTech } = useApp();
  const [bd, setBd] = useState(null);
  const [notFound, setNotFound] = useState(false);
  const [rootCause, setRootCause] = useState('');
  const [actionTaken, setActionTaken] = useState('');
  const [spares, setSpares] = useState([]);
  const [submitting, setSubmitting] = useState(false);

  const load = useCallback(() => {
    api.get(`/breakdowns/${breakdownId}`).then((r) => {
      setBd(r.data);
      setRootCause((v) => v || r.data.root_cause || '');
      setActionTaken((v) => v || r.data.action_taken || '');
    }).catch(() => setNotFound(true));
  }, [breakdownId]);
  useEffect(() => { load(); }, [load]);

  const act = async (payload, msg) => {
    setSubmitting(true);
    try {
      await api.put(`/breakdowns/${bd.id}`, payload);
      toast.success(msg);
      load();
      return true;
    } catch (e) {
      toast.error(errMsg(e));
      return false;
    } finally {
      setSubmitting(false);
    }
  };

  const completeRepair = async () => {
    if (!actionTaken.trim()) { toast.error('Action Taken is required to complete the repair'); return; }
    const ok = await act({
      action: 'complete',
      root_cause: rootCause || undefined,
      action_taken: actionTaken,
      consumed_spares: spares.filter((s) => s.sap_code && s.quantity > 0).map((s) => ({ sap_code: s.sap_code, quantity: parseFloat(s.quantity) })),
    }, 'Repair completed — machine restored');
    if (ok) navigate('/breakdowns');
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

      {active && isTech ? (
        <div className="space-y-4">
          {bd.status !== 'IN_PROGRESS' && (
            <Button data-testid="repair-start-button" disabled={submitting} onClick={() => act({ action: 'start' }, 'Repair started — machine marked under repair')}
              className="w-full">
              <Wrench className="mr-1 h-4 w-4" /> Start Repair Now
            </Button>
          )}
          <div className="cyber-panel space-y-3 p-4">
            <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">Repair record</div>
            <div>
              <Label className="text-xs">Root Cause {'(mandatory if downtime > 30 min)'}</Label>
              <Textarea data-testid="repair-root-cause" value={rootCause} onChange={(e) => setRootCause(e.target.value)} rows={2}
                placeholder="e.g. Bearing seized due to lubrication failure" className="bg-[hsl(var(--panel-2))]" />
            </div>
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
    </div>
  );
}
