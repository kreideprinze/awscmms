"""Ops routes: runtime tracking (manual + CSV import), analytics (multi-level), reliability/AWS."""
import csv
import io
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from auth import get_current_user, require_admin, require_admin_or_tech
from database import db
from events import create_timeline_event, now_iso

router = APIRouter()


# ============ PLANT RUNTIME CLOCK ============
@router.get('/plant-clock')
async def get_plant_clock(user: dict = Depends(get_current_user)):
    clock = await db.settings.find_one({'id': 'plant_clock'}, {'_id': 0})
    if not clock:
        clock = {'id': 'plant_clock', 'started_at': now_iso(), 'last_tick_at': now_iso()}
        await db.settings.insert_one(dict(clock))
        clock.pop('_id', None)
    started = datetime.fromisoformat(str(clock['started_at']).replace('Z', '+00:00'))
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    uptime = max((datetime.now(timezone.utc) - started).total_seconds(), 0)
    return {'started_at': clock['started_at'], 'last_tick_at': clock.get('last_tick_at'), 'uptime_seconds': int(uptime)}


@router.post('/plant-clock/reset')
async def reset_plant_clock(user: dict = Depends(require_admin)):
    ts = now_iso()
    await db.settings.update_one({'id': 'plant_clock'}, {'$set': {'started_at': ts, 'last_tick_at': ts}}, upsert=True)
    await create_timeline_event('plant_clock_reset', title='Plant runtime clock reset (shift start)', user=user['username'])
    return {'ok': True, 'started_at': ts}


# ============ RUNTIME (LINE-LEVEL, PLANNED-RUNTIME MODEL) ============
# ONE manual value per Line × Date: planned_hours (scheduled production hours —
# varies day to day, NOT a fixed 24h calendar constant). Downtime is derived LIVE
# from that line's Breakdowns (Warnings never count). Availability =
# ((Planned − Downtime) ÷ Planned) × 100, clamped at 0% with a `clamped`
# data-quality flag. All derivation lives in kpi_engine (single source of truth).
class RuntimeLogCreate(BaseModel):
    line: str                 # line name (line-wise logging only — not machine-wise)
    date: str                 # YYYY-MM-DD
    planned_hours: float      # scheduled run hours for that line that day (0 < h <= 24)


async def _recompute_line_reliability(line_name):
    machines = await db.machines.find({'line': line_name}, {'_id': 0, 'id': 1}).to_list(2000)
    from reliability import recompute_machine_reliability
    for m in machines:
        await recompute_machine_reliability(m['id'], trigger='runtime_log')
    return len(machines)


@router.post('/runtime-logs')
async def create_runtime_log(req: RuntimeLogCreate, user: dict = Depends(require_admin)):
    if not (0 < req.planned_hours <= 24):
        raise HTTPException(status_code=400, detail='planned_hours must be between 0 and 24')
    try:
        datetime.fromisoformat(req.date)
    except ValueError:
        raise HTTPException(status_code=400, detail='Invalid date (use YYYY-MM-DD)')
    machines_count = await db.machines.count_documents({'line': req.line})
    if not machines_count:
        raise HTTPException(status_code=404, detail=f'No machines found for line "{req.line}"')
    line_log = {
        'id': str(uuid.uuid4()), 'line': req.line, 'date': req.date,
        'planned_hours': round(req.planned_hours, 2),
        'machines_count': machines_count, 'entered_by': user['username'],
        'source': 'manual', 'created_at': now_iso(), 'updated_at': now_iso(),
    }
    m0 = await db.machines.find_one({'line': req.line}, {'_id': 0, 'department': 1})
    line_log['department'] = (m0 or {}).get('department')
    await db.line_runtime_logs.update_one({'line': req.line, 'date': req.date}, {'$set': line_log}, upsert=True)
    await _recompute_line_reliability(req.line)
    # respond with the fully derived row (downtime/run/availability computed live)
    from kpi_engine import derive_line_day_rows
    rows = await derive_line_day_rows(logs=[line_log])
    return rows[0]


@router.get('/line-runtime-logs')
async def list_line_runtime_logs(line: Optional[str] = None, date_from: Optional[str] = None,
                                 date_to: Optional[str] = None, limit: int = Query(500, le=5000), skip: int = 0,
                                 user: dict = Depends(get_current_user)):
    """Logged line-days with LIVE-derived figures: downtime (from breakdowns only),
    effective run hours, availability (clamped at 0%) and the `clamped` data-quality flag."""
    q = {}
    if line:
        q['line'] = line
    if date_from or date_to:
        q['date'] = {}
        if date_from:
            q['date']['$gte'] = date_from
        if date_to:
            q['date']['$lte'] = date_to
    total = await db.line_runtime_logs.count_documents(q)
    items = await db.line_runtime_logs.find(q, {'_id': 0}).sort('date', -1).skip(skip).limit(limit).to_list(limit)
    from kpi_engine import derive_line_day_rows
    rows = await derive_line_day_rows(logs=items)
    return {'items': rows, 'total': total}


@router.delete('/line-runtime-logs')
async def delete_line_runtime_log(line: str, date: str, user: dict = Depends(require_admin)):
    """Admin-only: remove a planned-runtime entry (the day reverts to unlogged)."""
    existing = await db.line_runtime_logs.find_one({'line': line, 'date': date}, {'_id': 0})
    if not existing:
        raise HTTPException(status_code=404, detail='Line runtime entry not found')
    await db.line_runtime_logs.delete_one({'line': line, 'date': date})
    n = await _recompute_line_reliability(line)
    await create_timeline_event('runtime_deleted', title=f'Planned runtime removed: {line} {date}',
                                description=f'{n} machines recomputed', user=user['username'])
    return {'ok': True, 'machines_recomputed': n}


@router.get('/runtime-logs')
async def list_runtime_logs(machine_id: Optional[str] = None, line: Optional[str] = None,
                            date_from: Optional[str] = None, date_to: Optional[str] = None,
                            limit: int = Query(500, le=5000), skip: int = 0, user: dict = Depends(get_current_user)):
    """Machine-scoped view of the planned-runtime model. Machines inherit their LINE's
    logged days (runtime is line-wise by design); figures are derived live."""
    if machine_id and not line:
        m = await db.machines.find_one({'id': machine_id}, {'_id': 0, 'line': 1})
        if not m:
            raise HTTPException(status_code=404, detail='Machine not found')
        line = m.get('line')
    from kpi_engine import derive_line_day_rows
    rows = await derive_line_day_rows(line=line, date_from=date_from, date_to=date_to)
    return {'items': rows[skip:skip + limit], 'total': len(rows)}


class RuntimeCSV(BaseModel):
    csv_text: str
    apply: bool = False


@router.post('/runtime-logs/import')
async def import_runtime_csv(req: RuntimeCSV, user: dict = Depends(require_admin)):
    """CSV columns: line, date, planned_hours. Preview unless apply=true.
    Downtime/availability are always derived — only Planned Runtime is entered."""
    reader = csv.DictReader(io.StringIO(req.csv_text.strip()))
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail='Empty CSV')
    cols = [c.strip().lower() for c in reader.fieldnames]
    required = {'line', 'date', 'planned_hours'}
    if not required.issubset(set(cols)):
        raise HTTPException(status_code=400, detail=f'Missing columns. Required: line, date, planned_hours. Found: {cols}')
    all_machines = await db.machines.find({}, {'_id': 0, 'id': 1, 'line': 1, 'department': 1}).to_list(20000)
    by_line = defaultdict(list)
    for m in all_machines:
        by_line[m['line']].append(m)
    rows, errors = [], []
    for i, raw in enumerate(reader, start=2):
        row = {k.strip().lower(): (v or '').strip() for k, v in raw.items()}
        line_name = row.get('line', '')
        machines = by_line.get(line_name)
        if not machines:
            errors.append(f'Row {i}: unknown line \u201c{line_name}\u201d')
            continue
        try:
            planned = float(row['planned_hours'])
            if not (0 < planned <= 24):
                raise ValueError()
        except ValueError:
            errors.append(f'Row {i}: invalid planned_hours \u201c{row.get("planned_hours")}\u201d (must be 0-24)')
            continue
        date = row.get('date', '')
        try:
            datetime.fromisoformat(date)
        except ValueError:
            errors.append(f'Row {i}: invalid date \u201c{date}\u201d (use YYYY-MM-DD)')
            continue
        rows.append({'line': line_name, 'department': machines[0].get('department'),
                     'date': date, 'planned_hours': round(planned, 2), 'machines_count': len(machines)})
    if not req.apply:
        return {'preview': True, 'valid_rows': len(rows), 'errors': errors, 'rows': rows[:100]}
    if errors:
        raise HTTPException(status_code=400, detail=f'{len(errors)} validation errors; fix before applying: ' + '; '.join(errors[:5]))
    affected_lines = set()
    for r in rows:
        log = {**r, 'id': str(uuid.uuid4()), 'entered_by': user['username'], 'source': 'csv_import',
               'created_at': now_iso(), 'updated_at': now_iso()}
        await db.line_runtime_logs.update_one({'line': r['line'], 'date': r['date']}, {'$set': log}, upsert=True)
        affected_lines.add(r['line'])
    machines_affected = 0
    for ln in affected_lines:
        machines_affected += await _recompute_line_reliability(ln)
    await create_timeline_event('runtime_imported', title=f'Planned runtime CSV imported ({len(rows)} rows)',
                                description=f'{machines_affected} machines affected', user=user['username'])
    return {'preview': False, 'imported': len(rows), 'machines_affected': machines_affected}


@router.get('/runtime-templates')
async def list_runtime_templates(user: dict = Depends(get_current_user)):
    return await db.runtime_templates.find({}, {'_id': 0}).to_list(100)


# ============ ANALYTICS ============
def scope_query(level: str, value: Optional[str]):
    if level == 'plant' or not value:
        return {}
    key = {'department': 'department', 'line': 'line', 'process_group': 'process_group', 'machine': 'machine_id'}.get(level)
    if not key:
        raise HTTPException(status_code=400, detail='Invalid level')
    return {key: value}


@router.get('/analytics/kpis')
async def analytics_kpis(level: str = 'plant', value: Optional[str] = None,
                         date_from: Optional[str] = None, date_to: Optional[str] = None,
                         user: dict = Depends(get_current_user)):
    """Multi-level KPIs. `date_from`/`date_to` (YYYY-MM-DD, inclusive) slice ALL
    charts/KPIs on the page. Availability uses the shared KPI engine — the same
    single runtime source of truth as the Control Room (logged line days override,
    otherwise live 24/7 assumption)."""
    q = scope_query(level, value)

    def in_range_date(d):
        if not d:
            return False
        d = str(d)[:10]
        if date_from and d < date_from:
            return False
        if date_to and d > date_to:
            return False
        return True

    bd_q = dict(q)
    if date_from or date_to:
        rng = {}
        if date_from:
            rng['$gte'] = date_from
        if date_to:
            rng['$lte'] = date_to + 'T23:59:59.999999+00:00'
        bd_q['start_time'] = rng

    breakdowns = await db.breakdowns.find(bd_q, {'_id': 0}).to_list(100000)
    closed = [b for b in breakdowns if b.get('downtime_minutes') is not None]
    failures = len(breakdowns)
    total_downtime_min = sum(b['downtime_minutes'] for b in closed)
    mttr_hours = round(total_downtime_min / len(closed) / 60, 2) if closed else None

    # ---- Closure rate within the selected range: reported vs closed ----
    closed_in_range = len([b for b in breakdowns if b.get('status') in ('COMPLETED', 'CLOSED')])
    closure_rate = round(closed_in_range / failures * 100, 1) if failures else None

    # ---- Runtime (single source of truth: PLANNED-RUNTIME model) ----
    # Runtime is line-wise; machine/PG/department scopes map to their parent line(s).
    lines_scope = None  # None = all lines (plant)
    if value and level != 'plant':
        if level == 'line':
            lines_scope = [value]
        else:
            mq = {'id': value} if level == 'machine' else {level: value}
            ms = await db.machines.find(mq, {'_id': 0, 'line': 1}).to_list(100000)
            lines_scope = sorted({m['line'] for m in ms if m.get('line')}) or ['__none__']
    from kpi_engine import derive_line_day_rows
    rt_rows = await derive_line_day_rows(lines=lines_scope, date_from=date_from, date_to=date_to)
    run_hours = round(sum(r['run_hours'] for r in rt_rows), 1)
    planned_hours = round(sum(r['planned_hours'] for r in rt_rows), 1)

    # availability: plant/line scopes use the SHARED KPI ENGINE (identical to Control Room)
    availability = None
    if level in ('plant', 'line'):
        from datetime import datetime, timezone, timedelta
        from kpi_engine import compute_line_kpis
        now = datetime.now(timezone.utc)
        since = datetime.fromisoformat(date_from).replace(tzinfo=timezone.utc) if date_from else now - timedelta(hours=24)
        until = (datetime.fromisoformat(date_to).replace(tzinfo=timezone.utc) + timedelta(days=1)) if date_to else now
        until = min(until, now)
        if until > since:
            engine = await compute_line_kpis(since, until)
            if level == 'plant':
                availability = engine['plant_availability']
            else:
                row = next((l for l in engine['lines'] if l['line'] == value), None)
                availability = row['availability'] if row else None
    if availability is None and planned_hours:
        # scope fallback over logged line-days: (Σplanned − Σdowntime)/Σplanned, day-clamped
        availability = round(run_hours / planned_hours * 100, 1)

    # ---- MTBF ----
    # MACHINE level: UNIFIED with the AWS/reliability engine — reads the SAME
    # TBF-based MTBF (mean run-hours between consecutive failures, driving
    # category) from reliability_metrics that the AWS page displays, so the two
    # modules always agree. This is a lifetime reliability metric: the date
    # slicer intentionally does not re-window it.
    # Aggregate levels (plant/line/dept/PG) keep the run_hours ÷ failures form,
    # since inter-failure intervals are not meaningful across mixed machines.
    mtbf = None
    mtbf_source = 'aggregate'
    if level == 'machine':
        rm = await db.reliability_metrics.find_one({'machine_id': value}, {'_id': 0, 'mtbf': 1})
        if rm and rm.get('mtbf') is not None:
            mtbf = rm['mtbf']
            mtbf_source = 'reliability_engine'
        elif failures and run_hours:
            # fallback only when the engine has not computed metrics yet
            mtbf = round(run_hours / failures, 1)
    elif failures and run_hours:
        mtbf = round(run_hours / failures, 1)
    failure_rate = round(failures / run_hours * 1000, 3) if run_hours else None  # failures per 1000 run-hours

    # PM compliance
    pm_q = dict(q)
    completions = await db.pm_completions.find(pm_q, {'_id': 0}).to_list(100000)
    if date_from or date_to:
        completions = [c for c in completions if in_range_date(c.get('completed_at'))]
    on_time = len([c for c in completions if c.get('on_time')])
    today = now_iso()[:10]
    overdue_now = await db.pm_tasks.count_documents({**q, 'active': True, 'next_due_date': {'$lt': today}})
    denom = len(completions) + overdue_now
    pm_compliance = round(on_time / denom * 100, 1) if denom else None

    # monthly trends (downtime + failures)
    downtime_by_month = defaultdict(float)
    failures_by_month = defaultdict(int)
    for b in breakdowns:
        month = (b.get('start_time') or b.get('created_at', ''))[:7]
        if month:
            failures_by_month[month] += 1
            if b.get('downtime_minutes'):
                downtime_by_month[month] += b['downtime_minutes']
    months = sorted(set(list(downtime_by_month) + list(failures_by_month)))[-12:]
    downtime_trend = [{'month': m, 'downtime_hours': round(downtime_by_month.get(m, 0) / 60, 1)} for m in months]
    failure_trend = [{'month': m, 'failures': failures_by_month.get(m, 0)} for m in months]

    # availability trend by month (planned-runtime model, respects date slice)
    trend_map = defaultdict(lambda: {'run': 0.0, 'planned': 0.0})
    for r in rt_rows:
        mth = str(r['date'])[:7]
        trend_map[mth]['run'] += r['run_hours']
        trend_map[mth]['planned'] += r['planned_hours']
    availability_trend = [{'month': m, 'availability': round(v['run'] / v['planned'] * 100, 1) if v['planned'] else 0}
                          for m, v in sorted(trend_map.items())][-12:]

    # top failing machines in scope (respects date slice)
    top_map = defaultdict(lambda: {'failures': 0, 'downtime': 0.0, 'name': ''})
    for b in breakdowns:
        t = top_map[b['machine_id']]
        t['failures'] += 1
        t['downtime'] += b.get('downtime_minutes') or 0
        t['name'] = b.get('machine_name') or t['name']
    top_failing = [{'machine_id': mid, 'machine_name': t['name'], 'failures': t['failures'],
                    'downtime_hours': round(t['downtime'] / 60, 1)}
                   for mid, t in sorted(top_map.items(), key=lambda kv: -kv[1]['failures'])[:10]]

    # failure modes distribution (respects date slice)
    fm_map = defaultdict(lambda: {'count': 0, 'downtime': 0.0})
    for b in breakdowns:
        fm = fm_map[b.get('failure_mode') or 'Unknown']
        fm['count'] += 1
        fm['downtime'] += b.get('downtime_minutes') or 0
    failure_modes = [{'mode': m, 'count': v['count']} for m, v in sorted(fm_map.items(), key=lambda kv: -kv[1]['count'])[:10]]

    # ---- Pareto analysis: failure modes desc by TOTAL DOWNTIME + cumulative % overlay ----
    # Bars = downtime contribution per failure mode (NOT occurrence count); the
    # cumulative line = cumulative downtime share — classic 80/20 against downtime.
    pareto_rows = sorted(fm_map.items(), key=lambda kv: (-kv[1]['downtime'], -kv[1]['count']))
    total_downtime = sum(v['downtime'] for _, v in pareto_rows) or 1
    cum = 0.0
    pareto = []
    for mode, v in pareto_rows[:15]:
        cum += v['downtime']
        pareto.append({'mode': mode, 'count': v['count'],
                       'downtime_hours': round(v['downtime'] / 60, 1),
                       'cumulative_pct': round(cum / total_downtime * 100, 1)})

    return {
        'level': level, 'value': value, 'date_from': date_from, 'date_to': date_to,
        'mtbf_hours': mtbf, 'mtbf_source': mtbf_source, 'mttr_hours': mttr_hours, 'availability': availability,
        'failure_rate_per_1000h': failure_rate, 'pm_compliance': pm_compliance,
        'failures_total': failures, 'downtime_hours_total': round(total_downtime_min / 60, 1),
        'breakdowns_reported': failures, 'breakdowns_closed': closed_in_range, 'closure_rate': closure_rate,
        'run_hours': run_hours, 'planned_hours': planned_hours,
        'downtime_trend': downtime_trend, 'failure_trend': failure_trend,
        'availability_trend': availability_trend, 'top_failing_machines': top_failing,
        'failure_modes': failure_modes, 'pareto': pareto,
    }


# ============ TECHNICIAN ANALYTICS (ADMIN-ONLY) ============
@router.get('/analytics/technicians')
async def technician_analytics(date_from: Optional[str] = None, date_to: Optional[str] = None,
                               line: Optional[str] = None, department: Optional[str] = None,
                               wo_type: Optional[str] = None, user: dict = Depends(require_admin)):
    """Per-technician performance metrics. ADMIN-ONLY (enforced at role level, 403 otherwise).
    Covers breakdown handling, work order execution and PM compliance, filterable by
    date range, line/department and work order type."""
    settings = await db.settings.find_one({'id': 'reliability_settings'}, {'_id': 0}) or {}
    on_time_target = settings.get('root_cause_downtime_minutes', 30)

    def in_range(ts):
        if not ts:
            return False
        d = str(ts)[:10]
        if date_from and d < date_from:
            return False
        if date_to and d > date_to:
            return False
        return True

    techs = await db.users.find({'role': {'$in': ['technician', 'admin']}}, {'_id': 0, 'username': 1, 'name': 1}).to_list(1000)
    names = {t['username']: t.get('name') or t['username'] for t in techs}
    stats = defaultdict(lambda: {
        'breakdowns_resolved': 0, 'breakdown_repair_minutes': 0.0,
        'wo_completed': 0, 'wo_minutes': 0.0, 'wo_on_time': 0,
        'pm_completed': 0, 'pm_on_time': 0,
    })

    # Breakdowns handled (resolved = COMPLETED/CLOSED with an assigned technician)
    bd_q = {'status': {'$in': ['COMPLETED', 'CLOSED']}, 'assigned_to': {'$ne': None}}
    if line:
        bd_q['line'] = line
    if department:
        bd_q['department'] = department
    async for b in db.breakdowns.find(bd_q, {'_id': 0, 'assigned_to': 1, 'end_time': 1, 'repair_duration_minutes': 1, 'downtime_minutes': 1}):
        if (date_from or date_to) and not in_range(b.get('end_time')):
            continue
        s = stats[b['assigned_to']]
        s['breakdowns_resolved'] += 1
        s['breakdown_repair_minutes'] += b.get('repair_duration_minutes') or b.get('downtime_minutes') or 0

    # Work orders completed (excluding PM-generated to avoid double counting with PM section)
    wo_q = {'status': {'$in': ['COMPLETED', 'PENDING_ADMIN_CLOSURE', 'CLOSED']}, 'assigned_to': {'$ne': None}}
    if line:
        wo_q['line'] = line
    if department:
        wo_q['department'] = department
    if wo_type:
        wo_q['wo_type'] = wo_type
    async for w in db.work_orders.find(wo_q, {'_id': 0, 'assigned_to': 1, 'completed_at': 1, 'duration_minutes': 1}):
        if (date_from or date_to) and not in_range(w.get('completed_at')):
            continue
        s = stats[w['assigned_to']]
        s['wo_completed'] += 1
        dur = w.get('duration_minutes') or 0
        s['wo_minutes'] += dur
        if dur <= on_time_target:
            s['wo_on_time'] += 1

    # PM completions + compliance (on_time flag captured at completion time)
    pm_q = {}
    if line:
        pm_q['line'] = line
    async for c in db.pm_completions.find(pm_q, {'_id': 0, 'completed_by': 1, 'completed_at': 1, 'on_time': 1}):
        if (date_from or date_to) and not in_range(c.get('completed_at')):
            continue
        s = stats[c['completed_by']]
        s['pm_completed'] += 1
        if c.get('on_time'):
            s['pm_on_time'] += 1

    rows = []
    for tech, s in stats.items():
        total_minutes = s['breakdown_repair_minutes'] + s['wo_minutes']
        rows.append({
            'technician': tech, 'name': names.get(tech, tech),
            'breakdowns_resolved': s['breakdowns_resolved'],
            'avg_repair_minutes': round(s['breakdown_repair_minutes'] / s['breakdowns_resolved'], 1) if s['breakdowns_resolved'] else None,
            'total_repair_minutes': round(s['breakdown_repair_minutes'], 1),
            'wo_completed': s['wo_completed'],
            'wo_avg_minutes': round(s['wo_minutes'] / s['wo_completed'], 1) if s['wo_completed'] else None,
            'wo_total_minutes': round(s['wo_minutes'], 1),
            'wo_on_time_rate': round(s['wo_on_time'] / s['wo_completed'] * 100, 1) if s['wo_completed'] else None,
            'pm_completed': s['pm_completed'],
            'pm_compliance_rate': round(s['pm_on_time'] / s['pm_completed'] * 100, 1) if s['pm_completed'] else None,
            'total_hours': round(total_minutes / 60, 1),
        })
    rows.sort(key=lambda r: (-r['breakdowns_resolved'], -r['wo_completed']))
    for i, r in enumerate(rows, start=1):
        r['rank'] = i
    return {'technicians': rows, 'on_time_target_minutes': on_time_target,
            'filters': {'date_from': date_from, 'date_to': date_to, 'line': line, 'department': department, 'wo_type': wo_type}}


# ============ RELIABILITY / AWS ============
@router.get('/reliability/metrics')
async def reliability_metrics(health: Optional[str] = None, line: Optional[str] = None,
                              category: Optional[str] = None,
                              limit: int = Query(500, le=5000), user: dict = Depends(require_admin_or_tech)):
    q = {}
    if health:
        q['health'] = health
    if line:
        q['line'] = line
    items = await db.reliability_metrics.find(q, {'_id': 0}).sort('life_pct', -1).limit(limit).to_list(limit)
    # Failure category counts per machine (MECHANICAL / ELECTRICAL / CONTROL_PLC)
    agg = await db.breakdowns.aggregate([
        {'$group': {'_id': {'m': '$machine_id', 'c': {'$ifNull': ['$breakdown_type', 'MECHANICAL']}}, 'n': {'$sum': 1}}},
    ]).to_list(100000)
    cat_map = defaultdict(dict)
    for row in agg:
        cat_map[row['_id']['m']][row['_id']['c']] = row['n']
    for m in items:
        cats = cat_map.get(m['machine_id'], {})
        m['failure_categories'] = cats
        m['dominant_category'] = max(sorted(cats), key=lambda c: cats[c]) if cats else None
    if category:
        # category filter matches machines with an ACTIVE pool for that category
        items = [m for m in items if category in (m.get('categories') or {}) or m.get('dominant_category') == category]
    return items


@router.get('/reliability/metrics/{machine_id}')
async def machine_reliability(machine_id: str, user: dict = Depends(get_current_user)):
    metrics = await db.reliability_metrics.find_one({'machine_id': machine_id}, {'_id': 0})
    models = await db.weibull_models.find({'machine_id': machine_id}, {'_id': 0}).sort('fitted_at', -1).limit(5).to_list(5)
    curve = []
    if metrics and metrics.get('weibull'):
        import math
        beta, eta = metrics['weibull']['beta'], metrics['weibull']['eta']
        max_t = eta * 2.5
        for i in range(0, 51):
            t = max_t * i / 50
            r = math.exp(-((t / eta) ** beta)) if t > 0 else 1.0
            h = (beta / eta) * ((t / eta) ** (beta - 1)) if t > 0 else 0
            curve.append({'t': round(t, 1), 'reliability': round(r, 4), 'hazard': round(h, 6)})
    return {'metrics': metrics, 'weibull_history': models, 'curve': curve}


@router.post('/reliability/recompute')
async def recompute_reliability(machine_id: Optional[str] = None, user: dict = Depends(require_admin)):
    from reliability import recompute_machine_reliability, recompute_all
    if machine_id:
        m = await recompute_machine_reliability(machine_id, trigger='manual')
        return {'ok': True, 'metrics': m}
    await recompute_all(trigger='manual')
    return {'ok': True}


@router.get('/reliability/settings')
async def get_reliability_settings(user: dict = Depends(require_admin_or_tech)):
    return await db.settings.find_one({'id': 'reliability_settings'}, {'_id': 0})


class ReliabilitySettings(BaseModel):
    healthy_threshold_pct: Optional[float] = None
    watch_threshold_pct: Optional[float] = None
    inspection_threshold_pct: Optional[float] = None
    alert_trigger_pct: Optional[float] = None
    predictive_trigger_pct: Optional[float] = None  # AWS Predictive WO trigger (admin-configurable, default 80)
    level2_min_failures: Optional[int] = None
    level3_min_failures: Optional[int] = None
    rolling_window: Optional[int] = None
    root_cause_downtime_minutes: Optional[float] = None


@router.put('/reliability/settings')
async def update_reliability_settings(req: ReliabilitySettings, user: dict = Depends(require_admin)):
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    updates['updated_at'] = now_iso()
    await db.settings.update_one({'id': 'reliability_settings'}, {'$set': updates})
    return await db.settings.find_one({'id': 'reliability_settings'}, {'_id': 0})
