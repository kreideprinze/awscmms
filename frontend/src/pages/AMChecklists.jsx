import React, { useCallback, useEffect, useState } from 'react';
import { ClipboardCheck, Plus, Pencil, Copy, Trash2, Download, FileText, CalendarClock, Power } from 'lucide-react';
import { toast } from 'sonner';
import { api, errMsg } from '@/lib/api';
import { useApp } from '@/context/AppContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { ChecklistBuilder } from '@/components/ChecklistBuilder';
import { MachineSelect, TechnicianSelect } from '@/components/Shared';
import { AmChecklistForm, AmSubmissionHistory, downloadAmPdf } from '@/components/AmChecklistForm';

const SHIFTS = ['A', 'B', 'C'];
const EMPTY_GROUPS = [{ description: '', items: [{ checked_for: '', parameter: '' }] }];

/**
 * In-app AM Checklist module (all roles) — operator-driven, SHIFT-BASED routine
 * checks, deliberately separate from PM scheduling:
 *   • Today's per-shift (A/B/C) coverage board
 *   • Fill-out form (same shared form as the public kiosk)
 *   • Admin-only template management (reuses the PM ChecklistBuilder pattern)
 *   • Submission history with filters + PDF export
 */
export default function AMChecklists() {
  const { user } = useApp();
  const isAdmin = user?.role === 'admin';
  const [coverage, setCoverage] = useState(null);
  const [templates, setTemplates] = useState([]);
  const [tasks, setTasks] = useState([]);          // scheduled shift occurrences (last 7d)
  const [schedules, setSchedules] = useState([]);  // admin-managed per-shift recurrences
  const [fillTpl, setFillTpl] = useState(null);      // template being filled out
  const [fillShift, setFillShift] = useState('');    // preselected shift when opened from a task
  const [editor, setEditor] = useState(null);        // {id?, machine_id, template_name, groups}
  const [dupOf, setDupOf] = useState(null);          // template being duplicated
  const [schedDialog, setSchedDialog] = useState(null); // {mode:'machine'|'line', template_id, line, shifts:[], assigned_to}
  const [lines, setLines] = useState([]);
  const [historyKey, setHistoryKey] = useState(0);   // bump to refresh history after submit

  const load = useCallback(() => {
    api.get('/am-coverage').then((r) => setCoverage(r.data)).catch(() => {});
    api.get('/am-templates').then((r) => setTemplates(r.data)).catch(() => {});
    api.get('/am-tasks').then((r) => setTasks(r.data)).catch(() => {});
    api.get('/am-schedules').then((r) => setSchedules(r.data)).catch(() => {});
    api.get('/hierarchy').then((r) => setLines((r.data.lines || r.data || []).map((l) => l.name || l).filter(Boolean))).catch(() => {});
  }, []);
  useEffect(() => { load(); }, [load]);

  const saveSchedule = async () => {
    const d = schedDialog;
    if (!d.shifts.length) return toast.error('Select at least one shift');
    try {
      if (d.mode === 'line') {
        if (!d.line) return toast.error('Select a line');
        const { data } = await api.post('/am-schedules/line-wide', { line: d.line, shifts: d.shifts, assigned_to: d.assigned_to || null });
        toast.success(`Line ${d.line}: ${data.created} created, ${data.updated} updated${data.machines_without_template ? ` · ${data.machines_without_template} machine(s) skipped (no AM template)` : ''}`);
      } else {
        if (!d.template_id) return toast.error('Select a machine checklist');
        await api.post('/am-schedules', { template_id: d.template_id, shifts: d.shifts, assigned_to: d.assigned_to || null });
        toast.success('AM schedule created');
      }
      setSchedDialog(null);
      load();
    } catch (e) { toast.error(errMsg(e)); }
  };

  const toggleScheduleShift = async (s, shift) => {
    const next = ['A', 'B', 'C'].filter((x) => (x === shift ? !s.shifts.includes(x) : s.shifts.includes(x)));
    if (!next.length) return toast.error('A schedule needs at least one shift — deactivate it instead');
    try { await api.put(`/am-schedules/${s.id}`, { shifts: next }); load(); } catch (e) { toast.error(errMsg(e)); }
  };

  const toggleScheduleActive = async (s) => {
    try {
      await api.put(`/am-schedules/${s.id}`, { active: !s.active });
      toast.success(s.active ? `Schedule deactivated — ${s.machine_name}` : `Schedule reactivated — ${s.machine_name}`);
      load();
    } catch (e) { toast.error(errMsg(e)); }
  };

  const removeSchedule = async (s) => {
    if (!window.confirm(`Delete the AM schedule for ${s.machine_name}? Pending occurrences are removed; submitted history is kept.`)) return;
    try { await api.delete(`/am-schedules/${s.id}`); toast.success('Schedule deleted'); load(); } catch (e) { toast.error(errMsg(e)); }
  };

  const openFillForTask = (t) => {
    const tpl = templates.find((x) => x.id === t.template_id);
    if (!tpl) return toast.error('Template not found');
    setFillShift(t.shift);
    setFillTpl(tpl);
  };

  const saveTemplate = async () => {
    const groups = (editor.groups || []).filter((g) => g.description.trim() && g.items.some((i) => i.checked_for.trim()));
    if (!editor.template_name?.trim()) return toast.error('Template name is required');
    if (!editor.id && !editor.machine_id) return toast.error('Select a machine');
    if (!groups.length) return toast.error('Add at least one sub-component with a check item');
    try {
      if (editor.id) {
        await api.put(`/am-templates/${editor.id}`, { template_name: editor.template_name.trim(), checklist_groups: groups });
        toast.success('AM template updated');
      } else {
        await api.post('/am-templates', { machine_id: editor.machine_id, template_name: editor.template_name.trim(), checklist_groups: groups });
        toast.success('AM template created');
      }
      setEditor(null);
      load();
    } catch (e) { toast.error(errMsg(e)); }
  };

  const duplicate = async () => {
    if (!dupOf?.target_machine_id) return toast.error('Select the target machine');
    try {
      await api.post(`/am-templates/${dupOf.id}/duplicate`, { target_machine_id: dupOf.target_machine_id, template_name: dupOf.template_name?.trim() || undefined });
      toast.success('Template duplicated');
      setDupOf(null);
      load();
    } catch (e) { toast.error(errMsg(e)); }
  };

  const remove = async (t) => {
    if (!window.confirm(`Delete AM template "${t.template_name}" for ${t.machine_name}? Submission history is kept.`)) return;
    try {
      await api.delete(`/am-templates/${t.id}`);
      toast.success('Template deleted');
      load();
    } catch (e) { toast.error(errMsg(e)); }
  };

  const itemCount = (t) => (t.checklist_groups || []).reduce((n, g) => n + g.items.length, 0);

  return (
    <div className="p-6" data-testid="am-page">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight"><ClipboardCheck className="h-5 w-5 text-[#05ffa1]" /> AM Checklists</h1>
          <p className="text-sm text-muted-foreground">Autonomous Maintenance — operator-driven, once per shift (A/B/C) · separate from PM scheduling</p>
        </div>
        {isAdmin && (
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" data-testid="am-new-schedule-btn" onClick={() => setSchedDialog({ mode: 'machine', template_id: '', line: '', shifts: [], assigned_to: '' })}>
              <CalendarClock className="mr-1 h-4 w-4" /> Schedule AM Tasks
            </Button>
            <Button data-testid="am-new-template-btn" onClick={() => setEditor({ machine_id: '', template_name: '', groups: JSON.parse(JSON.stringify(EMPTY_GROUPS)) })}>
              <Plus className="mr-1 h-4 w-4" /> New AM Template
            </Button>
          </div>
        )}
      </div>

      {/* SCHEDULED AM TASKS — due / missed / submitted shift occurrences (last 7 days) */}
      {tasks.length > 0 && (() => {
        const today = new Date().toISOString().slice(0, 10);
        const missed = tasks.filter((t) => t.status === 'PENDING' && t.date < today);
        const dueToday = tasks.filter((t) => t.status === 'PENDING' && t.date === today);
        const doneToday = tasks.filter((t) => t.status === 'SUBMITTED' && t.date === today);
        return (
          <div className="cyber-panel mb-4 p-4" data-testid="am-tasks-panel">
            <div className="mb-2 flex flex-wrap items-center gap-3 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
              <span className="flex items-center gap-1.5"><CalendarClock className="h-3.5 w-3.5 text-[hsl(var(--primary))]" /> Scheduled AM Tasks</span>
              <span className="font-mono text-[10px] normal-case tracking-normal">
                <span className={dueToday.length ? 'text-[#f9f871]' : ''}>{dueToday.length} due today</span> · <span className={missed.length ? 'text-[#ff2e63]' : ''}>{missed.length} missed (7d)</span> · <span className="text-[#05ffa1]">{doneToday.length} submitted today</span>
              </span>
            </div>
            <div className="space-y-1.5">
              {[...dueToday, ...missed].map((t) => (
                <div key={t.id} data-testid={`am-task-${t.id}`}
                  className={`flex flex-wrap items-center gap-2 border px-3 py-2 ${t.date < today ? 'border-[#ff2e63]/40 bg-[#ff2e63]/[0.04]' : 'border-[#f9f871]/40 bg-[#f9f871]/[0.03]'}`}>
                  <span className={`border px-1.5 py-px font-mono text-[10px] ${t.date < today ? 'border-[#ff2e63]/60 text-[#ff2e63]' : 'border-[#f9f871]/60 text-[#f9f871]'}`}>
                    {t.date < today ? 'MISSED' : 'DUE'}
                  </span>
                  <span className="text-sm font-medium">{t.machine_name}</span>
                  <span className="font-mono text-[10px] text-muted-foreground">{t.template_name} · {t.line}</span>
                  <span className="border border-border px-1.5 py-px font-mono text-[10px]">Shift {t.shift}</span>
                  <span className="font-mono text-[10px] text-muted-foreground">{t.date}</span>
                  {t.assigned_to && <span className="font-mono text-[10px] text-muted-foreground">→ {t.assigned_to}</span>}
                  {t.date === today && (
                    <Button size="sm" data-testid={`am-task-fill-${t.id}`} onClick={() => openFillForTask(t)}
                      className="ml-auto h-7 border border-[#05ffa1]/60 bg-transparent px-2 text-[10px] text-[#05ffa1] hover:bg-[#05ffa1]/10">
                      <FileText className="mr-1 h-3 w-3" /> Fill Out
                    </Button>
                  )}
                </div>
              ))}
              {dueToday.length === 0 && missed.length === 0 && (
                <div className="border border-[#05ffa1]/30 px-3 py-2 text-xs text-[#05ffa1]" data-testid="am-tasks-all-clear">All scheduled shift checks are submitted — nothing pending.</div>
              )}
            </div>
          </div>
        );
      })()}

      {/* SCHEDULES — admin-managed per-shift recurrences (mirrors PM scheduling) */}
      {(schedules.length > 0 || isAdmin) && (
        <div className="cyber-panel mb-4 overflow-hidden" data-testid="am-schedules-panel">
          <div className="border-b border-border px-4 py-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">Recurring Schedules ({schedules.length}) · generated automatically each shift</div>
          <Table>
            <TableHeader>
              <TableRow className="border-border bg-[hsl(var(--panel-1))] hover:bg-[hsl(var(--panel-1))]">
                <TableHead className="text-xs uppercase">Machine / Template</TableHead>
                <TableHead className="text-xs uppercase">Shifts</TableHead>
                <TableHead className="text-xs uppercase">Default Assignee</TableHead>
                <TableHead className="text-xs uppercase">Status</TableHead>
                {isAdmin && <TableHead className="text-right text-xs uppercase">Actions</TableHead>}
              </TableRow>
            </TableHeader>
            <TableBody>
              {schedules.length === 0 && <TableRow><TableCell colSpan={5} className="py-6 text-center text-muted-foreground">No recurring schedules yet — click “Schedule AM Tasks”.</TableCell></TableRow>}
              {schedules.map((s) => (
                <TableRow key={s.id} data-testid={`am-schedule-row-${s.id}`} className="border-border hover:bg-white/[0.03]">
                  <TableCell>
                    <div className="text-sm font-medium">{s.machine_name}</div>
                    <div className="text-[10px] text-muted-foreground">{s.template_name} · {s.line}</div>
                  </TableCell>
                  <TableCell>
                    <div className="flex gap-1">
                      {['A', 'B', 'C'].map((sh) => (
                        <button key={sh} type="button" disabled={!isAdmin} data-testid={`am-schedule-${s.id}-shift-${sh}`}
                          onClick={() => isAdmin && toggleScheduleShift(s, sh)}
                          title={isAdmin ? `Toggle Shift ${sh}` : undefined}
                          className={`flex h-7 w-7 items-center justify-center border font-mono text-[11px] ${s.shifts.includes(sh) ? 'border-[hsl(var(--primary))]/60 text-[hsl(var(--primary))] bg-[hsl(var(--primary))]/10' : 'border-border text-muted-foreground'} ${isAdmin ? 'hover:border-[hsl(var(--primary))]' : 'cursor-default'}`}>
                          {sh}
                        </button>
                      ))}
                    </div>
                  </TableCell>
                  <TableCell className="font-mono text-xs">{s.assigned_to || <span className="text-muted-foreground">open pick-up</span>}</TableCell>
                  <TableCell>
                    <span className={`border px-1.5 py-px font-mono text-[10px] ${s.active ? 'border-[#05ffa1]/50 text-[#05ffa1]' : 'border-border text-muted-foreground'}`}>{s.active ? 'ACTIVE' : 'INACTIVE'}</span>
                  </TableCell>
                  {isAdmin && (
                    <TableCell>
                      <div className="flex justify-end gap-1">
                        <Button size="sm" variant="outline" className="h-7 px-1.5 text-[10px]" title={s.active ? 'Deactivate schedule' : 'Reactivate schedule'} data-testid={`am-schedule-toggle-${s.id}`}
                          onClick={() => toggleScheduleActive(s)}>
                          <Power className={`h-3 w-3 ${s.active ? 'text-[#05ffa1]' : ''}`} />
                        </Button>
                        <Button size="sm" variant="ghost" className="h-7 px-1.5 text-[10px] text-muted-foreground hover:text-[#ff2e63]" title="Delete schedule" data-testid={`am-schedule-delete-${s.id}`}
                          onClick={() => removeSchedule(s)}>
                          <Trash2 className="h-3 w-3" />
                        </Button>
                      </div>
                    </TableCell>
                  )}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {/* TODAY'S SHIFT COVERAGE BOARD */}
      <div className="cyber-panel mb-4 p-4" data-testid="am-coverage-board">
        <div className="mb-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">Today's Shift Coverage · {coverage?.date}</div>
        {!coverage && <div className="py-4 text-center text-xs text-muted-foreground">Loading…</div>}
        {coverage && coverage.rows.length === 0 && <div className="py-6 text-center text-sm text-muted-foreground" data-testid="am-coverage-empty">No AM templates configured yet{isAdmin ? ' — create one to start tracking shift coverage.' : '.'}</div>}
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-3">
          {(coverage?.rows || []).map((r) => (
            <div key={r.template_id} className="flex items-center justify-between gap-2 border border-border bg-[hsl(var(--panel-2))] px-3 py-2" data-testid={`am-coverage-${r.machine_id}`}>
              <div className="min-w-0">
                <div className="truncate text-sm font-medium">{r.machine_name}</div>
                <div className="truncate font-mono text-[9px] text-muted-foreground">{r.template_name} · {r.line}</div>
              </div>
              <div className="flex shrink-0 gap-1">
                {SHIFTS.map((sh) => {
                  const st = r.shifts[sh];
                  return (
                    <span key={sh} data-testid={`am-coverage-${r.machine_id}-${sh}`}
                      title={st.done ? `Shift ${sh} done by ${st.last_by}` : `Shift ${sh} pending`}
                      className={`flex h-7 w-7 items-center justify-center border font-mono text-[11px] ${st.done ? 'border-[#05ffa1]/60 text-[#05ffa1] bg-[#05ffa1]/10' : 'border-border text-muted-foreground'}`}>
                      {sh}
                    </span>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* TEMPLATES */}
      <div className="cyber-panel mb-4 overflow-hidden" data-testid="am-templates-panel">
        <div className="border-b border-border px-4 py-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">Templates ({templates.length})</div>
        <Table>
          <TableHeader>
            <TableRow className="border-border bg-[hsl(var(--panel-1))] hover:bg-[hsl(var(--panel-1))]">
              <TableHead className="text-xs uppercase">Machine</TableHead>
              <TableHead className="text-xs uppercase">Template</TableHead>
              <TableHead className="text-xs uppercase">Items</TableHead>
              <TableHead className="text-xs uppercase">Frequency</TableHead>
              <TableHead className="text-right text-xs uppercase">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {templates.length === 0 && <TableRow><TableCell colSpan={5} className="py-8 text-center text-muted-foreground">No AM templates yet{isAdmin ? ' — click “New AM Template”.' : '.'}</TableCell></TableRow>}
            {templates.map((t) => (
              <TableRow key={t.id} data-testid={`am-template-row-${t.id}`} className="border-border hover:bg-white/[0.03]">
                <TableCell>
                  <div className="text-sm font-medium">{t.machine_name}</div>
                  <div className="text-[10px] text-muted-foreground">{t.line} / {t.process_group}</div>
                </TableCell>
                <TableCell className="text-sm">{t.template_name}</TableCell>
                <TableCell className="font-mono text-xs">{(t.checklist_groups || []).length} groups · {itemCount(t)} items</TableCell>
                <TableCell><span className="border border-[#05ffa1]/40 px-1.5 py-px font-mono text-[10px] text-[#05ffa1]">PER SHIFT</span></TableCell>
                <TableCell>
                  <div className="flex flex-wrap justify-end gap-1">
                    <Button size="sm" data-testid={`am-fill-${t.id}`} onClick={() => setFillTpl(t)}
                      className="h-7 border border-[#05ffa1]/60 bg-transparent px-2 text-[10px] text-[#05ffa1] hover:bg-[#05ffa1]/10">
                      <FileText className="mr-1 h-3 w-3" /> Fill Out
                    </Button>
                    <Button size="sm" variant="outline" className="h-7 px-1.5 text-[10px]" title="Download blank sheet PDF" data-testid={`am-pdf-blank-${t.id}`}
                      onClick={() => downloadAmPdf(t.id, null, `AM_${t.machine_name}_blank.pdf`).catch(() => toast.error('PDF download failed'))}>
                      <Download className="h-3 w-3" />
                    </Button>
                    {isAdmin && (
                      <>
                        <Button size="sm" variant="outline" className="h-7 px-1.5 text-[10px]" title="Edit template" data-testid={`am-edit-${t.id}`}
                          onClick={() => setEditor({ id: t.id, machine_id: t.machine_id, template_name: t.template_name, groups: JSON.parse(JSON.stringify(t.checklist_groups || EMPTY_GROUPS)) })}>
                          <Pencil className="h-3 w-3" />
                        </Button>
                        <Button size="sm" variant="outline" className="h-7 px-1.5 text-[10px]" title="Duplicate to another machine" data-testid={`am-duplicate-${t.id}`}
                          onClick={() => setDupOf({ id: t.id, template_name: '', target_machine_id: '', source: t })}>
                          <Copy className="h-3 w-3" />
                        </Button>
                        <Button size="sm" variant="ghost" className="h-7 px-1.5 text-[10px] text-muted-foreground hover:text-[#ff2e63]" title="Delete template" data-testid={`am-delete-${t.id}`}
                          onClick={() => remove(t)}>
                          <Trash2 className="h-3 w-3" />
                        </Button>
                      </>
                    )}
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {/* SUBMISSION HISTORY */}
      <div className="cyber-panel p-4" data-testid="am-history-panel">
        <div className="mb-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">Submission History</div>
        <AmSubmissionHistory key={historyKey} />
      </div>

      {/* FILL-OUT dialog (same shared form as the public kiosk) */}
      <Dialog open={!!fillTpl} onOpenChange={(v) => { if (!v) { setFillTpl(null); setFillShift(''); } }}>
        <DialogContent className="max-h-[92vh] w-[calc(100%-1rem)] overflow-y-auto border-border bg-[hsl(var(--panel-1))] sm:w-full sm:max-w-2xl" data-testid="am-fill-dialog">
          <DialogHeader>
            <DialogTitle className="text-base uppercase tracking-[0.25em] text-[#05ffa1]">AM Checklist — {fillTpl?.machine_name}{fillShift ? ` · Shift ${fillShift}` : ''}</DialogTitle>
          </DialogHeader>
          {fillTpl && <AmChecklistForm template={fillTpl} initialShift={fillShift} onDone={() => { setFillTpl(null); setFillShift(''); setHistoryKey((k) => k + 1); load(); }} />}
        </DialogContent>
      </Dialog>

      {/* SCHEDULE dialog (admin) — per machine or line-wide, per-shift recurrence */}
      <Dialog open={!!schedDialog} onOpenChange={(v) => { if (!v) setSchedDialog(null); }}>
        <DialogContent className="border-border bg-[hsl(var(--panel-1))] sm:max-w-md" data-testid="am-schedule-dialog">
          <DialogHeader>
            <DialogTitle className="text-base uppercase tracking-[0.25em]">Schedule AM Tasks</DialogTitle>
          </DialogHeader>
          {schedDialog && (
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-1">
                {[['machine', 'Single Machine'], ['line', 'Line-wide']].map(([k, lbl]) => (
                  <button key={k} type="button" data-testid={`am-schedule-mode-${k}`} onClick={() => setSchedDialog({ ...schedDialog, mode: k })}
                    className={`border px-2 py-1.5 font-mono text-[10px] uppercase tracking-wide ${schedDialog.mode === k ? 'border-[hsl(var(--primary))] text-[hsl(var(--primary))] bg-[hsl(var(--primary))]/10' : 'border-border text-muted-foreground hover:text-foreground'}`}>
                    {lbl}
                  </button>
                ))}
              </div>
              {schedDialog.mode === 'machine' ? (
                <div>
                  <Label className="text-[10px] uppercase tracking-widest text-muted-foreground">Machine Checklist <span className="text-[#ff2e63]">*</span></Label>
                  <Select value={schedDialog.template_id} onValueChange={(v) => setSchedDialog({ ...schedDialog, template_id: v })}>
                    <SelectTrigger data-testid="am-schedule-template-select" className="mt-0.5 bg-[hsl(var(--panel-2))]"><SelectValue placeholder="Select a template" /></SelectTrigger>
                    <SelectContent>
                      {templates.filter((t) => !schedules.some((s) => s.template_id === t.id)).map((t) => (
                        <SelectItem key={t.id} value={t.id}>{t.machine_name} — {t.template_name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <p className="mt-1 text-[10px] text-muted-foreground">Templates that already have a schedule are hidden — edit them in the table instead.</p>
                </div>
              ) : (
                <div>
                  <Label className="text-[10px] uppercase tracking-widest text-muted-foreground">Line <span className="text-[#ff2e63]">*</span></Label>
                  <Select value={schedDialog.line} onValueChange={(v) => setSchedDialog({ ...schedDialog, line: v })}>
                    <SelectTrigger data-testid="am-schedule-line-select" className="mt-0.5 bg-[hsl(var(--panel-2))]"><SelectValue placeholder="Select a line" /></SelectTrigger>
                    <SelectContent>{lines.map((l) => <SelectItem key={l} value={l}>{l}</SelectItem>)}</SelectContent>
                  </Select>
                  <p className="mt-1 text-[10px] text-muted-foreground">Applies to every machine on the line that has an AM template; machines without one are skipped.</p>
                </div>
              )}
              <div>
                <Label className="text-[10px] uppercase tracking-widest text-muted-foreground">Shifts <span className="text-[#ff2e63]">*</span></Label>
                <div className="mt-1 flex gap-1.5">
                  {['A', 'B', 'C'].map((sh) => (
                    <button key={sh} type="button" data-testid={`am-schedule-shift-${sh}`}
                      onClick={() => setSchedDialog({ ...schedDialog, shifts: schedDialog.shifts.includes(sh) ? schedDialog.shifts.filter((x) => x !== sh) : [...schedDialog.shifts, sh] })}
                      className={`flex h-10 w-10 items-center justify-center border font-mono text-sm ${schedDialog.shifts.includes(sh) ? 'border-[hsl(var(--primary))] text-[hsl(var(--primary))] bg-[hsl(var(--primary))]/10' : 'border-border text-muted-foreground hover:text-foreground'}`}>
                      {sh}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <Label className="text-[10px] uppercase tracking-widest text-muted-foreground">Default Assignee (optional)</Label>
                <div className="mt-0.5">
                  <TechnicianSelect value={schedDialog.assigned_to} onChange={(v) => setSchedDialog({ ...schedDialog, assigned_to: v })} testId="am-schedule-assignee" allowNone />
                </div>
                <p className="mt-1 text-[10px] text-muted-foreground">Leave empty for open pick-up — any on-shift person can submit it.</p>
              </div>
              <Button data-testid="am-schedule-save" onClick={saveSchedule} className="w-full">Create Schedule{schedDialog.mode === 'line' ? 's' : ''}</Button>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* TEMPLATE EDITOR (admin) — reuses the PM ChecklistBuilder pattern */}
      <Dialog open={!!editor} onOpenChange={(v) => { if (!v) setEditor(null); }}>
        <DialogContent className="max-h-[92vh] w-[calc(100%-1rem)] overflow-y-auto border-border bg-[hsl(var(--panel-1))] sm:w-full sm:max-w-2xl" data-testid="am-editor-dialog">
          <DialogHeader>
            <DialogTitle className="text-base uppercase tracking-[0.25em]">{editor?.id ? 'Edit AM Template' : 'New AM Template'}</DialogTitle>
          </DialogHeader>
          {editor && (
            <div className="space-y-3">
              {!editor.id && (
                <div>
                  <Label className="text-[10px] uppercase tracking-widest text-muted-foreground">Machine <span className="text-[#ff2e63]">*</span></Label>
                  <MachineSelect value={editor.machine_id} onChange={(v) => setEditor({ ...editor, machine_id: v })} testId="am-editor-machine" />
                </div>
              )}
              <div>
                <Label className="text-[10px] uppercase tracking-widest text-muted-foreground">Template Name <span className="text-[#ff2e63]">*</span></Label>
                <Input data-testid="am-editor-name" value={editor.template_name} onChange={(e) => setEditor({ ...editor, template_name: e.target.value })}
                  placeholder='e.g. "AM — Fryer"' className="mt-0.5 bg-[hsl(var(--panel-2))]" />
              </div>
              <div>
                <Label className="text-[10px] uppercase tracking-widest text-muted-foreground">Sub-Components & Check Items</Label>
                <div className="mt-1">
                  <ChecklistBuilder groups={editor.groups} setGroups={(g) => setEditor({ ...editor, groups: g })} />
                </div>
              </div>
              <Button data-testid="am-editor-save" onClick={saveTemplate} className="w-full">{editor.id ? 'Save Changes' : 'Create Template'}</Button>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* DUPLICATE dialog (admin) */}
      <Dialog open={!!dupOf} onOpenChange={(v) => { if (!v) setDupOf(null); }}>
        <DialogContent className="border-border bg-[hsl(var(--panel-1))] sm:max-w-md" data-testid="am-duplicate-dialog">
          <DialogHeader>
            <DialogTitle className="text-base uppercase tracking-[0.25em]">Duplicate Template</DialogTitle>
          </DialogHeader>
          {dupOf && (
            <div className="space-y-3">
              <p className="text-xs text-muted-foreground">Copy “{dupOf.source?.template_name}” ({dupOf.source?.machine_name}) to another machine.</p>
              <div>
                <Label className="text-[10px] uppercase tracking-widest text-muted-foreground">Target Machine <span className="text-[#ff2e63]">*</span></Label>
                <MachineSelect value={dupOf.target_machine_id} onChange={(v) => setDupOf({ ...dupOf, target_machine_id: v })} testId="am-duplicate-machine" />
              </div>
              <div>
                <Label className="text-[10px] uppercase tracking-widest text-muted-foreground">New Name (optional)</Label>
                <Input data-testid="am-duplicate-name" value={dupOf.template_name} onChange={(e) => setDupOf({ ...dupOf, template_name: e.target.value })}
                  placeholder="Defaults to “AM — <machine>”" className="mt-0.5 bg-[hsl(var(--panel-2))]" />
              </div>
              <Button data-testid="am-duplicate-confirm" onClick={duplicate} className="w-full">Duplicate</Button>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
