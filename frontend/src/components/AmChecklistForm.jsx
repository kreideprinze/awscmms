import React, { useEffect, useMemo, useState } from 'react';
import { Download, ChevronDown, ChevronRight, ClipboardCheck } from 'lucide-react';
import { toast } from 'sonner';
import { api, errMsg } from '@/lib/api';
import { useApp } from '@/context/AppContext';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { fmtDate } from '@/components/StatusBits';

// Download an AM checklist PDF (blank template or completed submission)
export async function downloadAmPdf(templateId, submissionId = null, filename = 'AM_checklist.pdf') {
  const res = await api.get(`/am-templates/${templateId}/pdf${submissionId ? `?submission_id=${submissionId}` : ''}`, { responseType: 'blob' });
  const url = URL.createObjectURL(res.data);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

const STATUS_META = {
  OK: { label: 'OK', cls: 'border-[#05ffa1] text-[#05ffa1] bg-[#05ffa1]/10' },
  NOT_OK: { label: 'NOT OK', cls: 'border-[#ff2e63] text-[#ff2e63] bg-[#ff2e63]/10' },
  NA: { label: 'NA', cls: 'border-[#9ca3af] text-[#9ca3af] bg-[#9ca3af]/10' },
};
const SHIFTS = ['A', 'B', 'C'];

/**
 * Shared AM checklist fill-out form — used by the PUBLIC kiosk page (no login)
 * and the in-app AM module. Tri-state per item (OK / NOT OK / NA), remarks
 * MANDATORY on NOT OK. Start time auto-captured when the form opens; Name +
 * GPID + Shift required; email auto-fills from the logged-in user, else 'anonymous'.
 */
export function AmChecklistForm({ template, publicMode = false, onDone, initialShift = '' }) {
  const { user } = useApp();
  const [startedAt, setStartedAt] = useState(() => new Date().toISOString());
  const [meta, setMeta] = useState({ name: '', gpid: '', shift: initialShift || '' });
  const [res, setRes] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [tried, setTried] = useState(false);

  useEffect(() => { // fresh sheet per template — restart the duration clock
    setStartedAt(new Date().toISOString());
    setRes({});
    setTried(false);
    setMeta((m) => ({ ...m, shift: initialShift || m.shift }));
  }, [template?.id, initialShift]);

  const rows = useMemo(() => {
    const out = [];
    (template?.checklist_groups || []).forEach((g, gi) => {
      g.items.forEach((item, ii) => out.push({
        key: `${gi}|${ii}`, gi, ii, firstOfGroup: ii === 0, group: g.description,
        item: item.checked_for, parameter: item.parameter || '',
      }));
    });
    return out;
  }, [template]);

  const answered = rows.filter((r) => res[r.key]?.status).length;
  const email = publicMode ? 'anonymous' : (user?.email || user?.username || 'anonymous');

  const setStatus = (key, status) => setRes((p) => ({ ...p, [key]: { ...(p[key] || {}), status } }));
  const setRemarks = (key, remarks) => setRes((p) => ({ ...p, [key]: { ...(p[key] || {}), remarks } }));

  const problems = () => {
    const errs = {};
    if (!meta.name.trim()) errs.name = true;
    if (!meta.gpid.trim()) errs.gpid = true;
    if (!SHIFTS.includes(meta.shift)) errs.shift = true;
    rows.forEach((r) => {
      const v = res[r.key];
      if (!v?.status) errs[r.key] = 'status';
      else if (v.status === 'NOT_OK' && !(v.remarks || '').trim()) errs[r.key] = 'remarks';
    });
    return errs;
  };

  const submit = async () => {
    setTried(true);
    const errs = problems();
    if (Object.keys(errs).length) {
      toast.error(errs.name || errs.gpid || errs.shift ? 'Fill in Name, GPID and Shift' : 'Every item needs a status — and NOT OK items need remarks');
      return;
    }
    setSubmitting(true);
    try {
      const payload = {
        template_id: template.id, name: meta.name.trim(), gpid: meta.gpid.trim(), shift: meta.shift,
        started_at: startedAt,
        row_results: rows.map((r) => ({
          description: r.group, checked_for: r.item, parameter: r.parameter,
          status: res[r.key].status, remarks: (res[r.key].remarks || '').trim(),
        })),
      };
      const url = publicMode ? '/public/am-submissions' : '/am-submissions';
      const { data } = await api.post(url, payload);
      const notOk = data.not_ok_count ?? data.notOk ?? 0;
      toast.success(`AM checklist submitted — Shift ${meta.shift}${notOk ? ` · ${notOk} item(s) flagged NOT OK` : ''}`);
      onDone?.(data);
    } catch (e) { toast.error(errMsg(e)); }
    setSubmitting(false);
  };

  if (!template) return null;
  const errs = tried ? problems() : {};

  return (
    <div className="space-y-4" data-testid="am-fill-form">
      {/* Submission metadata */}
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
        <div>
          <Label className="text-[10px] uppercase tracking-widest text-muted-foreground">Name <span className="text-[#ff2e63]">*</span></Label>
          <Input data-testid="am-name-input" value={meta.name} onChange={(e) => setMeta({ ...meta, name: e.target.value })}
            placeholder="Your full name" className={`mt-0.5 h-11 bg-[hsl(var(--panel-2))] text-base sm:h-10 sm:text-sm ${errs.name ? 'input-error' : ''}`} />
        </div>
        <div>
          <Label className="text-[10px] uppercase tracking-widest text-muted-foreground">GPID (Employee ID) <span className="text-[#ff2e63]">*</span></Label>
          <Input data-testid="am-gpid-input" value={meta.gpid} onChange={(e) => setMeta({ ...meta, gpid: e.target.value })}
            placeholder="e.g. 90012345" className={`mt-0.5 h-11 bg-[hsl(var(--panel-2))] text-base sm:h-10 sm:text-sm ${errs.gpid ? 'input-error' : ''}`} />
        </div>
        <div>
          <Label className="text-[10px] uppercase tracking-widest text-muted-foreground">Shift <span className="text-[#ff2e63]">*</span></Label>
          <Select value={meta.shift} onValueChange={(v) => setMeta({ ...meta, shift: v })}>
            <SelectTrigger data-testid="am-shift-select" className={`mt-0.5 h-11 bg-[hsl(var(--panel-2))] sm:h-10 ${errs.shift ? 'input-error' : ''}`}>
              <SelectValue placeholder="A / B / C" />
            </SelectTrigger>
            <SelectContent>{SHIFTS.map((s) => <SelectItem key={s} value={s}>Shift {s}</SelectItem>)}</SelectContent>
          </Select>
        </div>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2 border border-border bg-[hsl(var(--panel-2))] px-3 py-2">
        <span className="font-mono text-[10px] text-muted-foreground" data-testid="am-email-display">Email: <span className="text-foreground">{email}</span></span>
        <span className="font-mono text-[10px] text-muted-foreground">Started: {fmtDate(startedAt)} · <span data-testid="am-progress" className="text-[hsl(var(--primary))]">{answered}/{rows.length} answered</span></span>
      </div>

      {/* Checklist — grouped by Sub-Component, tri-state per item */}
      <div className="space-y-3">
        {(template.checklist_groups || []).map((g, gi) => (
          <div key={gi} className="border border-border" data-testid={`am-group-${gi}`}>
            <div className="border-b border-border bg-[hsl(var(--panel-2))] px-3 py-1.5 text-xs font-semibold uppercase tracking-widest text-[hsl(var(--primary))]">{g.description}</div>
            <div className="divide-y divide-border/60">
              {g.items.map((item, ii) => {
                const key = `${gi}|${ii}`;
                const v = res[key] || {};
                const rowErr = errs[key];
                return (
                  <div key={ii} className={`px-3 py-2 ${rowErr ? 'bg-[#ff2e63]/[0.04]' : ''}`} data-testid={`am-item-${gi}-${ii}`}>
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="min-w-[180px] flex-1">
                        <div className="text-sm">{item.checked_for}</div>
                        {item.parameter && <div className="text-[10px] text-muted-foreground">{item.parameter}</div>}
                      </div>
                      <div className="flex gap-1">
                        {Object.keys(STATUS_META).map((s) => (
                          <button key={s} type="button" data-testid={`am-status-${gi}-${ii}-${s}`}
                            onClick={() => setStatus(key, s)}
                            className={`h-9 min-w-[52px] border px-2 font-mono text-[10px] uppercase tracking-wide transition-colors sm:h-8 ${v.status === s ? STATUS_META[s].cls : 'border-border text-muted-foreground hover:text-foreground'}`}>
                            {STATUS_META[s].label}
                          </button>
                        ))}
                      </div>
                    </div>
                    {(v.status === 'NOT_OK' || (v.remarks || '').length > 0) && (
                      <Input data-testid={`am-remarks-${gi}-${ii}`} value={v.remarks || ''} onChange={(e) => setRemarks(key, e.target.value)}
                        placeholder={v.status === 'NOT_OK' ? 'Remarks required — describe the issue found' : 'Remarks (optional)'}
                        className={`mt-1.5 h-9 bg-[hsl(var(--panel-2))] text-xs ${rowErr === 'remarks' ? 'input-error' : ''}`} />
                    )}
                    {rowErr === 'remarks' && <p className="mt-1 text-[10px] text-[#ff2e63]">Remarks are required for NOT OK</p>}
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      <Button data-testid="am-submit-button" disabled={submitting} onClick={submit}
        className="cyber-primary h-11 w-full sm:h-10">
        <ClipboardCheck className="mr-1.5 h-4 w-4" />
        {submitting ? 'Submitting…' : `Submit AM Checklist (${answered}/${rows.length})`}
      </Button>
    </div>
  );
}

/**
 * Compact scheduled-task banner for a machine — DUE (today) and MISSED (past)
 * AM shift occurrences, so an unsubmitted shift check is never silently absent.
 * Used by the Machine Drawer's AM Checklist tab.
 */
export function AmPendingTasks({ machineId }) {
  const [tasks, setTasks] = useState([]);
  useEffect(() => {
    api.get(`/am-tasks?machine_id=${machineId}&status=PENDING`).then((r) => setTasks(r.data)).catch(() => {});
  }, [machineId]);
  if (!tasks.length) return null;
  const today = new Date().toISOString().slice(0, 10);
  return (
    <div className="mb-3 border border-[#f9f871]/40 bg-[#f9f871]/[0.04] p-2.5" data-testid="am-pending-banner">
      <div className="mb-1 font-mono text-[10px] uppercase tracking-widest text-[#f9f871]">Scheduled AM checks awaiting submission</div>
      <div className="flex flex-wrap gap-1.5">
        {tasks.map((t) => (
          <span key={t.id} data-testid={`am-pending-${t.id}`}
            className={`border px-2 py-0.5 font-mono text-[10px] ${t.date < today ? 'border-[#ff2e63]/60 text-[#ff2e63]' : 'border-[#f9f871]/60 text-[#f9f871]'}`}>
            {t.date} · Shift {t.shift} {t.date < today ? '· MISSED' : '· DUE'}
          </span>
        ))}
      </div>
    </div>
  );
}

/**
 * Reusable AM submission history list — used by the AM module page and the
 * Machine Drawer tab. Filterable by shift + date range; per-row PDF download
 * and expandable detail showing every item's tri-state result.
 */
export function AmSubmissionHistory({ machineId = null, compact = false }) {
  const [subs, setSubs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({ shift: 'all', date_from: '', date_to: '' });
  const [expanded, setExpanded] = useState(null);

  useEffect(() => {
    const p = new URLSearchParams();
    if (machineId) p.set('machine_id', machineId);
    if (filters.shift !== 'all') p.set('shift', filters.shift);
    if (filters.date_from) p.set('date_from', filters.date_from);
    if (filters.date_to) p.set('date_to', filters.date_to);
    setLoading(true);
    api.get(`/am-submissions?${p}`).then((r) => setSubs(r.data)).catch(() => {}).finally(() => setLoading(false));
  }, [machineId, filters]);

  return (
    <div data-testid="am-history">
      <div className="mb-2 flex flex-wrap items-end gap-2">
        <div>
          <Label className="text-[9px] uppercase tracking-widest text-muted-foreground">Shift</Label>
          <Select value={filters.shift} onValueChange={(v) => setFilters({ ...filters, shift: v })}>
            <SelectTrigger data-testid="am-history-shift-filter" className="mt-0.5 h-8 w-28 bg-[hsl(var(--panel-2))] text-xs"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All shifts</SelectItem>
              {SHIFTS.map((s) => <SelectItem key={s} value={s}>Shift {s}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <div>
          <Label className="text-[9px] uppercase tracking-widest text-muted-foreground">From</Label>
          <Input type="date" data-testid="am-history-from" value={filters.date_from} onChange={(e) => setFilters({ ...filters, date_from: e.target.value })} className="mt-0.5 h-8 w-36 bg-[hsl(var(--panel-2))] text-xs" />
        </div>
        <div>
          <Label className="text-[9px] uppercase tracking-widest text-muted-foreground">To</Label>
          <Input type="date" data-testid="am-history-to" value={filters.date_to} onChange={(e) => setFilters({ ...filters, date_to: e.target.value })} className="mt-0.5 h-8 w-36 bg-[hsl(var(--panel-2))] text-xs" />
        </div>
      </div>
      {loading && <div className="py-6 text-center text-xs text-muted-foreground">Loading AM submissions…</div>}
      {!loading && subs.length === 0 && <div className="border border-border py-8 text-center text-sm text-muted-foreground" data-testid="am-history-empty">No AM submissions match the filters</div>}
      <div className="space-y-1.5">
        {subs.map((s) => (
          <div key={s.id} className="border border-border bg-[hsl(var(--panel-2))]" data-testid={`am-sub-${s.id}`}>
            <button type="button" className="flex w-full flex-wrap items-center gap-2 px-3 py-2 text-left"
              onClick={() => setExpanded(expanded === s.id ? null : s.id)}>
              {expanded === s.id ? <ChevronDown className="h-3.5 w-3.5 shrink-0 text-muted-foreground" /> : <ChevronRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />}
              <span className="border border-[hsl(var(--primary))]/40 px-1.5 py-px font-mono text-[10px] text-[hsl(var(--primary))]">Shift {s.shift}</span>
              {!compact && !machineId && <span className="text-xs font-medium">{s.machine_name}</span>}
              <span className="text-xs">{s.name} <span className="font-mono text-[10px] text-muted-foreground">GPID {s.gpid}</span></span>
              <span className="font-mono text-[10px] text-muted-foreground">{fmtDate(s.completed_at)} · {s.duration_minutes} min</span>
              <span className="ml-auto flex items-center gap-2">
                {s.not_ok_count > 0
                  ? <span className="border border-[#ff2e63]/50 px-1.5 py-px font-mono text-[10px] text-[#ff2e63]" data-testid={`am-sub-notok-${s.id}`}>{s.not_ok_count} NOT OK</span>
                  : <span className="border border-[#05ffa1]/40 px-1.5 py-px font-mono text-[10px] text-[#05ffa1]">ALL OK</span>}
                <Button size="sm" variant="ghost" className="h-6 px-1.5 text-[10px] text-muted-foreground" title="Download completed sheet PDF"
                  data-testid={`am-sub-pdf-${s.id}`}
                  onClick={(e) => { e.stopPropagation(); downloadAmPdf(s.template_id, s.id, `AM_${s.machine_name}_${s.completed_at.slice(0, 10)}_Shift${s.shift}.pdf`).catch(() => toast.error('PDF download failed')); }}>
                  <Download className="h-3 w-3" />
                </Button>
              </span>
            </button>
            {expanded === s.id && (
              <div className="border-t border-border/60 px-3 py-2" data-testid={`am-sub-detail-${s.id}`}>
                <div className="mb-1 font-mono text-[9px] uppercase tracking-widest text-muted-foreground">Started {fmtDate(s.started_at)} → Completed {fmtDate(s.completed_at)} · via {s.submitted_via === 'public_kiosk' ? 'public kiosk' : 'app'} · {s.email}</div>
                <div className="space-y-0.5">
                  {(s.row_results || []).map((r, i) => (
                    <div key={i} className="flex flex-wrap items-center gap-2 text-xs">
                      <span className={`w-14 shrink-0 border px-1 py-px text-center font-mono text-[9px] ${STATUS_META[r.status]?.cls || 'border-border'}`}>{(r.status || '').replace('_', ' ')}</span>
                      <span className="text-muted-foreground">{r.description} —</span>
                      <span>{r.checked_for}</span>
                      {r.remarks && <span className="text-[10px] italic text-[#ff9e1c]">“{r.remarks}”</span>}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
