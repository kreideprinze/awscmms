"""Maintenance routes: breakdowns (lifecycle + 30-min root-cause rule), work orders, PM tasks & templates."""
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from auth import get_current_user, require_admin, require_admin_or_tech
from database import db
from events import create_timeline_event, create_notification, broadcast_machine_update, next_counter, now_iso

router = APIRouter()

LIFECYCLE = ['OPEN', 'ASSIGNED', 'IN_PROGRESS', 'COMPLETED', 'CLOSED']


class SpareUse(BaseModel):
    sap_code: str
    quantity: float


# ============ BREAKDOWNS ============
BREAKDOWN_TYPES = ['MECHANICAL', 'ELECTRICAL', 'CONTROL_PLC']


class BreakdownCreate(BaseModel):
    machine_id: str
    description: str
    failure_mode: Optional[str] = None
    breakdown_type: str = 'MECHANICAL'
    reporter_name: Optional[str] = None
    auto_create_work_order: bool = True
    start_time: Optional[str] = None


async def _create_breakdown_internal(machine_id: str, description: str, failure_mode: str, reporter: str,
                                     start_time: str = None, breakdown_type: str = 'MECHANICAL',
                                     auto_create_work_order: bool = True):
    machine = await db.machines.find_one({'id': machine_id}, {'_id': 0})
    if not machine:
        raise HTTPException(status_code=404, detail='Machine not found')
    if breakdown_type not in BREAKDOWN_TYPES:
        raise HTTPException(status_code=400, detail=f'Invalid breakdown_type. Valid: {BREAKDOWN_TYPES}')
    ticket = await next_counter('breakdowns', 'BD')
    bd = {
        'id': str(uuid.uuid4()), 'ticket_number': ticket,
        'machine_id': machine['id'], 'machine_name': machine['name'],
        'department': machine['department'], 'line': machine['line'], 'process_group': machine.get('process_group'),
        'failure_mode': failure_mode or breakdown_type.replace('_', ' ').title(),
        'breakdown_type': breakdown_type,
        'description': description, 'reporter': reporter,
        'status': 'OPEN', 'assigned_to': None,
        'start_time': start_time or now_iso(), 'end_time': None,
        'downtime_minutes': None, 'repair_duration_minutes': None,
        'root_cause': None, 'action_taken': None, 'consumed_spares': [],
        'rca_task_id': None, 'work_order_id': None, 'created_at': now_iso(),
    }
    await db.breakdowns.insert_one(dict(bd))
    await db.machines.update_one({'id': machine['id']}, {'$set': {'status': 'failed'}})
    machine['status'] = 'failed'
    await broadcast_machine_update(machine)
    await create_timeline_event('breakdown_created', machine_id=machine['id'], machine_name=machine['name'],
                                title=f"Breakdown {ticket} created", description=description, user=reporter,
                                reference_id=bd['id'], reference_type='breakdown',
                                department=machine['department'], line=machine['line'])
    severity = 'critical'
    notif_type = 'critical_failure' if machine.get('criticality') == 'critical' else 'breakdown'
    title = f"CRITICAL FAILURE: {machine['name']}" if notif_type == 'critical_failure' else f"Breakdown: {machine['name']}"
    await create_notification(notif_type, title, f"{ticket} \u2014 [{breakdown_type}] {bd['failure_mode']}: {description}", severity=severity,
                              machine_id=machine['id'], machine_name=machine['name'],
                              reference_id=bd['id'], reference_type='breakdown')

    # Auto-dispatch a Corrective Work Order to maintenance immediately
    if auto_create_work_order:
        tech = await db.users.find_one({'role': 'technician', 'active': True}, {'_id': 0, 'username': 1})
        assigned = tech['username'] if tech else None
        wo_num = await next_counter('work_orders', 'WO')
        wo = {
            'id': str(uuid.uuid4()), 'wo_number': wo_num, 'wo_type': 'Corrective',
            'title': f"Corrective \u2014 {machine['name']} ({ticket})",
            'description': f"Auto-dispatched from breakdown {ticket} [{breakdown_type}]: {description}",
            'machine_id': machine['id'], 'machine_name': machine['name'],
            'department': machine['department'], 'line': machine['line'],
            'assigned_to': assigned, 'priority': 'critical' if machine.get('criticality') == 'critical' else 'high',
            'status': 'ASSIGNED' if assigned else 'OPEN',
            'root_cause': None, 'action_taken': None, 'spare_parts': [],
            'duration_minutes': None, 'source': 'breakdown_auto', 'source_breakdown_id': bd['id'],
            'auto_generated': True, 'created_at': now_iso(),
        }
        await db.work_orders.insert_one(dict(wo))
        await db.breakdowns.update_one({'id': bd['id']}, {'$set': {'work_order_id': wo['id'], 'work_order_number': wo_num}})
        bd['work_order_id'] = wo['id']
        bd['work_order_number'] = wo_num
        await create_notification('work_order', f"Maintenance Dispatched: {machine['name']}",
                                  f"{wo_num} auto-created from {ticket}" + (f" \u2014 assigned to {assigned}" if assigned else ''),
                                  severity='warning', machine_id=machine['id'], machine_name=machine['name'],
                                  reference_id=wo['id'], reference_type='work_order')
        await create_timeline_event('wo_created', machine_id=machine['id'], machine_name=machine['name'],
                                    title=f"WO {wo_num} auto-dispatched to maintenance", user='system',
                                    reference_id=wo['id'], reference_type='work_order',
                                    department=machine['department'], line=machine['line'])
    bd.pop('_id', None)
    return bd


@router.post('/breakdowns')
async def create_breakdown(req: BreakdownCreate, user: dict = Depends(get_current_user)):
    reporter = req.reporter_name or user['username']
    return await _create_breakdown_internal(req.machine_id, req.description, req.failure_mode, reporter,
                                            req.start_time, req.breakdown_type, req.auto_create_work_order)


@router.get('/breakdowns')
async def list_breakdowns(machine_id: Optional[str] = None, status: Optional[str] = None,
                          department: Optional[str] = None, line: Optional[str] = None,
                          assigned_to: Optional[str] = None, search: Optional[str] = None,
                          limit: int = Query(200, le=2000), skip: int = 0, user: dict = Depends(get_current_user)):
    q = {}
    if machine_id:
        q['machine_id'] = machine_id
    if status:
        q['status'] = status
    if department:
        q['department'] = department
    if line:
        q['line'] = line
    if assigned_to:
        q['assigned_to'] = assigned_to
    if search:
        q['$or'] = [{'ticket_number': {'$regex': search, '$options': 'i'}}, {'machine_name': {'$regex': search, '$options': 'i'}}, {'description': {'$regex': search, '$options': 'i'}}]
    total = await db.breakdowns.count_documents(q)
    items = await db.breakdowns.find(q, {'_id': 0}).sort('created_at', -1).skip(skip).limit(limit).to_list(limit)
    return {'items': items, 'total': total}


@router.get('/breakdowns/{bd_id}')
async def get_breakdown(bd_id: str, user: dict = Depends(get_current_user)):
    bd = await db.breakdowns.find_one({'id': bd_id}, {'_id': 0})
    if not bd:
        raise HTTPException(status_code=404, detail='Breakdown not found')
    return bd


class BreakdownUpdate(BaseModel):
    action: str  # assign | start | complete | close | update
    assigned_to: Optional[str] = None
    root_cause: Optional[str] = None
    action_taken: Optional[str] = None
    consumed_spares: Optional[List[SpareUse]] = None
    end_time: Optional[str] = None
    description: Optional[str] = None
    failure_mode: Optional[str] = None


def parse_dt(iso):
    try:
        dt = datetime.fromisoformat(str(iso).replace('Z', '+00:00'))
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    except Exception:
        return None


@router.put('/breakdowns/{bd_id}')
async def update_breakdown(bd_id: str, req: BreakdownUpdate, user: dict = Depends(require_admin_or_tech)):
    bd = await db.breakdowns.find_one({'id': bd_id}, {'_id': 0})
    if not bd:
        raise HTTPException(status_code=404, detail='Breakdown not found')
    machine = await db.machines.find_one({'id': bd['machine_id']}, {'_id': 0})
    updates = {}

    if req.action == 'update':
        if req.description:
            updates['description'] = req.description
        if req.failure_mode:
            updates['failure_mode'] = req.failure_mode
        if req.root_cause:
            updates['root_cause'] = req.root_cause
        if req.action_taken:
            updates['action_taken'] = req.action_taken
        await db.breakdowns.update_one({'id': bd_id}, {'$set': updates})
        return {'ok': True}

    if req.action == 'assign':
        if not req.assigned_to:
            raise HTTPException(status_code=400, detail='assigned_to required')
        updates = {'status': 'ASSIGNED', 'assigned_to': req.assigned_to}
        await db.breakdowns.update_one({'id': bd_id}, {'$set': updates})
        await create_timeline_event('breakdown_assigned', machine_id=bd['machine_id'], machine_name=bd['machine_name'],
                                    title=f"{bd['ticket_number']} assigned to {req.assigned_to}", user=user['username'],
                                    reference_id=bd_id, reference_type='breakdown', department=bd['department'], line=bd['line'])
        await create_notification('breakdown', f"Breakdown Assigned: {bd['machine_name']}",
                                  f"{bd['ticket_number']} assigned to {req.assigned_to}", severity='info',
                                  machine_id=bd['machine_id'], machine_name=bd['machine_name'], reference_id=bd_id, reference_type='breakdown')
        return {'ok': True, 'status': 'ASSIGNED'}

    if req.action == 'start':
        updates = {'status': 'IN_PROGRESS', 'repair_started_at': now_iso()}
        if not bd.get('assigned_to'):
            updates['assigned_to'] = user['username']
        await db.breakdowns.update_one({'id': bd_id}, {'$set': updates})
        if machine:
            await db.machines.update_one({'id': machine['id']}, {'$set': {'status': 'repair'}})
            machine['status'] = 'repair'
            await broadcast_machine_update(machine)
        await create_timeline_event('breakdown_started', machine_id=bd['machine_id'], machine_name=bd['machine_name'],
                                    title=f"Repair started on {bd['ticket_number']}", user=user['username'],
                                    reference_id=bd_id, reference_type='breakdown', department=bd['department'], line=bd['line'])
        return {'ok': True, 'status': 'IN_PROGRESS'}

    if req.action in ('complete', 'close'):
        end_time = req.end_time or bd.get('end_time') or now_iso()
        start = parse_dt(bd['start_time'])
        end = parse_dt(end_time)
        downtime = round((end - start).total_seconds() / 60.0, 1) if start and end else 0
        settings = await db.settings.find_one({'id': 'reliability_settings'}, {'_id': 0}) or {}
        rc_threshold = settings.get('root_cause_downtime_minutes', 30)

        root_cause = req.root_cause or bd.get('root_cause')
        if downtime > rc_threshold and not root_cause:
            raise HTTPException(status_code=400, detail=f'Root cause is mandatory: downtime {downtime:.0f} min exceeds {rc_threshold} min')

        repair_start = parse_dt(bd.get('repair_started_at')) or start
        repair_duration = round((end - repair_start).total_seconds() / 60.0, 1) if repair_start and end else downtime

        consumed = [s.model_dump() for s in (req.consumed_spares or [])]
        if consumed:
            from routers_spares import consume_spares
            consumed = await consume_spares(consumed, 'BREAKDOWN_CONSUMPTION', bd_id, f"Breakdown {bd['ticket_number']}",
                                            bd['machine_id'], bd['machine_name'], user['username'])

        new_status = 'COMPLETED' if req.action == 'complete' else 'CLOSED'
        updates = {
            'status': new_status, 'end_time': end_time, 'downtime_minutes': downtime,
            'repair_duration_minutes': repair_duration, 'root_cause': root_cause,
            'action_taken': req.action_taken or bd.get('action_taken'),
        }
        if consumed:
            updates['consumed_spares'] = (bd.get('consumed_spares') or []) + consumed

        # 30-min rule: auto follow-up RCA task for attending technician
        rca_task_id = bd.get('rca_task_id')
        if downtime > rc_threshold and not rca_task_id:
            tech = bd.get('assigned_to') or user['username']
            wo_num = await next_counter('work_orders', 'WO')
            rca_wo = {
                'id': str(uuid.uuid4()), 'wo_number': wo_num, 'wo_type': 'Inspection',
                'title': f"Root Cause Analysis \u2014 {bd['machine_name']} ({bd['ticket_number']})",
                'description': f"Auto-generated follow-up: breakdown {bd['ticket_number']} downtime {downtime:.0f} min exceeded {rc_threshold} min. Submit detailed root-cause analysis for this machine.",
                'machine_id': bd['machine_id'], 'machine_name': bd['machine_name'],
                'department': bd['department'], 'line': bd['line'],
                'assigned_to': tech, 'priority': 'high', 'status': 'ASSIGNED',
                'root_cause': None, 'action_taken': None, 'spare_parts': [],
                'duration_minutes': None, 'source': 'rca_followup', 'source_breakdown_id': bd_id,
                'auto_generated': True, 'created_at': now_iso(),
            }
            await db.work_orders.insert_one(dict(rca_wo))
            updates['rca_task_id'] = rca_wo['id']
            await create_notification('work_order', f"RCA Task Assigned: {bd['machine_name']}",
                                      f"{wo_num} \u2014 Detailed root-cause submission required for {bd['ticket_number']} (downtime {downtime:.0f} min)",
                                      severity='warning', machine_id=bd['machine_id'], machine_name=bd['machine_name'],
                                      reference_id=rca_wo['id'], reference_type='work_order')
            await create_timeline_event('wo_assigned', machine_id=bd['machine_id'], machine_name=bd['machine_name'],
                                        title=f"RCA follow-up {wo_num} auto-assigned to {tech}", user='system',
                                        reference_id=rca_wo['id'], reference_type='work_order', department=bd['department'], line=bd['line'])

        await db.breakdowns.update_one({'id': bd_id}, {'$set': updates})
        # repair event record
        await db.repair_events.insert_one({
            'id': str(uuid.uuid4()), 'breakdown_id': bd_id, 'ticket_number': bd['ticket_number'],
            'machine_id': bd['machine_id'], 'machine_name': bd['machine_name'],
            'technician': bd.get('assigned_to') or user['username'],
            'downtime_minutes': downtime, 'repair_duration_minutes': repair_duration,
            'root_cause': root_cause, 'action_taken': req.action_taken, 'created_at': now_iso(),
        })
        if machine:
            await db.machines.update_one({'id': machine['id']}, {'$set': {'status': 'running', 'inspection_recommended': False}})
            machine['status'] = 'running'
            await broadcast_machine_update(machine)
        await create_timeline_event('breakdown_closed', machine_id=bd['machine_id'], machine_name=bd['machine_name'],
                                    title=f"Breakdown {bd['ticket_number']} {new_status.lower()}",
                                    description=f"Downtime {downtime:.0f} min. {req.action_taken or ''}",
                                    user=user['username'], reference_id=bd_id, reference_type='breakdown',
                                    department=bd['department'], line=bd['line'])
        await create_notification('breakdown', f"Breakdown {new_status.title()}: {bd['machine_name']}",
                                  f"{bd['ticket_number']} resolved \u2014 downtime {downtime:.0f} min", severity='success',
                                  machine_id=bd['machine_id'], machine_name=bd['machine_name'], reference_id=bd_id, reference_type='breakdown')
        # reliability recompute (starts immediately after first breakdown)
        from reliability import recompute_machine_reliability
        await recompute_machine_reliability(bd['machine_id'], trigger='breakdown_closed')
        return {'ok': True, 'status': new_status, 'downtime_minutes': downtime}

    raise HTTPException(status_code=400, detail='Invalid action')


# ============ WORK ORDERS ============
class WOCreate(BaseModel):
    machine_id: str
    title: str
    description: Optional[str] = None
    wo_type: str = 'Corrective'  # Corrective | Preventive | Inspection
    priority: str = 'medium'
    assigned_to: Optional[str] = None


@router.post('/work-orders')
async def create_work_order(req: WOCreate, user: dict = Depends(require_admin_or_tech)):
    machine = await db.machines.find_one({'id': req.machine_id}, {'_id': 0})
    if not machine:
        raise HTTPException(status_code=404, detail='Machine not found')
    if req.wo_type not in ('Corrective', 'Preventive', 'Inspection'):
        raise HTTPException(status_code=400, detail='Invalid wo_type')
    wo_num = await next_counter('work_orders', 'WO')
    wo = {
        'id': str(uuid.uuid4()), 'wo_number': wo_num, 'wo_type': req.wo_type,
        'title': req.title, 'description': req.description,
        'machine_id': machine['id'], 'machine_name': machine['name'],
        'department': machine['department'], 'line': machine['line'],
        'assigned_to': req.assigned_to, 'priority': req.priority,
        'status': 'ASSIGNED' if req.assigned_to else 'OPEN',
        'root_cause': None, 'action_taken': None, 'spare_parts': [],
        'duration_minutes': None, 'source': 'manual', 'auto_generated': False, 'created_at': now_iso(),
    }
    await db.work_orders.insert_one(dict(wo))
    await create_timeline_event('wo_created', machine_id=machine['id'], machine_name=machine['name'],
                                title=f"WO {wo_num} created: {req.title}", user=user['username'],
                                reference_id=wo['id'], reference_type='work_order', department=machine['department'], line=machine['line'])
    await create_notification('work_order', f"Work Order: {machine['name']}", f"{wo_num} \u2014 {req.title}",
                              severity='info', machine_id=machine['id'], machine_name=machine['name'],
                              reference_id=wo['id'], reference_type='work_order')
    wo.pop('_id', None)
    return wo


@router.get('/work-orders')
async def list_work_orders(machine_id: Optional[str] = None, status: Optional[str] = None,
                           wo_type: Optional[str] = None, assigned_to: Optional[str] = None,
                           search: Optional[str] = None, limit: int = Query(200, le=2000), skip: int = 0,
                           user: dict = Depends(require_admin_or_tech)):
    q = {}
    if machine_id:
        q['machine_id'] = machine_id
    if status:
        q['status'] = status
    if wo_type:
        q['wo_type'] = wo_type
    if assigned_to:
        q['assigned_to'] = assigned_to
    if search:
        q['$or'] = [{'wo_number': {'$regex': search, '$options': 'i'}}, {'machine_name': {'$regex': search, '$options': 'i'}}, {'title': {'$regex': search, '$options': 'i'}}]
    total = await db.work_orders.count_documents(q)
    items = await db.work_orders.find(q, {'_id': 0}).sort('created_at', -1).skip(skip).limit(limit).to_list(limit)
    return {'items': items, 'total': total}


class WOUpdate(BaseModel):
    action: str  # assign | start | complete | close | update
    assigned_to: Optional[str] = None
    root_cause: Optional[str] = None
    action_taken: Optional[str] = None
    spare_parts: Optional[List[SpareUse]] = None
    duration_minutes: Optional[float] = None
    checklist_results: Optional[dict] = None


@router.put('/work-orders/{wo_id}')
async def update_work_order(wo_id: str, req: WOUpdate, user: dict = Depends(require_admin_or_tech)):
    wo = await db.work_orders.find_one({'id': wo_id}, {'_id': 0})
    if not wo:
        raise HTTPException(status_code=404, detail='Work order not found')

    if req.action == 'assign':
        if not req.assigned_to:
            raise HTTPException(status_code=400, detail='assigned_to required')
        await db.work_orders.update_one({'id': wo_id}, {'$set': {'status': 'ASSIGNED', 'assigned_to': req.assigned_to}})
        await create_notification('work_order', f"WO Assigned: {wo['machine_name']}",
                                  f"{wo['wo_number']} assigned to {req.assigned_to}", severity='info',
                                  machine_id=wo['machine_id'], machine_name=wo['machine_name'], reference_id=wo_id, reference_type='work_order')
        await create_timeline_event('wo_assigned', machine_id=wo['machine_id'], machine_name=wo['machine_name'],
                                    title=f"{wo['wo_number']} assigned to {req.assigned_to}", user=user['username'],
                                    reference_id=wo_id, reference_type='work_order', department=wo.get('department'), line=wo.get('line'))
        return {'ok': True, 'status': 'ASSIGNED'}

    if req.action == 'start':
        updates = {'status': 'IN_PROGRESS', 'started_at': now_iso()}
        if not wo.get('assigned_to'):
            updates['assigned_to'] = user['username']
        await db.work_orders.update_one({'id': wo_id}, {'$set': updates})
        return {'ok': True, 'status': 'IN_PROGRESS'}

    if req.action in ('complete', 'close'):
        spares = [s.model_dump() for s in (req.spare_parts or [])]
        if spares:
            from routers_spares import consume_spares
            spares = await consume_spares(spares, 'WORKORDER_CONSUMPTION', wo_id, f"Work Order {wo['wo_number']}",
                                          wo['machine_id'], wo['machine_name'], user['username'])
        started = wo.get('started_at') or wo.get('created_at')
        duration = req.duration_minutes
        if duration is None and started:
            try:
                duration = round((datetime.now(timezone.utc) - parse_dt(started)).total_seconds() / 60.0, 1)
            except Exception:
                duration = None
        new_status = 'COMPLETED' if req.action == 'complete' else 'CLOSED'
        updates = {
            'status': new_status, 'completed_at': now_iso(),
            'root_cause': req.root_cause or wo.get('root_cause'),
            'action_taken': req.action_taken or wo.get('action_taken'),
            'duration_minutes': duration,
        }
        if spares:
            updates['spare_parts'] = (wo.get('spare_parts') or []) + spares
        if req.checklist_results:
            updates['checklist_results'] = req.checklist_results
        await db.work_orders.update_one({'id': wo_id}, {'$set': updates})

        # if PM-generated, mark PM occurrence complete
        if wo.get('pm_task_id'):
            await db.pm_tasks.update_one({'id': wo['pm_task_id']}, {'$set': {'last_completed_at': now_iso()}})
            await create_timeline_event('pm_completed', machine_id=wo['machine_id'], machine_name=wo['machine_name'],
                                        title=f"PM completed: {wo['title']}", user=user['username'],
                                        reference_id=wo['pm_task_id'], reference_type='pm_task', department=wo.get('department'), line=wo.get('line'))

        await create_timeline_event('wo_completed', machine_id=wo['machine_id'], machine_name=wo['machine_name'],
                                    title=f"WO {wo['wo_number']} {new_status.lower()}",
                                    description=req.action_taken or '', user=user['username'],
                                    reference_id=wo_id, reference_type='work_order', department=wo.get('department'), line=wo.get('line'))
        await create_notification('work_order', f"WO {new_status.title()}: {wo['machine_name']}",
                                  f"{wo['wo_number']} \u2014 {wo['title']}", severity='success',
                                  machine_id=wo['machine_id'], machine_name=wo['machine_name'], reference_id=wo_id, reference_type='work_order')
        return {'ok': True, 'status': new_status}

    if req.action == 'update':
        updates = {}
        if req.root_cause is not None:
            updates['root_cause'] = req.root_cause
        if req.action_taken is not None:
            updates['action_taken'] = req.action_taken
        if updates:
            await db.work_orders.update_one({'id': wo_id}, {'$set': updates})
        return {'ok': True}

    raise HTTPException(status_code=400, detail='Invalid action')


# ============ PREVENTIVE MAINTENANCE ============
FREQ_DAYS = {'daily': 1, 'weekly': 7, 'monthly': 30, 'quarterly': 91, 'yearly': 365, 'once': 0}


class PMTaskCreate(BaseModel):
    task_name: str
    description: Optional[str] = None
    priority: str = 'medium'
    machine_id: str
    assigned_to: Optional[str] = None
    frequency: str = 'monthly'
    checklist: List[str] = Field(default_factory=list)
    reminder_offset_days: int = 1
    next_due_date: Optional[str] = None


@router.post('/pm-tasks')
async def create_pm_task(req: PMTaskCreate, user: dict = Depends(require_admin)):
    machine = await db.machines.find_one({'id': req.machine_id}, {'_id': 0})
    if not machine:
        raise HTTPException(status_code=404, detail='Machine not found')
    if req.frequency not in FREQ_DAYS:
        raise HTTPException(status_code=400, detail=f'Invalid frequency. Valid: {list(FREQ_DAYS)}')
    due = req.next_due_date or (datetime.now(timezone.utc) + timedelta(days=FREQ_DAYS.get(req.frequency, 30))).date().isoformat()
    task = {
        'id': str(uuid.uuid4()), 'task_name': req.task_name, 'description': req.description,
        'priority': req.priority, 'machine_id': machine['id'], 'machine_name': machine['name'],
        'department': machine['department'], 'line': machine['line'],
        'assigned_to': req.assigned_to, 'frequency': req.frequency, 'checklist': req.checklist,
        'reminder_offset_days': req.reminder_offset_days, 'next_due_date': due,
        'status': 'active', 'source': 'manual', 'auto_generated': False, 'active': True,
        'last_generated_date': None, 'last_completed_at': None, 'reminder_sent_for': None, 'overdue_sent_for': None,
        'created_at': now_iso(),
    }
    await db.pm_tasks.insert_one(dict(task))
    await create_timeline_event('pm_created', machine_id=machine['id'], machine_name=machine['name'],
                                title=f"PM task created: {req.task_name}", user=user['username'],
                                reference_id=task['id'], reference_type='pm_task', department=machine['department'], line=machine['line'])
    task.pop('_id', None)
    return task


@router.get('/pm-tasks')
async def list_pm_tasks(machine_id: Optional[str] = None, status: Optional[str] = None, frequency: Optional[str] = None,
                        due: Optional[str] = None, limit: int = Query(500, le=5000), skip: int = 0,
                        user: dict = Depends(get_current_user)):
    q = {}
    if machine_id:
        q['machine_id'] = machine_id
    if status:
        q['status'] = status
    if frequency:
        q['frequency'] = frequency
    if due == 'overdue':
        q['next_due_date'] = {'$lt': now_iso()[:10]}
        q['active'] = True
    total = await db.pm_tasks.count_documents(q)
    items = await db.pm_tasks.find(q, {'_id': 0}).sort('next_due_date', 1).skip(skip).limit(limit).to_list(limit)
    return {'items': items, 'total': total}


class PMTaskUpdate(BaseModel):
    task_name: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    assigned_to: Optional[str] = None
    frequency: Optional[str] = None
    checklist: Optional[List[str]] = None
    reminder_offset_days: Optional[int] = None
    next_due_date: Optional[str] = None
    active: Optional[bool] = None
    status: Optional[str] = None


@router.put('/pm-tasks/{task_id}')
async def update_pm_task(task_id: str, req: PMTaskUpdate, user: dict = Depends(require_admin)):
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if not updates:
        return {'ok': True}
    await db.pm_tasks.update_one({'id': task_id}, {'$set': updates})
    return {'ok': True}


@router.delete('/pm-tasks/{task_id}')
async def delete_pm_task(task_id: str, user: dict = Depends(require_admin)):
    await db.pm_tasks.update_one({'id': task_id}, {'$set': {'active': False, 'status': 'retired'}})
    return {'ok': True}


class PMComplete(BaseModel):
    remarks: Optional[str] = None
    checklist_results: Optional[dict] = None
    spares_consumed: Optional[List[SpareUse]] = None


@router.post('/pm-tasks/{task_id}/complete')
async def complete_pm_task(task_id: str, req: PMComplete, user: dict = Depends(require_admin_or_tech)):
    task = await db.pm_tasks.find_one({'id': task_id}, {'_id': 0})
    if not task:
        raise HTTPException(status_code=404, detail='PM task not found')
    spares = [s.model_dump() for s in (req.spares_consumed or [])]
    if spares:
        from routers_spares import consume_spares
        spares = await consume_spares(spares, 'PM_CONSUMPTION', task_id, f"PM {task['task_name']}",
                                      task['machine_id'], task['machine_name'], user['username'])
    completion = {
        'id': str(uuid.uuid4()), 'pm_task_id': task_id, 'task_name': task['task_name'],
        'machine_id': task['machine_id'], 'machine_name': task['machine_name'],
        'completed_by': user['username'], 'remarks': req.remarks,
        'checklist_results': req.checklist_results, 'spares_consumed': spares,
        'due_date': task.get('next_due_date'), 'completed_at': now_iso(),
        'on_time': task.get('next_due_date', '9999') >= now_iso()[:10],
    }
    await db.pm_completions.insert_one(dict(completion))
    freq_days = FREQ_DAYS.get(task.get('frequency', 'monthly'), 30)
    updates = {'last_completed_at': now_iso(), 'reminder_sent_for': None, 'overdue_sent_for': None}
    if freq_days > 0:
        updates['next_due_date'] = (datetime.now(timezone.utc) + timedelta(days=freq_days)).date().isoformat()
    else:
        updates['status'] = 'completed'
        updates['active'] = False
    await db.pm_tasks.update_one({'id': task_id}, {'$set': updates})
    await create_timeline_event('pm_completed', machine_id=task['machine_id'], machine_name=task['machine_name'],
                                title=f"PM completed: {task['task_name']}", description=req.remarks or '',
                                user=user['username'], reference_id=task_id, reference_type='pm_task',
                                department=task.get('department'), line=task.get('line'))
    await create_notification('work_order', f"PM Completed: {task['machine_name']}",
                              f"{task['task_name']} completed by {user['username']}", severity='success',
                              machine_id=task['machine_id'], machine_name=task['machine_name'], reference_id=task_id, reference_type='pm_task')
    completion.pop('_id', None)
    return completion


@router.get('/pm-completions')
async def list_pm_completions(machine_id: Optional[str] = None, limit: int = Query(200, le=2000), user: dict = Depends(get_current_user)):
    q = {'machine_id': machine_id} if machine_id else {}
    return await db.pm_completions.find(q, {'_id': 0}).sort('completed_at', -1).limit(limit).to_list(limit)


@router.get('/pm-templates')
async def list_pm_templates(user: dict = Depends(get_current_user)):
    return await db.pm_templates.find({}, {'_id': 0}).to_list(1000)
