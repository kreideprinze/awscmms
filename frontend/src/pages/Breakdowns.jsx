import React, { useEffect, useState, useCallback } from 'react';
import { toast } from 'sonner';
import { Plus, Search } from 'lucide-react';
import { api, errMsg } from '@/lib/api';
import { useApp } from '@/context/AppContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { LifecycleBadge, fmtDate } from '@/components/StatusBits';
import { MachineSelect } from '@/components/Shared';
import { BreakdownActions } from '@/components/MachineDrawer';

const STATUSES = ['all', 'OPEN', 'ASSIGNED', 'IN_PROGRESS', 'COMPLETED', 'CLOSED'];

export default function Breakdowns() {
  const { openMachine, liveFeed } = useApp();
  const [data, setData] = useState({ items: [], total: 0 });
  const [status, setStatus] = useState('all');
  const [search, setSearch] = useState('');
  const [createOpen, setCreateOpen] = useState(false);
  const [machineId, setMachineId] = useState('');
  const [failureModes, setFailureModes] = useState([]);
  const [mode, setMode] = useState('');
  const [desc, setDesc] = useState('');
  const [expanded, setExpanded] = useState(null);

  const load = useCallback(() => {
    const params = new URLSearchParams();
    if (status !== 'all') params.set('status', status);
    if (search) params.set('search', search);
    api.get(`/breakdowns?${params}`).then((r) => setData(r.data));
  }, [status, search]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { load(); }, [liveFeed.length]); // refresh on live events
  useEffect(() => { api.get('/failure-modes').then((r) => setFailureModes(r.data)); }, []);

  const create = async () => {
    if (!machineId || !mode || !desc) { toast.error('Machine, failure mode and description are required'); return; }
    try {
      const res = await api.post('/breakdowns', { machine_id: machineId, failure_mode: mode, description: desc });
      toast.success(`Breakdown ${res.data.ticket_number} created`);
      setCreateOpen(false); setMachineId(''); setMode(''); setDesc('');
      load();
    } catch (e) { toast.error(errMsg(e)); }
  };

  return (
    <div className="p-6" data-testid="breakdowns-page">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Breakdowns</h1>
          <p className="text-sm text-muted-foreground">{data.total} total · lifecycle OPEN → ASSIGNED → IN_PROGRESS → COMPLETED → CLOSED</p>
        </div>
        <Button data-testid="breakdowns-create-button" onClick={() => setCreateOpen(true)} className="bg-red-500/20 text-red-200 hover:bg-red-500/30">
          <Plus className="mr-1 h-4 w-4" /> Report Breakdown
        </Button>
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="relative">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input data-testid="breakdowns-search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search ticket / machine / description" className="w-72 bg-[hsl(var(--panel-2))] pl-8" />
        </div>
        {STATUSES.map((s) => (
          <button key={s} data-testid={`breakdowns-filter-${s}`} onClick={() => setStatus(s)}
            className={`rounded-full border px-3 py-1 text-xs ${status === s ? 'border-[hsl(var(--primary))] bg-[rgba(46,168,255,0.12)]' : 'border-border text-muted-foreground hover:text-foreground'}`}>
            {s === 'all' ? 'All' : s}
          </button>
        ))}
      </div>

      <div className="overflow-hidden rounded-lg border border-border">
        <Table data-testid="breakdowns-table">
          <TableHeader>
            <TableRow className="border-border bg-[hsl(var(--panel-1))] hover:bg-[hsl(var(--panel-1))]">
              <TableHead className="text-xs uppercase">Ticket</TableHead>
              <TableHead className="text-xs uppercase">Machine</TableHead>
              <TableHead className="text-xs uppercase">Failure Mode</TableHead>
              <TableHead className="text-xs uppercase">Status</TableHead>
              <TableHead className="text-xs uppercase">Start</TableHead>
              <TableHead className="text-xs uppercase">Downtime</TableHead>
              <TableHead className="text-xs uppercase">Assigned</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.items.length === 0 && (
              <TableRow><TableCell colSpan={7} className="py-10 text-center text-muted-foreground">No breakdowns match filters</TableCell></TableRow>
            )}
            {data.items.map((bd) => (
              <React.Fragment key={bd.id}>
                <TableRow data-testid={`breakdowns-row-${bd.ticket_number}`} onClick={() => setExpanded(expanded === bd.id ? null : bd.id)}
                  className="cursor-pointer border-border hover:bg-white/[0.03]">
                  <TableCell className="font-mono text-xs text-[hsl(var(--primary))]">{bd.ticket_number}</TableCell>
                  <TableCell>
                    <button className="text-sm font-medium hover:text-[hsl(var(--primary))]" onClick={(e) => { e.stopPropagation(); openMachine(bd.machine_id); }}>
                      {bd.machine_name}
                    </button>
                    <div className="text-[10px] text-muted-foreground">{bd.line} / {bd.process_group}</div>
                  </TableCell>
                  <TableCell className="text-sm">{bd.failure_mode}</TableCell>
                  <TableCell><LifecycleBadge status={bd.status} /></TableCell>
                  <TableCell className="font-mono text-xs">{fmtDate(bd.start_time)}</TableCell>
                  <TableCell className="tabular-nums text-sm">{bd.downtime_minutes != null ? `${Math.round(bd.downtime_minutes)} min` : '—'}</TableCell>
                  <TableCell className="text-sm">{bd.assigned_to || '—'}</TableCell>
                </TableRow>
                {expanded === bd.id && (
                  <TableRow className="border-border bg-[hsl(var(--panel-1))]/60 hover:bg-[hsl(var(--panel-1))]/60">
                    <TableCell colSpan={7} className="p-4">
                      <div className="text-sm">{bd.description}</div>
                      {bd.root_cause && <div className="mt-1 text-xs"><span className="text-muted-foreground">Root cause:</span> {bd.root_cause}</div>}
                      {bd.action_taken && <div className="mt-1 text-xs"><span className="text-muted-foreground">Action taken:</span> {bd.action_taken}</div>}
                      {bd.consumed_spares?.length > 0 && (
                        <div className="mt-1 text-xs"><span className="text-muted-foreground">Spares:</span> {bd.consumed_spares.map((s) => `${s.material_name || s.sap_code} ×${s.quantity}`).join(', ')}</div>
                      )}
                      <BreakdownActions bd={bd} onDone={load} />
                    </TableCell>
                  </TableRow>
                )}
              </React.Fragment>
            ))}
          </TableBody>
        </Table>
      </div>

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="border-border bg-[hsl(var(--panel-1))]">
          <DialogHeader><DialogTitle>Report Breakdown</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div><Label className="text-xs">Machine</Label><MachineSelect value={machineId} onChange={(id) => setMachineId(id)} testId="bd-create-machine-select" /></div>
            <div>
              <Label className="text-xs">Failure Mode</Label>
              <Select value={mode} onValueChange={setMode}>
                <SelectTrigger data-testid="bd-create-failure-mode" className="bg-[hsl(var(--panel-2))]"><SelectValue placeholder="Select failure mode" /></SelectTrigger>
                <SelectContent>{failureModes.map((f) => <SelectItem key={f.id} value={f.name}>{f.name}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div><Label className="text-xs">Description</Label><Textarea data-testid="bd-create-description" value={desc} onChange={(e) => setDesc(e.target.value)} placeholder="What happened?" className="bg-[hsl(var(--panel-2))]" /></div>
            <Button onClick={create} data-testid="bd-create-submit" className="w-full bg-red-500/20 text-red-200 hover:bg-red-500/30">Create Breakdown Ticket</Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
