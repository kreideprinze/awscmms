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


# ============ RUNTIME ============
class RuntimeLogCreate(BaseModel):
    machine_id: str
    date: str  # YYYY-MM-DD
    calendar_hours: float = 24.0
    run_hours: float


@router.post('/runtime-logs')
async def create_runtime_log(req: RuntimeLogCreate, user: dict = Depends(require_admin)):
    machine = await db.machines.find_one({'id': req.machine_id}, {'_id': 0})
    if not machine:
        raise HTTPException(status_code=404, detail='Machine not found')
    if req.run_hours < 0 or req.calendar_hours <= 0 or req.run_hours > req.calendar_hours:
        raise HTTPException(status_code=400, detail='Invalid hours: run_hours must be 0..calendar_hours')
    dark = round(req.calendar_hours - req.run_hours, 2)
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
    """CSV columns: machine_code, date, run_hours[, calendar_hours]. Preview unless apply=true."""
    reader = csv.DictReader(io.StringIO(req.csv_text.strip()))
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail='Empty CSV')
    cols = [c.strip().lower() for c in reader.fieldnames]
    required = {'machine_code', 'date', 'run_hours'}
    if not required.issubset(set(cols)):
        raise HTTPException(status_code=400, detail=f'Missing columns. Required: machine_code, date, run_hours. Found: {cols}')
    rows, errors = [], []
    machines = {m['code']: m for m in await db.machines.find({}, {'_id': 0}).to_list(20000)}
    for i, raw in enumerate(reader, start=2):
        row = {k.strip().lower(): (v or '').strip() for k, v in raw.items()}
        code = row.get('machine_code', '')
        m = machines.get(code)
        if not m:
            errors.append(f'Row {i}: unknown machine_code \u201c{code}\u201d')
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
        rows.append({'machine_id': m['id'], 'machine_name': m['name'], 'machine_code': code,
                     'department': m['department'], 'line': m['line'], 'process_group': m.get('process_group'),
                     'date': date, 'calendar_hours': cal_h, 'run_hours': run_h,
                     'dark_hours': round(cal_h - run_h, 2), 'availability': round(run_h / cal_h * 100, 1)})
    if not req.apply:
        return {'preview': True, 'valid_rows': len(rows), 'errors': errors, 'rows': rows[:100]}
    if errors:
        raise HTTPException(status_code=400, detail=f'{len(errors)} validation errors; fix before applying: ' + '; '.join(errors[:5]))
    affected = set()
    for r in rows:
        log = {**r, 'id': str(uuid.uuid4()), 'entered_by': user['username'], 'source': 'csv_import', 'created_at': now_iso()}
        await db.runtime_logs.update_one({'machine_id': r['machine_id'], 'date': r['date']}, {'$set': log}, upsert=True)
        affected.add(r['machine_id'])
    from reliability import recompute_machine_reliability
    for mid in affected:
        await recompute_machine_reliability(mid, trigger='runtime_import')
    await create_timeline_event('runtime_imported', title=f'Runtime CSV imported ({len(rows)} rows)',
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


# ============ RELIABILITY / AWS ============
@router.get('/reliability/metrics')
async def reliability_metrics(health: Optional[str] = None, line: Optional[str] = None,
                              limit: int = Query(500, le=5000), user: dict = Depends(require_admin_or_tech)):
    q = {}
    if health:
        q['health'] = health
    if line:
        q['line'] = line
    return await db.reliability_metrics.find(q, {'_id': 0}).sort('life_pct', -1).limit(limit).to_list(limit)


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
