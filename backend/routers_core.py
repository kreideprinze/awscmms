"""Core routes: auth, hierarchy (read), machines, reports, notes, documents, timeline, notifications."""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from auth import get_current_user, require_admin, require_admin_or_tech, verify_password, create_token
from database import db
from events import create_timeline_event, create_notification, broadcast_machine_update, now_iso

router = APIRouter()


# ---------------- AUTH ----------------
class LoginRequest(BaseModel):
    username: str
    password: str


@router.post('/auth/login')
async def login(req: LoginRequest):
    user = await db.users.find_one({'username': req.username}, {'_id': 0})
    if not user or not user.get('active', True) or not verify_password(req.password, user['password']):
        raise HTTPException(status_code=401, detail='Invalid username or password')
    token = create_token(user)
    return {'token': token, 'user': {'id': user['id'], 'username': user['username'], 'role': user['role'], 'name': user.get('name')}}


@router.get('/auth/me')
async def me(user: dict = Depends(get_current_user)):
    return user


# ---------------- HIERARCHY (read; admin CRUD lives in admin router) ----------------
@router.get('/hierarchy')
async def get_hierarchy(user: dict = Depends(get_current_user)):
    """Line-first hierarchy: Line → Department → Process Group → Machine.
    Lines are top-level; departments are per-line sub-records (line/line_id on each)."""
    lines = await db.lines.find({}, {'_id': 0}).sort('order', 1).to_list(10000)
    departments = await db.departments.find({}, {'_id': 0}).sort([('line', 1), ('order', 1)]).to_list(10000)
    process_groups = await db.process_groups.find({}, {'_id': 0}).sort('order', 1).to_list(100000)
    return {'lines': lines, 'departments': departments, 'process_groups': process_groups}


# ---------------- MACHINES ----------------
@router.get('/machines')
async def list_machines(department: Optional[str] = None, line: Optional[str] = None,
                        process_group: Optional[str] = None, status: Optional[str] = None,
                        search: Optional[str] = None, limit: int = Query(5000, le=20000), skip: int = 0,
                        user: dict = Depends(get_current_user)):
    q = {}
    if department:
        q['department'] = department
    if line:
        q['line'] = line
    if process_group:
        q['process_group'] = process_group
    if status:
        q['status'] = status
    if search:
        q['$or'] = [{'name': {'$regex': search, '$options': 'i'}}, {'code': {'$regex': search, '$options': 'i'}}, {'sap_code': {'$regex': search, '$options': 'i'}}]
    return await db.machines.find(q, {'_id': 0}).skip(skip).limit(limit).to_list(limit)


@router.get('/machines/{machine_id}')
async def get_machine(machine_id: str, user: dict = Depends(get_current_user)):
    m = await db.machines.find_one({'id': machine_id}, {'_id': 0})
    if not m:
        raise HTTPException(status_code=404, detail='Machine not found')
    metrics = await db.reliability_metrics.find_one({'machine_id': machine_id}, {'_id': 0})
    counts = {
        'reports': await db.machine_reports.count_documents({'machine_id': machine_id}),
        'breakdowns': await db.breakdowns.count_documents({'machine_id': machine_id}),
        'open_breakdowns': await db.breakdowns.count_documents({'machine_id': machine_id, 'status': {'$in': ['OPEN', 'ASSIGNED', 'IN_PROGRESS']}}),
        'work_orders': await db.work_orders.count_documents({'machine_id': machine_id}),
        'open_work_orders': await db.work_orders.count_documents({'machine_id': machine_id, 'status': {'$in': ['OPEN', 'ASSIGNED', 'IN_PROGRESS']}}),
        'pm_tasks': await db.pm_tasks.count_documents({'machine_id': machine_id, 'active': True}),
        'notes': await db.machine_notes.count_documents({'machine_id': machine_id}),
    }
    # runtime summary
    pipeline = [{'$match': {'machine_id': machine_id}}, {'$group': {'_id': None, 'run': {'$sum': '$run_hours'}, 'cal': {'$sum': '$calendar_hours'}}}]
    agg = await db.runtime_logs.aggregate(pipeline).to_list(1)
    runtime = {'run_hours': round(agg[0]['run'], 1) if agg else 0, 'calendar_hours': round(agg[0]['cal'], 1) if agg else 0}
    runtime['availability'] = round(runtime['run_hours'] / runtime['calendar_hours'] * 100, 1) if runtime['calendar_hours'] else None
    return {'machine': m, 'reliability': metrics, 'counts': counts, 'runtime': runtime}


class StatusUpdate(BaseModel):
    status: str


@router.put('/machines/{machine_id}/status')
async def update_machine_status(machine_id: str, req: StatusUpdate, user: dict = Depends(require_admin_or_tech)):
    valid = ['running', 'watch', 'inspection_due', 'repair', 'failed', 'idle']
    if req.status not in valid:
        raise HTTPException(status_code=400, detail=f'Invalid status. Valid: {valid}')
    m = await db.machines.find_one({'id': machine_id}, {'_id': 0})
    if not m:
        raise HTTPException(status_code=404, detail='Machine not found')
    old = m.get('status')
    await db.machines.update_one({'id': machine_id}, {'$set': {'status': req.status}})
    await db.machine_status.insert_one({'id': str(uuid.uuid4()), 'machine_id': machine_id, 'machine_name': m['name'],
                                        'old_status': old, 'new_status': req.status, 'changed_by': user['username'], 'created_at': now_iso()})
    m['status'] = req.status
    await broadcast_machine_update(m)
    await create_timeline_event('status_changed', machine_id=machine_id, machine_name=m['name'],
                                title=f"Status: {old} \u2192 {req.status}", description=f"Changed by {user['username']}",
                                user=user['username'], department=m.get('department'), line=m.get('line'))
    return {'ok': True, 'status': req.status}


# ---------------- MACHINE REPORTS ----------------
class ReportCreate(BaseModel):
    machine_id: str
    error_code: str
    description: str


@router.get('/error-codes')
async def list_error_codes(user: dict = Depends(get_current_user)):
    return await db.error_codes.find({'active': True}, {'_id': 0}).to_list(1000)


@router.post('/reports')
async def create_report(req: ReportCreate, user: dict = Depends(get_current_user)):
    m = await db.machines.find_one({'id': req.machine_id}, {'_id': 0})
    if not m:
        raise HTTPException(status_code=404, detail='Machine not found')
    from events import next_counter
    code = await next_counter('reports', 'RPT')
    report = {
        'id': str(uuid.uuid4()), 'report_number': code,
        'machine_id': m['id'], 'machine_name': m['name'], 'department': m['department'], 'line': m['line'],
        'error_code': req.error_code, 'description': req.description,
        'reporter': user['username'], 'status': 'PENDING_REVIEW',
        'reviewed_by': None, 'review_notes': None, 'converted_breakdown_id': None,
        'created_at': now_iso(),
    }
    await db.machine_reports.insert_one(dict(report))
    await create_timeline_event('report_created', machine_id=m['id'], machine_name=m['name'],
                                title=f"Report {code}: {req.error_code}", description=req.description,
                                user=user['username'], reference_id=report['id'], reference_type='report',
                                department=m['department'], line=m['line'])
    await create_notification('report', f"New Report: {m['name']}", f"{code} [{req.error_code}] {req.description}",
                              severity='info', machine_id=m['id'], machine_name=m['name'],
                              reference_id=report['id'], reference_type='report')
    report.pop('_id', None)
    return report


@router.get('/reports')
async def list_reports(machine_id: Optional[str] = None, status: Optional[str] = None,
                       limit: int = Query(200, le=2000), skip: int = 0, user: dict = Depends(get_current_user)):
    q = {}
    if machine_id:
        q['machine_id'] = machine_id
    if status:
        q['status'] = status
    return await db.machine_reports.find(q, {'_id': 0}).sort('created_at', -1).skip(skip).limit(limit).to_list(limit)


class ReportReview(BaseModel):
    action: str  # dismiss | acknowledge | convert
    review_notes: Optional[str] = None
    failure_mode: Optional[str] = None


@router.put('/reports/{report_id}/review')
async def review_report(report_id: str, req: ReportReview, user: dict = Depends(require_admin_or_tech)):
    report = await db.machine_reports.find_one({'id': report_id}, {'_id': 0})
    if not report:
        raise HTTPException(status_code=404, detail='Report not found')
    if req.action == 'dismiss':
        await db.machine_reports.update_one({'id': report_id}, {'$set': {'status': 'DISMISSED', 'reviewed_by': user['username'], 'review_notes': req.review_notes, 'reviewed_at': now_iso()}})
        return {'ok': True, 'status': 'DISMISSED'}
    if req.action == 'acknowledge':
        await db.machine_reports.update_one({'id': report_id}, {'$set': {'status': 'ACKNOWLEDGED', 'reviewed_by': user['username'], 'review_notes': req.review_notes, 'reviewed_at': now_iso()}})
        return {'ok': True, 'status': 'ACKNOWLEDGED'}
    if req.action == 'convert':
        from routers_maintenance import _create_breakdown_internal
        bd = await _create_breakdown_internal(
            machine_id=report['machine_id'],
            description=f"[From report {report['report_number']}] {report['description']}",
            failure_mode=req.failure_mode or 'Blockage / Product Jam',
            reporter=user['username'],
        )
        await db.machine_reports.update_one({'id': report_id}, {'$set': {'status': 'CONVERTED', 'reviewed_by': user['username'], 'review_notes': req.review_notes, 'converted_breakdown_id': bd['id'], 'reviewed_at': now_iso()}})
        return {'ok': True, 'status': 'CONVERTED', 'breakdown': bd}
    raise HTTPException(status_code=400, detail='Invalid action')


# ---------------- MACHINE NOTES ----------------
class NoteCreate(BaseModel):
    machine_id: str
    text: str


@router.post('/notes')
async def create_note(req: NoteCreate, user: dict = Depends(get_current_user)):
    m = await db.machines.find_one({'id': req.machine_id}, {'_id': 0})
    if not m:
        raise HTTPException(status_code=404, detail='Machine not found')
    note = {'id': str(uuid.uuid4()), 'machine_id': m['id'], 'machine_name': m['name'],
            'text': req.text, 'author': user['username'], 'created_at': now_iso()}
    await db.machine_notes.insert_one(dict(note))
    await create_timeline_event('note_added', machine_id=m['id'], machine_name=m['name'],
                                title='Note added', description=req.text[:120], user=user['username'],
                                reference_id=note['id'], reference_type='note', department=m['department'], line=m['line'])
    note.pop('_id', None)
    return note


@router.get('/notes')
async def list_notes(machine_id: Optional[str] = None, limit: int = Query(200, le=2000), user: dict = Depends(get_current_user)):
    q = {'machine_id': machine_id} if machine_id else {}
    return await db.machine_notes.find(q, {'_id': 0}).sort('created_at', -1).limit(limit).to_list(limit)


# ---------------- MACHINE DOCUMENTS (metadata) ----------------
class DocCreate(BaseModel):
    machine_id: str
    title: str
    doc_type: str = 'manual'
    url: Optional[str] = None
    notes: Optional[str] = None


@router.post('/documents')
async def create_document(req: DocCreate, user: dict = Depends(require_admin_or_tech)):
    m = await db.machines.find_one({'id': req.machine_id}, {'_id': 0})
    if not m:
        raise HTTPException(status_code=404, detail='Machine not found')
    doc = {'id': str(uuid.uuid4()), 'machine_id': m['id'], 'machine_name': m['name'], 'title': req.title,
           'doc_type': req.doc_type, 'url': req.url, 'notes': req.notes, 'added_by': user['username'], 'created_at': now_iso()}
    await db.machine_documents.insert_one(dict(doc))
    doc.pop('_id', None)
    return doc


@router.get('/documents')
async def list_documents(machine_id: Optional[str] = None, user: dict = Depends(get_current_user)):
    q = {'machine_id': machine_id} if machine_id else {}
    return await db.machine_documents.find(q, {'_id': 0}).sort('created_at', -1).to_list(1000)


@router.delete('/documents/{doc_id}')
async def delete_document(doc_id: str, user: dict = Depends(require_admin)):
    await db.machine_documents.delete_one({'id': doc_id})
    return {'ok': True}


# ---------------- TIMELINE ----------------
@router.get('/timeline')
async def get_timeline(machine_id: Optional[str] = None, event_type: Optional[str] = None,
                       department: Optional[str] = None, line: Optional[str] = None,
                       limit: int = Query(100, le=1000), skip: int = 0, user: dict = Depends(get_current_user)):
    q = {}
    if machine_id:
        q['machine_id'] = machine_id
    if event_type:
        q['event_type'] = event_type
    if department:
        q['department'] = department
    if line:
        q['line'] = line
    return await db.timeline_events.find(q, {'_id': 0}).sort('created_at', -1).skip(skip).limit(limit).to_list(limit)


# ---------------- NOTIFICATIONS ----------------
@router.get('/notifications')
async def get_notifications(unread_only: bool = False, limit: int = Query(50, le=500), user: dict = Depends(get_current_user)):
    q = {}
    if unread_only:
        q['read_by'] = {'$ne': user['username']}
    return await db.notifications.find(q, {'_id': 0}).sort('created_at', -1).limit(limit).to_list(limit)


@router.put('/notifications/{notif_id}/read')
async def mark_read(notif_id: str, user: dict = Depends(get_current_user)):
    await db.notifications.update_one({'id': notif_id}, {'$addToSet': {'read_by': user['username']}})
    return {'ok': True}


@router.put('/notifications/read-all')
async def mark_all_read(user: dict = Depends(get_current_user)):
    await db.notifications.update_many({}, {'$addToSet': {'read_by': user['username']}})
    return {'ok': True}


# ---------------- CONTROL ROOM SUMMARY ----------------
@router.get('/control-room/summary')
async def control_room_summary(user: dict = Depends(get_current_user)):
    total = await db.machines.count_documents({})
    by_status = {}
    async for row in db.machines.aggregate([{'$group': {'_id': '$status', 'count': {'$sum': 1}}}]):
        by_status[row['_id']] = row['count']
    open_breakdowns = await db.breakdowns.count_documents({'status': {'$in': ['OPEN', 'ASSIGNED', 'IN_PROGRESS']}})
    open_wos = await db.work_orders.count_documents({'status': {'$in': ['OPEN', 'ASSIGNED', 'IN_PROGRESS']}})
    today = now_iso()[:10]
    overdue_pm = await db.pm_tasks.count_documents({'active': True, 'status': {'$ne': 'suggested'}, 'next_due_date': {'$lt': today}})
    watchlist = await db.machines.count_documents({'health': {'$in': ['watch', 'inspection_due', 'overdue']}})
    # plant availability — same single runtime source of truth as line KPIs (last 24h window)
    try:
        kpis = await control_room_line_kpis(hours=24, date_from=None, date_to=None, user=user)
        availability = kpis.get('plant_availability')
    except Exception:
        availability = None
    return {'total_machines': total, 'by_status': by_status, 'open_breakdowns': open_breakdowns,
            'open_work_orders': open_wos, 'overdue_pm': overdue_pm, 'watchlist': watchlist, 'availability': availability}


# ---------------- CONTROL ROOM LINE / SECTION KPIS ----------------
@router.get('/control-room/line-kpis')
async def control_room_line_kpis(hours: float = Query(24, gt=0, le=8760),
                                 date_from: Optional[str] = None, date_to: Optional[str] = None,
                                 user: dict = Depends(get_current_user)):
    """Availability + total downtime per Line and per Section (process group).

    Window: presets Shift=8h / Day=24h / Week=168h via `hours`, OR a custom range via
    `date_from`/`date_to` (YYYY-MM-DD, inclusive).

    Uses the shared KPI engine (kpi_engine.py) — the SINGLE runtime source of truth:
    logged line-runtime days are authoritative; un-logged periods assume 24/7 live
    operation with breakdown-interval downtime.
    """
    from datetime import datetime, timezone, timedelta
    from kpi_engine import compute_line_kpis
    now = datetime.now(timezone.utc)
    if date_from:
        try:
            since = datetime.fromisoformat(date_from).replace(tzinfo=timezone.utc)
        except ValueError:
            raise HTTPException(status_code=400, detail='Invalid date_from (YYYY-MM-DD)')
        if date_to:
            try:
                until = datetime.fromisoformat(date_to).replace(tzinfo=timezone.utc) + timedelta(days=1)
            except ValueError:
                raise HTTPException(status_code=400, detail='Invalid date_to (YYYY-MM-DD)')
        else:
            until = now
        until = min(until, now)
        if until <= since:
            raise HTTPException(status_code=400, detail='date_to must be after date_from')
    else:
        until = now
        since = now - timedelta(hours=hours)
    result = await compute_line_kpis(since, until)
    return {'window_hours': round(result['window_minutes'] / 60.0, 2), 'since': result['since'],
            'until': result['until'], 'generated_at': now.isoformat(),
            'plant_availability': result['plant_availability'], 'lines': result['lines']}


# ---------------- USER UI PREFERENCES (sidebar order + icon colors) ----------------
import re as _re

VALID_MODULE_KEYS = {'control-room', 'breakdowns', 'work-orders', 'pm', 'analytics', 'runtime', 'inventory', 'admin', 'aws'}
HEX_RE = _re.compile(r'^#[0-9a-fA-F]{6}$')


class UiPrefs(BaseModel):
    sidebar_order: Optional[list] = None
    icon_colors: Optional[dict] = None


@router.get('/users/me/ui-prefs')
async def get_ui_prefs(user: dict = Depends(get_current_user)):
    doc = await db.users.find_one({'username': user['username']}, {'_id': 0, 'ui_prefs': 1})
    return (doc or {}).get('ui_prefs') or {}


@router.put('/users/me/ui-prefs')
async def put_ui_prefs(req: UiPrefs, user: dict = Depends(get_current_user)):
    prefs = {}
    if req.sidebar_order is not None:
        keys = [k for k in req.sidebar_order if k in VALID_MODULE_KEYS]
        if len(keys) != len(set(keys)):
            raise HTTPException(status_code=400, detail='Duplicate module keys in sidebar_order')
        prefs['sidebar_order'] = keys
    if req.icon_colors is not None:
        colors = {}
        for k, v in req.icon_colors.items():
            if k not in VALID_MODULE_KEYS:
                continue
            if v and not HEX_RE.match(str(v)):
                raise HTTPException(status_code=400, detail=f'Invalid hex color for {k}: {v}')
            if v:
                colors[k] = v
        prefs['icon_colors'] = colors
    if prefs:
        await db.users.update_one({'username': user['username']}, {'$set': {f'ui_prefs.{k}': v for k, v in prefs.items()}})
    doc = await db.users.find_one({'username': user['username']}, {'_id': 0, 'ui_prefs': 1})
    return (doc or {}).get('ui_prefs') or {}
