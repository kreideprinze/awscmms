import React, { useEffect, useState, useCallback } from 'react';
import { toast } from 'sonner';
import { Plus, Upload, Search, Package } from 'lucide-react';
import { api, errMsg } from '@/lib/api';
import { useApp } from '@/context/AppContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { fmtDate } from '@/components/StatusBits';
import { KpiCard } from '@/components/Shared';

const TX_COLORS = {
  CSV_IMPORT: 'text-[#00fff5]', MANUAL_ADJUSTMENT: 'text-slate-300', BREAKDOWN_CONSUMPTION: 'text-[#ff2e63]',
  WORKORDER_CONSUMPTION: 'text-[#ff9e1c]', PM_CONSUMPTION: 'text-[#f9f871]', STOCK_ADDITION: 'text-[#05ffa1]', STOCK_REDUCTION: 'text-[#ff2e63]',
};

export default function Inventory() {
  const { isAdmin } = useApp();
  const [dash, setDash] = useState(null);
  const [spares, setSpares] = useState({ items: [], total: 0 });
  const [txs, setTxs] = useState({ items: [], total: 0 });
  const [search, setSearch] = useState('');
  const [stockFilter, setStockFilter] = useState('all');
  const [locations, setLocations] = useState([]);
  const [adjustSpare, setAdjustSpare] = useState(null);
  const [adjustQty, setAdjustQty] = useState('');
  const [adjustNotes, setAdjustNotes] = useState('');
  const [addOpen, setAddOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [csvText, setCsvText] = useState('');
  const [csvMode, setCsvMode] = useState('add');
  const [preview, setPreview] = useState(null);
  const [newSpare, setNewSpare] = useState({ sap_code: '', material_name: '', long_text: '', location: '', quantity: 0, uom: 'EA', category: '' });

  const load = useCallback(() => {
    api.get('/spares/dashboard').then((r) => setDash(r.data));
    const params = new URLSearchParams();
    if (search) params.set('search', search);
    if (stockFilter !== 'all') params.set('stock', stockFilter);
    api.get(`/spares?${params}`).then((r) => setSpares(r.data));
    api.get('/spare-transactions?limit=100').then((r) => setTxs(r.data));
    api.get('/spare-locations').then((r) => setLocations(r.data));
  }, [search, stockFilter]);
  useEffect(() => { load(); }, [load]);

  const doAdjust = async () => {
    try {
      await api.post(`/spares/${adjustSpare.sap_code}/adjust`, { quantity_change: parseFloat(adjustQty), notes: adjustNotes || undefined });
      toast.success('Stock adjusted — transaction recorded');
      setAdjustSpare(null); setAdjustQty(''); setAdjustNotes('');
      load();
    } catch (e) { toast.error(errMsg(e)); }
  };

  const doAdd = async () => {
    if (!newSpare.sap_code || !newSpare.material_name) { toast.error('SAP code and material name required'); return; }
    try {
      await api.post('/spares', { ...newSpare, quantity: parseFloat(newSpare.quantity) || 0 });
      toast.success('Spare material created');
      setAddOpen(false);
      load();
    } catch (e) { toast.error(errMsg(e)); }
  };

  const doPreview = async () => {
    try {
      const res = await api.post('/spares/import', { csv_text: csvText, mode: csvMode, apply: false });
      setPreview(res.data);
    } catch (e) { toast.error(errMsg(e)); }
  };

  const doApply = async () => {
    try {
      const res = await api.post('/spares/import', { csv_text: csvText, mode: csvMode, apply: true });
      toast.success(`Imported ${res.data.imported} rows`);
      setImportOpen(false); setPreview(null); setCsvText('');
      load();
    } catch (e) { toast.error(errMsg(e)); }
  };

  return (
    <div className="p-6" data-testid="inventory-page">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight"><Package className="h-6 w-6 text-[hsl(var(--primary))]" /> Spares Inventory</h1>
          <p className="text-sm text-muted-foreground">SAP-centric — every movement is a ledger transaction; inventory is never edited directly</p>
        </div>
        {isAdmin && (
          <div className="flex gap-2">
            <Button variant="outline" data-testid="inventory-import-button" onClick={() => setImportOpen(true)} className="border-border bg-[hsl(var(--panel-2))]"><Upload className="mr-1 h-4 w-4" /> CSV Import</Button>
            <Button data-testid="inventory-add-button" onClick={() => setAddOpen(true)} className="bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))]"><Plus className="mr-1 h-4 w-4" /> New Material</Button>
          </div>
        )}
      </div>

      {dash && (
        <div className="mb-5 grid grid-cols-2 gap-2 sm:grid-cols-4">
          <KpiCard testId="inventory-kpi-materials" label="SAP Materials" value={dash.total_materials} />
          <KpiCard testId="inventory-kpi-quantity" label="Total Quantity" value={dash.total_quantity} />
          <KpiCard testId="inventory-kpi-in-stock" label="In Stock" value={dash.in_stock} accent="text-[#05ffa1]" />
          <KpiCard testId="inventory-kpi-out-stock" label="Out of Stock" value={dash.out_of_stock} accent={dash.out_of_stock ? 'text-[#ff2e63]' : ''} />
        </div>
      )}

      <Tabs defaultValue="stock">
        <TabsList className="bg-[hsl(var(--panel-2))]">
          <TabsTrigger value="stock" data-testid="inventory-tab-stock">Stock</TabsTrigger>
          <TabsTrigger value="transactions" data-testid="inventory-tab-transactions">Transactions</TabsTrigger>
          <TabsTrigger value="analytics" data-testid="inventory-tab-analytics">Most Used</TabsTrigger>
        </TabsList>

        <TabsContent value="stock" className="mt-4">
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <div className="relative">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input data-testid="inventory-search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="SAP code / name / description / location" className="w-80 bg-[hsl(var(--panel-2))] pl-8" />
            </div>
            {['all', 'in', 'out'].map((s) => (
              <button key={s} onClick={() => setStockFilter(s)} data-testid={`inventory-stock-filter-${s}`}
                className={`cyber-chamfer-sm border px-3 py-1 font-mono text-[11px] uppercase tracking-wide transition-colors ${stockFilter === s ? 'power-on border-[hsl(var(--primary))] bg-transparent text-[hsl(var(--primary))] shadow-[0_0_8px_rgba(var(--accent-rgb),0.25)]' : 'border-border text-muted-foreground'}`}>
                {s === 'all' ? 'All' : s === 'in' ? 'In Stock' : 'Out of Stock'}
              </button>
            ))}
            <span className="text-xs text-muted-foreground">{spares.total} materials</span>
          </div>
          <div className="overflow-hidden border border-border">
            <Table data-testid="inventory-table">
              <TableHeader>
                <TableRow className="border-border bg-[hsl(var(--panel-1))] hover:bg-[hsl(var(--panel-1))]">
                  <TableHead className="text-xs uppercase">SAP Code</TableHead>
                  <TableHead className="text-xs uppercase">Material</TableHead>
                  <TableHead className="text-xs uppercase">Location</TableHead>
                  <TableHead className="text-xs uppercase">Qty</TableHead>
                  <TableHead className="text-xs uppercase">UoM</TableHead>
                  <TableHead className="text-xs uppercase">Status</TableHead>
                  <TableHead className="text-xs uppercase">Consumed</TableHead>
                  {isAdmin && <TableHead className="text-xs uppercase">Actions</TableHead>}
                </TableRow>
              </TableHeader>
              <TableBody>
                {spares.items.map((s) => (
                  <TableRow key={s.sap_code} data-testid={`inventory-row-${s.sap_code}`} className="border-border hover:bg-white/[0.03]">
                    <TableCell className="font-mono text-xs text-[hsl(var(--primary))]">{s.sap_code}</TableCell>
                    <TableCell>
                      <div className="text-sm font-medium">{s.material_name}</div>
                      <div className="max-w-72 truncate text-[10px] text-muted-foreground">{s.long_text}</div>
                    </TableCell>
                    <TableCell className="text-sm">{s.location || '—'}</TableCell>
                    <TableCell className="tabular-nums text-sm font-semibold">{s.quantity}</TableCell>
                    <TableCell className="text-xs">{s.uom}</TableCell>
                    <TableCell>
                      <Badge variant="outline" className={s.quantity > 0 ? 'border-[#05ffa1]/40 bg-[#05ffa1]/15 text-[10px] text-[#05ffa1]' : 'border-[#ff2e63]/40 bg-[#ff2e63]/15 text-[10px] text-[#ff2e63]'}>
                        {s.quantity > 0 ? 'IN STOCK' : 'OUT OF STOCK'}
                      </Badge>
                    </TableCell>
                    <TableCell className="tabular-nums text-sm text-muted-foreground">{s.total_consumed || 0}</TableCell>
                    {isAdmin && (
                      <TableCell>
                        <Button size="sm" variant="outline" className="h-6 border-border bg-[hsl(var(--panel-2))] text-[10px]" data-testid={`inventory-adjust-${s.sap_code}`} onClick={() => setAdjustSpare(s)}>Adjust</Button>
                      </TableCell>
                    )}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </TabsContent>

        <TabsContent value="transactions" className="mt-4">
          <div className="overflow-hidden border border-border">
            <Table data-testid="transactions-table">
              <TableHeader>
                <TableRow className="border-border bg-[hsl(var(--panel-1))] hover:bg-[hsl(var(--panel-1))]">
                  <TableHead className="text-xs uppercase">When</TableHead>
                  <TableHead className="text-xs uppercase">SAP Code</TableHead>
                  <TableHead className="text-xs uppercase">Type</TableHead>
                  <TableHead className="text-xs uppercase">Change</TableHead>
                  <TableHead className="text-xs uppercase">Old → New</TableHead>
                  <TableHead className="text-xs uppercase">Reference</TableHead>
                  <TableHead className="text-xs uppercase">By</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {txs.items.length === 0 && <TableRow><TableCell colSpan={7} className="py-10 text-center text-muted-foreground">No transactions yet</TableCell></TableRow>}
                {txs.items.map((t) => (
                  <TableRow key={t.id} className="border-border hover:bg-white/[0.03]">
                    <TableCell className="font-mono text-xs">{fmtDate(t.created_at)}</TableCell>
                    <TableCell className="font-mono text-xs text-[hsl(var(--primary))]">{t.sap_code}</TableCell>
                    <TableCell><span className={`text-xs ${TX_COLORS[t.transaction_type] || ''}`}>{t.transaction_type}</span></TableCell>
                    <TableCell className={`tabular-nums text-sm font-semibold ${t.quantity_change < 0 ? 'text-[#ff2e63]' : t.quantity_change > 0 ? 'text-[#05ffa1]' : 'text-muted-foreground'}`}>
                      {t.quantity_change > 0 ? '+' : ''}{t.quantity_change}
                    </TableCell>
                    <TableCell className="tabular-nums text-xs text-muted-foreground">{t.old_quantity ?? '—'} → {t.new_quantity ?? '—'}</TableCell>
                    <TableCell className="text-xs">{t.reference_label || '—'}{t.machine_name ? ` · ${t.machine_name}` : ''}</TableCell>
                    <TableCell className="text-xs">{t.performed_by}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </TabsContent>

        <TabsContent value="analytics" className="mt-4">
          {dash && (
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
              <div className="cyber-panel p-4">
                <div className="mb-3 text-xs font-semibold uppercase tracking-widest text-muted-foreground">Top 10 Consumed SAP Materials</div>
                {dash.most_used.length === 0 ? <div className="py-6 text-center text-sm text-muted-foreground">No consumption yet</div> :
                  dash.most_used.map((m) => (
                    <div key={m.sap_code} className="flex items-center justify-between border-b border-border/50 py-1.5 text-sm">
                      <span><span className="font-mono text-xs text-[hsl(var(--primary))]">{m.sap_code}</span> {m.material_name}</span>
                      <span className="tabular-nums text-xs text-muted-foreground">{m.total_consumed}</span>
                    </div>
                  ))}
              </div>
              <div className="cyber-panel p-4">
                <div className="mb-3 text-xs font-semibold uppercase tracking-widest text-muted-foreground">Recently Used</div>
                {dash.recently_used.length === 0 ? <div className="py-6 text-center text-sm text-muted-foreground">No usage yet</div> :
                  dash.recently_used.map((m) => (
                    <div key={m.sap_code} className="flex items-center justify-between border-b border-border/50 py-1.5 text-sm">
                      <span><span className="font-mono text-xs text-[hsl(var(--primary))]">{m.sap_code}</span> {m.material_name}</span>
                      <span className="font-mono text-[10px] text-muted-foreground">{fmtDate(m.last_used)}</span>
                    </div>
                  ))}
              </div>
              <div className="cyber-panel p-4">
                <div className="mb-3 text-xs font-semibold uppercase tracking-widest text-muted-foreground">Top Machines by Consumption</div>
                {dash.top_machines.length === 0 ? <div className="py-6 text-center text-sm text-muted-foreground">No consumption yet</div> :
                  dash.top_machines.map((m) => (
                    <div key={m.machine_name} className="flex items-center justify-between border-b border-border/50 py-1.5 text-sm">
                      <span>{m.machine_name}</span>
                      <span className="tabular-nums text-xs text-muted-foreground">{m.total_consumed}</span>
                    </div>
                  ))}
              </div>
            </div>
          )}
        </TabsContent>
      </Tabs>

      {/* Adjust dialog */}
      <Dialog open={!!adjustSpare} onOpenChange={(o) => !o && setAdjustSpare(null)}>
        <DialogContent className="border-border bg-[hsl(var(--panel-1))]">
          <DialogHeader><DialogTitle>Adjust Stock — {adjustSpare?.material_name}</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <p className="text-xs text-muted-foreground">Current quantity: <span className="font-semibold text-foreground">{adjustSpare?.quantity} {adjustSpare?.uom}</span>. Positive adds stock, negative subtracts.</p>
            <div><Label className="text-xs">Quantity Change (+/-)</Label><Input type="number" step="any" data-testid="adjust-qty-input" value={adjustQty} onChange={(e) => setAdjustQty(e.target.value)} className="bg-[hsl(var(--panel-2))]" /></div>
            <div><Label className="text-xs">Notes</Label><Input data-testid="adjust-notes-input" value={adjustNotes} onChange={(e) => setAdjustNotes(e.target.value)} className="bg-[hsl(var(--panel-2))]" /></div>
            <Button onClick={doAdjust} data-testid="adjust-confirm" className="w-full bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))]">Apply Adjustment</Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Add material dialog */}
      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent className="border-border bg-[hsl(var(--panel-1))]">
          <DialogHeader><DialogTitle>New SAP Material</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div><Label className="text-xs">SAP Code</Label><Input data-testid="spare-create-sap" value={newSpare.sap_code} onChange={(e) => setNewSpare({ ...newSpare, sap_code: e.target.value })} className="bg-[hsl(var(--panel-2))] font-mono" /></div>
              <div><Label className="text-xs">Material Name</Label><Input data-testid="spare-create-name" value={newSpare.material_name} onChange={(e) => setNewSpare({ ...newSpare, material_name: e.target.value })} className="bg-[hsl(var(--panel-2))]" /></div>
            </div>
            <div><Label className="text-xs">Long Text Description</Label><Input value={newSpare.long_text} onChange={(e) => setNewSpare({ ...newSpare, long_text: e.target.value })} className="bg-[hsl(var(--panel-2))]" /></div>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <Label className="text-xs">Location</Label>
                <Select value={newSpare.location} onValueChange={(v) => setNewSpare({ ...newSpare, location: v })}>
                  <SelectTrigger data-testid="spare-create-location" className="bg-[hsl(var(--panel-2))]"><SelectValue placeholder="Location" /></SelectTrigger>
                  <SelectContent>{locations.filter((l) => l.active).map((l) => <SelectItem key={l.id} value={l.name}>{l.name}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div><Label className="text-xs">Initial Qty</Label><Input type="number" min="0" data-testid="spare-create-qty" value={newSpare.quantity} onChange={(e) => setNewSpare({ ...newSpare, quantity: e.target.value })} className="bg-[hsl(var(--panel-2))]" /></div>
              <div><Label className="text-xs">UoM</Label><Input value={newSpare.uom} onChange={(e) => setNewSpare({ ...newSpare, uom: e.target.value })} className="bg-[hsl(var(--panel-2))]" /></div>
            </div>
            <div><Label className="text-xs">Category</Label><Input value={newSpare.category} onChange={(e) => setNewSpare({ ...newSpare, category: e.target.value })} className="bg-[hsl(var(--panel-2))]" /></div>
            <Button onClick={doAdd} data-testid="spare-create-submit" className="w-full bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))]">Create Material</Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* CSV import dialog */}
      <Dialog open={importOpen} onOpenChange={(o) => { setImportOpen(o); if (!o) setPreview(null); }}>
        <DialogContent className="max-h-[85vh] max-w-2xl overflow-y-auto border-border bg-[hsl(var(--panel-1))]">
          <DialogHeader><DialogTitle>Inventory CSV Import</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <Label className="text-xs">Mode</Label>
              <Select value={csvMode} onValueChange={(v) => { setCsvMode(v); setPreview(null); }}>
                <SelectTrigger className="w-44 bg-[hsl(var(--panel-2))]" data-testid="csv-mode-select"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="replace">Replace quantity</SelectItem>
                  <SelectItem value="add">Add to quantity</SelectItem>
                  <SelectItem value="subtract">Subtract from quantity</SelectItem>
                  <SelectItem value="adjustment">Stock adjustment (+/-)</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <p className="text-xs text-muted-foreground">
              {csvMode === 'adjustment'
                ? <>Columns: <span className="font-mono">sap_code,quantity_change</span> (positive adds, negative subtracts)</>
                : <>Columns: <span className="font-mono">sap_code,quantity[,material_name,location,uom,long_text,category]</span></>}
            </p>
            <Textarea data-testid="csv-textarea" value={csvText} onChange={(e) => setCsvText(e.target.value)} rows={7}
              placeholder={csvMode === 'adjustment' ? 'sap_code,quantity_change\n400001234,-2' : 'sap_code,quantity,material_name\n400001234,10,Bearing 6205 ZZ'}
              className="bg-[hsl(var(--panel-2))] font-mono text-xs" />
            <div className="flex gap-2">
              <Button variant="outline" onClick={doPreview} data-testid="csv-preview-button" className="border-border bg-[hsl(var(--panel-2))]">Preview</Button>
              {preview && preview.errors.length === 0 && preview.valid_rows > 0 && (
                <Button onClick={doApply} data-testid="csv-apply-button" className="border border-[#05ffa1]/60 bg-transparent text-[#05ffa1] hover:bg-[#05ffa1]/10">Apply {preview.valid_rows} rows</Button>
              )}
            </div>
            {preview && (
              <div className="space-y-2" data-testid="csv-preview-panel">
                {preview.errors.length > 0 && (
                  <div className="rounded-md border border-[#ff2e63]/40 bg-[#ff2e63]/10 p-2 text-xs text-[#ff2e63]" data-testid="csv-preview-errors">
                    {preview.errors.map((e, i) => <div key={i}>{e}</div>)}
                  </div>
                )}
                <div className="max-h-52 overflow-y-auto rounded-md border border-border">
                  <table className="w-full text-xs">
                    <thead className="bg-[hsl(var(--panel-2))]"><tr><th className="p-1.5 text-left">SAP</th><th className="p-1.5 text-left">Material</th><th className="p-1.5">Old</th><th className="p-1.5">Change</th><th className="p-1.5">New</th><th className="p-1.5">New?</th></tr></thead>
                    <tbody>
                      {preview.rows.map((r, i) => (
                        <tr key={i} className="border-t border-border">
                          <td className="p-1.5 font-mono">{r.sap_code}</td><td className="p-1.5">{r.material_name}</td>
                          <td className="p-1.5 text-center">{r.old_quantity}</td>
                          <td className={`p-1.5 text-center ${r.change < 0 ? 'text-[#ff2e63]' : 'text-[#05ffa1]'}`}>{r.change > 0 ? '+' : ''}{r.change}</td>
                          <td className="p-1.5 text-center font-semibold">{r.new_quantity}</td>
                          <td className="p-1.5 text-center">{r.is_new ? 'NEW' : ''}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
