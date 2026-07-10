import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { ArrowLeft, FileDown, CheckCircle2 } from 'lucide-react';
import { api, errMsg } from '@/lib/api';
import { useApp } from '@/context/AppContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { SpareRows } from '@/components/Shared';
import { checklistRows, downloadPmPdf } from '@/components/ChecklistBuilder';

function StatusToggle({ value, onChange, testId }) {
  return (
    <div className="flex gap-1" data-testid={testId}>
      <button type="button" onClick={() => onChange('OK')}
        className={`cyber-chamfer-sm border px-2.5 py-1 font-mono text-[10px] uppercase tracking-wide transition-colors ${
          value === 'OK' ? 'power-on border-[#05ffa1] text-[#05ffa1] shadow-[0_0_8px_rgba(5,255,161,0.3)]' : 'border-border text-muted-foreground hover:border-[#05ffa1]/50 hover:text-[#05ffa1]'
        }`}>OK</button>
      <button type="button" onClick={() => onChange('NOT_OK')}
        className={`cyber-chamfer-sm border px-2.5 py-1 font-mono text-[10px] uppercase tracking-wide transition-colors ${
          value === 'NOT_OK' ? 'power-on border-[#ff2e63] text-[#ff2e63] shadow-[0_0_8px_rgba(255,46,99,0.3)]' : 'border-border text-muted-foreground hover:border-[#ff2e63]/50 hover:text-[#ff2e63]'
        }`}>NOT OK</button>
    </div>
  );
}

// Dedicated Close PM Task page — the technician walks the full checklist,
// toggles OK / NOT OK per row and writes per-row remarks before closing.
export default function ClosePMTask() {
  const { taskId } = useParams();
  const navigate = useNavigate();
  const { user } = useApp();
  const [task, setTask] = useState(null);
  const [rows, setRows] = useState([]);
  const [results, setResults] = useState({}); // key -> {status, remarks}
  const [doneBy, setDoneBy] = useState('');
  const [checkedBy, setCheckedBy] = useState('');
  const [remarks, setRemarks] = useState('');
  const [spares, setSpares] = useState([]);
  const [submitting, setSubmitting] = useState(false);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    api.get(`/pm-tasks/${taskId}`)
      .then((r) => {
        setTask(r.data);
        setRows(checklistRows(r.data));
      })
      .catch(() => setNotFound(true));
    setDoneBy(user?.name || '');
  }, [taskId, user]);

  const setRow = (key, patch) => setResults((prev) => ({ ...prev, [key]: { ...prev[key], ...patch } }));

  const submit = async () => {
    const missing = rows.filter((r) => !results[r.key]?.status);
    if (missing.length) {
      toast.error(`Set OK / NOT OK for every row — ${missing.length} remaining`);
      return;
    }
    if (!doneBy.trim()) { toast.error('Done By name is required'); return; }
    setSubmitting(true);
    try {
      const res = await api.post(`/pm-tasks/${taskId}/complete`, {
        remarks: remarks || undefined,
        done_by: doneBy.trim(),
        checked_by: checkedBy.trim() || undefined,
        row_results: rows.map((r) => ({
          sn: r.sn, description: r.description, checked_for: r.checked_for, parameter: r.parameter,
          status: results[r.key].status, remarks: results[r.key]?.remarks || '',
        })),
        spares_consumed: spares.filter((s) => s.sap_code && s.quantity > 0).map((s) => ({ sap_code: s.sap_code, quantity: parseFloat(s.quantity) })),
      });
      toast.success(`PM “${task.task_name}” closed`, {
        description: 'Per-row results saved to the completion record',
        action: { label: 'Download PDF', onClick: () => downloadPmPdf(taskId, res.data.id, `PM_${task.task_name}_completed.pdf`) },
      });
      navigate('/preventive-maintenance');
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setSubmitting(false);
    }
  };

  if (notFound) {
    return (
      <div className="p-10 text-center text-muted-foreground" data-testid="close-pm-not-found">
        PM task not found.
        <Button variant="ghost" className="ml-2" onClick={() => navigate('/preventive-maintenance')}>Back to PM</Button>
      </div>
    );
  }
  if (!task) return <div className="p-10"><div className="cyber-loading w-64" /></div>;

  const doneCount = rows.filter((r) => results[r.key]?.status).length;

  return (
    <div className="mx-auto max-w-5xl p-6" data-testid="close-pm-page">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => navigate('/preventive-maintenance')} data-testid="close-pm-back"><ArrowLeft className="h-4 w-4" /></Button>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Close PM Task — {task.task_name}</h1>
            <p className="text-xs text-muted-foreground">Walk the checklist: every row needs a status. Remarks are per row.</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs tabular-nums text-muted-foreground" data-testid="close-pm-progress">{doneCount}/{rows.length} rows</span>
          <Button variant="outline" size="sm" onClick={() => downloadPmPdf(task.id, null, `PM_${task.task_name}_blank.pdf`)} data-testid="close-pm-blank-pdf">
            <FileDown className="mr-1 h-3.5 w-3.5" /> Blank PDF
          </Button>
        </div>
      </div>

      {/* Header sheet fields — mirrors the printed form */}
      <div className="cyber-panel mb-4 grid grid-cols-2 gap-x-6 gap-y-2 p-4 sm:grid-cols-5" data-testid="close-pm-header">
        {[['Machine', task.machine_name], ['Line', task.line], ['Location / Area', task.location || '—'], ['Frequency', task.frequency], ['Date', new Date().toISOString().slice(0, 10)]].map(([k, v]) => (
          <div key={k}>
            <div className="font-mono text-[9px] uppercase tracking-[0.2em] text-muted-foreground">{k}</div>
            <div className="text-sm font-semibold capitalize">{v}</div>
          </div>
        ))}
      </div>

      {/* Checklist table */}
      <div className="overflow-hidden border border-border">
        <table className="w-full text-sm" data-testid="close-pm-table">
          <thead>
            <tr className="border-b border-border bg-[hsl(var(--panel-1))] text-left font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
              <th className="w-10 px-2 py-2">S.N.</th>
              <th className="px-2 py-2">Description</th>
              <th className="px-2 py-2">Checked For</th>
              <th className="px-2 py-2">Parameter / Process</th>
              <th className="w-40 px-2 py-2">Status</th>
              <th className="w-64 px-2 py-2">Remarks</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && <tr><td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">This task has no checklist defined. Ask an admin to add one.</td></tr>}
            {rows.map((r) => (
              <tr key={r.key} className="border-b border-border/60 align-top hover:bg-white/[0.02]" data-testid={`close-pm-row-${r.key}`}>
                {r.firstOfGroup && (
                  <td rowSpan={r.groupSize} className="border-r border-border/60 px-2 py-2 text-center font-mono text-xs text-muted-foreground">{r.sn}</td>
                )}
                {r.firstOfGroup && (
                  <td rowSpan={r.groupSize} className="border-r border-border/60 px-2 py-2 font-semibold">{r.description}</td>
                )}
                <td className="px-2 py-2">{r.checked_for}</td>
                <td className="px-2 py-2 text-xs text-muted-foreground">{r.parameter || '—'}</td>
                <td className="px-2 py-2"><StatusToggle value={results[r.key]?.status} onChange={(s) => setRow(r.key, { status: s })} testId={`close-pm-status-${r.key}`} /></td>
                <td className="px-2 py-2">
                  <Input value={results[r.key]?.remarks || ''} onChange={(e) => setRow(r.key, { remarks: e.target.value })}
                    placeholder="Row remarks…" data-testid={`close-pm-remarks-${r.key}`} className="h-8 bg-[hsl(var(--panel-2))] text-xs" />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Footer: overall remarks, spares, signatures */}
      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="space-y-3">
          <div><Label className="text-xs">Overall Remarks (optional)</Label><Textarea data-testid="close-pm-overall-remarks" value={remarks} onChange={(e) => setRemarks(e.target.value)} rows={3} className="bg-[hsl(var(--panel-2))]" /></div>
          <SpareRows rows={spares} setRows={setSpares} />
        </div>
        <div className="cyber-panel space-y-3 p-4">
          <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">Sign-off</div>
          <div><Label className="text-xs">Done By (name)</Label><Input data-testid="close-pm-done-by" value={doneBy} onChange={(e) => setDoneBy(e.target.value)} className="bg-[hsl(var(--panel-2))]" /></div>
          <div><Label className="text-xs">Checked By (name, optional)</Label><Input data-testid="close-pm-checked-by" value={checkedBy} onChange={(e) => setCheckedBy(e.target.value)} placeholder="Supervisor / shift lead" className="bg-[hsl(var(--panel-2))]" /></div>
          <Button onClick={submit} disabled={submitting} data-testid="close-pm-submit" className="w-full border border-[#05ffa1]/60 bg-transparent text-[#05ffa1] hover:bg-[#05ffa1]/10">
            <CheckCircle2 className="mr-1 h-4 w-4" /> {submitting ? 'Closing…' : `Close PM Task (${doneCount}/${rows.length})`}
          </Button>
        </div>
      </div>
    </div>
  );
}
