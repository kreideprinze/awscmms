import React, { useCallback, useEffect, useState } from 'react';
import { ClipboardCheck, Plus, Pencil, Copy, Trash2, Download, FileText } from 'lucide-react';
import { toast } from 'sonner';
import { api, errMsg } from '@/lib/api';
import { useApp } from '@/context/AppContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { ChecklistBuilder } from '@/components/ChecklistBuilder';
import { MachineSelect } from '@/components/Shared';
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
  const [fillTpl, setFillTpl] = useState(null);      // template being filled out
  const [editor, setEditor] = useState(null);        // {id?, machine_id, template_name, groups}
  const [dupOf, setDupOf] = useState(null);          // template being duplicated
  const [historyKey, setHistoryKey] = useState(0);   // bump to refresh history after submit

  const load = useCallback(() => {
    api.get('/am-coverage').then((r) => setCoverage(r.data)).catch(() => {});
    api.get('/am-templates').then((r) => setTemplates(r.data)).catch(() => {});
  }, []);
  useEffect(() => { load(); }, [load]);

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
          <Button data-testid="am-new-template-btn" onClick={() => setEditor({ machine_id: '', template_name: '', groups: JSON.parse(JSON.stringify(EMPTY_GROUPS)) })}>
            <Plus className="mr-1 h-4 w-4" /> New AM Template
          </Button>
        )}
      </div>

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
      <Dialog open={!!fillTpl} onOpenChange={(v) => { if (!v) setFillTpl(null); }}>
        <DialogContent className="max-h-[92vh] w-[calc(100%-1rem)] overflow-y-auto border-border bg-[hsl(var(--panel-1))] sm:w-full sm:max-w-2xl" data-testid="am-fill-dialog">
          <DialogHeader>
            <DialogTitle className="text-base uppercase tracking-[0.25em] text-[#05ffa1]">AM Checklist — {fillTpl?.machine_name}</DialogTitle>
          </DialogHeader>
          {fillTpl && <AmChecklistForm template={fillTpl} onDone={() => { setFillTpl(null); setHistoryKey((k) => k + 1); load(); }} />}
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
