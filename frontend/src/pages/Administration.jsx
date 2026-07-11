import React, { useEffect, useState, useCallback } from 'react';
import { toast } from 'sonner';
import { Plus, Trash2, Save } from 'lucide-react';
import { api, errMsg } from '@/lib/api';
import { useApp } from '@/context/AppContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { fmtDate } from '@/components/StatusBits';

function Section({ title, children, action }) {
  return (
    <div className="cyber-panel p-4">
      <div className="mb-3 flex items-center justify-between">
        <div className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">{title}</div>
        {action}
      </div>
      {children}
    </div>
  );
}

/* ---- Hierarchy tab ---- */
function HierarchyTab() {
  const { openMachine } = useApp();
  const [h, setH] = useState({ departments: [], lines: [], process_groups: [] });
  const [machines, setMachines] = useState([]);
  const [selLine, setSelLine] = useState('');
  const [newLine, setNewLine] = useState('');
  const [newDept, setNewDept] = useState({ name: '', line_id: '' });
  const [newPG, setNewPG] = useState({ name: '', department_id: '' });
  const [newMachine, setNewMachine] = useState({ name: '', code: '', process_group_id: '', criticality: 'medium' });
  const [posEdit, setPosEdit] = useState(null);

  const load = useCallback(() => {
    api.get('/hierarchy').then((r) => setH(r.data));
    api.get('/machines?limit=10000').then((r) => setMachines(r.data));
  }, []);
  useEffect(() => { load(); }, [load]);

  const call = async (fn, msg) => {
    try { await fn(); toast.success(msg); load(); } catch (e) { toast.error(errMsg(e)); }
  };

  const lineMachines = machines.filter((m) => m.line === selLine);

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Section title="Lines (top level)">
          <div className="max-h-56 overflow-y-auto">
            {h.lines.map((l) => (
              <div key={l.id} className="flex items-center justify-between border-b border-border/50 py-1.5 text-sm">
                <span>{l.name}</span>
                <Button size="sm" variant="ghost" className="h-6 w-6 p-0" onClick={() => call(() => api.delete(`/lines/${l.id}`), 'Line deleted')}><Trash2 className="h-3 w-3" /></Button>
              </div>
            ))}
          </div>
          <div className="mt-2 flex gap-2">
            <Input value={newLine} onChange={(e) => setNewLine(e.target.value)} placeholder="New line (e.g. PC40)" className="bg-[hsl(var(--panel-2))]" data-testid="admin-new-line-input" />
            <Button size="sm" data-testid="admin-new-line-add" onClick={() => newLine && call(() => api.post('/lines', { name: newLine }).then(() => setNewLine('')), 'Line created')}><Plus className="h-4 w-4" /></Button>
          </div>
        </Section>
        <Section title="Departments (per line)">
          <div className="max-h-56 overflow-y-auto">
            {h.departments.map((d) => (
              <div key={d.id} className="flex items-center justify-between border-b border-border/50 py-1.5 text-sm">
                <span>{d.name} <span className="text-[10px] text-muted-foreground">({d.line})</span></span>
                <Button size="sm" variant="ghost" className="h-6 w-6 p-0" onClick={() => call(() => api.delete(`/departments/${d.id}`), 'Department deleted')}><Trash2 className="h-3 w-3" /></Button>
              </div>
            ))}
          </div>
          <div className="mt-2 space-y-2">
            <Select value={newDept.line_id} onValueChange={(v) => setNewDept({ ...newDept, line_id: v })}>
              <SelectTrigger className="bg-[hsl(var(--panel-2))]" data-testid="admin-new-dept-line"><SelectValue placeholder="Line" /></SelectTrigger>
              <SelectContent>{h.lines.map((l) => <SelectItem key={l.id} value={l.id}>{l.name}</SelectItem>)}</SelectContent>
            </Select>
            <div className="flex gap-2">
              <Input value={newDept.name} onChange={(e) => setNewDept({ ...newDept, name: e.target.value })} placeholder="New department" className="bg-[hsl(var(--panel-2))]" data-testid="admin-new-dept-input" />
              <Button size="sm" data-testid="admin-new-dept-add" onClick={() => newDept.name && newDept.line_id && call(() => api.post('/departments', newDept).then(() => setNewDept({ name: '', line_id: '' })), 'Department created')}><Plus className="h-4 w-4" /></Button>
            </div>
          </div>
        </Section>
        <Section title="Process Groups (per department)">
          <div className="max-h-56 overflow-y-auto">
            {h.process_groups.slice(0, 60).map((p) => (
              <div key={p.id} className="flex items-center justify-between border-b border-border/50 py-1.5 text-sm">
                <span>{p.name} <span className="text-[10px] text-muted-foreground">({p.line} / {p.department})</span></span>
                <Button size="sm" variant="ghost" className="h-6 w-6 p-0" onClick={() => call(() => api.delete(`/process-groups/${p.id}`), 'Process group deleted')}><Trash2 className="h-3 w-3" /></Button>
              </div>
            ))}
          </div>
          <div className="mt-2 space-y-2">
            <Select value={newPG.department_id} onValueChange={(v) => setNewPG({ ...newPG, department_id: v })}>
              <SelectTrigger className="bg-[hsl(var(--panel-2))]" data-testid="admin-new-pg-dept"><SelectValue placeholder="Line / Department" /></SelectTrigger>
              <SelectContent>{h.departments.map((d) => <SelectItem key={d.id} value={d.id}>{d.line} / {d.name}</SelectItem>)}</SelectContent>
            </Select>
            <div className="flex gap-2">
              <Input value={newPG.name} onChange={(e) => setNewPG({ ...newPG, name: e.target.value })} placeholder="New process group" className="bg-[hsl(var(--panel-2))]" data-testid="admin-new-pg-input" />
              <Button size="sm" data-testid="admin-new-pg-add" onClick={() => newPG.name && newPG.department_id && call(() => api.post('/process-groups', newPG).then(() => setNewPG({ name: '', department_id: '' })), 'Process group created')}><Plus className="h-4 w-4" /></Button>
            </div>
          </div>
        </Section>
      </div>

      <Section title="Machines & Digital Twin layout (X / Y / W / H)" action={
        <Select value={selLine} onValueChange={setSelLine}>
          <SelectTrigger className="w-52 bg-[hsl(var(--panel-2))]" data-testid="admin-machines-line-select"><SelectValue placeholder="Select line" /></SelectTrigger>
          <SelectContent>{h.lines.map((l) => <SelectItem key={l.id} value={l.name}>{l.name}</SelectItem>)}</SelectContent>
        </Select>
      }>
        <div className="mb-3 grid grid-cols-1 items-end gap-2 md:grid-cols-5">
          <div><Label className="text-[10px] uppercase">Name</Label><Input data-testid="admin-new-machine-name" value={newMachine.name} onChange={(e) => setNewMachine({ ...newMachine, name: e.target.value })} className="bg-[hsl(var(--panel-2))]" /></div>
          <div><Label className="text-[10px] uppercase">Code</Label><Input data-testid="admin-new-machine-code" value={newMachine.code} onChange={(e) => setNewMachine({ ...newMachine, code: e.target.value })} className="bg-[hsl(var(--panel-2))] font-mono" /></div>
          <div>
            <Label className="text-[10px] uppercase">Process Group</Label>
            <Select value={newMachine.process_group_id} onValueChange={(v) => setNewMachine({ ...newMachine, process_group_id: v })}>
              <SelectTrigger className="bg-[hsl(var(--panel-2))]" data-testid="admin-new-machine-pg"><SelectValue placeholder="PG" /></SelectTrigger>
              <SelectContent>{h.process_groups.filter((p) => !selLine || p.line === selLine).map((p) => <SelectItem key={p.id} value={p.id}>{p.line} / {p.name}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div>
            <Label className="text-[10px] uppercase">Criticality</Label>
            <Select value={newMachine.criticality} onValueChange={(v) => setNewMachine({ ...newMachine, criticality: v })}>
              <SelectTrigger className="bg-[hsl(var(--panel-2))]"><SelectValue /></SelectTrigger>
              <SelectContent>{['low', 'medium', 'high', 'critical'].map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <Button data-testid="admin-new-machine-add" onClick={() => newMachine.name && newMachine.code && newMachine.process_group_id && call(() => api.post('/machines', newMachine).then(() => setNewMachine({ name: '', code: '', process_group_id: '', criticality: 'medium' })), 'Machine created')}>
            <Plus className="mr-1 h-4 w-4" /> Add Machine
          </Button>
        </div>
        {selLine ? (
          <div className="max-h-96 overflow-y-auto rounded-md border border-border">
            <Table>
              <TableHeader>
                <TableRow className="border-border bg-[hsl(var(--panel-2))] hover:bg-[hsl(var(--panel-2))]">
                  <TableHead className="text-xs uppercase">Machine</TableHead><TableHead className="text-xs uppercase">Code</TableHead>
                  <TableHead className="text-xs uppercase">PG</TableHead><TableHead className="text-xs uppercase">X</TableHead>
                  <TableHead className="text-xs uppercase">Y</TableHead><TableHead className="text-xs uppercase">W</TableHead>
                  <TableHead className="text-xs uppercase">H</TableHead><TableHead className="text-xs uppercase">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {lineMachines.map((m) => {
                  const editing = posEdit?.id === m.id;
                  return (
                    <TableRow key={m.id} className="border-border">
                      <TableCell><button className="text-sm hover:text-[hsl(var(--primary))]" onClick={() => openMachine(m.id)}>{m.name}</button></TableCell>
                      <TableCell className="font-mono text-xs">{m.code}</TableCell>
                      <TableCell className="text-xs">{m.process_group}</TableCell>
                      {['position_x', 'position_y', 'width', 'height'].map((f) => (
                        <TableCell key={f} className="w-20">
                          {editing ? (
                            <Input type="number" value={posEdit[f]} onChange={(e) => setPosEdit({ ...posEdit, [f]: e.target.value })} className="h-7 bg-[hsl(var(--panel-2))] text-xs" />
                          ) : <span className="tabular-nums text-xs">{m[f]}</span>}
                        </TableCell>
                      ))}
                      <TableCell>
                        <div className="flex gap-1">
                          {editing ? (
                            <Button size="sm" className="h-6 text-[10px]" data-testid={`admin-machine-save-${m.code}`} onClick={() => call(() => api.put(`/machines/${m.id}`, {
                              position_x: parseFloat(posEdit.position_x), position_y: parseFloat(posEdit.position_y),
                              width: parseFloat(posEdit.width), height: parseFloat(posEdit.height),
                            }).then(() => setPosEdit(null)), 'Layout updated')}><Save className="h-3 w-3" /></Button>
                          ) : (
                            <Button size="sm" variant="outline" className="h-6 border-border bg-[hsl(var(--panel-2))] text-[10px]" data-testid={`admin-machine-edit-${m.code}`} onClick={() => setPosEdit({ id: m.id, position_x: m.position_x, position_y: m.position_y, width: m.width, height: m.height })}>Edit</Button>
                          )}
                          <Button size="sm" variant="ghost" className="h-6 w-6 p-0" onClick={() => call(() => api.delete(`/machines/${m.id}`), 'Machine deleted')}><Trash2 className="h-3 w-3" /></Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        ) : <div className="py-6 text-center text-sm text-muted-foreground">Select a line to manage its machines and layout positions</div>}
      </Section>
    </div>
  );
}

/* ---- Users tab ---- */
function UsersTab() {
  const [users, setUsers] = useState([]);
  const [form, setForm] = useState({ username: '', password: '', name: '', role: 'operator' });
  const load = useCallback(() => { api.get('/users').then((r) => setUsers(r.data)); }, []);
  useEffect(() => { load(); }, [load]);
  const create = async () => {
    if (!form.username || !form.password || !form.name) { toast.error('All fields required'); return; }
    try { await api.post('/users', form); toast.success('User created'); setForm({ username: '', password: '', name: '', role: 'operator' }); load(); } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <Section title="Users (exactly 3 roles: Admin · Technician · Operator)">
      <div className="mb-3 grid grid-cols-1 items-end gap-2 md:grid-cols-5">
        <div><Label className="text-[10px] uppercase">Username</Label><Input data-testid="admin-user-username" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} className="bg-[hsl(var(--panel-2))]" /></div>
        <div><Label className="text-[10px] uppercase">Password</Label><Input data-testid="admin-user-password" type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} className="bg-[hsl(var(--panel-2))]" /></div>
        <div><Label className="text-[10px] uppercase">Full Name</Label><Input data-testid="admin-user-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="bg-[hsl(var(--panel-2))]" /></div>
        <div>
          <Label className="text-[10px] uppercase">Role</Label>
          <Select value={form.role} onValueChange={(v) => setForm({ ...form, role: v })}>
            <SelectTrigger className="bg-[hsl(var(--panel-2))]" data-testid="admin-user-role"><SelectValue /></SelectTrigger>
            <SelectContent>{['admin', 'technician', 'operator'].map((r) => <SelectItem key={r} value={r}>{r}</SelectItem>)}</SelectContent>
          </Select>
        </div>
        <Button onClick={create} data-testid="admin-user-create"><Plus className="mr-1 h-4 w-4" /> Create User</Button>
      </div>
      <Table>
        <TableHeader>
          <TableRow className="border-border bg-[hsl(var(--panel-2))] hover:bg-[hsl(var(--panel-2))]">
            <TableHead className="text-xs uppercase">Username</TableHead><TableHead className="text-xs uppercase">Name</TableHead>
            <TableHead className="text-xs uppercase">Role</TableHead><TableHead className="text-xs uppercase">Active</TableHead>
            <TableHead className="text-xs uppercase">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {users.map((u) => (
            <TableRow key={u.id} className="border-border">
              <TableCell className="font-mono text-sm">{u.username}</TableCell>
              <TableCell className="text-sm">{u.name}</TableCell>
              <TableCell className="text-xs uppercase text-[hsl(var(--primary))]">{u.role}</TableCell>
              <TableCell className="text-xs">{u.active ? 'Yes' : 'No'}</TableCell>
              <TableCell>
                {u.active && <Button size="sm" variant="ghost" className="h-6 text-[10px] text-[#ff2e63]" onClick={async () => { try { await api.delete(`/users/${u.id}`); toast.success('User deactivated'); load(); } catch (e) { toast.error(errMsg(e)); } }}>Deactivate</Button>}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Section>
  );
}

/* ---- Catalogs tab (failure modes, error codes, PM templates, spare locations) ---- */
function CatalogsTab() {
  const [failureModes, setFailureModes] = useState([]);
  const [errorCodes, setErrorCodes] = useState([]);
  const [pmTemplates, setPmTemplates] = useState([]);
  const [locations, setLocations] = useState([]);
  const [newFM, setNewFM] = useState('');
  const [newEC, setNewEC] = useState({ code: '', label: '' });
  const [newLoc, setNewLoc] = useState('');

  const load = useCallback(() => {
    api.get('/failure-modes').then((r) => setFailureModes(r.data));
    api.get('/error-codes').then((r) => setErrorCodes(r.data));
    api.get('/pm-templates').then((r) => setPmTemplates(r.data));
    api.get('/spare-locations').then((r) => setLocations(r.data));
  }, []);
  useEffect(() => { load(); }, [load]);

  const call = async (fn, msg) => { try { await fn(); toast.success(msg); load(); } catch (e) { toast.error(errMsg(e)); } };

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <Section title="Failure Modes (breakdown dropdown)">
        <div className="max-h-52 overflow-y-auto">
          {failureModes.map((f) => (
            <div key={f.id} className="flex items-center justify-between border-b border-border/50 py-1 text-sm">
              {f.name}
              <Button size="sm" variant="ghost" className="h-6 w-6 p-0" onClick={() => call(() => api.delete(`/failure-modes/${f.id}`), 'Failure mode removed')}><Trash2 className="h-3 w-3" /></Button>
            </div>
          ))}
        </div>
        <div className="mt-2 flex gap-2">
          <Input data-testid="admin-new-fm-input" value={newFM} onChange={(e) => setNewFM(e.target.value)} placeholder="New failure mode" className="bg-[hsl(var(--panel-2))]" />
          <Button size="sm" data-testid="admin-new-fm-add" onClick={() => newFM && call(() => api.post('/failure-modes', { name: newFM }).then(() => setNewFM('')), 'Failure mode created')}><Plus className="h-4 w-4" /></Button>
        </div>
      </Section>
      <Section title="Report Error Codes (operator report dropdown)">
        <div className="max-h-52 overflow-y-auto">
          {errorCodes.map((c) => (
            <div key={c.id} className="flex items-center justify-between border-b border-border/50 py-1 text-sm">
              <span><span className="font-mono text-xs text-[hsl(var(--primary))]">{c.code}</span> {c.label}</span>
              <Button size="sm" variant="ghost" className="h-6 w-6 p-0" onClick={() => call(() => api.delete(`/error-codes/${c.id}`), 'Error code removed')}><Trash2 className="h-3 w-3" /></Button>
            </div>
          ))}
        </div>
        <div className="mt-2 flex gap-2">
          <Input data-testid="admin-new-ec-code" value={newEC.code} onChange={(e) => setNewEC({ ...newEC, code: e.target.value })} placeholder="Code" className="w-24 bg-[hsl(var(--panel-2))] font-mono" />
          <Input data-testid="admin-new-ec-label" value={newEC.label} onChange={(e) => setNewEC({ ...newEC, label: e.target.value })} placeholder="Label" className="bg-[hsl(var(--panel-2))]" />
          <Button size="sm" data-testid="admin-new-ec-add" onClick={() => newEC.code && newEC.label && call(() => api.post('/error-codes', newEC).then(() => setNewEC({ code: '', label: '' })), 'Error code created')}><Plus className="h-4 w-4" /></Button>
        </div>
      </Section>
      <Section title="PM Templates">
        <div className="max-h-64 overflow-y-auto">
          {pmTemplates.map((t) => (
            <div key={t.id} className="flex items-center justify-between border-b border-border/50 py-1.5 text-sm">
              <span>{t.name} <span className="text-[10px] text-muted-foreground">({t.frequency} · {t.checklist?.length || 0} items)</span></span>
              <Button size="sm" variant="ghost" className="h-6 w-6 p-0" onClick={() => call(() => api.delete(`/pm-templates/${t.id}`), 'Template deleted')}><Trash2 className="h-3 w-3" /></Button>
            </div>
          ))}
        </div>
      </Section>
      <Section title="Spare Locations (racks / stores)">
        <div className="max-h-52 overflow-y-auto">
          {locations.map((l) => (
            <div key={l.id} className="flex items-center justify-between border-b border-border/50 py-1 text-sm">
              <span className={l.active ? '' : 'line-through text-muted-foreground'}>{l.name}</span>
              {l.active && <Button size="sm" variant="ghost" className="h-6 text-[10px] text-[#ff2e63]" onClick={() => call(() => api.put(`/spare-locations/${l.id}`, { active: false }), 'Location retired')}>Retire</Button>}
            </div>
          ))}
        </div>
        <div className="mt-2 flex gap-2">
          <Input data-testid="admin-new-loc-input" value={newLoc} onChange={(e) => setNewLoc(e.target.value)} placeholder="New location (e.g. Rack C1)" className="bg-[hsl(var(--panel-2))]" />
          <Button size="sm" data-testid="admin-new-loc-add" onClick={() => newLoc && call(() => api.post('/spare-locations', { name: newLoc }).then(() => setNewLoc('')), 'Location created')}><Plus className="h-4 w-4" /></Button>
        </div>
      </Section>
    </div>
  );
}

/* ---- System tab (branding + audit) ---- */
function SystemTab() {
  const { refreshBranding } = useApp();
  const [branding, setBranding] = useState({ app_name: '', plant_name: '', accent: '', logo_data: '' });
  const [audit, setAudit] = useState([]);
  const load = () => {
    api.get('/branding').then((r) => setBranding((b) => ({ ...b, ...r.data })));
    api.get('/audit-logs?limit=100').then((r) => setAudit(r.data));
  };
  useEffect(() => { load(); }, []);
  const save = async () => {
    try {
      const payload = { app_name: branding.app_name, plant_name: branding.plant_name };
      if (branding.accent) {
        if (!/^#[0-9a-fA-F]{6}$/.test(branding.accent)) { toast.error('Brand color must be a hex value like #00fff5'); return; }
        payload.accent = branding.accent;
      }
      await api.put('/branding', payload);
      await refreshBranding();
      toast.success('Branding saved — accent applied platform-wide');
    } catch (e) { toast.error(errMsg(e)); }
  };
  const uploadLogo = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 500 * 1024) { toast.error('Logo too large (max 500KB)'); return; }
    const form = new FormData();
    form.append('file', file);
    try {
      const res = await api.post('/branding/logo', form, { headers: { 'Content-Type': 'multipart/form-data' } });
      setBranding((b) => ({ ...b, logo_data: res.data.logo_data }));
      await refreshBranding();
      toast.success('Logo uploaded — applied to the top-left mark');
    } catch (err) { toast.error(errMsg(err)); }
    e.target.value = '';
  };
  const removeLogo = async () => {
    try {
      await api.delete('/branding/logo');
      setBranding((b) => ({ ...b, logo_data: '' }));
      await refreshBranding();
      toast.success('Logo removed — default mark restored');
    } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <Section title="Branding">
        <div className="space-y-3">
          <div><Label className="text-xs">Application Name</Label><Input data-testid="admin-branding-app" value={branding.app_name || ''} onChange={(e) => setBranding({ ...branding, app_name: e.target.value })} className="bg-[hsl(var(--panel-2))]" /></div>
          <div><Label className="text-xs">Plant Name</Label><Input data-testid="admin-branding-plant" value={branding.plant_name || ''} onChange={(e) => setBranding({ ...branding, plant_name: e.target.value })} className="bg-[hsl(var(--panel-2))]" /></div>
          <div>
            <Label className="text-xs">Brand Accent Color (hex)</Label>
            <div className="mt-1 flex items-center gap-2">
              <input
                type="color"
                data-testid="admin-branding-color-picker"
                value={/^#[0-9a-fA-F]{6}$/.test(branding.accent || '') ? branding.accent : '#00fff5'}
                onChange={(e) => setBranding({ ...branding, accent: e.target.value })}
                className="h-9 w-10 shrink-0 cursor-pointer border border-border bg-transparent p-0.5"
                title="Pick brand accent color"
              />
              <Input
                data-testid="admin-branding-accent"
                value={branding.accent || ''}
                onChange={(e) => setBranding({ ...branding, accent: e.target.value })}
                placeholder="#00fff5"
                className="w-32 bg-[hsl(var(--panel-2))] font-mono"
              />
              <span className="text-[11px] text-muted-foreground">Applied to icons, buttons, borders & highlights platform-wide</span>
            </div>
          </div>
          <div>
            <Label className="text-xs">Custom Logo / Icon (replaces top-left mark, max 500KB)</Label>
            <div className="mt-1 flex items-center gap-3">
              {branding.logo_data ? (
                <img src={branding.logo_data} alt="logo preview" data-testid="admin-logo-preview" className="h-10 w-10 border border-border object-contain p-1" />
              ) : (
                <div className="flex h-10 w-10 items-center justify-center border border-dashed border-border text-[9px] text-muted-foreground">none</div>
              )}
              <label className="cyber-chamfer-sm cursor-pointer border border-[hsl(var(--primary))]/50 bg-transparent px-3 py-1.5 text-xs uppercase tracking-wide text-[hsl(var(--primary))] transition-colors hover:bg-[hsl(var(--primary))]/10">
                Upload logo
                <input type="file" accept="image/png,image/jpeg,image/svg+xml,image/webp,image/gif" onChange={uploadLogo} className="hidden" data-testid="admin-logo-upload" />
              </label>
              {branding.logo_data && (
                <Button variant="ghost" size="sm" className="h-8 text-xs text-[#ff2e63]" onClick={removeLogo} data-testid="admin-logo-remove">Remove</Button>
              )}
            </div>
          </div>
          <Button onClick={save} data-testid="admin-branding-save">Save Branding</Button>
        </div>
      </Section>
      <Section title="Audit Log (admin actions)">
        <div className="max-h-80 overflow-y-auto">
          {audit.length === 0 && <div className="py-6 text-center text-sm text-muted-foreground">No admin actions logged yet</div>}
          {audit.map((a) => (
            <div key={a.id} className="border-b border-border/50 py-1.5 text-xs">
              <span className="font-semibold">{a.user}</span> {a.action} {a.entity} <span className="text-muted-foreground">{a.detail}</span>
              <span className="ml-2 font-mono text-[10px] text-muted-foreground">{fmtDate(a.created_at)}</span>
            </div>
          ))}
        </div>
      </Section>
      <div className="lg:col-span-2"><DataManagement onDone={load} /></div>
    </div>
  );
}

// Admin-only Data Management: seed demo data / purge operational data (machines & config kept)
function DataManagement({ onDone }) {
  const [seeding, setSeeding] = useState(false);
  const [purgeInput, setPurgeInput] = useState('');
  const [purging, setPurging] = useState(false);

  const seed = async () => {
    setSeeding(true);
    try {
      const r = await api.post('/data/seed-sample');
      const c = r.data.seeded;
      toast.success(`Sample data seeded: ${c.work_orders} WOs (incl. ${c.rca_work_orders} RCA), ${c.breakdowns} breakdowns, ${c.warnings} warnings, ${c.pm_tasks} PM task, ${c.line_runtime_days} days of line runtime`);
      onDone && onDone();
    } catch (e) { toast.error(errMsg(e)); }
    setSeeding(false);
  };

  const purge = async () => {
    setPurging(true);
    try {
      const r = await api.post('/data/purge-operational', { confirm: purgeInput });
      const rm = r.data.removed;
      const total = Object.values(rm).reduce((n, x) => n + x, 0);
      toast.success(`Purged ${total} records (WOs: ${rm.work_orders}, breakdowns: ${rm.breakdowns}, runtime: ${rm.runtime_logs + rm.line_runtime_logs}, timeline: ${rm.timeline_events}). Machines & configuration kept.`);
      setPurgeInput('');
      onDone && onDone();
    } catch (e) { toast.error(errMsg(e)); }
    setPurging(false);
  };

  return (
    <Section title="Data Management">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2" data-testid="admin-data-management">
        <div className="space-y-2 border border-[hsl(var(--primary))]/30 p-3">
          <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-[hsl(var(--primary))]">Seed Sample Data</div>
          <p className="text-xs text-muted-foreground">
            Generates realistic demo data against your <b>existing machines</b>: work orders in every Kanban stage,
            closed breakdowns with varied downtimes (including RCA-triggering ones), warnings, a sample PM task
            with completion, and 7 days of line runtime. All records are tagged <span className="font-mono">sample</span>.
          </p>
          <Button onClick={seed} disabled={seeding} data-testid="admin-seed-sample"
            className="border border-[hsl(var(--primary))]/60 bg-transparent text-xs text-[hsl(var(--primary))] hover:bg-[hsl(var(--primary))]/10">
            {seeding ? 'Seeding…' : 'Seed Sample Data'}
          </Button>
        </div>
        <div className="space-y-2 border border-[#ff2e63]/40 bg-[#ff2e63]/[0.03] p-3">
          <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-[#ff2e63]">Purge Operational Data</div>
          <p className="text-xs text-muted-foreground">
            <b>Destructive.</b> Removes ALL work orders, breakdowns, warnings, PM completions, runtime logs
            (machine + line), timeline, notifications, repair history, spare transactions and reliability metrics.
            <b> Machines, hierarchy, users, spares catalog, PM definitions and branding are kept.</b> Ticket counters reset.
          </p>
          <div className="flex gap-2">
            <Input value={purgeInput} onChange={(e) => setPurgeInput(e.target.value)} placeholder='Type PURGE to confirm'
              data-testid="admin-purge-confirm-input" className="w-44 bg-[hsl(var(--panel-2))] font-mono text-xs" />
            <Button onClick={purge} disabled={purgeInput !== 'PURGE' || purging} data-testid="admin-purge-button"
              className="border border-[#ff2e63]/60 bg-transparent text-xs text-[#ff2e63] hover:bg-[#ff2e63]/10 disabled:opacity-40">
              {purging ? 'Purging…' : 'Purge Data'}
            </Button>
          </div>
        </div>
      </div>
    </Section>
  );
}

export default function Administration() {
  return (
    <div className="p-6" data-testid="administration-page">
      <div className="mb-5">
        <h1 className="text-2xl font-semibold tracking-tight">Administration</h1>
        <p className="text-sm text-muted-foreground">Admin-only CRUD — hierarchy, layout, users, catalogs, branding, audit</p>
      </div>
      <Tabs defaultValue="hierarchy">
        <TabsList className="bg-[hsl(var(--panel-2))]">
          <TabsTrigger value="hierarchy" data-testid="admin-tab-hierarchy">Factory Hierarchy</TabsTrigger>
          <TabsTrigger value="users" data-testid="admin-tab-users">Users</TabsTrigger>
          <TabsTrigger value="catalogs" data-testid="admin-tab-catalogs">Catalogs & Templates</TabsTrigger>
          <TabsTrigger value="system" data-testid="admin-tab-system">System</TabsTrigger>
        </TabsList>
        <TabsContent value="hierarchy" className="mt-4"><HierarchyTab /></TabsContent>
        <TabsContent value="users" className="mt-4"><UsersTab /></TabsContent>
        <TabsContent value="catalogs" className="mt-4"><CatalogsTab /></TabsContent>
        <TabsContent value="system" className="mt-4"><SystemTab /></TabsContent>
      </Tabs>
    </div>
  );
}
