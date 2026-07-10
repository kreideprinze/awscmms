import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { ArrowLeft, GitBranch, CheckCircle2 } from 'lucide-react';
import { api, errMsg } from '@/lib/api';
import { useApp } from '@/context/AppContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { LifecycleBadge, CritBadge, fmtDate } from '@/components/StatusBits';

// Dedicated 5-Why Root Cause Analysis submission page.
// The RCA work order cannot be completed until all 5 Whys + Root Cause + Corrective Action are submitted.
export default function RcaForm() {
  const { woId } = useParams();
  const navigate = useNavigate();
  const { user, isAdmin } = useApp();
  const [wo, setWo] = useState(null);
  const [whys, setWhys] = useState(['', '', '', '', '']);
  const [rootCause, setRootCause] = useState('');
  const [corrective, setCorrective] = useState('');
  const [saving, setSaving] = useState(false);
  const [completing, setCompleting] = useState(false);

  const load = useCallback(() => {
    api.get(`/work-orders/${woId}`).then((r) => {
      setWo(r.data);
      const rca = r.data.rca;
      if (rca) {
        setWhys(rca.whys || ['', '', '', '', '']);
        setRootCause(rca.root_cause || '');
        setCorrective(rca.corrective_action || '');
      }
    }).catch((e) => toast.error(errMsg(e)));
  }, [woId]);
  useEffect(() => { load(); }, [load]);

  if (!wo) return <div className="p-6 text-muted-foreground" data-testid="rca-loading">Loading RCA work order…</div>;

  const locked = ['PENDING_ADMIN_CLOSURE', 'CLOSED'].includes(wo.status);
  const canEdit = !locked && (isAdmin || wo.assigned_to === user?.username);
  const allWhysFilled = whys.every((w) => w.trim());
  const formComplete = allWhysFilled && rootCause.trim() && corrective.trim();
  const rcaSubmitted = !!wo.rca;

  const setWhy = (i, v) => {
    const next = [...whys];
    next[i] = v;
    setWhys(next);
  };

  const submitRca = async () => {
    if (!formComplete) { toast.error('All 5 Whys, Root Cause and Corrective Action are required'); return; }
    setSaving(true);
    try {
      await api.put(`/work-orders/${wo.id}/rca`, { whys: whys.map((w) => w.trim()), root_cause: rootCause.trim(), corrective_action: corrective.trim() });
      toast.success('5-Why RCA submitted');
      load();
    } catch (e) { toast.error(errMsg(e)); }
    setSaving(false);
  };

  const completeWo = async () => {
    setCompleting(true);
    try {
      await api.put(`/work-orders/${wo.id}`, { action: 'complete' });
      toast.success(`${wo.wo_number} completed — awaiting admin closure`);
      navigate('/work-orders');
    } catch (e) { toast.error(errMsg(e)); }
    setCompleting(false);
  };

  return (
    <div className="mx-auto max-w-3xl p-6" data-testid="rca-form-page">
      <button onClick={() => navigate('/work-orders')} data-testid="rca-back-button"
        className="mb-4 flex items-center gap-1 text-xs uppercase tracking-widest text-muted-foreground transition-colors hover:text-[hsl(var(--primary))]">
        <ArrowLeft className="h-3.5 w-3.5" /> Work Orders
      </button>

      <div className="mb-5 flex flex-wrap items-center gap-2">
        <GitBranch className="h-6 w-6 text-[#ff2e63]" />
        <h1 className="text-2xl font-semibold tracking-tight">5-Why Root Cause Analysis</h1>
        <span className="font-mono text-sm text-[hsl(var(--primary))]" data-testid="rca-wo-number">{wo.wo_number}</span>
        <LifecycleBadge status={wo.status} />
        <CritBadge level={wo.priority} />
      </div>

      <div className="mb-4 grid grid-cols-2 gap-x-4 gap-y-2 rounded-md border border-border bg-[hsl(var(--panel-1))] p-3 sm:grid-cols-4">
        <div><div className="text-[10px] uppercase tracking-widest text-muted-foreground">Machine</div><div className="font-mono text-xs" data-testid="rca-machine">{wo.machine_name}</div></div>
        <div><div className="text-[10px] uppercase tracking-widest text-muted-foreground">Assigned To</div><div className="font-mono text-xs">{wo.assigned_to || '—'}</div></div>
        <div><div className="text-[10px] uppercase tracking-widest text-muted-foreground">Triggered</div><div className="font-mono text-xs">{fmtDate(wo.created_at)}</div></div>
        <div>
          <div className="text-[10px] uppercase tracking-widest text-muted-foreground">Origin</div>
          <div className="font-mono text-xs" data-testid="rca-origin">
            {wo.origin_breakdown ? `${wo.origin_breakdown.ticket_number} (${Math.round(wo.origin_breakdown.downtime_minutes || 0)} min down)`
              : wo.origin_work_order ? `${wo.origin_work_order.wo_number} (${Math.round(wo.origin_work_order.duration_minutes || 0)} min)` : '—'}
          </div>
        </div>
      </div>

      {wo.description && <p className="mb-5 text-xs text-muted-foreground" data-testid="rca-description">{wo.description}</p>}

      {!canEdit && !locked && (
        <div className="mb-4 border border-[#ff9e1c]/40 bg-[#ff9e1c]/5 p-2 text-xs text-[#ff9e1c]" data-testid="rca-readonly-banner">
          Read-only — only an Admin or the assigned technician ({wo.assigned_to || 'unassigned'}) can submit this RCA.
        </div>
      )}
      {locked && (
        <div className="mb-4 flex items-center gap-2 border border-[#05ffa1]/40 bg-[#05ffa1]/5 p-2 text-xs text-[#05ffa1]" data-testid="rca-locked-banner">
          <CheckCircle2 className="h-4 w-4" /> RCA completed{wo.rca?.submitted_by ? ` by ${wo.rca.submitted_by}` : ''} — {wo.status === 'CLOSED' ? 'closed by admin' : 'awaiting admin closure'}.
        </div>
      )}

      {/* Sequential 5-Why chain — each Why unlocks after the previous is answered */}
      <div className="space-y-3">
        {whys.map((w, i) => {
          const unlocked = i === 0 || whys[i - 1].trim();
          return (
            <div key={i} className={`rounded-md border p-3 transition-colors ${w.trim() ? 'border-[hsl(var(--primary))]/40 bg-[hsl(var(--panel-1))]' : unlocked ? 'border-border bg-[hsl(var(--panel-1))]' : 'border-border/50 bg-[hsl(var(--panel-1))]/40 opacity-50'}`}>
              <Label className="mb-1 flex items-center gap-2 text-[11px] uppercase tracking-widest">
                <span className="flex h-5 w-5 items-center justify-center border border-[hsl(var(--primary))]/50 font-mono text-[10px] text-[hsl(var(--primary))]">{i + 1}</span>
                Why did this happen?{i > 0 && <span className="normal-case tracking-normal text-muted-foreground">(building on Why {i})</span>}
              </Label>
              <Textarea data-testid={`rca-why-${i + 1}`} value={w} disabled={!canEdit || !unlocked} rows={2}
                placeholder={unlocked ? (i === 0 ? 'Why did the failure occur?' : `Why did that (Why ${i}) happen?`) : `Answer Why ${i} first`}
                onChange={(e) => setWhy(i, e.target.value)} className="bg-[hsl(var(--panel-2))] text-sm" />
            </div>
          );
        })}

        <div className={`rounded-md border p-3 ${allWhysFilled ? 'border-[#ff2e63]/50' : 'border-border/50 opacity-50'} bg-[hsl(var(--panel-1))]`}>
          <Label className="mb-1 block text-[11px] uppercase tracking-widest text-[#ff2e63]">Identified Root Cause</Label>
          <Textarea data-testid="rca-root-cause" value={rootCause} disabled={!canEdit || !allWhysFilled} rows={2}
            placeholder="The final, fundamental cause identified by the 5-Why chain" onChange={(e) => setRootCause(e.target.value)} className="bg-[hsl(var(--panel-2))] text-sm" />
        </div>
        <div className={`rounded-md border p-3 ${allWhysFilled ? 'border-[#05ffa1]/50' : 'border-border/50 opacity-50'} bg-[hsl(var(--panel-1))]`}>
          <Label className="mb-1 block text-[11px] uppercase tracking-widest text-[#05ffa1]">Corrective Action</Label>
          <Textarea data-testid="rca-corrective-action" value={corrective} disabled={!canEdit || !allWhysFilled} rows={2}
            placeholder="Action(s) taken or planned to prevent recurrence" onChange={(e) => setCorrective(e.target.value)} className="bg-[hsl(var(--panel-2))] text-sm" />
        </div>
      </div>

      {canEdit && (
        <div className="mt-5 flex flex-wrap gap-2">
          <Button onClick={submitRca} disabled={!formComplete || saving} data-testid="rca-submit-button"
            className="border border-[hsl(var(--primary))]/60 bg-transparent text-[hsl(var(--primary))] hover:bg-[hsl(var(--primary))]/10 disabled:opacity-40">
            {saving ? 'Submitting…' : rcaSubmitted ? 'Update RCA' : 'Submit RCA'}
          </Button>
          <Button onClick={completeWo} disabled={!rcaSubmitted || completing} data-testid="rca-complete-button"
            className="border border-[#05ffa1]/60 bg-transparent text-[#05ffa1] hover:bg-[#05ffa1]/10 disabled:opacity-40"
            title={rcaSubmitted ? 'Complete RCA work order' : 'Submit the RCA first'}>
            {completing ? 'Completing…' : 'Complete Work Order'}
          </Button>
        </div>
      )}
    </div>
  );
}
