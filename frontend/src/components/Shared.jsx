import React, { useEffect, useMemo, useState } from 'react';
import { api } from '@/lib/api';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { X, Plus, ArrowRightLeft } from 'lucide-react';

// ISO <-> datetime-local helpers (local timezone aware)
export const toLocalInput = (iso) => {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
};
export const toIsoUtc = (local) => (local ? new Date(local).toISOString() : '');

// Datetime input that ALWAYS opens the native calendar picker on click (no manual typing needed)
export function DateTimeField({ label, value, onChange, testId, disabled, required }) {
  return (
    <div>
      {label && <Label className="text-xs">{label}{required ? ' *' : ''}</Label>}
      <Input
        type="datetime-local"
        data-testid={testId}
        value={value}
        disabled={disabled}
        onClick={(e) => { try { e.currentTarget.showPicker && e.currentTarget.showPicker(); } catch {} }}
        onChange={(e) => onChange(e.target.value)}
        className="mt-0.5 cursor-pointer bg-[hsl(var(--panel-2))] font-mono text-xs"
      />
    </div>
  );
}

// Searchable machine picker
export function MachineSelect({ value, onChange, testId = 'machine-select' }) {
  const [machines, setMachines] = useState([]);
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);

  useEffect(() => {
    api.get('/machines?limit=5000').then((r) => setMachines(r.data)).catch(() => {});
  }, []);

  const selected = machines.find((m) => m.id === value);
  const filtered = useMemo(() => {
    if (!query) return machines.slice(0, 50);
    const q = query.toLowerCase();
    return machines.filter((m) => m.name.toLowerCase().includes(q) || m.code.toLowerCase().includes(q) || (m.line || '').toLowerCase().includes(q)).slice(0, 50);
  }, [machines, query]);

  return (
    <div className="relative">
      <Input
        data-testid={testId}
        value={open ? query : selected ? `${selected.name} (${selected.code})` : query}
        placeholder="Search machine by name / code / line..."
        onFocus={() => setOpen(true)}
        onChange={(e) => { setQuery(e.target.value); setOpen(true); }}
        className="bg-[hsl(var(--panel-2))]"
      />
      {open && (
        <div className="absolute z-50 mt-1 max-h-64 w-full overflow-y-auto rounded-md border border-border bg-[hsl(var(--panel-1))] shadow-xl">
          {filtered.length === 0 && <div className="px-3 py-2 text-sm text-muted-foreground">No machines found</div>}
          {filtered.map((m) => (
            <button
              key={m.id}
              type="button"
              data-testid={`machine-option-${m.code}`}
              className="block w-full px-3 py-2 text-left text-sm hover:bg-white/5"
              onClick={() => { onChange(m.id, m); setOpen(false); setQuery(''); }}
            >
              <span className="font-medium">{m.name}</span>
              <span className="ml-2 font-mono text-xs text-muted-foreground">{m.code}</span>
              <span className="ml-2 text-xs text-muted-foreground">{m.line} / {m.process_group}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// Dynamic spare consumption rows (SAP code + qty)
// Fuzzy typeahead search: type partial SAP code, material name or description —
// results filter live (all typed tokens must match somewhere in the record).
function SpareSearch({ value, onChange, spares, testId }) {
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const selected = spares.find((s) => s.sap_code === value);

  const filtered = useMemo(() => {
    if (!query.trim()) return spares.slice(0, 50);
    const tokens = query.toLowerCase().split(/\s+/).filter(Boolean);
    return spares.filter((s) => {
      const hay = `${s.sap_code} ${s.material_name || ''} ${s.description || ''}`.toLowerCase();
      return tokens.every((t) => hay.includes(t));
    }).slice(0, 50);
  }, [spares, query]);

  return (
    <div className="relative flex-1">
      <Input
        data-testid={testId}
        value={open ? query : selected ? `${selected.sap_code} — ${selected.material_name}` : query}
        placeholder="Search SAP code / material / description..."
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        onChange={(e) => { setQuery(e.target.value); setOpen(true); }}
        className="bg-[hsl(var(--panel-2))]"
      />
      {open && (
        <div className="absolute z-50 mt-1 max-h-64 w-full min-w-[320px] overflow-y-auto rounded-md border border-border bg-[hsl(var(--panel-1))] shadow-xl">
          {filtered.length === 0 && <div className="px-3 py-2 text-sm text-muted-foreground">No matching material</div>}
          {filtered.map((s) => (
            <button
              key={s.sap_code}
              type="button"
              data-testid={`spare-option-${s.sap_code}`}
              className="block w-full px-3 py-2 text-left text-sm hover:bg-white/5"
              onMouseDown={(e) => { e.preventDefault(); onChange(s.sap_code); setOpen(false); setQuery(''); }}
            >
              <span className="font-mono text-xs text-[hsl(var(--primary))]">{s.sap_code}</span>
              <span className="ml-2 font-medium">{s.material_name}</span>
              <span className="ml-2 text-xs text-muted-foreground">stock: {s.quantity}</span>
              {s.description && <div className="truncate text-[11px] text-muted-foreground">{s.description}</div>}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export function SpareRows({ rows, setRows }) {
  const [spares, setSpares] = useState([]);
  useEffect(() => {
    api.get('/spares?limit=1000').then((r) => setSpares(r.data.items)).catch(() => {});
  }, []);

  const update = (i, field, val) => {
    const next = [...rows];
    next[i] = { ...next[i], [field]: val };
    setRows(next);
  };

  return (
    <div className="space-y-2">
      <Label className="text-xs text-muted-foreground">Used Spares (SAP material + quantity)</Label>
      {rows.map((row, i) => (
        <div key={i} className="flex items-center gap-2">
          <SpareSearch value={row.sap_code} onChange={(v) => update(i, 'sap_code', v)} spares={spares} testId={`spare-row-select-${i}`} />
          <Input
            type="number" min="0.1" step="any"
            value={row.quantity}
            data-testid={`spare-row-qty-${i}`}
            onChange={(e) => update(i, 'quantity', e.target.value)}
            className="w-24 bg-[hsl(var(--panel-2))]"
            placeholder="Qty"
          />
          <Button type="button" variant="ghost" size="icon" onClick={() => setRows(rows.filter((_, j) => j !== i))}>
            <X className="h-4 w-4" />
          </Button>
        </div>
      ))}
      <Button type="button" variant="outline" size="sm" data-testid="spare-row-add" onClick={() => setRows([...rows, { sap_code: '', quantity: 1 }])} className="border-border bg-[hsl(var(--panel-2))]">
        <Plus className="mr-1 h-3 w-3" /> Add spare
      </Button>
    </div>
  );
}

export function TechnicianSelect({ value, onChange, testId = 'technician-select', allowNone = false, exclude, placeholder }) {
  const [techs, setTechs] = useState([]);
  useEffect(() => {
    api.get('/users/technicians').then((r) => setTechs((r.data || []).filter((t) => t.role === 'technician'))).catch(() => {});
  }, []);
  return (
    <Select value={value || (allowNone ? 'none' : '')} onValueChange={(v) => onChange(allowNone && v === 'none' ? '' : v)}>
      <SelectTrigger className="bg-[hsl(var(--panel-2))]" data-testid={testId}>
        <SelectValue placeholder={placeholder || (allowNone ? 'Unassigned — any technician can claim' : 'Select technician')} />
      </SelectTrigger>
      <SelectContent>
        {allowNone && <SelectItem value="none">Unassigned — any technician can claim</SelectItem>}
        {techs.filter((t) => t.username !== exclude).map((t) => (
          <SelectItem key={t.id} value={t.username}>{t.name} ({t.username})</SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

// Transfer an assigned task to another technician — shared by the WO modal,
// PM table and breakdown views. Governance is enforced server-side (current
// holder or admin only); RCA tasks reject transfers entirely.
// MID-REPAIR HANDOFF: pass requireNote for IN_PROGRESS tasks — a Pass-On Note
// becomes mandatory and is forwarded as the 2nd argument of onTransfer.
export function TransferControl({ current, onTransfer, testId = 'transfer-control', label = 'Transfer To', requireNote = false }) {
  const [tech, setTech] = useState('');
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const noteMissing = requireNote && !note.trim();
  const go = async () => {
    if (!tech || noteMissing) return;
    setBusy(true);
    try { await onTransfer(tech, note.trim() || undefined); setTech(''); setNote(''); } finally { setBusy(false); }
  };
  return (
    <div className="w-full space-y-2" data-testid={testId} onClick={(e) => e.stopPropagation()}>
      <div className="flex w-full flex-wrap items-center gap-2">
        <div className="min-w-[200px] flex-1">
          <TechnicianSelect value={tech} onChange={setTech} exclude={current} testId={`${testId}-select`} placeholder={`${label}…`} />
        </div>
        <Button size="sm" disabled={!tech || busy || noteMissing} data-testid={`${testId}-btn`}
          className="h-9 border border-[hsl(var(--primary))]/60 bg-transparent text-xs text-[hsl(var(--primary))] hover:bg-[hsl(var(--primary))]/10 disabled:opacity-40"
          onClick={go}
          title={noteMissing ? 'A Pass-On Note is required to hand off an in-progress task' : undefined}>
          <ArrowRightLeft className="mr-1 h-3 w-3" /> {busy ? 'Transferring…' : requireNote ? 'Hand Off' : 'Transfer'}
        </Button>
      </div>
      {requireNote && (
        <div>
          <Label className="text-[10px] uppercase tracking-widest text-[#ff9e1c]">Pass-On Note <span className="text-[#ff2e63]">*</span></Label>
          <Textarea data-testid={`${testId}-note`} value={note} onChange={(e) => setNote(e.target.value)} rows={2}
            placeholder="Required — what has been done so far, current state of the repair, and anything the incoming technician needs to know"
            className="mt-0.5 bg-[hsl(var(--panel-2))] text-xs" />
        </div>
      )}
    </div>
  );
}

// Animated numeric display: count-up on value change (cyberpunk data readout)
export function AnimatedNumber({ value }) {
  const str = value == null ? '—' : String(value);
  const match = str.match(/^(-?\d+(?:\.\d+)?)(.*)$/);
  const target = match ? parseFloat(match[1]) : null;
  const suffix = match ? match[2] : '';
  const decimals = match && match[1].includes('.') ? match[1].split('.')[1].length : 0;
  const [display, setDisplay] = useState(target);
  const prevRef = React.useRef(target);

  useEffect(() => {
    if (target == null) return undefined;
    const from = prevRef.current == null || Number.isNaN(prevRef.current) ? 0 : prevRef.current;
    prevRef.current = target;
    if (from === target) { setDisplay(target); return undefined; }
    const start = performance.now();
    const dur = 450;
    let raf;
    const step = (t) => {
      const p = Math.min((t - start) / dur, 1);
      const eased = 1 - (1 - p) ** 3;
      setDisplay(from + (target - from) * eased);
      if (p < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [target]);

  if (target == null) return <>{str}</>;
  return <>{Number(display ?? target).toFixed(decimals)}{suffix}</>;
}

export function KpiCard({ label, value, sub, accent, testId }) {
  return (
    <div data-testid={testId} className="cyber-panel group px-4 py-3">
      <div className="text-[10px] font-semibold uppercase tracking-[0.2em] text-muted-foreground transition-colors group-hover:text-foreground/80">{label}</div>
      <div className={`mt-1 font-mono text-2xl tabular-nums transition-all duration-200 group-hover:[text-shadow:0_0_14px_rgba(var(--accent-rgb),0.35)] ${accent || ''}`}>
        <AnimatedNumber value={value} />
      </div>
      {sub && <div className="mt-0.5 text-xs text-muted-foreground">{sub}</div>}
    </div>
  );
}
