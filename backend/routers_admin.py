"""Administration: users, hierarchy CRUD (incl. machine layout), failure modes, error codes,
templates, branding, system settings, audit logs. Admin-only."""
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
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


# ---------- HIERARCHY CRUD ----------
class DeptCreate(BaseModel):
    name: str


@router.post('/departments')
async def create_department(req: DeptCreate, user: dict = Depends(require_admin)):
    d = {'id': str(uuid.uuid4()), 'name': req.name, 'order': await db.departments.count_documents({}), 'created_at': now_iso()}
    await db.departments.insert_one(dict(d))
    await audit(user, 'create', 'department', d['id'], req.name)
    d.pop('_id', None)
    return d


@router.delete('/departments/{dept_id}')
async def delete_department(dept_id: str, user: dict = Depends(require_admin)):
    cnt = await db.machines.count_documents({'department_id': dept_id})
    if cnt:
        raise HTTPException(status_code=400, detail=f'Department has {cnt} machines; move them first')
    await db.departments.delete_one({'id': dept_id})
    await db.lines.delete_many({'department_id': dept_id})
    await audit(user, 'delete', 'department', dept_id)
    return {'ok': True}


class LineCreate(BaseModel):
    name: str
    department_id: str


@router.post('/lines')
async def create_line(req: LineCreate, user: dict = Depends(require_admin)):
    dept = await db.departments.find_one({'id': req.department_id}, {'_id': 0})
    if not dept:
        raise HTTPException(status_code=404, detail='Department not found')
    line = {'id': str(uuid.uuid4()), 'name': req.name, 'department': dept['name'], 'department_id': dept['id'],
            'order': await db.lines.count_documents({}), 'created_at': now_iso()}
    await db.lines.insert_one(dict(line))
    await audit(user, 'create', 'line', line['id'], req.name)
    line.pop('_id', None)
    return line


@router.delete('/lines/{line_id}')
async def delete_line(line_id: str, user: dict = Depends(require_admin)):
    cnt = await db.machines.count_documents({'line_id': line_id})
    if cnt:
        raise HTTPException(status_code=400, detail=f'Line has {cnt} machines; move them first')
    await db.lines.delete_one({'id': line_id})
    await db.process_groups.delete_many({'line_id': line_id})
    await audit(user, 'delete', 'line', line_id)
    return {'ok': True}


class PGCreate(BaseModel):
    name: str
    line_id: str


@router.post('/process-groups')
async def create_process_group(req: PGCreate, user: dict = Depends(require_admin)):
    line = await db.lines.find_one({'id': req.line_id}, {'_id': 0})
    if not line:
        raise HTTPException(status_code=404, detail='Line not found')
    pg = {'id': str(uuid.uuid4()), 'name': req.name, 'line': line['name'], 'line_id': line['id'],
          'department': line['department'], 'department_id': line['department_id'],
          'order': await db.process_groups.count_documents({'line_id': line['id']}), 'created_at': now_iso()}
    await db.process_groups.insert_one(dict(pg))
    await audit(user, 'create', 'process_group', pg['id'], req.name)
    pg.pop('_id', None)
    return pg


@router.delete('/process-groups/{pg_id}')
async def delete_process_group(pg_id: str, user: dict = Depends(require_admin)):
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


class BrandingUpdate(BaseModel):
    app_name: Optional[str] = None
    plant_name: Optional[str] = None
    accent: Optional[str] = None


@router.put('/branding')
async def update_branding(req: BrandingUpdate, user: dict = Depends(require_admin)):
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    updates['updated_at'] = now_iso()
    await db.branding.update_one({'id': 'branding'}, {'$set': updates}, upsert=True)
    await audit(user, 'update', 'branding', 'branding')
    return await db.branding.find_one({'id': 'branding'}, {'_id': 0})


@router.get('/audit-logs')
async def list_audit_logs(limit: int = 200, user: dict = Depends(require_admin)):
    return await db.audit_logs.find({}, {'_id': 0}).sort('created_at', -1).limit(min(limit, 1000)).to_list(1000)
