import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ClipboardCheck, ArrowLeft, CheckCircle2 } from 'lucide-react';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { AmChecklistForm } from '@/components/AmChecklistForm';
import { FuzzyPicker } from '@/components/ReportBreakdownDialog';

/**
 * PUBLIC (no login) AM Checklist kiosk — shift-floor operators identified by
 * Name + GPID + Shift fill their per-shift routine checks here. Linked from the
 * login page next to the public Breakdown / Red Tag entry points.
 */
export default function AMChecklistPublic() {
  const navigate = useNavigate();
  const [templates, setTemplates] = useState([]);
  const [loadingCtx, setLoadingCtx] = useState(true);
  const [templateId, setTemplateId] = useState('');
  const [template, setTemplate] = useState(null);
  const [done, setDone] = useState(null);

  useEffect(() => {
    api.get('/public/am-context').then((r) => setTemplates(r.data.templates)).catch(() => {}).finally(() => setLoadingCtx(false));
  }, []);

  useEffect(() => {
    setTemplate(null);
    if (templateId) api.get(`/public/am-templates/${templateId}`).then((r) => setTemplate(r.data)).catch(() => {});
  }, [templateId]);

  const selected = templates.find((t) => t.id === templateId);
  // Fuzzy search options — every typed token must match machine / template / line / group
  const pickerOptions = useMemo(() => templates.map((t) => ({
    key: t.id, t,
    haystack: `${t.machine_name} ${t.template_name} ${t.line || ''} ${t.process_group || ''}`.toLowerCase(),
  })), [templates]);

  return (
    <div className="relative min-h-screen overflow-x-hidden bg-background px-4 py-6">
      <div className="pointer-events-none absolute inset-0"
        style={{ backgroundImage: 'radial-gradient(900px 500px at 20% 10%, rgba(var(--accent-rgb),0.08), transparent 60%), radial-gradient(700px 420px at 80% 0%, rgba(5,255,161,0.05), transparent 55%)' }} />
      <div className="relative mx-auto w-full max-w-2xl">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <ClipboardCheck className="h-5 w-5 text-[#05ffa1]" />
            <div>
              <h1 className="text-lg font-semibold tracking-tight">AM Checklist</h1>
              <p className="text-[10px] uppercase tracking-widest text-muted-foreground">Autonomous Maintenance · once per shift · no login needed</p>
            </div>
          </div>
          <Button variant="outline" size="sm" data-testid="am-public-back" onClick={() => navigate('/login')} className="h-9">
            <ArrowLeft className="mr-1 h-3.5 w-3.5" /> Login page
          </Button>
        </div>

        {done ? (
          <div className="border border-[#05ffa1]/40 bg-[hsl(var(--panel-1))]/90 p-6 text-center" data-testid="am-public-success">
            <CheckCircle2 className="mx-auto h-10 w-10 text-[#05ffa1]" />
            <h2 className="mt-2 text-lg font-semibold">Checklist submitted</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              {done.machine_name} · Shift {done.shift} · {done.duration_minutes} min
              {done.not_ok_count > 0 && <span className="text-[#ff2e63]"> · {done.not_ok_count} item(s) flagged NOT OK — maintenance has been notified</span>}
            </p>
            <div className="mt-4 flex flex-wrap justify-center gap-2">
              <Button data-testid="am-public-again" onClick={() => { setDone(null); setTemplate(null); setTemplateId(''); }} className="h-11 sm:h-10">Fill another checklist</Button>
              <Button variant="outline" onClick={() => navigate('/login')} className="h-11 sm:h-10">Back to login</Button>
            </div>
          </div>
        ) : (
          <div className="border border-border bg-[hsl(var(--panel-1))]/90 p-4 backdrop-blur-md sm:p-6">
            <Label className="text-[10px] uppercase tracking-widest text-muted-foreground">Machine / Checklist <span className="text-[#ff2e63]">*</span></Label>
            <div className="mt-0.5">
              <FuzzyPicker
                testId="am-public-template-select"
                value={templateId}
                display={selected ? `${selected.machine_name} — ${selected.template_name} (${selected.line})` : ''}
                options={pickerOptions}
                onSelect={(o) => setTemplateId(o.key)}
                placeholder={loadingCtx ? 'Loading…' : templates.length ? 'Search machine by name / line / group…' : 'No AM checklists configured yet'}
                renderOption={(o) => (
                  <span>
                    <span className="font-medium">{o.t.machine_name}</span>
                    <span className="text-muted-foreground"> — {o.t.template_name} · {o.t.line}{o.t.process_group ? ` / ${o.t.process_group}` : ''}</span>
                  </span>
                )}
              />
            </div>
            {!loadingCtx && templates.length === 0 && (
              <p className="mt-3 text-xs text-muted-foreground" data-testid="am-public-empty">An administrator must create AM checklist templates first.</p>
            )}
            {template && (
              <div className="mt-4">
                <AmChecklistForm template={template} publicMode onDone={(d) => setDone(d)} />
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
