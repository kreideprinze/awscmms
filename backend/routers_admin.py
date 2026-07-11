"""Administration: users, hierarchy CRUD (incl. machine layout), failure modes, error codes,
templates, branding, system settings, audit logs. Admin-only."""
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

from auth import get_current_user, require_admin, hash_password
from database import db
from events import broadcast_machine_update, now_iso

router = APIRouter()


async def audit(user, action, entity, entity_id, detail=''):
    await db.audit_logs.insert_one({'id': str(uuid.uuid4()), 'user': user['username'], 'action': action,
                                    'entity': entity, 'entity_id': entity_id, 'detail': detail, 'created_at': now_iso()})


# ---------- USERS ----------
class UserCreate(BaseModel):
    username: str
    password: str
    role: str
    name: str
    email: Optional[str] = None


@router.get('/users')
async def list_users(user: dict = Depends(require_admin)):
    return await db.users.find({}, {'_id': 0, 'password': 0}).to_list(10000)


@router.get('/users/technicians')
async def list_technicians(user: dict = Depends(get_current_user)):
    return await db.users.find({'role': {'$in': ['technician', 'admin']}, 'active': True}, {'_id': 0, 'password': 0}).to_list(1000)


@router.post('/users')
async def create_user(req: UserCreate, user: dict = Depends(require_admin)):
    if req.role not in ('admin', 'technician', 'operator'):
        raise HTTPException(status_code=400, detail='Role must be admin, technician, or operator')
    if await db.users.find_one({'username': req.username}):
        raise HTTPException(status_code=400, detail='Username already exists')
    u = {'id': str(uuid.uuid4()), 'username': req.username, 'password': hash_password(req.password),
         'role': req.role, 'name': req.name, 'email': req.email, 'active': True, 'created_at': now_iso()}
    await db.users.insert_one(dict(u))
    await audit(user, 'create', 'user', u['id'], req.username)
    u.pop('password')
    u.pop('_id', None)
    return u


class UserUpdate(BaseModel):
    password: Optional[str] = None
    role: Optional[str] = None
    name: Optional[str] = None
    email: Optional[str] = None
    active: Optional[bool] = None


@router.put('/users/{user_id}')
async def update_user(user_id: str, req: UserUpdate, user: dict = Depends(require_admin)):
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if 'password' in updates:
        updates['password'] = hash_password(updates['password'])
    if 'role' in updates and updates['role'] not in ('admin', 'technician', 'operator'):
        raise HTTPException(status_code=400, detail='Invalid role')
    if updates:
        await db.users.update_one({'id': user_id}, {'$set': updates})
        await audit(user, 'update', 'user', user_id)
    return {'ok': True}


@router.delete('/users/{user_id}')
async def delete_user(user_id: str, user: dict = Depends(require_admin)):
    target = await db.users.find_one({'id': user_id}, {'_id': 0})
    if target and target['username'] == user['username']:
        raise HTTPException(status_code=400, detail='Cannot delete yourself')
    await db.users.update_one({'id': user_id}, {'$set': {'active': False}})
    await audit(user, 'deactivate', 'user', user_id)
    return {'ok': True}


# ---------- HIERARCHY CRUD (Line-first: Line → Department → Process Group → Machine) ----------
class LineCreate(BaseModel):
    name: str


@router.post('/lines')
async def create_line(req: LineCreate, user: dict = Depends(require_admin)):
    """Lines are the TOP-LEVEL entity (PC21, PC32, ...). Departments are defined within a line."""
    if await db.lines.find_one({'name': req.name}):
        raise HTTPException(status_code=400, detail='Line already exists')
    line = {'id': str(uuid.uuid4()), 'name': req.name,
            'order': await db.lines.count_documents({}), 'created_at': now_iso()}
    await db.lines.insert_one(dict(line))
    await audit(user, 'create', 'line', line['id'], req.name)
    line.pop('_id', None)
    return line


@router.delete('/lines/{line_id}')
async def delete_line(line_id: str, user: dict = Depends(require_admin)):
    if not await db.lines.find_one({'id': line_id}):
        raise HTTPException(status_code=404, detail='Line not found')
    cnt = await db.machines.count_documents({'line_id': line_id})
    if cnt:
        raise HTTPException(status_code=400, detail=f'Line has {cnt} machines; move them first')
    await db.lines.delete_one({'id': line_id})
    await db.departments.delete_many({'line_id': line_id})
    await db.process_groups.delete_many({'line_id': line_id})
    await audit(user, 'delete', 'line', line_id)
    return {'ok': True}


class DeptCreate(BaseModel):
    name: str
    line_id: str


@router.post('/departments')
async def create_department(req: DeptCreate, user: dict = Depends(require_admin)):
    """Departments live WITHIN a line (e.g., PC21 → PROCESS / PACKAGING / UTILITIES)."""
    line = await db.lines.find_one({'id': req.line_id}, {'_id': 0})
    if not line:
        raise HTTPException(status_code=404, detail='Line not found')
    if await db.departments.find_one({'line_id': line['id'], 'name': req.name}):
        raise HTTPException(status_code=400, detail=f'Department "{req.name}" already exists in line {line["name"]}')
    d = {'id': str(uuid.uuid4()), 'name': req.name, 'line': line['name'], 'line_id': line['id'],
         'order': await db.departments.count_documents({'line_id': line['id']}), 'created_at': now_iso()}
    await db.departments.insert_one(dict(d))
    await audit(user, 'create', 'department', d['id'], f"{line['name']}/{req.name}")
    d.pop('_id', None)
    return d


@router.delete('/departments/{dept_id}')
async def delete_department(dept_id: str, user: dict = Depends(require_admin)):
    if not await db.departments.find_one({'id': dept_id}):
        raise HTTPException(status_code=404, detail='Department not found')
    cnt = await db.machines.count_documents({'department_id': dept_id})
    if cnt:
        raise HTTPException(status_code=400, detail=f'Department has {cnt} machines; move them first')
    await db.departments.delete_one({'id': dept_id})
    await db.process_groups.delete_many({'department_id': dept_id})
    await audit(user, 'delete', 'department', dept_id)
    return {'ok': True}


class PGCreate(BaseModel):
    name: str
    department_id: str


@router.post('/process-groups')
async def create_process_group(req: PGCreate, user: dict = Depends(require_admin)):
    dept = await db.departments.find_one({'id': req.department_id}, {'_id': 0})
    if not dept:
        raise HTTPException(status_code=404, detail='Department not found')
    pg = {'id': str(uuid.uuid4()), 'name': req.name,
          'line': dept['line'], 'line_id': dept['line_id'],
          'department': dept['name'], 'department_id': dept['id'],
          'order': await db.process_groups.count_documents({'department_id': dept['id']}), 'created_at': now_iso()}
    await db.process_groups.insert_one(dict(pg))
    await audit(user, 'create', 'process_group', pg['id'], req.name)
    pg.pop('_id', None)
    return pg


@router.delete('/process-groups/{pg_id}')
async def delete_process_group(pg_id: str, user: dict = Depends(require_admin)):
    if not await db.process_groups.find_one({'id': pg_id}):
        raise HTTPException(status_code=404, detail='Process group not found')
    cnt = await db.machines.count_documents({'process_group_id': pg_id})
    if cnt:
        raise HTTPException(status_code=400, detail=f'Process group has {cnt} machines; move them first')
    await db.process_groups.delete_one({'id': pg_id})
    await audit(user, 'delete', 'process_group', pg_id)
    return {'ok': True}


# ---------- MACHINES CRUD ----------
class MachineCreate(BaseModel):
    name: str
    code: str
    sap_code: Optional[str] = None
    process_group_id: str
    machine_type: Optional[str] = 'General Equipment'
    criticality: str = 'medium'


@router.post('/machines')
async def create_machine(req: MachineCreate, user: dict = Depends(require_admin)):
    pg = await db.process_groups.find_one({'id': req.process_group_id}, {'_id': 0})
    if not pg:
        raise HTTPException(status_code=404, detail='Process group not found')
    if await db.machines.find_one({'code': req.code}):
        raise HTTPException(status_code=400, detail='Machine code already exists')
    count = await db.machines.count_documents({'process_group_id': pg['id']})
    m = {'id': str(uuid.uuid4()), 'name': req.name, 'code': req.code, 'sap_code': req.sap_code,
         'department': pg['department'], 'department_id': pg['department_id'],
         'line': pg['line'], 'line_id': pg['line_id'],
         'process_group': pg['name'], 'process_group_id': pg['id'],
         'machine_type': req.machine_type, 'criticality': req.criticality,
         'status': 'idle', 'health': 'healthy', 'reliability_state': 'no_data',
         'position_x': count * 220, 'position_y': pg.get('order', 0) * 130, 'width': 200, 'height': 110,
         'total_run_hours': 0.0, 'inspection_recommended': False,
         'created_at': now_iso(), 'commissioned_at': now_iso()}
    await db.machines.insert_one(dict(m))
    await audit(user, 'create', 'machine', m['id'], req.name)
    m.pop('_id', None)
    await broadcast_machine_update(m)
    return m


class MachineUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    sap_code: Optional[str] = None
    machine_type: Optional[str] = None
    criticality: Optional[str] = None
    position_x: Optional[float] = None
    position_y: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None


@router.put('/machines/{machine_id}')
async def update_machine(machine_id: str, req: MachineUpdate, user: dict = Depends(require_admin)):
    m = await db.machines.find_one({'id': machine_id}, {'_id': 0})
    if not m:
        raise HTTPException(status_code=404, detail='Machine not found')
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if updates:
        await db.machines.update_one({'id': machine_id}, {'$set': updates})
        await audit(user, 'update', 'machine', machine_id, str(list(updates.keys())))
        m.update(updates)
        await broadcast_machine_update(m)
    return m


@router.delete('/machines/{machine_id}')
async def delete_machine(machine_id: str, user: dict = Depends(require_admin)):
    if not await db.machines.find_one({'id': machine_id}):
        raise HTTPException(status_code=404, detail='Machine not found')
    await db.machines.delete_one({'id': machine_id})
    await audit(user, 'delete', 'machine', machine_id)
    return {'ok': True}


# ---------- FAILURE MODES ----------
class NamedCreate(BaseModel):
    name: str


@router.get('/failure-modes')
async def list_failure_modes(user: dict = Depends(get_current_user)):
    return await db.failure_modes.find({'active': True}, {'_id': 0}).sort('name', 1).to_list(1000)


@router.post('/failure-modes')
async def create_failure_mode(req: NamedCreate, user: dict = Depends(require_admin)):
    fm = {'id': str(uuid.uuid4()), 'name': req.name, 'active': True, 'created_at': now_iso()}
    await db.failure_modes.insert_one(dict(fm))
    await audit(user, 'create', 'failure_mode', fm['id'], req.name)
    fm.pop('_id', None)
    return fm


@router.delete('/failure-modes/{fm_id}')
async def delete_failure_mode(fm_id: str, user: dict = Depends(require_admin)):
    await db.failure_modes.update_one({'id': fm_id}, {'$set': {'active': False}})
    await audit(user, 'delete', 'failure_mode', fm_id)
    return {'ok': True}


# ---------- ERROR CODES ----------
class ErrorCodeCreate(BaseModel):
    code: str
    label: str


@router.post('/error-codes')
async def create_error_code(req: ErrorCodeCreate, user: dict = Depends(require_admin)):
    ec = {'id': str(uuid.uuid4()), 'code': req.code, 'label': req.label, 'active': True, 'created_at': now_iso()}
    await db.error_codes.insert_one(dict(ec))
    await audit(user, 'create', 'error_code', ec['id'], req.code)
    ec.pop('_id', None)
    return ec


@router.delete('/error-codes/{ec_id}')
async def delete_error_code(ec_id: str, user: dict = Depends(require_admin)):
    await db.error_codes.update_one({'id': ec_id}, {'$set': {'active': False}})
    await audit(user, 'delete', 'error_code', ec_id)
    return {'ok': True}


# ---------- PM TEMPLATES ----------
class PMTemplateCreate(BaseModel):
    name: str
    frequency: str
    priority: str = 'medium'
    checklist: List[str] = []


@router.post('/pm-templates')
async def create_pm_template(req: PMTemplateCreate, user: dict = Depends(require_admin)):
    t = {'id': str(uuid.uuid4()), **req.model_dump(), 'created_at': now_iso()}
    await db.pm_templates.insert_one(dict(t))
    await audit(user, 'create', 'pm_template', t['id'], req.name)
    t.pop('_id', None)
    return t


@router.delete('/pm-templates/{t_id}')
async def delete_pm_template(t_id: str, user: dict = Depends(require_admin)):
    await db.pm_templates.delete_one({'id': t_id})
    await audit(user, 'delete', 'pm_template', t_id)
    return {'ok': True}


# ---------- NOTIFICATION TEMPLATES ----------
@router.get('/notification-templates')
async def list_notification_templates(user: dict = Depends(require_admin)):
    return await db.notification_templates.find({}, {'_id': 0}).to_list(100)


# ---------- BRANDING & SETTINGS ----------
@router.get('/branding')
async def get_branding():
    return await db.branding.find_one({'id': 'branding'}, {'_id': 0}) or {}


import re as _re
HEX_COLOR_RE = _re.compile(r'^#[0-9a-fA-F]{6}$')


class BrandingUpdate(BaseModel):
    app_name: Optional[str] = None
    plant_name: Optional[str] = None
    accent: Optional[str] = None


@router.put('/branding')
async def update_branding(req: BrandingUpdate, user: dict = Depends(require_admin)):
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if 'accent' in updates and updates['accent'] != '' and not HEX_COLOR_RE.match(updates['accent']):
        raise HTTPException(status_code=400, detail='accent must be a hex color like #00fff5')
    updates['updated_at'] = now_iso()
    await db.branding.update_one({'id': 'branding'}, {'$set': updates}, upsert=True)
    await audit(user, 'update', 'branding', 'branding')
    return await db.branding.find_one({'id': 'branding'}, {'_id': 0})


@router.post('/branding/logo')
async def upload_branding_logo(file: UploadFile = File(...), user: dict = Depends(require_admin)):
    """Upload a custom logo/icon (png/jpg/svg/webp, max 500KB). Stored as a data URI and
    served with the branding document — replaces the default factory mark app-wide."""
    allowed = {'image/png', 'image/jpeg', 'image/svg+xml', 'image/webp', 'image/gif'}
    if file.content_type not in allowed:
        raise HTTPException(status_code=400, detail=f'Unsupported image type {file.content_type}. Allowed: png, jpg, svg, webp, gif')
    data = await file.read()
    if len(data) > 500 * 1024:
        raise HTTPException(status_code=400, detail='Logo too large (max 500KB)')
    import base64
    data_uri = f"data:{file.content_type};base64,{base64.b64encode(data).decode()}"
    await db.branding.update_one({'id': 'branding'}, {'$set': {'logo_data': data_uri, 'updated_at': now_iso()}}, upsert=True)
    await audit(user, 'update', 'branding_logo', 'branding', file.filename)
    return {'ok': True, 'logo_data': data_uri}


@router.delete('/branding/logo')
async def remove_branding_logo(user: dict = Depends(require_admin)):
    await db.branding.update_one({'id': 'branding'}, {'$unset': {'logo_data': ''}, '$set': {'updated_at': now_iso()}})
    await audit(user, 'delete', 'branding_logo', 'branding')
    return {'ok': True}


@router.get('/audit-logs')
async def list_audit_logs(limit: int = 200, user: dict = Depends(require_admin)):
    return await db.audit_logs.find({}, {'_id': 0}).sort('created_at', -1).limit(min(limit, 1000)).to_list(1000)


@router.get('/system/seed-summary')
async def seed_summary(user: dict = Depends(require_admin)):
    stored = await db.settings.find_one({'id': 'seed_summary'}, {'_id': 0})
    live = {}
    for coll in ['users', 'departments', 'lines', 'process_groups', 'machines', 'failure_modes', 'error_codes',
                 'pm_templates', 'runtime_templates', 'notification_templates', 'spare_locations', 'spares_inventory', 'machine_spares']:
        live[coll] = await db[coll].count_documents({})
    return {'seed_summary': stored, 'live_counts': live}


@router.post('/system/reseed-verify')
async def reseed_verify(user: dict = Depends(require_admin)):
    """Re-run the idempotent seed to top-up any missing master data (never duplicates)."""
    from seed import seed_all
    summary = await seed_all()
    await audit(user, 'reseed_verify', 'system', 'seed')
    return summary


# ---------- DATA MANAGEMENT (SEED SAMPLE / PURGE OPERATIONAL) ----------
class PurgeRequest(BaseModel):
    confirm: str  # must be exactly "PURGE"


@router.post('/data/seed-sample')
async def seed_sample_data(user: dict = Depends(require_admin)):
    """Generate realistic demo data against EXISTING machines only (tagged sample=true):
    work orders in every kanban stage, closed breakdowns with varied downtimes (incl.
    RCA-triggering ones), warnings, a sample PM task + completion, and 7 days of line runtime."""
    import random
    from datetime import datetime, timezone, timedelta
    from events import next_counter, create_timeline_event
    from routers_ops import _fan_out_line_runtime
    from reliability import recompute_machine_reliability

    machines = await db.machines.find({}, {'_id': 0}).to_list(5000)
    if not machines:
        raise HTTPException(status_code=400, detail='No machines exist — create machines first')
    tech = await db.users.find_one({'role': 'technician', 'active': True}, {'_id': 0, 'username': 1})
    if not tech:
        raise HTTPException(status_code=400, detail='No active technician user exists')
    tech = tech['username']
    now = datetime.now(timezone.utc)
    rng = random.Random(42)
    picks = rng.sample(machines, min(8, len(machines)))
    counts = {'work_orders': 0, 'breakdowns': 0, 'warnings': 0, 'pm_tasks': 0, 'pm_completions': 0, 'line_runtime_days': 0, 'rca_work_orders': 0}

    async def mk_wo(m, wo_type, title, status, started_min_ago=None, dur=None, closed=False, extra=None):
        wo_num = await next_counter('work_orders', 'WO')
        started = (now - timedelta(minutes=started_min_ago)).isoformat() if started_min_ago else None
        doc = {
            'id': str(uuid.uuid4()), 'wo_number': wo_num, 'wo_type': wo_type, 'title': title,
            'description': f'Sample data: {title}', 'machine_id': m['id'], 'machine_name': m['name'],
            'department': m['department'], 'line': m['line'], 'assigned_to': tech,
            'priority': rng.choice(['medium', 'high']), 'status': status,
            'root_cause': None, 'action_taken': 'Sample corrective action' if status in ('PENDING_ADMIN_CLOSURE', 'CLOSED') else None,
            'spare_parts': [], 'duration_minutes': dur, 'source': 'sample', 'auto_generated': False,
            'sample': True, 'created_at': (now - timedelta(minutes=(started_min_ago or 60) + 30)).isoformat(),
            'started_at': started,
            'completed_at': (now - timedelta(minutes=10)).isoformat() if status in ('PENDING_ADMIN_CLOSURE', 'CLOSED') else None,
        }
        if closed:
            doc['closed_by'] = 'admin'
            doc['closed_at'] = (now - timedelta(minutes=5)).isoformat()
        if extra:
            doc.update(extra)
        await db.work_orders.insert_one(dict(doc))
        counts['work_orders'] += 1
        return doc

    # --- Work orders in every kanban stage ---
    await mk_wo(picks[0], 'Corrective', f"Belt tension check — {picks[0]['name']}", 'ASSIGNED')
    await mk_wo(picks[1], 'Inspection', f"Gearbox oil inspection — {picks[1]['name']}", 'ASSIGNED')
    await mk_wo(picks[2], 'Corrective', f"Motor vibration repair — {picks[2]['name']}", 'IN_PROGRESS', started_min_ago=50)
    await mk_wo(picks[3], 'Inspection', f"Sensor calibration — {picks[3]['name']}", 'PENDING_ADMIN_CLOSURE', started_min_ago=45, dur=35.0)
    await mk_wo(picks[4], 'Corrective', f"Chain link replacement — {picks[4]['name']}", 'CLOSED', started_min_ago=180, dur=25.0, closed=True)
    await mk_wo(picks[5 % len(picks)], 'Preventive', f"Weekly lube round — {picks[5 % len(picks)]['name']}", 'CLOSED', started_min_ago=300, dur=40.0, closed=True)

    # --- Closed breakdowns with varied downtimes (45/75 min trigger RCA WOs) ---
    bd_specs = [(picks[0], 12, 'MECHANICAL', False), (picks[1], 25, 'ELECTRICAL', False),
                (picks[2], 45, 'MECHANICAL', True), (picks[3], 75, 'CONTROL_PLC', True)]
    for i, (m, dt_min, cat, rca) in enumerate(bd_specs):
        ticket = await next_counter('breakdowns', 'BD')
        start = now - timedelta(days=i + 1, minutes=dt_min)
        end = start + timedelta(minutes=dt_min)
        bd_id = str(uuid.uuid4())
        wo = await mk_wo(m, 'Corrective', f"Corrective — {m['name']} ({ticket})", 'CLOSED',
                         started_min_ago=None, dur=float(dt_min), closed=True,
                         extra={'source_breakdown_id': bd_id, 'source': 'breakdown_auto', 'auto_generated': True,
                                'started_at': start.isoformat(), 'completed_at': end.isoformat()})
        rca_id = None
        if rca:
            rca_num = await next_counter('work_orders', 'WO')
            rca_id = str(uuid.uuid4())
            filled = i % 2 == 1
            await db.work_orders.insert_one({
                'id': rca_id, 'wo_number': rca_num, 'wo_type': 'RCA',
                'title': f"5-Why RCA — {m['name']} ({ticket})",
                'description': f'Sample data: auto-triggered RCA, downtime {dt_min} min exceeded 30 min threshold.',
                'machine_id': m['id'], 'machine_name': m['name'], 'department': m['department'], 'line': m['line'],
                'assigned_to': tech, 'priority': 'high',
                'status': 'CLOSED' if filled else 'ASSIGNED',
                'rca': ({'whys': ['Bearing seized', 'Lubrication film broke down', 'Grease interval exceeded',
                                  'Lube route not scheduled', 'PM plan missing this asset'],
                         'root_cause': 'Asset missing from lubrication PM plan',
                         'corrective_action': 'Added machine to weekly lube route',
                         'submitted_by': tech, 'submitted_at': end.isoformat()} if filled else None),
                'root_cause': 'Asset missing from lubrication PM plan' if filled else None,
                'action_taken': 'Added machine to weekly lube route' if filled else None,
                'closed_by': 'admin' if filled else None,
                'source': 'rca_auto', 'source_breakdown_id': bd_id, 'auto_generated': True, 'sample': True,
                'spare_parts': [], 'duration_minutes': None, 'created_at': end.isoformat(),
            })
            counts['rca_work_orders'] += 1
            counts['work_orders'] += 1
        await db.breakdowns.insert_one({
            'id': bd_id, 'ticket_number': ticket, 'machine_id': m['id'], 'machine_name': m['name'],
            'department': m['department'], 'line': m['line'], 'process_group': m.get('process_group'),
            'failure_mode': cat.replace('_', ' ').title(), 'breakdown_type': cat,
            'description': f'Sample data: {cat.lower()} failure on {m["name"]}', 'reporter': 'operator',
            'status': 'CLOSED', 'assigned_to': tech,
            'start_time': start.isoformat(), 'end_time': end.isoformat(),
            'downtime_minutes': float(dt_min), 'repair_duration_minutes': float(max(dt_min - 5, 5)),
            'root_cause': None, 'action_taken': 'Sample repair action', 'consumed_spares': [],
            'rca_task_id': rca_id, 'work_order_id': wo['id'], 'work_order_number': wo['wo_number'],
            'sample': True, 'created_at': start.isoformat(),
        })
        counts['breakdowns'] += 1

    # --- Warnings: one OPEN (with linked assigned WO, machine -> watch), one CLOSED ---
    for j, (m, st) in enumerate([(picks[6 % len(picks)], 'OPEN'), (picks[7 % len(picks)], 'CLOSED')]):
        tag = await next_counter('warnings', 'WRN')
        w_id = str(uuid.uuid4())
        wo = await mk_wo(m, 'Inspection', f"Inspection — {m['name']} ({tag})",
                         'ASSIGNED' if st == 'OPEN' else 'CLOSED', dur=None if st == 'OPEN' else 15.0,
                         closed=(st == 'CLOSED'), extra={'source_warning_id': w_id, 'source': 'warning_auto'})
        await db.warnings.insert_one({
            'id': w_id, 'tag_number': tag, 'machine_id': m['id'], 'machine_name': m['name'],
            'department': m['department'], 'line': m['line'], 'warning_type': 'MECHANICAL',
            'description': f'Sample data: unusual noise observed on {m["name"]}', 'reporter': 'operator',
            'status': st, 'work_order_id': wo['id'], 'work_order_number': wo['wo_number'],
            'sample': True, 'created_at': (now - timedelta(hours=6 + j)).isoformat(),
        })
        if st == 'OPEN':
            await db.machines.update_one({'id': m['id'], 'status': 'running'}, {'$set': {'status': 'watch'}})
        counts['warnings'] += 1

    # --- Sample PM task + on-time completion ---
    pm_m = picks[0]
    pm_id = str(uuid.uuid4())
    await db.pm_tasks.insert_one({
        'id': pm_id, 'task_name': f'Sample Monthly PM — {pm_m["name"]}', 'machine_id': pm_m['id'],
        'machine_name': pm_m['name'], 'department': pm_m['department'], 'line': pm_m['line'],
        'location': pm_m.get('process_group'), 'frequency': 'monthly',
        'checklist_groups': [
            {'description': 'Drive Motor', 'items': [
                {'checked_for': 'Vibration level', 'parameter': '< 2.8 mm/s'},
                {'checked_for': 'Winding temperature', 'parameter': '< 75 C'}]},
            {'description': 'Conveyor Belt', 'items': [
                {'checked_for': 'Belt tracking', 'parameter': 'Centered +/- 5mm'},
                {'checked_for': 'Splice condition', 'parameter': 'No fraying'}]},
        ],
        'next_due_date': (now + timedelta(days=25)).date().isoformat(),
        'last_completed': (now - timedelta(days=5)).date().isoformat(),
        'active': True, 'sample': True, 'created_at': now.isoformat(),
    })
    counts['pm_tasks'] += 1
    await db.pm_completions.insert_one({
        'id': str(uuid.uuid4()), 'pm_task_id': pm_id, 'machine_id': pm_m['id'], 'machine_name': pm_m['name'],
        'line': pm_m['line'], 'location': pm_m.get('process_group'), 'frequency': 'monthly',
        'task_name': f'Sample Monthly PM — {pm_m["name"]}',
        'row_results': [{'sn': 1, 'description': 'Drive Motor', 'checked_for': 'Vibration level',
                         'parameter': '< 2.8 mm/s', 'status': 'OK', 'remarks': ''}],
        'remarks': 'Sample completion', 'completed_by': tech, 'done_by': tech, 'checked_by': 'admin',
        'on_time': True, 'checklist_date': (now - timedelta(days=5)).date().isoformat(),
        'completed_at': (now - timedelta(days=5)).isoformat(), 'sample': True,
    })
    counts['pm_completions'] += 1

    # --- 7 days of line runtime for every line ---
    lines = sorted({m['line'] for m in machines})
    by_line = {}
    for m in machines:
        by_line.setdefault(m['line'], []).append(m)
    for d in range(1, 8):
        date = (now - timedelta(days=d)).date().isoformat()
        for line in lines:
            run_h = round(rng.uniform(18, 23.5), 1)
            ms = by_line[line]
            await db.line_runtime_logs.update_one({'line': line, 'date': date}, {'$set': {
                'id': str(uuid.uuid4()), 'line': line, 'department': ms[0]['department'], 'date': date,
                'calendar_hours': 24.0, 'run_hours': run_h, 'dark_hours': round(24 - run_h, 2),
                'availability': round(run_h / 24 * 100, 1), 'machines_count': len(ms),
                'entered_by': user['username'], 'source': 'manual', 'sample': True, 'created_at': now.isoformat(),
            }}, upsert=True)
            await _fan_out_line_runtime(line, ms, date, 24.0, run_h, user['username'])
        counts['line_runtime_days'] += 1

    for m in picks[:4]:
        await recompute_machine_reliability(m['id'], trigger='sample_seed')
    await create_timeline_event('sample_seeded', title='Sample data seeded', description=str(counts), user=user['username'])
    await audit(user, 'seed_sample_data', 'system', 'sample', str(counts))
    return {'ok': True, 'seeded': counts}


@router.post('/data/purge-operational')
async def purge_operational_data(req: PurgeRequest, user: dict = Depends(require_admin)):
    """DESTRUCTIVE: remove ALL transactional/operational data while KEEPING machines,
    hierarchy, users, spares catalog, PM task definitions and branding/settings.
    Requires confirm == "PURGE"."""
    if req.confirm != 'PURGE':
        raise HTTPException(status_code=400, detail='Type PURGE to confirm this destructive action')
    removed = {}
    for coll in ['work_orders', 'breakdowns', 'warnings', 'pm_completions', 'runtime_logs',
                 'line_runtime_logs', 'timeline_events', 'notifications', 'repair_events',
                 'spare_transactions', 'reliability_metrics']:
        res = await db[coll].delete_many({})
        removed[coll] = res.deleted_count
    # machines kept — statuses reset, accumulated runtime zeroed
    await db.machines.update_many({}, {'$set': {'status': 'running', 'total_run_hours': 0}})
    # remove sample PM tasks only (real PM definitions are configuration and kept)
    res = await db.pm_tasks.delete_many({'sample': True})
    removed['sample_pm_tasks'] = res.deleted_count
    # reset ticket counters for a clean slate
    await db.counters.delete_many({'_id': {'$in': ['work_orders', 'breakdowns', 'warnings']}})
    from events import create_timeline_event
    await create_timeline_event('data_purged', title='Operational data purged',
                                description=f"by {user['username']}: {removed}", user=user['username'])
    await audit(user, 'purge_operational_data', 'system', 'purge', str(removed))
    return {'ok': True, 'removed': removed}
