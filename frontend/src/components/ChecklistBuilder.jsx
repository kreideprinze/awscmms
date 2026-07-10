import React from 'react';
import { Plus, Trash2, CornerDownRight } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';

// Download a PM checklist PDF (blank template or completed instance) with auth header
export async function downloadPmPdf(taskId, completionId = null, filename = 'PM_checklist.pdf') {
  const res = await api.get(`/pm-tasks/${taskId}/pdf${completionId ? `?completion_id=${completionId}` : ''}`, { responseType: 'blob' });
  const url = URL.createObjectURL(res.data);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

// Expand structured groups (or legacy flat checklist) into printable/checkable rows
export function checklistRows(task) {
  let groups = task?.checklist_groups || [];
  if (!groups.length && task?.checklist?.length) {
    groups = task.checklist.map((c) => ({ description: c, items: [{ checked_for: 'Condition', parameter: '' }] }));
  }
  const rows = [];
  groups.forEach((g, gi) => {
    g.items.forEach((item, ii) => {
      rows.push({
        key: `${gi}-${ii}`, sn: gi + 1, firstOfGroup: ii === 0, groupSize: g.items.length,
        description: g.description, checked_for: item.checked_for, parameter: item.parameter || '',
      });
    });
  });
  return rows;
}

/**
 * Structured PM checklist builder — one-to-many grouping:
 * Description (component, e.g. "Motor") -> multiple "Checked For" sub-rows
 * (Bearing / Over load / Condition), each with a Parameter/Process.
 */
export function ChecklistBuilder({ groups, setGroups }) {
  const update = (gi, patch) => setGroups(groups.map((g, i) => (i === gi ? { ...g, ...patch } : g)));
  const updateItem = (gi, ii, patch) =>
    update(gi, { items: groups[gi].items.map((it, j) => (j === ii ? { ...it, ...patch } : it)) });

  return (
    <div className="space-y-2" data-testid="checklist-builder">
      <div className="grid grid-cols-[24px_1fr_1fr_1fr_28px] gap-1.5 px-1 font-mono text-[9px] uppercase tracking-[0.15em] text-muted-foreground">
        <span>S.N.</span><span>Description (component)</span><span>Checked For</span><span>Parameter / Process</span><span />
      </div>
      {groups.map((g, gi) => (
        <div key={gi} className="border border-border/70 p-1.5" data-testid={`checklist-group-${gi}`}>
          {g.items.map((item, ii) => (
            <div key={ii} className="mb-1.5 grid grid-cols-[24px_1fr_1fr_1fr_28px] items-center gap-1.5 last:mb-0">
              {ii === 0 ? (
                <>
                  <span className="text-center font-mono text-xs text-muted-foreground">{gi + 1}</span>
                  <Input value={g.description} placeholder="e.g. Motor" data-testid={`checklist-desc-${gi}`}
                    onChange={(e) => update(gi, { description: e.target.value })} className="h-8 bg-[hsl(var(--panel-2))] text-xs font-semibold" />
                </>
              ) : (
                <>
                  <span />
                  <span className="flex items-center justify-end pr-1 text-muted-foreground"><CornerDownRight className="h-3.5 w-3.5" /></span>
                </>
              )}
              <Input value={item.checked_for} placeholder="e.g. Bearing" data-testid={`checklist-cf-${gi}-${ii}`}
                onChange={(e) => updateItem(gi, ii, { checked_for: e.target.value })} className="h-8 bg-[hsl(var(--panel-2))] text-xs" />
              <Input value={item.parameter} placeholder="e.g. Vibration, Sound" data-testid={`checklist-param-${gi}-${ii}`}
                onChange={(e) => updateItem(gi, ii, { parameter: e.target.value })} className="h-8 bg-[hsl(var(--panel-2))] text-xs" />
              <button type="button" data-testid={`checklist-del-${gi}-${ii}`} title="Remove row"
                onClick={() => {
                  const items = g.items.filter((_, j) => j !== ii);
                  if (!items.length) setGroups(groups.filter((_, i) => i !== gi));
                  else update(gi, { items });
                }}
                className="flex h-8 w-7 items-center justify-center border border-transparent text-muted-foreground transition-colors hover:border-[#ff2e63]/50 hover:text-[#ff2e63]">
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
          <button type="button" data-testid={`checklist-add-item-${gi}`}
            onClick={() => update(gi, { items: [...g.items, { checked_for: '', parameter: '' }] })}
            className="mt-1 flex items-center gap-1 font-mono text-[10px] uppercase tracking-wide text-muted-foreground transition-colors hover:text-[hsl(var(--primary))]">
            <Plus className="h-3 w-3" /> Add sub-item to “{g.description || 'component'}”
          </button>
        </div>
      ))}
      <Button type="button" variant="outline" size="sm" data-testid="checklist-add-group"
        onClick={() => setGroups([...groups, { description: '', items: [{ checked_for: '', parameter: '' }] }])} className="w-full">
        <Plus className="mr-1 h-3.5 w-3.5" /> Add component (Description)
      </Button>
    </div>
  );
}
