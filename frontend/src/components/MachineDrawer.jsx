import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip as RTooltip, ResponsiveContainer, BarChart, Bar, AreaChart, Area,
} from 'recharts';
import { api, errMsg } from '@/lib/api';
import { useApp } from '@/context/AppContext';
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { StatusBadge, HealthBadge, LifecycleBadge, CritBadge, fmtDate } from '@/components/StatusBits';
import { SpareRows, TechnicianSelect, TransferControl } from '@/components/Shared';
import { AmSubmissionHistory, AmPendingTasks } from '@/components/AmChecklistForm';
import { ReportBreakdownDialog } from '@/components/ReportBreakdownDialog';

const TABS = ['Overview', 'Reports', 'Breakdowns', 'Work Orders', 'PM Tasks', 'AM Checklist', 'Analytics', 'Timeline', 'Notes', 'Documents', 'Reliability', 'Spares'];

const chartTheme = {
  grid: 'rgba(255,255,255,0.08)',
  tick: { fill: 'rgba(229,231,235,0.7)', fontSize: 11 },
  tooltip: { backgroundColor: 'hsl(220 16% 10%)', border: '1px solid hsl(220 12% 18%)', borderRadius: 8, fontSize: 12 },
};

function Empty({ text }) {
  return <div className="rounded-md border border-dashed border-border p-6 text-center text-sm text-muted-foreground">{text}</div>;
}

/* ---------------- Overview ---------------- */
function OverviewTab({ detail, reload }) {
  const { isTech, user } = useApp();
  const m = detail.machine;
  const setStatus = async (status) => {
    try {
      await api.put(`/machines/${m.id}/status`, { status });
      toast.success(`Status set to ${status}`);
      reload();
    } catch (e) { toast.error(errMsg(e)); }
  };
  const rows = [
    ['Machine Code', m.code], ['SAP Code', m.sap_code || '—'], ['Type', m.machine_type],
    ['Department', m.department], ['Line', m.line], ['Process Group', m.process_group],
    ['Run Hours', `${detail.runtime.run_hours}h`], ['Availability', detail.runtime.availability != null ? `${detail.runtime.availability}%` : '—'],
    ['Reliability State', (m.reliability_state || 'no_data').replace('_', ' ')],
  ];
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-x-4 gap-y-2 rounded-lg border border-border bg-[hsl(var(--panel-2))] p-4">
        {rows.map(([k, v]) => (
          <div key={k}>
            <div className="text-[10px] uppercase tracking-widest text-muted-foreground">{k}</div>
            <div className="text-sm font-medium">{v}</div>
          </div>
        ))}
      </div>
      <div className="grid grid-cols-4 gap-2 text-center">
        {[['Reports', detail.counts.reports], ['Breakdowns', detail.counts.breakdowns], ['Work Orders', detail.counts.work_orders], ['PM Tasks', detail.counts.pm_tasks]].map(([k, v]) => (
          <div key={k} className="rounded-md border border-border bg-[hsl(var(--panel-1))] py-2">
            <div className="text-lg font-semibold tabular-nums">{v}</div>
            <div className="text-[10px] uppercase tracking-wide text-muted-foreground">{k}</div>
          </div>
        ))}
      </div>
      {isTech && (
        <div>
          <Label className="text-xs text-muted-foreground">Update machine status ({user.role})</Label>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {['running', 'watch', 'inspection_due', 'repair', 'failed', 'idle'].map((s) => (
              <Button key={s} size="sm" variant="outline" data-testid={`set-status-${s}`}
                onClick={() => setStatus(s)}
                className={`border-border bg-[hsl(var(--panel-2))] text-xs capitalize ${m.status === s ? 'ring-1 ring-[hsl(var(--primary))]' : ''}`}>
                {s.replace('_', ' ')}
              </Button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* ---------------- Reports ---------------- */
function ReportsTab({ machineId, machineName }) {
  const { isTech } = useApp();
  const [reports, setReports] = useState([]);
  const [codes, setCodes] = useState([]);
  const [errorCode, setErrorCode] = useState('');
  const [desc, setDesc] = useState('');
  const [convertId, setConvertId] = useState(null);
  const [failureModes, setFailureModes] = useState([]);
  const [convertMode, setConvertMode] = useState('');

  const load = useCallback(() => {
    api.get(`/reports?machine_id=${machineId}`).then((r) => setReports(r.data));
    api.get('/error-codes').then((r) => setCodes(r.data));
    api.get('/failure-modes').then((r) => setFailureModes(r.data));
  }, [machineId]);
  useEffect(() => { load(); }, [load]);

  const submit = async () => {
    if (!errorCode || !desc) { toast.error('Select an error code and describe the observation'); return; }
    try {
      await api.post('/reports', { machine_id: machineId, error_code: errorCode, description: desc });
      toast.success('Report submitted for maintenance review');
      setDesc(''); setErrorCode('');
      load();
    } catch (e) { toast.error(errMsg(e)); }
  };

  const review = async (id, action) => {
    try {
      await api.put(`/reports/${id}/review`, { action, failure_mode: action === 'convert' ? convertMode || undefined : undefined });
      toast.success(`Report ${action === 'convert' ? 'converted to breakdown' : action + 'd'}`);
      setConvertId(null);
      load();
    } catch (e) { toast.error(errMsg(e)); }
  };

  return (
    <div className="space-y-4">
      <div className="space-y-2 rounded-lg border border-border bg-[hsl(var(--panel-2))] p-3">
        <div className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Submit observation (not a breakdown)</div>
        <Select value={errorCode} onValueChange={setErrorCode}>
          <SelectTrigger data-testid="report-error-code-select" className="bg-[hsl(var(--panel-1))]"><SelectValue placeholder="Error code" /></SelectTrigger>
          <SelectContent>
            {codes.map((c) => <SelectItem key={c.id} value={c.code}>{c.code} — {c.label}</SelectItem>)}
          </SelectContent>
        </Select>
        <Textarea data-testid="report-description-input" value={desc} onChange={(e) => setDesc(e.target.value)} placeholder={`e.g. Abnormal vibration near gearbox on ${machineName}`} className="bg-[hsl(var(--panel-1))]" />
        <Button size="sm" onClick={submit} data-testid="report-submit-button" className="bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))]">Submit Report</Button>
      </div>
      {reports.length === 0 ? <Empty text="No reports for this machine" /> : reports.map((r) => (
        <div key={r.id} className="rounded-md border border-border bg-[hsl(var(--panel-1))] p-3" data-testid={`report-item-${r.report_number}`}>
          <div className="flex items-center justify-between">
            <span className="font-mono text-xs text-[hsl(var(--primary))]">{r.report_number}</span>
            <LifecycleBadge status={r.status} />
          </div>
          <div className="mt-1 text-sm">{r.description}</div>
          <div className="mt-1 text-[11px] text-muted-foreground">[{r.error_code}] by {r.reporter} · {fmtDate(r.created_at)}</div>
          {isTech && r.status === 'PENDING_REVIEW' && (
            <div className="mt-2 flex flex-wrap items-center gap-1.5">
              <Button size="sm" variant="outline" className="h-7 border-border bg-[hsl(var(--panel-2))] text-xs" data-testid={`report-acknowledge-${r.report_number}`} onClick={() => review(r.id, 'acknowledge')}>Acknowledge</Button>
              <Button size="sm" variant="outline" className="h-7 border-border bg-[hsl(var(--panel-2))] text-xs" data-testid={`report-dismiss-${r.report_number}`} onClick={() => review(r.id, 'dismiss')}>Dismiss</Button>
              {convertId === r.id ? (
                <>
                  <Select value={convertMode} onValueChange={setConvertMode}>
                    <SelectTrigger className="h-7 w-44 bg-[hsl(var(--panel-2))] text-xs"><SelectValue placeholder="Failure mode" /></SelectTrigger>
                    <SelectContent>{failureModes.map((f) => <SelectItem key={f.id} value={f.name}>{f.name}</SelectItem>)}</SelectContent>
                  </Select>
                  <Button size="sm" className="h-7 border border-[#ff2e63]/60 bg-transparent text-xs text-[#ff2e63] hover:bg-[#ff2e63]/10" data-testid={`report-convert-confirm-${r.report_number}`} onClick={() => review(r.id, 'convert')}>Confirm Convert</Button>
                </>
              ) : (
                <Button size="sm" className="h-7 border border-[#ff9e1c]/60 bg-transparent text-xs text-[#ff9e1c] hover:bg-[#ff9e1c]/10" data-testid={`report-convert-${r.report_number}`} onClick={() => setConvertId(r.id)}>Convert to Breakdown</Button>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

/* ---------------- Breakdowns ---------------- */
export function BreakdownActions({ bd, onDone, compact }) {
  const { isTech, isAdmin, user } = useApp();
  const navigate = useNavigate();
  const [assignTech, setAssignTech] = useState('');

  if (!isTech) return null;
  const act = async (payload, msg) => {
    try {
      const res = await api.put(`/breakdowns/${bd.id}`, payload);
      toast.success(msg || `Breakdown ${res.data.status || 'updated'}`);
      onDone();
    } catch (e) { toast.error(errMsg(e)); }
  };

  // Start Repair opens the dedicated repair page (progress, spares, completion)
  const startRepair = async () => {
    try {
      if (['OPEN', 'ASSIGNED'].includes(bd.status)) {
        await api.put(`/breakdowns/${bd.id}`, { action: 'start' });
      }
      navigate(`/breakdowns/repair/${bd.id}`);
    } catch (e) { toast.error(errMsg(e)); }
  };

  const active = ['OPEN', 'ASSIGNED', 'IN_PROGRESS'].includes(bd.status);

  return (
    <div className="mt-2 space-y-2">
      {/* Unassigned breakdown: admins assign a technician from the dropdown (no self-claim);
          technicians get BOTH options — claim it themselves OR assign a colleague */}
      {active && !bd.assigned_to && isAdmin && (
        <div className="flex flex-wrap items-center gap-2" data-testid={`bd-assign-row-${bd.ticket_number}`} onClick={(e) => e.stopPropagation()}>
          <div className="w-64">
            <TechnicianSelect value={assignTech} onChange={setAssignTech} testId={`bd-assign-select-${bd.ticket_number}`} placeholder="Assign To…" />
          </div>
          <Button size="sm" disabled={!assignTech} data-testid={`bd-assign-btn-${bd.ticket_number}`}
            className="h-9 border border-[#f9f871]/60 bg-transparent text-xs text-[#f9f871] hover:bg-[#f9f871]/10 disabled:opacity-40"
            onClick={() => act({ action: 'assign', assigned_to: assignTech }, `${bd.ticket_number} assigned to ${assignTech}`)}>
            Assign Technician
          </Button>
        </div>
      )}
      {active && !bd.assigned_to && !isAdmin && (
        <div className="space-y-2" data-testid={`bd-claim-row-${bd.ticket_number}`} onClick={(e) => e.stopPropagation()}>
          <Button size="sm" data-testid={`bd-claim-btn-${bd.ticket_number}`}
            className="h-7 border border-[#f9f871]/60 bg-transparent text-xs text-[#f9f871] hover:bg-[#f9f871]/10"
            onClick={() => act({ action: 'claim' }, `${bd.ticket_number} claimed by ${user?.username}`)}>
            Claim for Me
          </Button>
          <div className="flex flex-wrap items-center gap-2">
            <div className="w-64">
              <TechnicianSelect value={assignTech} onChange={setAssignTech} testId={`bd-tech-assign-select-${bd.ticket_number}`} placeholder="Assign To…" />
            </div>
            <Button size="sm" disabled={!assignTech} data-testid={`bd-tech-assign-btn-${bd.ticket_number}`}
              className="h-9 border border-[#f9f871]/60 bg-transparent text-xs text-[#f9f871] hover:bg-[#f9f871]/10 disabled:opacity-40"
              onClick={() => act({ action: 'assign', assigned_to: assignTech }, `${bd.ticket_number} assigned to ${assignTech}`)}>
              Assign Technician
            </Button>
          </div>
        </div>
      )}
      {/* Transfer: an assigned, still-active breakdown can be handed to another
          technician by its CURRENT HOLDER or an admin (server enforces governance) */}
      {active && bd.assigned_to && (isAdmin || bd.assigned_to === user?.username) && (
        <TransferControl current={bd.assigned_to} testId={`bd-transfer-${bd.ticket_number}`}
          requireNote={bd.status === 'IN_PROGRESS'}
          onTransfer={(t, note) => act({ action: 'assign', assigned_to: t, pass_on_note: note }, `${bd.ticket_number} ${bd.status === 'IN_PROGRESS' ? 'handed off' : 'transferred'} to ${t}`)} />
      )}
      {/* ENFORCEMENT: only the current assignee or an admin can work an assigned breakdown */}
      {active && bd.assigned_to && !isAdmin && bd.assigned_to !== user?.username && (
        <div className="border border-[#ff9e1c]/40 bg-[#ff9e1c]/5 px-2 py-1.5 text-[10px] text-[#ff9e1c]" data-testid={`bd-locked-note-${bd.ticket_number}`}>
          Assigned to {bd.assigned_to} — only they or an admin can start/complete this repair. Ask {bd.assigned_to} or an admin to transfer it to you.
        </div>
      )}
      <div className="flex flex-wrap gap-1.5">
        {['OPEN', 'ASSIGNED'].includes(bd.status) && (isAdmin || !bd.assigned_to || bd.assigned_to === user?.username) && (
          <Button size="sm" variant="outline" className="h-7 border-border bg-[hsl(var(--panel-2))] text-xs" data-testid={`bd-start-${bd.ticket_number}`} onClick={(e) => { e.stopPropagation(); startRepair(); }}>Start Repair</Button>
        )}
        {bd.status === 'IN_PROGRESS' && (isAdmin || !bd.assigned_to || bd.assigned_to === user?.username) && (
          <Button size="sm" className="h-7 border border-[#05ffa1]/60 bg-transparent text-xs text-[#05ffa1] hover:bg-[#05ffa1]/10" data-testid={`bd-open-repair-${bd.ticket_number}`} onClick={() => navigate(`/breakdowns/repair/${bd.id}`)}>Open Repair Page</Button>
        )}
        {bd.status === 'COMPLETED' && (
          <span className="self-center font-mono text-[10px] uppercase tracking-wide text-[#ff9e1c]" data-testid={`bd-awaiting-admin-${bd.ticket_number}`}>
            closure via WO admin approval
          </span>
        )}
      </div>
    </div>
  );
}

function BreakdownsTab({ machineId, machine }) {
  const [items, setItems] = useState([]);
  const [reportOpen, setReportOpen] = useState(false);
  const [warningOpen, setWarningOpen] = useState(false);

  const load = useCallback(() => {
    api.get(`/breakdowns?machine_id=${machineId}`).then((r) => setItems(r.data.items));
  }, [machineId]);
  useEffect(() => { load(); }, [load]);

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-2">
        <Button data-testid="drawer-report-breakdown-button" onClick={() => setReportOpen(true)}
          className="w-full border border-[#ff2e63]/60 bg-transparent text-[#ff2e63] hover:bg-[#ff2e63]/10 hover:shadow-[0_0_14px_rgba(255,46,99,0.4)]">
          Report Breakdown
        </Button>
        <Button data-testid="drawer-report-warning-button" onClick={() => setWarningOpen(true)}
          className="w-full border border-[#f9f871]/60 bg-transparent text-[#f9f871] hover:bg-[#f9f871]/10 hover:shadow-[0_0_14px_rgba(249,248,113,0.35)]">
          Report Red Tag
        </Button>
      </div>
      <ReportBreakdownDialog open={reportOpen} setOpen={setReportOpen} prefillMachine={machine} onCreated={load} />
      <ReportBreakdownDialog open={warningOpen} setOpen={setWarningOpen} prefillMachine={machine} mode="warning" onCreated={load} />
      {items.length === 0 ? <Empty text="No breakdowns recorded" /> : items.map((bd) => (
        <div key={bd.id} className="rounded-md border border-border bg-[hsl(var(--panel-1))] p-3" data-testid={`bd-item-${bd.ticket_number}`}>
          <div className="flex items-center justify-between">
            <span className="font-mono text-xs text-[hsl(var(--primary))]">{bd.ticket_number} {bd.breakdown_type ? `· ${bd.breakdown_type.replace('_', ' ')}` : ''}</span>
            <LifecycleBadge status={bd.status} />
          </div>
          <div className="mt-1 text-sm">{bd.failure_mode}: {bd.description}</div>
          <div className="mt-1 text-[11px] text-muted-foreground">
            {fmtDate(bd.start_time)} {bd.downtime_minutes != null && `· downtime ${Math.round(bd.downtime_minutes)} min`} {bd.assigned_to && `· ${bd.assigned_to}`} {bd.work_order_number && `· WO ${bd.work_order_number}`}
          </div>
          {bd.root_cause && <div className="mt-1 text-[11px]"><span className="text-muted-foreground">Root cause:</span> {bd.root_cause}</div>}
          <BreakdownActions bd={bd} onDone={load} />
        </div>
      ))}
    </div>
  );
}

/* ---------------- Work Orders ---------------- */
function WorkOrdersTab({ machineId }) {
  const { isTech, openWorkOrder, woVersion } = useApp();
  const [items, setItems] = useState([]);
  const load = useCallback(() => {
    if (!isTech) return;
    api.get(`/work-orders?machine_id=${machineId}`).then((r) => setItems(r.data.items)).catch(() => {});
  }, [machineId, isTech]);
  useEffect(() => { load(); }, [load, woVersion]);
  if (!isTech) return <Empty text="Work orders are visible to maintenance staff only" />;
  return (
    <div className="space-y-3">
      {items.length === 0 ? <Empty text="No work orders" /> : items.map((wo) => (
        <button key={wo.id} data-testid={`drawer-wo-${wo.wo_number}`} onClick={() => openWorkOrder(wo.id)}
          className="block w-full rounded-md border border-border bg-[hsl(var(--panel-1))] p-3 text-left transition-colors hover:border-[hsl(var(--primary))]/60">
          <div className="flex items-center justify-between">
            <span className="font-mono text-xs text-[hsl(var(--primary))]">{wo.wo_number} · {wo.wo_type}</span>
            <LifecycleBadge status={wo.status} />
          </div>
          <div className="mt-1 text-sm">{wo.title}</div>
          <div className="mt-1 text-[11px] text-muted-foreground">{wo.assigned_to || 'Unassigned'} · {fmtDate(wo.created_at)}</div>
        </button>
      ))}
    </div>
  );
}

/* ---------------- PM Tasks ---------------- */
function PMTab({ machineId }) {
  const { isTech } = useApp();
  const [items, setItems] = useState([]);
  const load = useCallback(() => {
    api.get(`/pm-tasks?machine_id=${machineId}`).then((r) => setItems(r.data.items));
  }, [machineId]);
  useEffect(() => { load(); }, [load]);
  const today = new Date().toISOString().slice(0, 10);
  return (
    <div className="space-y-3">
      {items.length === 0 ? <Empty text="No PM tasks for this machine" /> : items.map((t) => (
        <div key={t.id} className="rounded-md border border-border bg-[hsl(var(--panel-1))] p-3">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">{t.task_name}</span>
            <span className={`text-xs ${t.next_due_date < today ? 'text-[#ff2e63]' : 'text-muted-foreground'}`}>due {t.next_due_date}</span>
          </div>
          <div className="mt-1 text-[11px] text-muted-foreground">{t.frequency} · {t.priority} · {t.assigned_to || 'unassigned'} {t.source === 'predictive' && '· auto-suggested'}</div>
          {t.checklist?.length > 0 && <div className="mt-1 text-[11px] text-muted-foreground">Checklist: {t.checklist.join(' · ')}</div>}
        </div>
      ))}
    </div>
  );
}

/* ---------------- Analytics ---------------- */
function AnalyticsTab({ machineId }) {
  const [kpis, setKpis] = useState(null);
  useEffect(() => {
    api.get(`/analytics/kpis?level=machine&value=${machineId}`).then((r) => setKpis(r.data));
  }, [machineId]);
  if (!kpis) return <Empty text="Loading analytics…" />;
  const cards = [
    ['MTBF', kpis.mtbf_hours != null ? `${kpis.mtbf_hours}h` : '—'],
    ['MTTR', kpis.mttr_hours != null ? `${kpis.mttr_hours}h` : '—'],
    ['Availability', kpis.availability != null ? `${kpis.availability}%` : '—'],
    ['Failures', kpis.failures_total],
    ['Downtime', `${kpis.downtime_hours_total}h`],
    ['PM Compliance', kpis.pm_compliance != null ? `${kpis.pm_compliance}%` : '—'],
  ];
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-2">
        {cards.map(([k, v]) => (
          <div key={k} className="rounded-md border border-border bg-[hsl(var(--panel-1))] p-2 text-center">
            <div className="text-base font-semibold tabular-nums">{v}</div>
            <div className="text-[10px] uppercase tracking-wide text-muted-foreground">{k}</div>
          </div>
        ))}
      </div>
      {kpis.downtime_trend.length > 0 && (
        <div className="rounded-md border border-border bg-[hsl(var(--panel-1))] p-3">
          <div className="mb-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">Downtime trend (hours)</div>
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={kpis.downtime_trend}>
              <CartesianGrid stroke={chartTheme.grid} vertical={false} />
              <XAxis dataKey="month" tick={chartTheme.tick} />
              <YAxis tick={chartTheme.tick} width={30} />
              <RTooltip contentStyle={chartTheme.tooltip} />
              <Bar dataKey="downtime_hours" fill="#ff2e63" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}

/* ---------------- Timeline ---------------- */
const EVENT_TYPES = ['all', 'report_created', 'breakdown_created', 'breakdown_closed', 'warning_created', 'wo_assigned', 'wo_completed', 'pm_generated', 'pm_completed', 'reliability_alert', 'status_changed', 'note_added'];

function TimelineTab({ machineId }) {
  const [events, setEvents] = useState([]);
  const [filter, setFilter] = useState('all');
  useEffect(() => {
    const q = filter === 'all' ? '' : `&event_type=${filter}`;
    api.get(`/timeline?machine_id=${machineId}${q}&limit=100`).then((r) => setEvents(r.data));
  }, [machineId, filter]);
  return (
    <div className="space-y-3">
      <Select value={filter} onValueChange={setFilter}>
        <SelectTrigger className="bg-[hsl(var(--panel-2))]" data-testid="timeline-filter-select"><SelectValue /></SelectTrigger>
        <SelectContent>{EVENT_TYPES.map((t) => <SelectItem key={t} value={t}>{t === 'all' ? 'All events' : t === 'warning_created' ? 'red tag created' : t.replace(/_/g, ' ')}</SelectItem>)}</SelectContent>
      </Select>
      {events.length === 0 ? <Empty text="No timeline events" /> : (
        <div className="relative space-y-0 border-l border-border pl-4">
          {events.map((e) => (
            <div key={e.id} className="relative pb-4">
              <span className="absolute -left-[21px] top-1 h-2.5 w-2.5 rounded-full border-2 border-background bg-[hsl(var(--primary))]" />
              <div className="text-sm font-medium">{e.title}</div>
              {e.description && <div className="text-xs text-muted-foreground">{e.description}</div>}
              <div className="mt-0.5 font-mono text-[10px] text-muted-foreground">{fmtDate(e.created_at)} · {e.user} · {e.event_type === 'warning_created' ? 'red_tag_created' : e.event_type}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ---------------- Notes ---------------- */
function NotesTab({ machineId }) {
  const [notes, setNotes] = useState([]);
  const [text, setText] = useState('');
  const load = useCallback(() => { api.get(`/notes?machine_id=${machineId}`).then((r) => setNotes(r.data)); }, [machineId]);
  useEffect(() => { load(); }, [load]);
  const add = async () => {
    if (!text.trim()) return;
    try {
      await api.post('/notes', { machine_id: machineId, text });
      setText('');
      load();
    } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <div className="space-y-3">
      <div className="flex gap-2">
        <Input data-testid="note-input" value={text} onChange={(e) => setText(e.target.value)} placeholder="Operational observation (not a failure)…" className="bg-[hsl(var(--panel-2))]" onKeyDown={(e) => e.key === 'Enter' && add()} />
        <Button onClick={add} data-testid="note-add-button" size="sm" className="bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))]">Add</Button>
      </div>
      {notes.length === 0 ? <Empty text="No notes yet" /> : notes.map((n) => (
        <div key={n.id} className="rounded-md border border-border bg-[hsl(var(--panel-1))] p-3">
          <div className="text-sm">{n.text}</div>
          <div className="mt-1 font-mono text-[10px] text-muted-foreground">{n.author} · {fmtDate(n.created_at)}</div>
        </div>
      ))}
    </div>
  );
}

/* ---------------- Documents ---------------- */
function DocumentsTab({ machineId }) {
  const { isTech } = useApp();
  const [docs, setDocs] = useState([]);
  const [title, setTitle] = useState('');
  const [url, setUrl] = useState('');
  const load = useCallback(() => { api.get(`/documents?machine_id=${machineId}`).then((r) => setDocs(r.data)); }, [machineId]);
  useEffect(() => { load(); }, [load]);
  const add = async () => {
    if (!title.trim()) return;
    try {
      await api.post('/documents', { machine_id: machineId, title, url: url || undefined });
      setTitle(''); setUrl('');
      load();
    } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <div className="space-y-3">
      {isTech && (
        <div className="space-y-2 rounded-lg border border-border bg-[hsl(var(--panel-2))] p-3">
          <Input data-testid="doc-title-input" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Document title (e.g. O&M Manual)" className="bg-[hsl(var(--panel-1))]" />
          <Input data-testid="doc-url-input" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="Link / reference (optional)" className="bg-[hsl(var(--panel-1))]" />
          <Button size="sm" onClick={add} data-testid="doc-add-button">Add Document</Button>
        </div>
      )}
      {docs.length === 0 ? <Empty text="No documents linked" /> : docs.map((d) => (
        <div key={d.id} className="rounded-md border border-border bg-[hsl(var(--panel-1))] p-3">
          <div className="text-sm font-medium">{d.title}</div>
          {d.url && <a href={d.url} target="_blank" rel="noreferrer" className="text-xs text-[hsl(var(--primary))] underline">{d.url}</a>}
          <div className="mt-1 font-mono text-[10px] text-muted-foreground">{d.added_by} · {fmtDate(d.created_at)}</div>
        </div>
      ))}
    </div>
  );
}

/* ---------------- Reliability ---------------- */
function ReliabilityTab({ machineId }) {
  const [data, setData] = useState(null);
  useEffect(() => {
    api.get(`/reliability/metrics/${machineId}`).then((r) => setData(r.data));
  }, [machineId]);
  if (!data) return <Empty text="Loading…" />;
  const m = data.metrics;
  if (!m) return <Empty text="No reliability data yet. Metrics begin immediately after the first recorded breakdown." />;
  const rows = [
    ['Maturity Level', `Level ${m.level} (${m.failures_count} failure${m.failures_count > 1 ? 's' : ''})`],
    ['Prediction Tier', m.tier], ['MTBF', `${m.mtbf}h`], ['MTTR', m.mttr_hours != null ? `${m.mttr_hours}h` : '—'],
    ['Rolling MTBF', m.rolling_mtbf != null ? `${m.rolling_mtbf}h` : '—'],
    ['Weighted MTBF', m.weighted_mtbf != null ? `${m.weighted_mtbf}h` : '—'],
    ['Failure Trend', m.trend || '—'],
    ['Hours Since Failure', `${m.hours_since_last_failure}h`],
    ['Predicted Failure Life', `${m.predicted_failure_life}h`],
    ['Life Consumed', `${m.life_pct}%`],
  ];
  if (m.weibull) {
    rows.push(['Weibull β (shape)', m.weibull.beta], ['Weibull η (scale)', `${m.weibull.eta}h`], ['B10 Life', `${m.weibull.b10_life}h`],
      ['Reliability R(t)', m.reliability_now], ['Failure Probability', m.failure_probability], ['Hazard Rate', m.hazard_rate]);
  }
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between rounded-lg border border-border bg-[hsl(var(--panel-2))] p-3">
        <div>
          <div className="text-[10px] uppercase tracking-widest text-muted-foreground">Health State</div>
          <HealthBadge health={m.health} />
        </div>
        <div className="text-right">
          <div className="text-2xl font-semibold tabular-nums">{m.life_pct}%</div>
          <div className="text-[10px] uppercase tracking-wide text-muted-foreground">of predicted life</div>
        </div>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-[hsl(var(--panel-3))]">
        <div className={`h-full ${m.life_pct >= 100 ? 'bg-[#ff2e63]' : m.life_pct >= 80 ? 'bg-[#ff9e1c]' : m.life_pct >= 70 ? 'bg-[#f9f871]' : 'bg-[#05ffa1]'}`} style={{ width: `${Math.min(m.life_pct, 100)}%` }} />
      </div>
      <div className="grid grid-cols-2 gap-x-4 gap-y-2 rounded-lg border border-border bg-[hsl(var(--panel-1))] p-3">
        {rows.map(([k, v]) => (
          <div key={k}>
            <div className="text-[10px] uppercase tracking-widest text-muted-foreground">{k}</div>
            <div className="text-sm font-medium capitalize">{v}</div>
          </div>
        ))}
      </div>
      {data.curve.length > 0 && (
        <div className="rounded-md border border-border bg-[hsl(var(--panel-1))] p-3">
          <div className="mb-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">Weibull Reliability Curve R(t)</div>
          <ResponsiveContainer width="100%" height={180}>
            <AreaChart data={data.curve}>
              <CartesianGrid stroke={chartTheme.grid} vertical={false} />
              <XAxis dataKey="t" tick={chartTheme.tick} label={{ value: 'hours', fill: 'rgba(229,231,235,0.5)', fontSize: 10, position: 'insideBottomRight' }} />
              <YAxis tick={chartTheme.tick} width={35} domain={[0, 1]} />
              <RTooltip contentStyle={chartTheme.tooltip} />
              <Area type="monotone" dataKey="reliability" stroke="#00fff5" fill="rgba(var(--accent-rgb),0.12)" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
      {m.tbf_history?.length > 1 && (
        <div className="rounded-md border border-border bg-[hsl(var(--panel-1))] p-3">
          <div className="mb-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">Time Between Failures (h)</div>
          <ResponsiveContainer width="100%" height={140}>
            <LineChart data={m.tbf_history.map((t, i) => ({ n: i + 1, tbf: t }))}>
              <CartesianGrid stroke={chartTheme.grid} vertical={false} />
              <XAxis dataKey="n" tick={chartTheme.tick} />
              <YAxis tick={chartTheme.tick} width={40} />
              <RTooltip contentStyle={chartTheme.tooltip} />
              <Line type="monotone" dataKey="tbf" stroke="hsl(142 70% 45%)" strokeWidth={2} dot />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}

/* ---------------- Spares ---------------- */
function SparesTab({ machineId }) {
  const [data, setData] = useState(null);
  useEffect(() => {
    api.get(`/machines/${machineId}/spares`).then((r) => setData(r.data));
  }, [machineId]);
  if (!data) return <Empty text="Loading…" />;
  return (
    <div className="space-y-4">
      <div>
        <div className="mb-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">Recommended Spares (reference only)</div>
        {data.recommended.length === 0 ? <Empty text="No recommended spares configured" /> : (
          <div className="space-y-1.5">
            {data.recommended.map((r) => (
              <div key={r.sap_code} className="flex items-center justify-between rounded-md border border-border bg-[hsl(var(--panel-1))] px-3 py-2">
                <div>
                  <span className="font-mono text-xs text-[hsl(var(--primary))]">{r.sap_code}</span>
                  <span className="ml-2 text-sm">{r.material_name}</span>
                </div>
                <div className="text-xs text-muted-foreground">{r.location} · stock <span className={r.quantity > 0 ? 'text-[#05ffa1]' : 'text-[#ff2e63]'}>{r.quantity}</span></div>
              </div>
            ))}
          </div>
        )}
      </div>
      <div>
        <div className="mb-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">Most Consumed</div>
        {data.most_consumed.length === 0 ? <Empty text="No consumption recorded yet" /> : (
          <div className="space-y-1.5">
            {data.most_consumed.map((r) => (
              <div key={r.sap_code} className="flex items-center justify-between rounded-md border border-border bg-[hsl(var(--panel-1))] px-3 py-2 text-sm">
                <span><span className="font-mono text-xs text-[hsl(var(--primary))]">{r.sap_code}</span> {r.material_name}</span>
                <span className="tabular-nums text-muted-foreground">{r.consumed} used</span>
              </div>
            ))}
          </div>
        )}
      </div>
      <div>
        <div className="mb-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">Recent Usage History</div>
        {data.recent_usage.length === 0 ? <Empty text="No spare usage yet" /> : (
          <div className="space-y-1.5">
            {data.recent_usage.map((t) => (
              <div key={t.id} className="rounded-md border border-border bg-[hsl(var(--panel-1))] px-3 py-2 text-xs">
                <span className="font-mono text-[hsl(var(--primary))]">{t.sap_code}</span> ×{Math.abs(t.quantity_change)} — {t.reference_label}
                <span className="ml-2 text-muted-foreground">{fmtDate(t.created_at)} by {t.performed_by}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

/* ---------------- Drawer shell ---------------- */
export function MachineDrawer() {
  const { drawerMachineId, closeMachine, machineUpdates } = useApp();
  const [detail, setDetail] = useState(null);
  const [tab, setTab] = useState('Overview');

  const reload = useCallback(() => {
    if (!drawerMachineId) return;
    api.get(`/machines/${drawerMachineId}`).then((r) => setDetail(r.data)).catch(() => {});
  }, [drawerMachineId]);

  useEffect(() => { setDetail(null); setTab('Overview'); reload(); }, [reload]);
  useEffect(() => {
    if (drawerMachineId && machineUpdates[drawerMachineId]) {
      setDetail((d) => (d ? { ...d, machine: { ...d.machine, ...machineUpdates[drawerMachineId] } } : d));
    }
  }, [machineUpdates, drawerMachineId]);

  const m = detail?.machine;
  return (
    <Sheet open={!!drawerMachineId} onOpenChange={(o) => !o && closeMachine()}>
      <SheetContent side="right" className="w-full overflow-hidden border-border bg-[hsl(var(--panel-1))] p-0 sm:max-w-2xl" data-testid="machine-detail-drawer">
        {m ? (
          <div className="flex h-full flex-col">
            <SheetHeader className="border-b border-border px-5 py-4">
              <div className="flex items-start justify-between gap-3 pr-8">
                <div>
                  <SheetTitle className="text-lg font-semibold">{m.name}</SheetTitle>
                  <div className="mt-0.5 font-mono text-xs text-muted-foreground">{m.code} · {m.department} / {m.line} / {m.process_group}</div>
                </div>
                <div className="flex flex-col items-end gap-1.5">
                  <div className="flex gap-1.5"><StatusBadge status={m.status} /><HealthBadge health={m.health} /></div>
                  <CritBadge level={m.criticality} />
                </div>
              </div>
            </SheetHeader>
            <Tabs value={tab} onValueChange={setTab} className="flex min-h-0 flex-1 flex-col">
              <div className="border-b border-border px-3">
                <TabsList className="h-auto w-full flex-wrap justify-start gap-0.5 bg-transparent p-1">
                  {TABS.map((t) => (
                    <TabsTrigger key={t} value={t} data-testid={`machine-detail-tab-${t.toLowerCase().replace(/\s+/g, '-')}`}
                      className="rounded-md px-2.5 py-1 text-xs data-[state=active]:bg-transparent data-[state=active]:border data-[state=active]:border-[hsl(var(--primary))]/50 data-[state=active]:text-[hsl(var(--primary))]">
                      {t}
                    </TabsTrigger>
                  ))}
                </TabsList>
              </div>
              <ScrollArea className="min-h-0 flex-1">
                <div className="p-5">
                  {tab === 'Overview' && <OverviewTab detail={detail} reload={reload} />}
                  {tab === 'Reports' && <ReportsTab machineId={m.id} machineName={m.name} />}
                  {tab === 'Breakdowns' && <BreakdownsTab machineId={m.id} machine={m} />}
                  {tab === 'Work Orders' && <WorkOrdersTab machineId={m.id} />}
                  {tab === 'PM Tasks' && <PMTab machineId={m.id} />}
                  {tab === 'AM Checklist' && (<div><AmPendingTasks machineId={m.id} /><AmSubmissionHistory machineId={m.id} compact /></div>)}
                  {tab === 'Analytics' && <AnalyticsTab machineId={m.id} />}
                  {tab === 'Timeline' && <TimelineTab machineId={m.id} />}
                  {tab === 'Notes' && <NotesTab machineId={m.id} />}
                  {tab === 'Documents' && <DocumentsTab machineId={m.id} />}
                  {tab === 'Reliability' && <ReliabilityTab machineId={m.id} />}
                  {tab === 'Spares' && <SparesTab machineId={m.id} />}
                </div>
              </ScrollArea>
            </Tabs>
          </div>
        ) : (
          <div className="flex h-full items-center justify-center text-muted-foreground">Loading machine…</div>
        )}
      </SheetContent>
    </Sheet>
  );
}
