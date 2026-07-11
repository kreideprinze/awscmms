"""In-place schema migrations.

MIGRATION 2 — Hierarchy inversion (Line-first):
Old model:  Department → Line → Process Group → Machine
New model:  Line → Department → Process Group → Machine

The factory has a fixed set of top-level Lines (PC21, PC32, PC36, KKR, TWZ, BCP, ...).
Within each Line the Admin defines which Departments operate there (PROCESS, PACKAGING,
UTILITIES, ...). Process groups belong to a (line, department) pair.

Strategy (IN-PLACE, keeps ALL transactional history):
  1. Merge legacy "<X> Packaging" lines into base line "<X>" as its PACKAGING department
     (machines/PGs/transactions get line renamed; department stays PACKAGING).
  2. Rebuild `lines` docs as top-level (drop department parent fields).
  3. Rebuild `departments` as per-line sub-records: {id, name, line, line_id, order}.
  4. Re-parent `process_groups` to the per-line department.
  5. Remap machines' line_id / department_id (denormalized name strings stay stable).
Marks completion in settings {'id': 'hierarchy_migration', 'version': 2} so it never re-runs.
"""
import logging
import uuid
from datetime import datetime, timezone

from database import db

logger = logging.getLogger(__name__)

# collections that carry a denormalized `line` name on transactional documents
LINE_NAME_COLLECTIONS = [
    'machines', 'process_groups', 'breakdowns', 'warnings', 'work_orders',
    'pm_tasks', 'pm_completions', 'runtime_logs', 'line_runtime_logs',
    'timeline_events', 'reliability_metrics', 'machine_reports', 'repair_events',
]


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def nid():
    return str(uuid.uuid4())


async def migrate_hierarchy_line_first():
    """Idempotent, in-place inversion of the hierarchy. Safe to call at every startup."""
    flag = await db.settings.find_one({'id': 'hierarchy_migration'}, {'_id': 0})
    if flag and flag.get('version', 0) >= 2:
        return {'skipped': True, 'reason': 'already at version 2'}

    old_lines = await db.lines.find({}, {'_id': 0}).to_list(10000)
    old_depts = await db.departments.find({}, {'_id': 0}).to_list(1000)
    # Detect old model: lines carry a department parent OR departments lack a line parent
    old_model = any('department_id' in l or 'department' in l for l in old_lines) or \
                any('line_id' not in d for d in old_depts)
    if not (old_lines or old_depts):
        # empty DB — nothing to migrate; seed will create the new model directly
        await db.settings.update_one({'id': 'hierarchy_migration'},
                                     {'$set': {'version': 2, 'migrated_at': now_iso(), 'note': 'empty db'}}, upsert=True)
        return {'skipped': True, 'reason': 'empty database'}
    if not old_model:
        await db.settings.update_one({'id': 'hierarchy_migration'},
                                     {'$set': {'version': 2, 'migrated_at': now_iso(), 'note': 'already new model'}}, upsert=True)
        return {'skipped': True, 'reason': 'already new model'}

    summary = {'merged_lines': [], 'lines': 0, 'departments': 0, 'process_groups': 0, 'machines_remapped': 0}
    ts = now_iso()

    # ---------- 1. Merge "<X> Packaging" legacy lines into base line "<X>" ----------
    line_names = {l['name'] for l in old_lines}
    merge_map = {}  # old line name -> new (base) line name
    for l in old_lines:
        name = l['name']
        if name.endswith(' Packaging'):
            base = name[: -len(' Packaging')]
            if base in line_names:
                merge_map[name] = base
    for old_name, new_name in merge_map.items():
        for coll in LINE_NAME_COLLECTIONS:
            await db[coll].update_many({'line': old_name}, {'$set': {'line': new_name}})
        summary['merged_lines'].append(f'{old_name} → {new_name}')

    # ---------- 2. Rebuild lines (top-level, unique by final name) ----------
    final_lines = {}
    for l in sorted(old_lines, key=lambda x: x.get('order', 0)):
        final_name = merge_map.get(l['name'], l['name'])
        if final_name not in final_lines:
            final_lines[final_name] = {'id': l['id'] if l['name'] == final_name else None,
                                       'name': final_name, 'order': l.get('order', 0),
                                       'created_at': l.get('created_at', ts)}
    # ensure ids (merged-away lines keep the base line's id)
    for name, doc in final_lines.items():
        if not doc['id']:
            base = next((l for l in old_lines if l['name'] == name), None)
            doc['id'] = base['id'] if base else nid()
    await db.lines.delete_many({})
    if final_lines:
        await db.lines.insert_many([dict(v) for v in final_lines.values()])
    summary['lines'] = len(final_lines)

    # ---------- 3. Per-line departments from actual usage ----------
    # A (line, department) pair exists if any machine/PG lives there, or from the old line parent.
    pairs = set()
    old_line_dept = {l['name']: l.get('department') for l in old_lines}
    for l in old_lines:
        final_name = merge_map.get(l['name'], l['name'])
        dept = 'PACKAGING' if l['name'] in merge_map else (old_line_dept.get(l['name']) or 'PROCESS')
        pairs.add((final_name, dept))
    async for m in db.machines.find({}, {'_id': 0, 'line': 1, 'department': 1}):
        if m.get('line') and m.get('department'):
            pairs.add((m['line'], m['department']))
    async for pg in db.process_groups.find({}, {'_id': 0, 'line': 1, 'department': 1}):
        if pg.get('line') and pg.get('department'):
            pairs.add((pg['line'], pg['department']))

    dept_order = {'PROCESS': 0, 'PACKAGING': 1, 'UTILITIES': 2}
    new_depts = {}
    for line_name, dept_name in sorted(pairs):
        if line_name not in final_lines:
            continue
        new_depts[(line_name, dept_name)] = {
            'id': nid(), 'name': dept_name, 'line': line_name,
            'line_id': final_lines[line_name]['id'],
            'order': dept_order.get(dept_name, 9), 'created_at': ts,
        }
    await db.departments.delete_many({})
    if new_depts:
        await db.departments.insert_many([dict(v) for v in new_depts.values()])
    summary['departments'] = len(new_depts)

    # ---------- 4. Re-parent process groups ----------
    async for pg in db.process_groups.find({}, {'_id': 0}):
        line_name = pg.get('line')
        dept_name = pg.get('department') or 'PROCESS'
        dept = new_depts.get((line_name, dept_name))
        line_doc = final_lines.get(line_name)
        if not dept or not line_doc:
            continue
        await db.process_groups.update_one({'id': pg['id']}, {'$set': {
            'line': line_name, 'line_id': line_doc['id'],
            'department': dept_name, 'department_id': dept['id'],
        }})
        summary['process_groups'] += 1

    # ---------- 5. Remap machines ----------
    async for m in db.machines.find({}, {'_id': 0, 'id': 1, 'line': 1, 'department': 1}):
        line_doc = final_lines.get(m.get('line'))
        dept = new_depts.get((m.get('line'), m.get('department') or 'PROCESS'))
        if not line_doc:
            continue
        updates = {'line_id': line_doc['id']}
        if dept:
            updates['department_id'] = dept['id']
        await db.machines.update_one({'id': m['id']}, {'$set': updates})
        summary['machines_remapped'] += 1

    await db.settings.update_one({'id': 'hierarchy_migration'},
                                 {'$set': {'version': 2, 'migrated_at': ts, 'summary': str(summary)}}, upsert=True)
    logger.info(f'Hierarchy migration to Line-first complete: {summary}')
    return summary
