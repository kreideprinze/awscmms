import React, { useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';
import { api, errMsg } from '@/lib/api';
import { useApp } from '@/context/AppContext';
import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

const DEPARTMENTS = ['PROCESS', 'PACKAGING', 'UTILITIES'];
const BREAKDOWN_TYPES = [
  { value: 'MECHANICAL', label: 'MECHANICAL' },
  { value: 'ELECTRICAL', label: 'ELECTRICAL' },
  { value: 'CONTROL_PLC', label: 'CONTROL (PLC)' },
];
const WO_TYPES = [
  { value: 'Inspection', label: 'INSPECTION' },
  { value: 'Corrective', label: 'CORRECTIVE' },
];

function Segmented({ options, value, onChange, testPrefix, accent = 'primary' }) {
  const selCls = accent === 'yellow'
    ? 'power-on border-[#f9f871] bg-transparent text-[#f9f871] shadow-[0_0_10px_rgba(249,248,113,0.25)]'
    : 'power-on border-[hsl(var(--primary))] bg-transparent text-[hsl(var(--primary))] shadow-[0_0_10px_rgba(var(--accent-rgb),0.25)]';
  return (
    <div className={`grid gap-2 ${options.length === 2 ? 'grid-cols-2' : 'grid-cols-3'}`}>
      {options.map((opt) => {
        const val = typeof opt === 'string' ? opt : opt.value;
        const label = typeof opt === 'string' ? opt : opt.label;
        const selected = value === val;
        return (
          <button
            key={val}
            type="button"
            data-testid={`${testPrefix}-${val}`}
            onClick={() => onChange(val)}
            className={`cyber-chamfer-sm border px-2 py-2 text-[11px] font-semibold uppercase tracking-widest transition-all duration-150 ${
              selected ? selCls : 'border-border text-muted-foreground hover:border-muted-foreground hover:text-foreground'
            }`}
          >
            {label}
          </button>
        );
      })}
    </div>
  );
}

/**
 * Shared report dialog.
 * mode="breakdown" — machine down, counts as downtime, creates a Breakdown (red)
 * mode="warning"   — observation only: NO downtime, NO breakdown record, machine goes
 *                    yellow 'watch', and an Inspection/Corrective WO is always dispatched.
 * The dialog only closes via the explicit × button (no outside-click / Escape dismiss).
 */
export function ReportBreakdownDialog({ open, setOpen, prefillMachine = null, onCreated, publicMode = false, mode = 'breakdown' }) {
  const { user } = useApp();
  const isWarning = mode === 'warning';
  const [lines, setLines] = useState([]);
  const [machines, setMachines] = useState([]);
  const [technicians, setTechnicians] = useState([]);
  const [dept, setDept] = useState('PROCESS');
  const [area, setArea] = useState('');
  const [machineId, setMachineId] = useState('');
  const [reporterName, setReporterName] = useState('');
  const [breakdownType, setBreakdownType] = useState('MECHANICAL');
  const [woType, setWoType] = useState('Inspection');
  const [remarks, setRemarks] = useState('');
  const [technician, setTechnician] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [errors, setErrors] = useState({});

  useEffect(() => {
    if (!open) return;
    if (publicMode) {
      api.get('/public/report-context').then((r) => {
        setLines(r.data.lines);
        setMachines(r.data.machines);
        setTechnicians(r.data.technicians || []);
      });
    } else {
      api.get('/hierarchy').then((r) => setLines(r.data.lines));
      api.get('/machines?limit=10000').then((r) => setMachines(r.data));
      api.get('/users/technicians').then((r) => setTechnicians((r.data || []).filter((t) => t.role === 'technician').map((t) => ({ username: t.username, name: t.name })))).catch(() => {});
    }
    setReporterName(publicMode ? '' : user?.name || '');
    setBreakdownType('MECHANICAL');
    setWoType('Inspection');
    setRemarks('');
    setTechnician('');
    setErrors({});
    if (prefillMachine) {
      setDept(prefillMachine.department || 'PROCESS');
      setArea(prefillMachine.line || '');
      setMachineId(prefillMachine.id || '');
    } else {
      setDept('PROCESS');
      setArea('');
      setMachineId('');
    }
  }, [open, prefillMachine, user, publicMode]);

  const areaOptions = useMemo(() => lines.filter((l) => l.department === dept).map((l) => l.name), [lines, dept]);
  const machineOptions = useMemo(() => machines.filter((m) => m.line === area), [machines, area]);
  const selectedMachine = machines.find((m) => m.id === machineId);

  const ctx = {
    dept: selectedMachine?.department || dept || '—',
    area: selectedMachine?.line || area || '—',
    equipment: selectedMachine ? selectedMachine.name : '—',
  };

  const submit = async () => {
    const errs = {};
    if (!machineId) errs.machine = true;
    if (!reporterName.trim()) errs.reporter = true;
    if (!remarks.trim()) errs.remarks = true;
    if (!technician) errs.technician = true;
    setErrors(errs);
    if (Object.keys(errs).length) {
      toast.error('Machine, reporter name, remarks and assigned technician are required');
      return;
    }
    setSubmitting(true);
    try {
      let res;
      if (isWarning) {
        res = await api.post(publicMode ? '/public/warnings' : '/warnings', {
          machine_id: machineId,
          description: remarks,
          warning_type: breakdownType,
          reporter_name: reporterName,
          wo_type: woType,
          assigned_to: technician,
        });
        toast.warning(`Warning ${res.data.tag_number} raised — ${res.data.work_order_number} assigned to ${technician} (no downtime recorded)`);
      } else {
        res = await api.post(publicMode ? '/public/breakdowns' : '/breakdowns', {
          machine_id: machineId,
          description: remarks,
          breakdown_type: breakdownType,
          reporter_name: reporterName,
          assigned_to: technician,
        });
        toast.success(`Breakdown ${res.data.ticket_number} created — ${res.data.work_order_number} assigned to ${technician}`);
      }
      setOpen(false);
      onCreated && onCreated(res.data);
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent
        className="max-h-[90vh] gap-0 overflow-y-auto border-border bg-[#0a0a0f] p-0 sm:max-w-lg"
        data-testid={isWarning ? 'report-warning-dialog' : 'report-breakdown-dialog'}
        onInteractOutside={(e) => e.preventDefault()}
        onPointerDownOutside={(e) => e.preventDefault()}
        onEscapeKeyDown={(e) => e.preventDefault()}
      >
        {/* Header bar */}
        <div className={`flex items-center justify-between border-b px-5 py-4 ${isWarning ? 'border-[#f9f871]/30 bg-[#f9f871]/[0.04]' : 'border-border bg-[#08080c]'}`}>
          <DialogTitle className={`text-base font-semibold uppercase tracking-[0.3em] ${isWarning ? 'text-[#f9f871]' : 'text-foreground'}`}>
            {isWarning ? 'Report Warning' : 'Report Breakdown'}
          </DialogTitle>
        </div>

        <div className="space-y-4 p-5">
          {isWarning && (
            <div className="border border-[#f9f871]/30 bg-[#f9f871]/[0.05] px-3 py-2 text-[11px] text-[#f9f871]" data-testid="warning-info-note">
              Observation only — no downtime is recorded and availability/MTBF are unaffected. A work order is always dispatched.
            </div>
          )}
          {/* Context strip — read-only */}
          <div className={`cyber-chamfer-sm grid grid-cols-3 gap-3 border px-4 py-3 ${isWarning ? 'border-[#f9f871]/20 bg-[#f9f871]/[0.04]' : 'border-[#05ffa1]/20 bg-[#05ffa1]/[0.05]'}`} data-testid="breakdown-context-strip">
            {[['DEPT', ctx.dept], ['AREA', ctx.area], ['EQUIPMENT', ctx.equipment]].map(([k, v]) => (
              <div key={k} className="min-w-0">
                <div className="text-[9px] font-semibold uppercase tracking-[0.2em] text-muted-foreground">{k}</div>
                <div className="truncate text-sm font-medium text-foreground" title={v}>{v}</div>
              </div>
            ))}
          </div>

          {/* Editable hierarchy group */}
          <div className="space-y-3 border border-dashed border-border p-4">
            <div>
              <Label className="mb-1.5 block text-[10px] uppercase tracking-[0.2em] text-muted-foreground">Department</Label>
              <Segmented options={DEPARTMENTS} value={dept} onChange={(v) => { setDept(v); setArea(''); setMachineId(''); }} testPrefix="bd-dept" accent={isWarning ? 'yellow' : 'primary'} />
            </div>
            <div>
              <Label className="mb-1.5 block text-[10px] uppercase tracking-[0.2em] text-muted-foreground">Area</Label>
              <Select value={area} onValueChange={(v) => { setArea(v); setMachineId(''); }}>
                <SelectTrigger data-testid="bd-area-select" className="bg-[hsl(var(--panel-2))]"><SelectValue placeholder="Select area / line" /></SelectTrigger>
                <SelectContent>
                  {areaOptions.length === 0 && <div className="px-3 py-2 text-xs text-muted-foreground">No areas under {dept}</div>}
                  {areaOptions.map((a) => <SelectItem key={a} value={a}>{a}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="mb-1.5 block text-[10px] uppercase tracking-[0.2em] text-muted-foreground">Machine</Label>
              <Select value={machineId} onValueChange={setMachineId}>
                <SelectTrigger data-testid="bd-machine-select" className={`bg-[hsl(var(--panel-2))] ${errors.machine ? 'input-error' : ''}`}>
                  <SelectValue placeholder={area ? 'Select machine' : 'Select area first'} />
                </SelectTrigger>
                <SelectContent>
                  {machineOptions.length === 0 && <div className="px-3 py-2 text-xs text-muted-foreground">No machines under {area || 'selected area'}</div>}
                  {machineOptions.map((m) => (
                    <SelectItem key={m.id} value={m.id}>
                      <span className="font-mono text-xs">{m.code}</span> · {m.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Reporter name */}
          <div>
            <Label className="mb-1.5 block text-[10px] uppercase tracking-[0.2em] text-muted-foreground">Reporter Name *</Label>
            <Input
              data-testid="bd-reporter-input"
              value={reporterName}
              onChange={(e) => setReporterName(e.target.value)}
              placeholder="Who is reporting this?"
              className={`bg-[hsl(var(--panel-2))] ${errors.reporter ? 'input-error' : ''}`}
            />
          </div>

          {/* Type */}
          <div>
            <Label className="mb-1.5 block text-[10px] uppercase tracking-[0.2em] text-muted-foreground">{isWarning ? 'Warning Type' : 'Breakdown Type'}</Label>
            <Segmented options={BREAKDOWN_TYPES} value={breakdownType} onChange={setBreakdownType} testPrefix="bd-type" accent={isWarning ? 'yellow' : 'primary'} />
          </div>

          {/* Warning: WO type choice */}
          {isWarning && (
            <div>
              <Label className="mb-1.5 block text-[10px] uppercase tracking-[0.2em] text-muted-foreground">Work Order Type (always dispatched)</Label>
              <Segmented options={WO_TYPES} value={woType} onChange={setWoType} testPrefix="bd-wo-type" accent="yellow" />
            </div>
          )}

          {/* Remarks */}
          <div>
            <Label className="mb-1.5 block text-[10px] uppercase tracking-[0.2em] text-muted-foreground">Remarks *</Label>
            <Textarea
              data-testid="bd-remarks-input"
              value={remarks}
              onChange={(e) => setRemarks(e.target.value)}
              placeholder="What's happening on the floor?"
              rows={3}
              className={`bg-[hsl(var(--panel-2))] ${errors.remarks ? 'input-error' : ''}`}
            />
          </div>

          {/* Mandatory technician assignment — a WO is ALWAYS created for the selected technician */}
          <div>
            <Label className="mb-1.5 block text-[10px] uppercase tracking-[0.2em] text-muted-foreground">Assign Technician *</Label>
            <Select value={technician} onValueChange={setTechnician}>
              <SelectTrigger data-testid="bd-technician-select" className={`bg-[hsl(var(--panel-2))] ${errors.technician ? 'input-error' : ''}`}>
                <SelectValue placeholder="Select technician to attend" />
              </SelectTrigger>
              <SelectContent>
                {technicians.length === 0 && <div className="px-3 py-2 text-xs text-muted-foreground">No active technicians available</div>}
                {technicians.map((t) => (
                  <SelectItem key={t.username} value={t.username}>{t.name} ({t.username})</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="mt-1.5 text-[11px] text-muted-foreground" data-testid="bd-auto-wo-note">
              A work order is always created and assigned to the selected technician on submission.
            </p>
          </div>

          <Button
            onClick={submit}
            disabled={submitting}
            data-testid="bd-submit-button"
            className={isWarning
              ? 'w-full border border-[#f9f871]/60 bg-transparent font-semibold text-[#f9f871] hover:bg-[#f9f871]/10 hover:shadow-[0_0_14px_rgba(249,248,113,0.3)]'
              : 'cyber-primary w-full'}
          >
            {submitting ? 'Transmitting…' : isWarning ? 'Raise Warning' : 'Report Breakdown'}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
