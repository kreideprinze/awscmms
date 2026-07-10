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


# ============ RUNTIME (LINE-LEVEL) ============
# Runtime is logged PER LINE (one entry per line per day). Availability is computed from
# line run hours vs calendar hours. Each machine in the line inherits the line runtime
# (fanned out into runtime_logs) so per-machine Weibull/reliability computations keep working.
class RuntimeLogCreate(BaseModel):
    line: Optional[str] = None       # line name (preferred entry mode)
    machine_id: Optional[str] = None  # legacy per-machine entry (still accepted)
    date: str  # YYYY-MM-DD
    calendar_hours: float = 24.0
    run_hours: float


async def _fan_out_line_runtime(line_name, machines, date, cal_h, run_h, username, source='line'):
    """Upsert a per-machine runtime log for every machine in the line (machines inherit line runtime)."""
    dark = round(cal_h - run_h, 2)
    for m in machines:
        log = {
            'id': str(uuid.uuid4()), 'machine_id': m['id'], 'machine_name': m['name'],
            'department': m['department'], 'line': m['line'], 'process_group': m.get('process_group'),
            'date': date, 'calendar_hours': cal_h, 'run_hours': run_h,
            'dark_hours': dark, 'availability': round(run_h / cal_h * 100, 1),
            'entered_by': username, 'source': source, 'created_at': now_iso(),
        }
        await db.runtime_logs.update_one({'machine_id': m['id'], 'date': date}, {'$set': log}, upsert=True)


@router.post('/runtime-logs')
async def create_runtime_log(req: RuntimeLogCreate, user: dict = Depends(require_admin)):
    if req.run_hours < 0 or req.calendar_hours <= 0 or req.run_hours > req.calendar_hours:
        raise HTTPException(status_code=400, detail='Invalid hours: run_hours must be 0..calendar_hours')
    dark = round(req.calendar_hours - req.run_hours, 2)

    if req.line:
        machines = await db.machines.find({'line': req.line}, {'_id': 0}).to_list(2000)
        if not machines:
            raise HTTPException(status_code=404, detail=f'No machines found for line "{req.line}"')
        line_log = {
            'id': str(uuid.uuid4()), 'line': req.line, 'department': machines[0]['department'],
            'date': req.date, 'calendar_hours': req.calendar_hours, 'run_hours': req.run_hours,
            'dark_hours': dark, 'availability': round(req.run_hours / req.calendar_hours * 100, 1),
            'machines_count': len(machines), 'entered_by': user['username'], 'source': 'manual', 'created_at': now_iso(),
        }
        await db.line_runtime_logs.update_one({'line': req.line, 'date': req.date}, {'$set': line_log}, upsert=True)
        await _fan_out_line_runtime(req.line, machines, req.date, req.calendar_hours, req.run_hours, user['username'])
        from reliability import recompute_machine_reliability
        for m in machines:
            await recompute_machine_reliability(m['id'], trigger='runtime_log')
        line_log.pop('_id', None)
        return line_log

    # legacy per-machine entry (kept for compatibility)
    if not req.machine_id:
        raise HTTPException(status_code=400, detail='line (preferred) or machine_id is required')
    machine = await db.machines.find_one({'id': req.machine_id}, {'_id': 0})
    if not machine:
        raise HTTPException(status_code=404, detail='Machine not found')
    log = {
        'id': str(uuid.uuid4()), 'machine_id': machine['id'], 'machine_name': machine['name'],
        'department': machine['department'], 'line': machine['line'], 'process_group': machine.get('process_group'),
        'date': req.date, 'calendar_hours': req.calendar_hours, 'run_hours': req.run_hours,
        'dark_hours': dark, 'availability': round(req.run_hours / req.calendar_hours * 100, 1),
        'entered_by': user['username'], 'source': 'manual', 'created_at': now_iso(),
    }
    # upsert per machine+date
    await db.runtime_logs.update_one({'machine_id': machine['id'], 'date': req.date}, {'$set': log}, upsert=True)
    await db.machines.update_one({'id': machine['id']}, {'$inc': {'total_run_hours': req.run_hours}})
    from reliability import recompute_machine_reliability
    await recompute_machine_reliability(machine['id'], trigger='runtime_log')
    return log


@router.get('/line-runtime-logs')
async def list_line_runtime_logs(line: Optional[str] = None, date_from: Optional[str] = None,
                                 date_to: Optional[str] = None, limit: int = Query(500, le=5000), skip: int = 0,
                                 user: dict = Depends(get_current_user)):
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
    return {'items': items, 'total': total}


@router.get('/runtime-logs')
async def list_runtime_logs(machine_id: Optional[str] = None, line: Optional[str] = None,
                            date_from: Optional[str] = None, date_to: Optional[str] = None,
                            limit: int = Query(500, le=5000), skip: int = 0, user: dict = Depends(get_current_user)):
    q = {}
    if machine_id:
        q['machine_id'] = machine_id
    if line:
        q['line'] = line
    if date_from or date_to:
        q['date'] = {}
        if date_from:
            q['date']['$gte'] = date_from
        if date_to:
            q['date']['$lte'] = date_to
    total = await db.runtime_logs.count_documents(q)
    items = await db.runtime_logs.find(q, {'_id': 0}).sort('date', -1).skip(skip).limit(limit).to_list(limit)
    for it in items:  # auto-accumulated logs compute availability on read
        cal = it.get('calendar_hours') or 0
        run = it.get('run_hours') or 0
        it['calendar_hours'] = round(cal, 2)
        it['run_hours'] = round(run, 2)
        it['dark_hours'] = round(it.get('dark_hours') or (cal - run), 2)
        it['availability'] = it.get('availability') if it.get('source') in ('manual', 'csv_import') else (round(run / cal * 100, 1) if cal else 0)
    return {'items': items, 'total': total}


class RuntimeCSV(BaseModel):
    csv_text: str
    apply: bool = False


@router.post('/runtime-logs/import')
async def import_runtime_csv(req: RuntimeCSV, user: dict = Depends(require_admin)):
    """CSV columns: line, date, run_hours[, calendar_hours]. Preview unless apply=true.
    Each line entry fans out to all machines in that line (machines inherit line runtime)."""
    reader = csv.DictReader(io.StringIO(req.csv_text.strip()))
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail='Empty CSV')
    cols = [c.strip().lower() for c in reader.fieldnames]
    required = {'line', 'date', 'run_hours'}
    if not required.issubset(set(cols)):
        raise HTTPException(status_code=400, detail=f'Missing columns. Required: line, date, run_hours. Found: {cols}')
    all_machines = await db.machines.find({}, {'_id': 0}).to_list(20000)
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
            run_h = float(row['run_hours'])
            cal_h = float(row.get('calendar_hours') or 24)
            if run_h < 0 or cal_h <= 0 or run_h > cal_h:
                raise ValueError()
        except ValueError:
            errors.append(f'Row {i}: invalid hours (run={row.get("run_hours")}, cal={row.get("calendar_hours")})')
            continue
        date = row.get('date', '')
        try:
            datetime.fromisoformat(date)
        except ValueError:
            errors.append(f'Row {i}: invalid date \u201c{date}\u201d (use YYYY-MM-DD)')
            continue
        rows.append({'line': line_name, 'department': machines[0]['department'],
                     'date': date, 'calendar_hours': cal_h, 'run_hours': run_h,
                     'dark_hours': round(cal_h - run_h, 2), 'availability': round(run_h / cal_h * 100, 1),
                     'machines_count': len(machines)})
    if not req.apply:
        return {'preview': True, 'valid_rows': len(rows), 'errors': errors, 'rows': rows[:100]}
    if errors:
        raise HTTPException(status_code=400, detail=f'{len(errors)} validation errors; fix before applying: ' + '; '.join(errors[:5]))
    affected = set()
    for r in rows:
        log = {**r, 'id': str(uuid.uuid4()), 'entered_by': user['username'], 'source': 'csv_import', 'created_at': now_iso()}
        await db.line_runtime_logs.update_one({'line': r['line'], 'date': r['date']}, {'$set': log}, upsert=True)
        machines = by_line[r['line']]
        await _fan_out_line_runtime(r['line'], machines, r['date'], r['calendar_hours'], r['run_hours'], user['username'], source='csv_import')
        affected.update(m['id'] for m in machines)
    from reliability import recompute_machine_reliability
    for mid in affected:
        await recompute_machine_reliability(mid, trigger='runtime_import')
    await create_timeline_event('runtime_imported', title=f'Line runtime CSV imported ({len(rows)} rows)',
                                description=f'{len(affected)} machines affected', user=user['username'])
    return {'preview': False, 'imported': len(rows), 'machines_affected': len(affected)}


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
async def analytics_kpis(level: str = 'plant', value: Optional[str] = None, user: dict = Depends(get_current_user)):
    q = scope_query(level, value)

    breakdowns = await db.breakdowns.find(q, {'_id': 0}).to_list(100000)
    closed = [b for b in breakdowns if b.get('downtime_minutes') is not None]
    failures = len(breakdowns)
    total_downtime_min = sum(b['downtime_minutes'] for b in closed)
    mttr_hours = round(total_downtime_min / len(closed) / 60, 2) if closed else None

    rt = await db.runtime_logs.aggregate([
        {'$match': q}, {'$group': {'_id': None, 'run': {'$sum': '$run_hours'}, 'cal': {'$sum': '$calendar_hours'}}},
    ]).to_list(1)
    run_hours = round(rt[0]['run'], 1) if rt else 0
    cal_hours = round(rt[0]['cal'], 1) if rt else 0
    availability = round(run_hours / cal_hours * 100, 1) if cal_hours else None
    mtbf = round(run_hours / failures, 1) if failures and run_hours else None
    failure_rate = round(failures / run_hours * 1000, 3) if run_hours else None  # failures per 1000 run-hours

    # PM compliance
    pm_q = dict(q)
    completions = await db.pm_completions.find(pm_q, {'_id': 0}).to_list(100000)
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

    # availability trend by month
    avail_agg = await db.runtime_logs.aggregate([
        {'$match': q},
        {'$group': {'_id': {'$substr': ['$date', 0, 7]}, 'run': {'$sum': '$run_hours'}, 'cal': {'$sum': '$calendar_hours'}}},
        {'$sort': {'_id': 1}},
    ]).to_list(100)
    availability_trend = [{'month': a['_id'], 'availability': round(a['run'] / a['cal'] * 100, 1) if a['cal'] else 0} for a in avail_agg][-12:]

    # top failing machines in scope
    top_agg = await db.breakdowns.aggregate([
        {'$match': q},
        {'$group': {'_id': {'id': '$machine_id', 'name': '$machine_name'}, 'failures': {'$sum': 1}, 'downtime': {'$sum': {'$ifNull': ['$downtime_minutes', 0]}}}},
        {'$sort': {'failures': -1}}, {'$limit': 10},
    ]).to_list(10)
    top_failing = [{'machine_id': t['_id']['id'], 'machine_name': t['_id']['name'], 'failures': t['failures'], 'downtime_hours': round(t['downtime'] / 60, 1)} for t in top_agg]

    # failure modes distribution
    fm_agg = await db.breakdowns.aggregate([
        {'$match': q}, {'$group': {'_id': '$failure_mode', 'count': {'$sum': 1}}}, {'$sort': {'count': -1}}, {'$limit': 10},
    ]).to_list(10)
    failure_modes = [{'mode': f['_id'] or 'Unknown', 'count': f['count']} for f in fm_agg]

    return {
        'level': level, 'value': value,
        'mtbf_hours': mtbf, 'mttr_hours': mttr_hours, 'availability': availability,
        'failure_rate_per_1000h': failure_rate, 'pm_compliance': pm_compliance,
        'failures_total': failures, 'downtime_hours_total': round(total_downtime_min / 60, 1),
        'run_hours': run_hours, 'calendar_hours': cal_hours,
        'downtime_trend': downtime_trend, 'failure_trend': failure_trend,
        'availability_trend': availability_trend, 'top_failing_machines': top_failing,
        'failure_modes': failure_modes,
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
    # Failure category distribution (MECHANICAL / ELECTRICAL / CONTROL_PLC) per machine
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
        items = [m for m in items if m.get('dominant_category') == category]
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
