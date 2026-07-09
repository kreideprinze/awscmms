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

function Segmented({ options, value, onChange, testPrefix }) {
  return (
    <div className="grid grid-cols-3 gap-2">
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
              selected
                ? 'power-on border-[hsl(var(--primary))] bg-transparent text-[hsl(var(--primary))] shadow-[0_0_8px_rgba(var(--accent-rgb),0.25)] shadow-[0_0_10px_rgba(var(--accent-rgb),0.25)]'
                : 'border-border text-muted-foreground hover:border-muted-foreground hover:text-foreground'
            }`}
          >
            {label}
          </button>
        );
      })}
    </div>
  );
}

export function ReportBreakdownDialog({ open, setOpen, prefillMachine = null, onCreated }) {
  const { user } = useApp();
  const [lines, setLines] = useState([]);
  const [machines, setMachines] = useState([]);
  const [dept, setDept] = useState('PROCESS');
  const [area, setArea] = useState('');
  const [machineId, setMachineId] = useState('');
  const [reporterName, setReporterName] = useState('');
  const [breakdownType, setBreakdownType] = useState('MECHANICAL');
  const [remarks, setRemarks] = useState('');
  const [autoWo, setAutoWo] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [errors, setErrors] = useState({});

  useEffect(() => {
    if (!open) return;
    api.get('/hierarchy').then((r) => setLines(r.data.lines));
    api.get('/machines?limit=10000').then((r) => setMachines(r.data));
    setReporterName(user?.name || '');
    setBreakdownType('MECHANICAL');
    setRemarks('');
    setAutoWo(true);
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
  }, [open, prefillMachine, user]);

  const areaOptions = useMemo(() => lines.filter((l) => l.department === dept).map((l) => l.name), [lines, dept]);
  const machineOptions = useMemo(() => machines.filter((m) => m.line === area), [machines, area]);
  const selectedMachine = machines.find((m) => m.id === machineId);

  const ctx = {
    dept: selectedMachine?.department || dept || '\u2014',
    area: selectedMachine?.line || area || '\u2014',
    equipment: selectedMachine ? selectedMachine.name : '\u2014',
  };

  const submit = async () => {
    const errs = {};
    if (!machineId) errs.machine = true;
    if (!reporterName.trim()) errs.reporter = true;
    if (!remarks.trim()) errs.remarks = true;
    setErrors(errs);
    if (Object.keys(errs).length) {
      toast.error('Machine, reporter name and remarks are required');
      return;
    }
    setSubmitting(true);
    try {
      const res = await api.post('/breakdowns', {
        machine_id: machineId,
        description: remarks,
        breakdown_type: breakdownType,
        reporter_name: reporterName,
        auto_create_work_order: autoWo,
      });
      toast.success(`Breakdown ${res.data.ticket_number} created${res.data.work_order_number ? ` \u2014 ${res.data.work_order_number} dispatched to maintenance` : ''}`);
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
      <DialogContent className="max-h-[90vh] gap-0 overflow-y-auto border-border bg-[#0a0a0f] p-0 sm:max-w-lg" data-testid="report-breakdown-dialog">
        {/* Header bar */}
        <div className="flex items-center justify-between border-b border-border bg-[#08080c] px-5 py-4">
          <DialogTitle className="text-base font-semibold uppercase tracking-[0.3em] text-foreground">Report Breakdown</DialogTitle>
        </div>

        <div className="space-y-4 p-5">
          {/* Context strip \u2014 read-only, green-tinted */}
          <div className="cyber-chamfer-sm grid grid-cols-3 gap-3 border border-[#05ffa1]/20 bg-[#05ffa1]/[0.05] px-4 py-3" data-testid="breakdown-context-strip">
            {[['DEPT', ctx.dept], ['AREA', ctx.area], ['EQUIPMENT', ctx.equipment]].map(([k, v]) => (
              <div key={k} className="min-w-0">
                <div className="text-[9px] font-semibold uppercase tracking-[0.2em] text-muted-foreground">{k}</div>
                <div className="truncate text-sm font-medium text-foreground" title={v}>{v}</div>
              </div>
            ))}
          </div>

          {/* Editable hierarchy group \u2014 dotted border card */}
          <div className="space-y-3 border border-dashed border-border p-4">
            <div>
              <Label className="mb-1.5 block text-[10px] uppercase tracking-[0.2em] text-muted-foreground">Department</Label>
              <Segmented options={DEPARTMENTS} value={dept} onChange={(v) => { setDept(v); setArea(''); setMachineId(''); }} testPrefix="bd-dept" />
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
                      <span className="font-mono text-xs">{m.code}</span> \u00b7 {m.name}
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

          {/* Breakdown type */}
          <div>
            <Label className="mb-1.5 block text-[10px] uppercase tracking-[0.2em] text-muted-foreground">Breakdown Type</Label>
            <Segmented options={BREAKDOWN_TYPES} value={breakdownType} onChange={setBreakdownType} testPrefix="bd-type" />
          </div>

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

          {/* Auto-create WO */}
          <label className="flex cursor-pointer items-start gap-2.5" data-testid="bd-auto-wo-toggle">
            <input
              type="checkbox"
              checked={autoWo}
              onChange={(e) => setAutoWo(e.target.checked)}
              className="mt-0.5 h-4 w-4 accent-[#00fff5]"
              data-testid="bd-auto-wo-checkbox"
            />
            <span>
              <span className="block text-xs font-semibold uppercase tracking-widest">Auto-create Work Order</span>
              <span className="block text-[11px] text-muted-foreground">dispatches to maintenance immediately</span>
            </span>
          </label>

          <Button onClick={submit} disabled={submitting} data-testid="bd-submit-button" className="cyber-primary w-full">
            {submitting ? 'Transmitting\u2026' : 'Report Breakdown'}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
