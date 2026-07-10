import React, { useEffect, useMemo, useState } from 'react';
import { api } from '@/lib/api';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { X, Plus } from 'lucide-react';

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
          <Select value={row.sap_code} onValueChange={(v) => update(i, 'sap_code', v)}>
            <SelectTrigger className="flex-1 bg-[hsl(var(--panel-2))]" data-testid={`spare-row-select-${i}`}>
              <SelectValue placeholder="Select SAP material" />
            </SelectTrigger>
            <SelectContent>
              {spares.map((s) => (
                <SelectItem key={s.sap_code} value={s.sap_code}>
                  <span className="font-mono text-xs">{s.sap_code}</span> — {s.material_name} (stock: {s.quantity})
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
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

export function TechnicianSelect({ value, onChange, testId = 'technician-select' }) {
  const [techs, setTechs] = useState([]);
  useEffect(() => {
    api.get('/users/technicians').then((r) => setTechs(r.data)).catch(() => {});
  }, []);
  return (
    <Select value={value || ''} onValueChange={onChange}>
      <SelectTrigger className="bg-[hsl(var(--panel-2))]" data-testid={testId}>
        <SelectValue placeholder="Select technician" />
      </SelectTrigger>
      <SelectContent>
        {techs.map((t) => (
          <SelectItem key={t.id} value={t.username}>{t.name} ({t.username})</SelectItem>
        ))}
      </SelectContent>
    </Select>
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
