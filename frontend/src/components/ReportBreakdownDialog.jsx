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
import { DateTimeField, toLocalInput, toIsoUtc } from '@/components/Shared';

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

// Fuzzy typeahead picker: every typed token must match somewhere in the option haystack.
function FuzzyPicker({ value, display, options, onSelect, placeholder, testId, error, renderOption }) {
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);

  const filtered = useMemo(() => {
    if (!query.trim()) return options.slice(0, 60);
    const tokens = query.toLowerCase().split(/\s+/).filter(Boolean);
    return options.filter((o) => tokens.every((t) => o.haystack.includes(t))).slice(0, 60);
  }, [options, query]);

  return (
    <div className="relative">
      <Input
        data-testid={testId}
        value={open ? query : (value ? display : query)}
        placeholder={placeholder}
        onFocus={() => { setOpen(true); setQuery(''); }}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        onChange={(e) => { setQuery(e.target.value); setOpen(true); }}
        className={`bg-[hsl(var(--panel-2))] ${error ? 'input-error' : ''}`}
        autoComplete="off"
      />
      {open && (
        <div className="absolute z-50 mt-1 max-h-60 w-full overflow-y-auto border border-border bg-[hsl(var(--panel-1))] shadow-xl">
          {filtered.length === 0 && <div className="px-3 py-2 text-xs text-muted-foreground">No matches</div>}
          {filtered.map((o) => (
            <button
              key={o.key}
              type="button"
              data-testid={`${testId}-option-${o.key}`}
              className="block w-full px-3 py-2 text-left text-sm hover:bg-white/5"
              onMouseDown={(e) => { e.preventDefault(); onSelect(o); setOpen(false); setQuery(''); }}
            >
              {renderOption(o)}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * Shared report dialog — Line-first hierarchy (Line → Department → Process Group → Machine).
 * mode="breakdown" — machine down, counts as downtime, creates a Breakdown (red)
 * mode="warning"   — observation only: NO downtime, machine goes yellow 'watch',
 *                    and an Inspection/Corrective WO is always dispatched.
 * Technician assignment is OPTIONAL — omitted = WO starts UNASSIGNED (claimable by any tech).
 */
export function ReportBreakdownDialog({ open, setOpen, prefillMachine = null, onCreated, publicMode = false, mode = 'breakdown' }) {
  const { user } = useApp();
  const isWarning = mode === 'warning';
  const [lines, setLines] = useState([]);
  const [machines, setMachines] = useState([]);
  const [technicians, setTechnicians] = useState([]);
  const [area, setArea] = useState('');
  const [machineId, setMachineId] = useState('');
  const [reporterName, setReporterName] = useState('');
  const [breakdownType, setBreakdownType] = useState('MECHANICAL');
  const [woType, setWoType] = useState('Inspection');
  const [remarks, setRemarks] = useState('');
  const [technician, setTechnician] = useState('');
  const [startTime, setStartTime] = useState('');
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
    setStartTime(toLocalInput(new Date().toISOString()));
    setErrors({});
    if (prefillMachine) {
      setArea(prefillMachine.line || '');
      setMachineId(prefillMachine.id || '');
    } else {
      setArea('');
      setMachineId('');
    }
  }, [open, prefillMachine, user, publicMode]);

  const selectedMachine = machines.find((m) => m.id === machineId);

  // Fuzzy option sets
  const areaOptions = useMemo(
    () => lines.map((l) => ({ key: l.name, name: l.name, haystack: l.name.toLowerCase() })),
    [lines],
  );
  const machineOptions = useMemo(
    () => machines
      .filter((m) => !area || m.line === area)
      .map((m) => ({
        key: m.code,
        id: m.id,
        machine: m,
        haystack: `${m.code} ${m.name} ${m.line || ''} ${m.department || ''} ${m.process_group || ''}`.toLowerCase(),
      })),
    [machines, area],
  );

  const ctx = {
    line: selectedMachine?.line || area || '—',
    dept: selectedMachine?.department || '—',
    equipment: selectedMachine ? selectedMachine.name : '—',
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
      let res;
      const assignedMsg = technician ? `assigned to ${technician}` : 'UNASSIGNED — any technician can claim it';
      if (isWarning) {
        res = await api.post(publicMode ? '/public/warnings' : '/warnings', {
          machine_id: machineId,
          description: remarks,
          warning_type: breakdownType,
          reporter_name: reporterName,
          wo_type: woType,
          assigned_to: technician || undefined,
        });
        toast.warning(`Warning ${res.data.tag_number} raised — ${res.data.work_order_number} ${assignedMsg} (no downtime recorded)`);
      } else {
        res = await api.post(publicMode ? '/public/breakdowns' : '/breakdowns', {
          machine_id: machineId,
          description: remarks,
          breakdown_type: breakdownType,
          reporter_name: reporterName,
          assigned_to: technician || undefined,
          start_time: startTime ? toIsoUtc(startTime) : undefined,
        });
        toast.success(`Breakdown ${res.data.ticket_number} created — ${res.data.work_order_number} ${assignedMsg}`);
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
        onOpenAutoFocus={(e) => e.preventDefault()}
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
          {/* Context strip — read-only (Line-first) */}
          <div className={`cyber-chamfer-sm grid grid-cols-3 gap-3 border px-4 py-3 ${isWarning ? 'border-[#f9f871]/20 bg-[#f9f871]/[0.04]' : 'border-[#05ffa1]/20 bg-[#05ffa1]/[0.05]'}`} data-testid="breakdown-context-strip">
            {[['LINE', ctx.line], ['DEPT', ctx.dept], ['EQUIPMENT', ctx.equipment]].map(([k, v]) => (
              <div key={k} className="min-w-0">
                <div className="text-[9px] font-semibold uppercase tracking-[0.2em] text-muted-foreground">{k}</div>
                <div className="truncate text-sm font-medium text-foreground" title={v}>{v}</div>
              </div>
            ))}
          </div>

          {/* Editable hierarchy group — fuzzy typeahead search */}
          <div className="space-y-3 border border-dashed border-border p-4">
            <div>
              <Label className="mb-1.5 block text-[10px] uppercase tracking-[0.2em] text-muted-foreground">Area / Line — type to search</Label>
              <FuzzyPicker
                testId="bd-area-search"
                value={area}
                display={area}
                options={areaOptions}
                placeholder="Search line (e.g. PC21, KKR)..."
                onSelect={(o) => { setArea(o.name); setMachineId(''); }}
                renderOption={(o) => <span className="font-medium">{o.name}</span>}
              />
            </div>
            <div>
              <Label className="mb-1.5 block text-[10px] uppercase tracking-[0.2em] text-muted-foreground">Machine — type to search *</Label>
              <FuzzyPicker
                testId="bd-machine-search"
                value={machineId}
                display={selectedMachine ? `${selectedMachine.name} (${selectedMachine.code})` : ''}
                options={machineOptions}
                placeholder={area ? `Search machines on ${area}...` : 'Search machine by name / code / group...'}
                error={errors.machine}
                onSelect={(o) => { setMachineId(o.id); setArea(o.machine.line || ''); }}
                renderOption={(o) => (
                  <>
                    <span className="font-mono text-xs text-[hsl(var(--primary))]">{o.machine.code}</span>
                    <span className="ml-2 font-medium">{o.machine.name}</span>
                    <span className="ml-2 text-xs text-muted-foreground">{o.machine.line} · {o.machine.department} / {o.machine.process_group}</span>
                  </>
                )}
              />
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

          {/* Actual breakdown start — calendar picker, editable so downtime reflects reality */}
          {!isWarning && (
            <DateTimeField label="Breakdown Start Time" value={startTime} onChange={setStartTime} testId="bd-start-time" />
          )}

          {/* OPTIONAL technician assignment — omitted = UNASSIGNED WO claimable by any technician */}
          <div>
            <Label className="mb-1.5 block text-[10px] uppercase tracking-[0.2em] text-muted-foreground">Assign Technician (optional)</Label>
            <Select value={technician || 'none'} onValueChange={(v) => setTechnician(v === 'none' ? '' : v)}>
              <SelectTrigger data-testid="bd-technician-select" className="bg-[hsl(var(--panel-2))]">
                <SelectValue placeholder="Unassigned — any technician can claim" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">Unassigned — any technician can claim</SelectItem>
                {technicians.map((t) => (
                  <SelectItem key={t.username} value={t.username}>{t.name} ({t.username})</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="mt-1.5 text-[11px] text-muted-foreground" data-testid="bd-auto-wo-note">
              A work order is always created. Leave unassigned to place it in the UNASSIGNED column where any technician can claim it.
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
