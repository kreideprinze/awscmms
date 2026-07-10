"""Maintenance routes: breakdowns (lifecycle + 30-min root-cause rule), work orders, PM tasks & templates."""
import re as _re
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
    assigned_to: Optional[str] = None  # REQUIRED (validated in endpoint) — technician who will attend
    start_time: Optional[str] = None


async def _validate_technician(username):
    """Mandatory technician assignment: must be an existing, active technician."""
    if not username or not str(username).strip():
        raise HTTPException(status_code=400, detail='Assigned technician is required — select a technician for this report')
    tech = await db.users.find_one({'username': username, 'role': 'technician', 'active': True}, {'_id': 0, 'username': 1})
    if not tech:
        raise HTTPException(status_code=400, detail=f'Invalid technician "{username}" — must be an active technician')
    return username


async def _pick_technician():
    """Least-loaded active technician (fewest open work orders)."""
    techs = await db.users.find({'role': 'technician', 'active': True}, {'_id': 0, 'username': 1}).to_list(1000)
    if not techs:
        return None
    counts = {t['username']: 0 for t in techs}
    agg = await db.work_orders.aggregate([
        {'$match': {'status': {'$in': ['OPEN', 'ASSIGNED', 'IN_PROGRESS']}, 'assigned_to': {'$in': list(counts)}}},
        {'$group': {'_id': '$assigned_to', 'n': {'$sum': 1}}},
    ]).to_list(1000)
    for row in agg:
        counts[row['_id']] = row['n']
    return min(counts, key=counts.get)


async def _create_rca_wo(machine_id, machine_name, department, line, tech, origin_label, origin_desc,
                         source_breakdown_id=None, source_work_order_id=None):
    """Create an auto-triggered 5-Why RCA work order assigned to the attending technician.
    RCA WOs follow the standard lifecycle but cannot be completed without a full 5-Why submission."""
    wo_num = await next_counter('work_orders', 'WO')
    rca_wo = {
        'id': str(uuid.uuid4()), 'wo_number': wo_num, 'wo_type': 'RCA',
        'title': f"5-Why RCA \u2014 {machine_name} ({origin_label})",
        'description': origin_desc,
        'machine_id': machine_id, 'machine_name': machine_name,
        'department': department, 'line': line,
        'assigned_to': tech, 'priority': 'high', 'status': 'ASSIGNED' if tech else 'OPEN',
        'root_cause': None, 'action_taken': None, 'spare_parts': [],
        'duration_minutes': None, 'source': 'rca_auto', 'rca': None,
        'source_breakdown_id': source_breakdown_id, 'source_work_order_id': source_work_order_id,
        'auto_generated': True, 'created_at': now_iso(),
    }
    await db.work_orders.insert_one(dict(rca_wo))
    await create_notification('work_order', f"RCA Required: {machine_name}",
                              f"{wo_num} \u2014 5-Why root cause analysis assigned to {tech or 'unassigned'} ({origin_label})",
                              severity='warning', machine_id=machine_id, machine_name=machine_name,
                              reference_id=rca_wo['id'], reference_type='work_order')
    await create_timeline_event('rca_triggered', machine_id=machine_id, machine_name=machine_name,
                                title=f"RCA {wo_num} auto-assigned to {tech or 'unassigned'}",
                                description=origin_desc, user='system',
                                reference_id=rca_wo['id'], reference_type='work_order', department=department, line=line)
    rca_wo.pop('_id', None)
    return rca_wo


async def _create_breakdown_internal(machine_id: str, description: str, failure_mode: str, reporter: str,
                                     start_time: str = None, breakdown_type: str = 'MECHANICAL',
                                     assigned_to: str = None):
    """A linked Corrective Work Order is ALWAYS created (no opt-out). The submitter selects the
    technician; internal callers (e.g. report conversion) fall back to least-loaded auto-pick."""
    machine = await db.machines.find_one({'id': machine_id}, {'_id': 0})
    if not machine:
        raise HTTPException(status_code=404, detail='Machine not found')
    if breakdown_type not in BREAKDOWN_TYPES:
        raise HTTPException(status_code=400, detail=f'Invalid breakdown_type. Valid: {BREAKDOWN_TYPES}')
    if not assigned_to:
        assigned_to = await _pick_technician()
    ticket = await next_counter('breakdowns', 'BD')
    bd = {
        'id': str(uuid.uuid4()), 'ticket_number': ticket,
        'machine_id': machine['id'], 'machine_name': machine['name'],
        'department': machine['department'], 'line': machine['line'], 'process_group': machine.get('process_group'),
        'failure_mode': failure_mode or breakdown_type.replace('_', ' ').title(),
        'breakdown_type': breakdown_type,
        'description': description, 'reporter': reporter,
        'status': 'ASSIGNED' if assigned_to else 'OPEN', 'assigned_to': assigned_to,
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

    # Mandatory: auto-dispatch a Corrective Work Order to the selected technician (no opt-out)
    assigned = assigned_to
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
                                title=f"WO {wo_num} dispatched to {assigned or 'maintenance'}", user='system',
                                reference_id=wo['id'], reference_type='work_order',
                                department=machine['department'], line=machine['line'])
    bd.pop('_id', None)
    return bd


@router.post('/breakdowns')
async def create_breakdown(req: BreakdownCreate, user: dict = Depends(get_current_user)):
    reporter = req.reporter_name or user['username']
    # Mandatory technician assignment — a WO is always created for the selected technician
    assigned_to = await _validate_technician(req.assigned_to)
    return await _create_breakdown_internal(req.machine_id, req.description, req.failure_mode, reporter,
                                            req.start_time, req.breakdown_type, assigned_to)


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
    # subtitle metric: count of OPEN/ACTIVE breakdowns only (not all-time total)
    open_total = await db.breakdowns.count_documents({'status': {'$in': ['OPEN', 'ASSIGNED', 'IN_PROGRESS']}})
    return {'items': items, 'total': total, 'open_total': open_total}


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
    start_time: Optional[str] = None  # editable corrected start (downtime reflects reality)
    end_time: Optional[str] = None    # editable corrected end
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
        # Corrected/edited times take precedence over the raw elapsed timer — downtime,
        # availability and the RCA trigger all evaluate against the EDITED duration.
        start_time = req.start_time or bd['start_time']
        end_time = req.end_time or bd.get('end_time') or now_iso()
        start = parse_dt(start_time)
        end = parse_dt(end_time)
        if start and end and end < start:
            raise HTTPException(status_code=400, detail='End time cannot be before start time')
        downtime = round((end - start).total_seconds() / 60.0, 1) if start and end else 0
        settings = await db.settings.find_one({'id': 'reliability_settings'}, {'_id': 0}) or {}
        rc_threshold = settings.get('root_cause_downtime_minutes', 30)

        # Root cause is NOT captured here — it belongs exclusively to the dedicated
        # 5-Why RCA work order (auto-generated below when downtime exceeds the threshold).
        root_cause = req.root_cause or bd.get('root_cause')

        repair_start = parse_dt(bd.get('repair_started_at')) or start
        repair_duration = round((end - repair_start).total_seconds() / 60.0, 1) if repair_start and end else downtime
        if repair_duration < 0:
            repair_duration = downtime

        consumed = [s.model_dump() for s in (req.consumed_spares or [])]
        if consumed:
            from routers_spares import consume_spares
            consumed = await consume_spares(consumed, 'BREAKDOWN_CONSUMPTION', bd_id, f"Breakdown {bd['ticket_number']}",
                                            bd['machine_id'], bd['machine_name'], user['username'])

        new_status = 'COMPLETED' if req.action == 'complete' else 'CLOSED'
        updates = {
            'status': new_status, 'start_time': start_time, 'end_time': end_time, 'downtime_minutes': downtime,
            'repair_duration_minutes': repair_duration, 'root_cause': root_cause,
            'action_taken': req.action_taken or bd.get('action_taken'),
        }
        if consumed:
            updates['consumed_spares'] = (bd.get('consumed_spares') or []) + consumed

        # RCA rule: EDITED/corrected downtime above threshold auto-triggers a 5-Why RCA WO
        rca_task_id = bd.get('rca_task_id')
        if downtime > rc_threshold and not rca_task_id:
            tech = bd.get('assigned_to') or user['username']
            rca_wo = await _create_rca_wo(
                bd['machine_id'], bd['machine_name'], bd['department'], bd['line'], tech,
                origin_label=bd['ticket_number'],
                origin_desc=f"Auto-triggered RCA: breakdown {bd['ticket_number']} downtime {downtime:.0f} min exceeded {rc_threshold:.0f} min threshold. Complete the structured 5-Why analysis.",
                source_breakdown_id=bd_id)
            updates['rca_task_id'] = rca_wo['id']

        await db.breakdowns.update_one({'id': bd_id}, {'$set': updates})

        # SYNC: breakdown resolution must immediately propagate to the linked Work Order
        linked_wo = None
        if bd.get('work_order_id'):
            linked_wo = await db.work_orders.find_one({'id': bd['work_order_id']}, {'_id': 0})
        if not linked_wo:
            linked_wo = await db.work_orders.find_one(
                {'source_breakdown_id': bd_id, 'wo_type': {'$ne': 'RCA'}, 'status': {'$ne': 'CLOSED'}}, {'_id': 0})
        if linked_wo and linked_wo.get('status') != 'CLOSED':
            if req.action == 'close' and user.get('role') == 'admin':
                await db.work_orders.update_one({'id': linked_wo['id']}, {'$set': {
                    'status': 'CLOSED', 'closed_by': user['username'], 'closed_at': now_iso(),
                    'completed_at': linked_wo.get('completed_at') or end_time,
                    'started_at': linked_wo.get('started_at') or start_time,
                    'duration_minutes': linked_wo.get('duration_minutes') or repair_duration,
                    'action_taken': req.action_taken or linked_wo.get('action_taken'),
                }})
                await create_timeline_event('wo_closed', machine_id=bd['machine_id'], machine_name=bd['machine_name'],
                                            title=f"WO {linked_wo['wo_number']} closed (breakdown {bd['ticket_number']} closed)",
                                            user=user['username'], reference_id=linked_wo['id'], reference_type='work_order',
                                            department=bd['department'], line=bd['line'])
            elif linked_wo.get('status') != 'PENDING_ADMIN_CLOSURE':
                await db.work_orders.update_one({'id': linked_wo['id']}, {'$set': {
                    'status': 'PENDING_ADMIN_CLOSURE',
                    'started_at': linked_wo.get('started_at') or start_time,
                    'completed_at': end_time,
                    'duration_minutes': repair_duration,
                    'action_taken': req.action_taken or linked_wo.get('action_taken'),
                }})
                await create_timeline_event('wo_completed', machine_id=bd['machine_id'], machine_name=bd['machine_name'],
                                            title=f"WO {linked_wo['wo_number']} completed — awaiting admin closure",
                                            description=f"Synced from breakdown {bd['ticket_number']} resolution",
                                            user=user['username'], reference_id=linked_wo['id'], reference_type='work_order',
                                            department=bd['department'], line=bd['line'])
                await create_notification('work_order', f"Admin Review Required: {bd['machine_name']}",
                                          f"{linked_wo['wo_number']} — repair of {bd['ticket_number']} completed by {user['username']}. Admin closure required.",
                                          severity='warning', machine_id=bd['machine_id'], machine_name=bd['machine_name'],
                                          reference_id=linked_wo['id'], reference_type='work_order', target_role='admin')

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
    # Mandatory technician assignment — no WO is ever created unassigned/OPEN
    assigned_to = await _validate_technician(req.assigned_to)
    wo_num = await next_counter('work_orders', 'WO')
    wo = {
        'id': str(uuid.uuid4()), 'wo_number': wo_num, 'wo_type': req.wo_type,
        'title': req.title, 'description': req.description,
        'machine_id': machine['id'], 'machine_name': machine['name'],
        'department': machine['department'], 'line': machine['line'],
        'assigned_to': assigned_to, 'priority': req.priority,
        'status': 'ASSIGNED',
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


@router.post('/work-orders/clear-closed')
async def clear_closed_work_orders(user: dict = Depends(require_admin_or_tech)):
    """Clear CLOSED work orders off the Kanban board (cosmetic — records remain in the
    table view, reports and analytics; sets kanban_cleared flag)."""
    res = await db.work_orders.update_many(
        {'status': 'CLOSED', 'kanban_cleared': {'$ne': True}},
        {'$set': {'kanban_cleared': True, 'kanban_cleared_by': user['username'], 'kanban_cleared_at': now_iso()}})
    return {'ok': True, 'cleared': res.modified_count}


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
    started_at: Optional[str] = None    # ISO datetime — editable via Kanban detail modal
    completed_at: Optional[str] = None  # ISO datetime — editable via Kanban detail modal


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
        if req.action == 'close' and user.get('role') != 'admin':
            raise HTTPException(status_code=403, detail='Only an Admin can close a work order (final closure requires admin review)')
        # RCA governance: an RCA work order cannot be completed/closed without a full 5-Why submission
        if wo.get('wo_type') == 'RCA':
            rca = wo.get('rca') or {}
            whys = [w for w in (rca.get('whys') or []) if str(w or '').strip()]
            if len(whys) < 5 or not str(rca.get('root_cause') or '').strip() or not str(rca.get('corrective_action') or '').strip():
                raise HTTPException(status_code=400, detail='RCA work order cannot be completed: submit all 5 Whys, the final Root Cause and Corrective Action first')
        spares = [s.model_dump() for s in (req.spare_parts or [])]
        if spares:
            from routers_spares import consume_spares
            spares = await consume_spares(spares, 'WORKORDER_CONSUMPTION', wo_id, f"Work Order {wo['wo_number']}",
                                          wo['machine_id'], wo['machine_name'], user['username'])
        # Corrected/edited execution times take precedence over the raw timer — the duration
        # (and therefore the RCA trigger) evaluates against the edited values.
        started = req.started_at or wo.get('started_at') or wo.get('created_at')
        ended = req.completed_at or now_iso()
        s_dt, e_dt = (parse_dt(started) if started else None), parse_dt(ended)
        if s_dt and e_dt and e_dt < s_dt:
            raise HTTPException(status_code=400, detail='End time cannot be before start time')
        duration = req.duration_minutes
        if duration is None and s_dt and e_dt:
            duration = round((e_dt - s_dt).total_seconds() / 60.0, 1)
        # Lifecycle: tech completion parks the WO at PENDING_ADMIN_CLOSURE; only admin can CLOSE
        new_status = 'PENDING_ADMIN_CLOSURE' if req.action == 'complete' else 'CLOSED'
        updates = {
            'status': new_status, 'completed_at': ended,
            'root_cause': req.root_cause or wo.get('root_cause'),
            'action_taken': req.action_taken or wo.get('action_taken'),
            'duration_minutes': duration if req.action == 'complete' else (wo.get('duration_minutes') or duration),
        }
        if req.started_at:
            updates['started_at'] = req.started_at
        if req.action == 'close':
            updates['closed_at'] = now_iso()
            updates['closed_by'] = user['username']
        if spares:
            updates['spare_parts'] = (wo.get('spare_parts') or []) + spares
        if req.checklist_results:
            updates['checklist_results'] = req.checklist_results
        await db.work_orders.update_one({'id': wo_id}, {'$set': updates})

        # if PM-generated, mark PM occurrence complete on tech completion
        if wo.get('pm_task_id') and req.action == 'complete':
            await db.pm_tasks.update_one({'id': wo['pm_task_id']}, {'$set': {'last_completed_at': now_iso()}})
            await create_timeline_event('pm_completed', machine_id=wo['machine_id'], machine_name=wo['machine_name'],
                                        title=f"PM completed: {wo['title']}", user=user['username'],
                                        reference_id=wo['pm_task_id'], reference_type='pm_task', department=wo.get('department'), line=wo.get('line'))

        # warning-sourced WO fully closed by admin -> resolve warning, restore machine from watch
        if req.action == 'close' and wo.get('source_warning_id'):
            await db.warnings.update_one({'id': wo['source_warning_id']}, {'$set': {'status': 'CLOSED', 'closed_at': now_iso()}})
            machine = await db.machines.find_one({'id': wo['machine_id']}, {'_id': 0})
            if machine and machine.get('status') == 'watch':
                await db.machines.update_one({'id': machine['id']}, {'$set': {'status': 'running'}})
                machine['status'] = 'running'
                await broadcast_machine_update(machine)

        # SYNC: WO admin-closure is the single closure point — auto-close the linked breakdown.
        # (The redundant breakdown-level "Final Close" has been removed from the UI.)
        if req.action == 'close' and wo.get('source_breakdown_id') and wo.get('wo_type') != 'RCA':
            origin_bd = await db.breakdowns.find_one({'id': wo['source_breakdown_id']}, {'_id': 0})
            if origin_bd and origin_bd.get('status') != 'CLOSED':
                bd_updates = {'status': 'CLOSED'}
                if not origin_bd.get('end_time'):
                    end_now = now_iso()
                    bd_updates['end_time'] = end_now
                    s_dt, e_dt = parse_dt(origin_bd.get('start_time')), parse_dt(end_now)
                    if s_dt and e_dt:
                        bd_updates['downtime_minutes'] = round((e_dt - s_dt).total_seconds() / 60.0, 1)
                await db.breakdowns.update_one({'id': origin_bd['id']}, {'$set': bd_updates})
                machine = await db.machines.find_one({'id': origin_bd['machine_id']}, {'_id': 0})
                if machine and machine.get('status') in ('failed', 'down', 'repair'):
                    await db.machines.update_one({'id': machine['id']}, {'$set': {'status': 'running'}})
                    machine['status'] = 'running'
                    await broadcast_machine_update(machine)
                await create_timeline_event('breakdown_closed', machine_id=origin_bd['machine_id'], machine_name=origin_bd['machine_name'],
                                            title=f"Breakdown {origin_bd['ticket_number']} closed (via WO {wo['wo_number']} admin closure)",
                                            user=user['username'], reference_id=origin_bd['id'], reference_type='breakdown',
                                            department=origin_bd.get('department'), line=origin_bd.get('line'))

        # RCA rule: WO duration above threshold auto-triggers a 5-Why RCA WO for the attending technician
        # (skipped for RCA WOs themselves, and when the originating breakdown already triggered one)
        if req.action == 'complete' and wo.get('wo_type') != 'RCA' and not wo.get('rca_task_id'):
            settings = await db.settings.find_one({'id': 'reliability_settings'}, {'_id': 0}) or {}
            rc_threshold = settings.get('root_cause_downtime_minutes', 30)
            if (duration or 0) > rc_threshold:
                already = False
                if wo.get('source_breakdown_id'):
                    origin_bd = await db.breakdowns.find_one({'id': wo['source_breakdown_id']}, {'_id': 0, 'rca_task_id': 1})
                    already = bool(origin_bd and origin_bd.get('rca_task_id'))
                if not already:
                    tech = wo.get('assigned_to') or user['username']
                    rca_wo = await _create_rca_wo(
                        wo['machine_id'], wo['machine_name'], wo.get('department'), wo.get('line'), tech,
                        origin_label=wo['wo_number'],
                        origin_desc=f"Auto-triggered RCA: work order {wo['wo_number']} duration {duration:.0f} min exceeded {rc_threshold:.0f} min threshold. Complete the structured 5-Why analysis.",
                        source_work_order_id=wo_id, source_breakdown_id=wo.get('source_breakdown_id'))
                    await db.work_orders.update_one({'id': wo_id}, {'$set': {'rca_task_id': rca_wo['id']}})
                    if wo.get('source_breakdown_id'):
                        await db.breakdowns.update_one({'id': wo['source_breakdown_id']}, {'$set': {'rca_task_id': rca_wo['id']}})

        await create_timeline_event('wo_completed', machine_id=wo['machine_id'], machine_name=wo['machine_name'],
                                    title=f"WO {wo['wo_number']} {'completed — awaiting admin closure' if req.action == 'complete' else 'closed'}",
                                    description=req.action_taken or '', user=user['username'],
                                    reference_id=wo_id, reference_type='work_order', department=wo.get('department'), line=wo.get('line'))
        if req.action == 'complete':
            await create_notification('work_order', f"Admin Review Required: {wo['machine_name']}",
                                      f"{wo['wo_number']} — {wo['title']} completed by {user['username']}. Admin closure required.",
                                      severity='warning', machine_id=wo['machine_id'], machine_name=wo['machine_name'],
                                      reference_id=wo_id, reference_type='work_order', target_role='admin')
        else:
            await create_notification('work_order', f"WO Closed: {wo['machine_name']}",
                                      f"{wo['wo_number']} — {wo['title']} closed by admin {user['username']}", severity='success',
                                      machine_id=wo['machine_id'], machine_name=wo['machine_name'], reference_id=wo_id, reference_type='work_order')
        return {'ok': True, 'status': new_status}

    if req.action == 'update':
        updates = {}
        if req.root_cause is not None:
            updates['root_cause'] = req.root_cause
        if req.action_taken is not None:
            updates['action_taken'] = req.action_taken
        # Start/End time edits — restricted to Admins or the assigned Technician
        if req.started_at is not None or req.completed_at is not None:
            if user.get('role') != 'admin' and wo.get('assigned_to') != user['username']:
                raise HTTPException(status_code=403, detail='Only an Admin or the assigned technician can edit work order times')
            start_s = req.started_at if req.started_at is not None else wo.get('started_at')
            end_s = req.completed_at if req.completed_at is not None else wo.get('completed_at')
            start_dt = parse_dt(start_s) if start_s else None
            end_dt = parse_dt(end_s) if end_s else None
            if start_dt and end_dt and end_dt < start_dt:
                raise HTTPException(status_code=400, detail='End time cannot be before start time')
            if req.started_at is not None:
                updates['started_at'] = req.started_at or None
            if req.completed_at is not None:
                updates['completed_at'] = req.completed_at or None
            if start_dt and end_dt:
                updates['duration_minutes'] = round((end_dt - start_dt).total_seconds() / 60.0, 1)
            await create_timeline_event('wo_updated', machine_id=wo['machine_id'], machine_name=wo['machine_name'],
                                        title=f"WO {wo['wo_number']} times updated", user=user['username'],
                                        reference_id=wo_id, reference_type='work_order', department=wo.get('department'), line=wo.get('line'))
        if updates:
            await db.work_orders.update_one({'id': wo_id}, {'$set': updates})
        updated = await db.work_orders.find_one({'id': wo_id}, {'_id': 0})
        return {'ok': True, 'work_order': updated}

    raise HTTPException(status_code=400, detail='Invalid action')


# ============ ROOT CAUSE ANALYSIS (5-WHY) ============
class RCASubmit(BaseModel):
    whys: List[str]  # exactly 5 sequential "Why did this happen?" answers
    root_cause: str
    corrective_action: str


@router.put('/work-orders/{wo_id}/rca')
async def submit_rca(wo_id: str, req: RCASubmit, user: dict = Depends(require_admin_or_tech)):
    """Submit/update the structured 5-Why analysis on an RCA work order.
    Restricted to Admins or the assigned technician. All 5 Whys + Root Cause + Corrective Action are mandatory."""
    wo = await db.work_orders.find_one({'id': wo_id}, {'_id': 0})
    if not wo:
        raise HTTPException(status_code=404, detail='Work order not found')
    if wo.get('wo_type') != 'RCA':
        raise HTTPException(status_code=400, detail='This work order is not an RCA work order')
    if wo.get('status') in ('PENDING_ADMIN_CLOSURE', 'CLOSED'):
        raise HTTPException(status_code=400, detail='RCA already completed — cannot be edited')
    if user.get('role') != 'admin' and wo.get('assigned_to') != user['username']:
        raise HTTPException(status_code=403, detail='Only an Admin or the assigned technician can submit this RCA')
    whys = [str(w or '').strip() for w in (req.whys or [])]
    if len(whys) != 5 or any(not w for w in whys):
        raise HTTPException(status_code=400, detail='All five sequential "Why" answers are required')
    root_cause = req.root_cause.strip()
    corrective = req.corrective_action.strip()
    if not root_cause or not corrective:
        raise HTTPException(status_code=400, detail='Final Root Cause and Corrective Action are required')
    rca = {'whys': whys, 'root_cause': root_cause, 'corrective_action': corrective,
           'submitted_by': user['username'], 'submitted_at': now_iso()}
    await db.work_orders.update_one({'id': wo_id}, {'$set': {
        'rca': rca, 'root_cause': root_cause, 'action_taken': corrective,
    }})
    await create_timeline_event('rca_submitted', machine_id=wo['machine_id'], machine_name=wo['machine_name'],
                                title=f"5-Why RCA submitted for {wo['wo_number']}", description=f"Root cause: {root_cause}",
                                user=user['username'], reference_id=wo_id, reference_type='work_order',
                                department=wo.get('department'), line=wo.get('line'))
    updated = await db.work_orders.find_one({'id': wo_id}, {'_id': 0})
    return {'ok': True, 'work_order': updated}


@router.get('/work-orders/{wo_id}')
async def get_work_order(wo_id: str, user: dict = Depends(require_admin_or_tech)):
    """Single WO detail — includes linked RCA summary (for origin WOs) or origin references (for RCA WOs)."""
    wo = await db.work_orders.find_one({'id': wo_id}, {'_id': 0})
    if not wo:
        raise HTTPException(status_code=404, detail='Work order not found')
    if wo.get('rca_task_id'):
        wo['rca_work_order'] = await db.work_orders.find_one(
            {'id': wo['rca_task_id']}, {'_id': 0, 'id': 1, 'wo_number': 1, 'status': 1, 'rca': 1, 'assigned_to': 1})
    if wo.get('source_breakdown_id'):
        wo['origin_breakdown'] = await db.breakdowns.find_one(
            {'id': wo['source_breakdown_id']}, {'_id': 0, 'id': 1, 'ticket_number': 1, 'status': 1, 'downtime_minutes': 1, 'description': 1})
    if wo.get('source_work_order_id'):
        wo['origin_work_order'] = await db.work_orders.find_one(
            {'id': wo['source_work_order_id']}, {'_id': 0, 'id': 1, 'wo_number': 1, 'status': 1, 'title': 1, 'duration_minutes': 1})
    return wo


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
    checklist_groups: Optional[List[dict]] = None  # [{description, items: [{checked_for, parameter}]}]
    location: Optional[str] = None
    reminder_offset_days: int = 1
    next_due_date: Optional[str] = None


def _normalize_groups(groups):
    """Validate + normalize structured checklist groups (component -> sub-items)."""
    out = []
    for g in groups or []:
        desc = str(g.get('description', '')).strip()
        if not desc:
            continue
        items = []
        for it in g.get('items', []) or []:
            cf = str(it.get('checked_for', '')).strip()
            if not cf:
                continue
            items.append({'checked_for': cf, 'parameter': str(it.get('parameter', '')).strip()})
        if items:
            out.append({'description': desc, 'items': items})
    return out


def _groups_to_flat(groups):
    return [f"{g['description']} — {i['checked_for']}" for g in groups for i in g['items']]


@router.post('/pm-tasks')
async def create_pm_task(req: PMTaskCreate, user: dict = Depends(require_admin)):
    machine = await db.machines.find_one({'id': req.machine_id}, {'_id': 0})
    if not machine:
        raise HTTPException(status_code=404, detail='Machine not found')
    if req.frequency not in FREQ_DAYS:
        raise HTTPException(status_code=400, detail=f'Invalid frequency. Valid: {list(FREQ_DAYS)}')
    due = req.next_due_date or (datetime.now(timezone.utc) + timedelta(days=FREQ_DAYS.get(req.frequency, 30))).date().isoformat()
    groups = _normalize_groups(req.checklist_groups)
    flat = _groups_to_flat(groups) if groups else req.checklist
    task = {
        'id': str(uuid.uuid4()), 'task_name': req.task_name, 'description': req.description,
        'priority': req.priority, 'machine_id': machine['id'], 'machine_name': machine['name'],
        'department': machine['department'], 'line': machine['line'],
        'assigned_to': req.assigned_to, 'frequency': req.frequency, 'checklist': flat,
        'checklist_groups': groups, 'location': req.location or machine.get('process_group'),
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
    checklist_groups: Optional[List[dict]] = None
    location: Optional[str] = None
    reminder_offset_days: Optional[int] = None
    next_due_date: Optional[str] = None
    active: Optional[bool] = None
    status: Optional[str] = None


@router.get('/pm-tasks/{task_id}')
async def get_pm_task(task_id: str, user: dict = Depends(get_current_user)):
    task = await db.pm_tasks.find_one({'id': task_id}, {'_id': 0})
    if not task:
        raise HTTPException(status_code=404, detail='PM task not found')
    return task


@router.put('/pm-tasks/{task_id}')
async def update_pm_task(task_id: str, req: PMTaskUpdate, user: dict = Depends(require_admin)):
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if 'checklist_groups' in updates:
        updates['checklist_groups'] = _normalize_groups(updates['checklist_groups'])
        updates['checklist'] = _groups_to_flat(updates['checklist_groups'])
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
    row_results: Optional[List[dict]] = None  # [{sn, description, checked_for, parameter, status: OK|NOT_OK, remarks}]
    done_by: Optional[str] = None
    checked_by: Optional[str] = None
    checklist_date: Optional[str] = None  # editable Date on the checklist sheet (YYYY-MM-DD)
    spares_consumed: Optional[List[SpareUse]] = None


@router.post('/pm-tasks/{task_id}/complete')
async def complete_pm_task(task_id: str, req: PMComplete, user: dict = Depends(require_admin_or_tech)):
    task = await db.pm_tasks.find_one({'id': task_id}, {'_id': 0})
    if not task:
        raise HTTPException(status_code=404, detail='PM task not found')
    rows = []
    for r in req.row_results or []:
        status = str(r.get('status', '')).upper().replace(' ', '_')
        if status not in ('OK', 'NOT_OK'):
            raise HTTPException(status_code=400, detail=f"Invalid row status '{r.get('status')}' — must be OK or NOT_OK")
        rows.append({
            'sn': r.get('sn'), 'description': str(r.get('description', '')),
            'checked_for': str(r.get('checked_for', '')), 'parameter': str(r.get('parameter', '')),
            'status': status, 'remarks': str(r.get('remarks', '') or ''),
        })
    spares = [s.model_dump() for s in (req.spares_consumed or [])]
    if spares:
        from routers_spares import consume_spares
        spares = await consume_spares(spares, 'PM_CONSUMPTION', task_id, f"PM {task['task_name']}",
                                      task['machine_id'], task['machine_name'], user['username'])
    completion = {
        'id': str(uuid.uuid4()), 'pm_task_id': task_id, 'task_name': task['task_name'],
        'machine_id': task['machine_id'], 'machine_name': task['machine_name'],
        'line': task.get('line'), 'location': task.get('location'), 'frequency': task.get('frequency'),
        'completed_by': user['username'], 'remarks': req.remarks,
        'checklist_results': req.checklist_results, 'row_results': rows,
        'done_by': req.done_by or user.get('name') or user['username'],
        'checked_by': req.checked_by, 'spares_consumed': spares,
        'checklist_date': req.checklist_date or now_iso()[:10],
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

    # Lifecycle standardization: any open WO linked to this PM parks at PENDING_ADMIN_CLOSURE
    # (identical to the Corrective flow) — only an Admin can perform final closure.
    open_wos = await db.work_orders.find(
        {'pm_task_id': task_id, 'status': {'$in': ['OPEN', 'ASSIGNED', 'IN_PROGRESS']}}, {'_id': 0}).to_list(50)
    for wo in open_wos:
        started = wo.get('started_at') or wo.get('created_at')
        duration = None
        if started:
            try:
                duration = round((datetime.now(timezone.utc) - parse_dt(started)).total_seconds() / 60.0, 1)
            except Exception:
                duration = None
        await db.work_orders.update_one({'id': wo['id']}, {'$set': {
            'status': 'PENDING_ADMIN_CLOSURE', 'completed_at': now_iso(),
            'action_taken': req.remarks or wo.get('action_taken'),
            'duration_minutes': duration, 'pm_completion_id': completion['id'],
        }})
        await create_timeline_event('wo_completed', machine_id=wo['machine_id'], machine_name=wo['machine_name'],
                                    title=f"WO {wo['wo_number']} completed — awaiting admin closure",
                                    description=f"PM checklist submitted: {task['task_name']}", user=user['username'],
                                    reference_id=wo['id'], reference_type='work_order', department=wo.get('department'), line=wo.get('line'))
        await create_notification('work_order', f"Admin Review Required: {wo['machine_name']}",
                                  f"{wo['wo_number']} — {wo['title']} (PM) completed by {user['username']}. Admin closure required.",
                                  severity='warning', machine_id=wo['machine_id'], machine_name=wo['machine_name'],
                                  reference_id=wo['id'], reference_type='work_order', target_role='admin')

    completion.pop('_id', None)
    return completion


@router.get('/pm-completions')
async def list_pm_completions(machine_id: Optional[str] = None, limit: int = Query(200, le=2000), user: dict = Depends(get_current_user)):
    q = {'machine_id': machine_id} if machine_id else {}
    return await db.pm_completions.find(q, {'_id': 0}).sort('completed_at', -1).limit(limit).to_list(limit)


@router.get('/pm-templates')
async def list_pm_templates(user: dict = Depends(get_current_user)):
    return await db.pm_templates.find({}, {'_id': 0}).to_list(1000)


# ============ PM CHECKLIST PDF EXPORT ============
def _task_rows(task, completion=None):
    """Build printable rows: [sn, description(group), checked_for, parameter, status, remarks]."""
    groups = task.get('checklist_groups') or []
    if not groups and task.get('checklist'):
        groups = [{'description': c, 'items': [{'checked_for': 'Condition', 'parameter': ''}]} for c in task['checklist']]
    result_map = {}
    if completion:
        for r in completion.get('row_results') or []:
            result_map[(r.get('description'), r.get('checked_for'))] = r
    rows = []
    for gi, g in enumerate(groups, start=1):
        for ii, item in enumerate(g['items']):
            res = result_map.get((g['description'], item['checked_for']))
            status = ('OK' if res['status'] == 'OK' else 'NOT OK') if res else ''
            remarks = res.get('remarks', '') if res else ''
            rows.append({
                'sn': str(gi) if ii == 0 else '', 'first_of_group': ii == 0, 'group_size': len(g['items']),
                'description': g['description'] if ii == 0 else '',
                'checked_for': item['checked_for'], 'parameter': item.get('parameter', ''),
                'status': status, 'remarks': remarks,
            })
    return rows


@router.get('/pm-tasks/{task_id}/pdf')
async def pm_task_pdf(task_id: str, completion_id: Optional[str] = None, date: Optional[str] = None,
                      user: dict = Depends(get_current_user)):
    """Printable PM checklist sheet. Blank template by default; pass completion_id
    (or 'latest') to render a completed instance with per-row status + remarks.
    Optional `date` overrides the Date field (editable on-screen and in the PDF)."""
    import base64 as _b64
    from io import BytesIO
    from fastapi.responses import Response
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.lib.utils import ImageReader
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    task = await db.pm_tasks.find_one({'id': task_id}, {'_id': 0})
    if not task:
        raise HTTPException(status_code=404, detail='PM task not found')
    completion = None
    if completion_id:
        q = {'pm_task_id': task_id} if completion_id == 'latest' else {'id': completion_id, 'pm_task_id': task_id}
        completion = await db.pm_completions.find_one(q, {'_id': 0}, sort=[('completed_at', -1)])
        if not completion:
            raise HTTPException(status_code=404, detail='PM completion not found')
    branding = await db.branding.find_one({'id': 'branding'}, {'_id': 0}) or {}

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=12 * mm, rightMargin=12 * mm, topMargin=12 * mm, bottomMargin=12 * mm)
    styles = getSampleStyleSheet()
    cell = ParagraphStyle('cell', parent=styles['Normal'], fontSize=8, leading=10)
    cell_b = ParagraphStyle('cellb', parent=cell, fontName='Helvetica-Bold')
    title_style = ParagraphStyle('t', parent=styles['Title'], fontSize=14, spaceAfter=2)
    story = []

    # Header: embedded branding logo (real image, not placeholder text) + titles
    logo_flowable = None
    logo_data = branding.get('logo_data') or ''
    if logo_data.startswith('data:image') and ';base64,' in logo_data and 'svg' not in logo_data.split(';')[0]:
        try:
            raw = _b64.b64decode(logo_data.split(';base64,', 1)[1])
            img_reader = ImageReader(BytesIO(raw))
            iw, ih = img_reader.getSize()
            h = 14 * mm
            w = min(h * (iw / ih) if ih else h, 45 * mm)
            logo_flowable = RLImage(BytesIO(raw), width=w, height=h)
        except Exception:
            logo_flowable = None
    title_block = [
        Paragraph(branding.get('app_name') or 'Factory Operations', ParagraphStyle('org', parent=styles['Normal'], fontSize=9, textColor=colors.grey)),
        Paragraph('PREVENTIVE MAINTENANCE CHECKLIST', title_style),
        Paragraph(task['task_name'], ParagraphStyle('sub', parent=styles['Heading2'], fontSize=11, spaceAfter=0)),
    ]
    if logo_flowable:
        hdr = Table([[logo_flowable, title_block]], colWidths=[50 * mm, 136 * mm])
        hdr.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('LEFTPADDING', (0, 0), (0, 0), 0)]))
        story.append(hdr)
        story.append(Spacer(1, 3 * mm))
    else:
        story.extend(title_block)
        story.append(Spacer(1, 2 * mm))

    # Editable Date: explicit `date` param wins; else completion date; else blank line for handwriting
    if date:
        date_val = date
    elif completion:
        date_val = completion.get('checklist_date') or completion['completed_at'][:10]
    else:
        date_val = '_' * 16
    info = [[
        Paragraph(f"<b>Machine:</b> {task['machine_name']}", cell),
        Paragraph(f"<b>Line:</b> {task.get('line', '')}", cell),
        Paragraph(f"<b>Location/Area:</b> {task.get('location') or ''}", cell),
        Paragraph(f"<b>Frequency:</b> {(task.get('frequency') or '').title()}", cell),
        Paragraph(f"<b>Date:</b> {date_val}", cell),
    ]]
    info_t = Table(info, colWidths=[42 * mm, 28 * mm, 42 * mm, 30 * mm, 44 * mm])
    info_t.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.6, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(info_t)
    story.append(Spacer(1, 4 * mm))

    def status_boxes():
        """Outlined EMPTY checkboxes (☐ OK ☐ NOT OK) drawn as real bordered cells —
        never solid glyph squares that print unusable."""
        t = Table([['', 'OK', '', 'NOT OK']], colWidths=[3.6 * mm, 7 * mm, 3.6 * mm, 11 * mm], rowHeights=[3.6 * mm])
        t.setStyle(TableStyle([
            ('BOX', (0, 0), (0, 0), 0.7, colors.black),
            ('BOX', (2, 0), (2, 0), 0.7, colors.black),
            ('FONTSIZE', (0, 0), (-1, -1), 6.5),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 1), ('RIGHTPADDING', (0, 0), (-1, -1), 1),
            ('TOPPADDING', (0, 0), (-1, -1), 0), ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        return t

    rows = _task_rows(task, completion)
    header = [Paragraph(f'<b>{h}</b>', cell_b) for h in ['S.N.', 'Description', 'Checked For', 'Parameter / Process', 'Status', 'Remarks']]
    data = [header]
    span_cmds = []
    for idx, r in enumerate(rows, start=1):
        status_cell = Paragraph(r['status'], cell) if completion else status_boxes()
        data.append([
            Paragraph(r['sn'], cell), Paragraph(r['description'], cell_b if r['first_of_group'] else cell),
            Paragraph(r['checked_for'], cell), Paragraph(r['parameter'], cell),
            status_cell, Paragraph(r['remarks'], cell),
        ])
        if r['first_of_group'] and r['group_size'] > 1:
            span_cmds.append(('SPAN', (0, idx), (0, idx + r['group_size'] - 1)))
            span_cmds.append(('SPAN', (1, idx), (1, idx + r['group_size'] - 1)))
    if len(data) == 1:
        data.append([Paragraph('—', cell)] * 6)
    tbl = Table(data, colWidths=[11 * mm, 34 * mm, 34 * mm, 46 * mm, 26 * mm, 35 * mm], repeatRows=1)
    tbl.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.6, colors.black),
        ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.88, 0.88, 0.88)),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ] + span_cmds))
    story.append(tbl)
    story.append(Spacer(1, 10 * mm))

    done_by = completion.get('done_by', '') if completion else ''
    checked_by = completion.get('checked_by', '') if completion else ''
    sig = [[
        Paragraph('<b>Done By</b>', cell_b), Paragraph('<b>Checked By</b>', cell_b),
    ], [
        Paragraph(f"Name: {done_by or '_' * 28}", cell), Paragraph(f"Name: {checked_by or '_' * 28}", cell),
    ], [
        Paragraph('Signature: ' + '_' * 28, cell), Paragraph('Signature: ' + '_' * 28, cell),
    ]]
    sig_t = Table(sig, colWidths=[93 * mm, 93 * mm])
    sig_t.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.6, colors.black),
        ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(sig_t)
    doc.build(story)

    suffix = 'completed' if completion else 'blank'
    safe_name = _re.sub(r'[^A-Za-z0-9._-]+', '_', task['task_name'])[:40].strip('_') or 'task'
    fname = f"PM_{safe_name}_{suffix}.pdf"
    return Response(content=buf.getvalue(), media_type='application/pdf',
                    headers={'Content-Disposition': f'attachment; filename="{fname}"'})


class WarningWOGenerate(BaseModel):
    assigned_to: str
    wo_type: str = 'Inspection'  # Inspection | Corrective


@router.post('/warnings/{warning_id}/generate-wo')
async def generate_warning_wo(warning_id: str, req: WarningWOGenerate, user: dict = Depends(get_current_user)):
    """Generate a Work Order directly from a Warning with explicit technician assignment
    (for warnings without a linked WO, or when an additional dispatch is needed)."""
    warning = await db.warnings.find_one({'id': warning_id}, {'_id': 0})
    if not warning:
        raise HTTPException(status_code=404, detail='Warning not found')
    assigned_to = await _validate_technician(req.assigned_to)
    if warning.get('work_order_id'):
        existing = await db.work_orders.find_one({'id': warning['work_order_id']}, {'_id': 0, 'status': 1, 'wo_number': 1})
        if existing and existing.get('status') not in ('CLOSED',):
            raise HTTPException(status_code=400, detail=f"Warning already has an open work order ({existing['wo_number']})")
    wo_type = req.wo_type if req.wo_type in ('Inspection', 'Corrective') else 'Inspection'
    wo_num = await next_counter('work_orders', 'WO')
    wo = {
        'id': str(uuid.uuid4()), 'wo_number': wo_num, 'wo_type': wo_type,
        'title': f"{wo_type} \u2014 {warning['machine_name']} ({warning['tag_number']})",
        'description': f"Generated from warning {warning['tag_number']} [{warning.get('warning_type', 'MECHANICAL')}]: {warning['description']}",
        'machine_id': warning['machine_id'], 'machine_name': warning['machine_name'],
        'department': warning.get('department'), 'line': warning.get('line'),
        'assigned_to': assigned_to, 'priority': 'medium', 'status': 'ASSIGNED',
        'root_cause': None, 'action_taken': None, 'spare_parts': [],
        'duration_minutes': None, 'source': 'warning_manual', 'source_warning_id': warning_id,
        'auto_generated': False, 'created_at': now_iso(),
    }
    await db.work_orders.insert_one(dict(wo))
    await db.warnings.update_one({'id': warning_id}, {'$set': {'work_order_id': wo['id'], 'work_order_number': wo_num}})
    await create_timeline_event('wo_created', machine_id=warning['machine_id'], machine_name=warning['machine_name'],
                                title=f"WO {wo_num} generated from warning {warning['tag_number']} \u2192 {assigned_to}",
                                user=user['username'], reference_id=wo['id'], reference_type='work_order',
                                department=warning.get('department'), line=warning.get('line'))
    await create_notification('work_order', f"Work Order Dispatched: {warning['machine_name']}",
                              f"{wo_num} generated from {warning['tag_number']} \u2014 assigned to {assigned_to}",
                              severity='warning', machine_id=warning['machine_id'], machine_name=warning['machine_name'],
                              reference_id=wo['id'], reference_type='work_order')
    wo.pop('_id', None)
    return wo


# ============ PUBLIC (NO-LOGIN) BREAKDOWN REPORTING ============
@router.get('/public/report-context')
async def public_report_context():
    """Minimal hierarchy + machine list + technicians for the public kiosk report form. No auth."""
    lines = await db.lines.find({}, {'_id': 0, 'name': 1, 'department': 1, 'order': 1}).sort('order', 1).to_list(1000)
    machines = await db.machines.find({}, {'_id': 0, 'id': 1, 'name': 1, 'code': 1, 'line': 1, 'department': 1, 'process_group': 1}).to_list(100000)
    technicians = await db.users.find({'role': 'technician', 'active': True}, {'_id': 0, 'username': 1, 'name': 1}).to_list(1000)
    return {'lines': lines, 'machines': machines, 'technicians': technicians}


class PublicBreakdownCreate(BaseModel):
    machine_id: str
    description: str
    breakdown_type: str = 'MECHANICAL'
    reporter_name: str
    assigned_to: Optional[str] = None  # REQUIRED (validated) — technician who will attend
    start_time: Optional[str] = None   # editable actual start (calendar picker on the form)


@router.post('/public/breakdowns')
async def public_create_breakdown(req: PublicBreakdownCreate):
    """Public kiosk endpoint — operators without logins can report breakdowns.
    Reporter name AND technician assignment are mandatory; a WO is always created."""
    reporter = req.reporter_name.strip()
    if not reporter:
        raise HTTPException(status_code=400, detail='Reporter name is required')
    if not req.description.strip():
        raise HTTPException(status_code=400, detail='Description is required')
    assigned_to = await _validate_technician(req.assigned_to)
    bd = await _create_breakdown_internal(req.machine_id, req.description.strip(), None, reporter,
                                          req.start_time, req.breakdown_type, assigned_to)
    await db.breakdowns.update_one({'id': bd['id']}, {'$set': {'submitted_via': 'public_kiosk'}})
    bd['submitted_via'] = 'public_kiosk'
    return bd


# ============ WARNINGS (non-downtime observations, yellow-tagged) ============
async def _create_warning_internal(machine_id: str, description: str, warning_type: str, reporter: str,
                                   wo_type: str = 'Inspection', submitted_via: str = 'authenticated',
                                   assigned_to: str = None):
    """A Warning flags a machine concern WITHOUT declaring downtime:
    - no breakdown record, no effect on availability / MTBF / MTTR
    - machine goes to yellow 'watch' status in the Control Room
    - an Inspection/Corrective work order is ALWAYS created for the selected technician"""
    machine = await db.machines.find_one({'id': machine_id}, {'_id': 0})
    if not machine:
        raise HTTPException(status_code=404, detail='Machine not found')
    if warning_type not in BREAKDOWN_TYPES:
        raise HTTPException(status_code=400, detail=f'Invalid warning_type. Valid: {BREAKDOWN_TYPES}')
    if wo_type not in ('Inspection', 'Corrective'):
        raise HTTPException(status_code=400, detail='Warning work order must be Inspection or Corrective')
    tag = await next_counter('warnings', 'WRN')
    warning = {
        'id': str(uuid.uuid4()), 'tag_number': tag,
        'machine_id': machine['id'], 'machine_name': machine['name'],
        'department': machine['department'], 'line': machine['line'], 'process_group': machine.get('process_group'),
        'warning_type': warning_type, 'description': description, 'reporter': reporter,
        'status': 'OPEN', 'submitted_via': submitted_via,
        'work_order_id': None, 'work_order_number': None, 'created_at': now_iso(),
    }
    await db.warnings.insert_one(dict(warning))

    # yellow visibility in the Control Room (does NOT count as downtime)
    if machine.get('status') == 'running':
        await db.machines.update_one({'id': machine['id']}, {'$set': {'status': 'watch'}})
        machine['status'] = 'watch'
        await broadcast_machine_update(machine)

    await create_timeline_event('warning_created', machine_id=machine['id'], machine_name=machine['name'],
                                title=f"Warning {tag} raised", description=description, user=reporter,
                                reference_id=warning['id'], reference_type='warning',
                                department=machine['department'], line=machine['line'])
    await create_notification('warning', f"Warning: {machine['name']}",
                              f"{tag} — [{warning_type}] {description}", severity='warning',
                              machine_id=machine['id'], machine_name=machine['name'],
                              reference_id=warning['id'], reference_type='warning')

    # ALWAYS create the work order — assigned to the submitter-selected technician (fallback: least-loaded)
    assigned = assigned_to or await _pick_technician()
    wo_num = await next_counter('work_orders', 'WO')
    wo = {
        'id': str(uuid.uuid4()), 'wo_number': wo_num, 'wo_type': wo_type,
        'title': f"{wo_type} — {machine['name']} ({tag})",
        'description': f"Auto-dispatched from warning {tag} [{warning_type}]: {description}",
        'machine_id': machine['id'], 'machine_name': machine['name'],
        'department': machine['department'], 'line': machine['line'],
        'assigned_to': assigned, 'priority': 'medium',
        'status': 'ASSIGNED' if assigned else 'OPEN',
        'root_cause': None, 'action_taken': None, 'spare_parts': [],
        'duration_minutes': None, 'source': 'warning_auto', 'source_warning_id': warning['id'],
        'auto_generated': True, 'created_at': now_iso(),
    }
    await db.work_orders.insert_one(dict(wo))
    await db.warnings.update_one({'id': warning['id']}, {'$set': {'work_order_id': wo['id'], 'work_order_number': wo_num}})
    warning['work_order_id'] = wo['id']
    warning['work_order_number'] = wo_num
    await create_timeline_event('wo_created', machine_id=machine['id'], machine_name=machine['name'],
                                title=f"WO {wo_num} auto-dispatched from warning {tag}", user='system',
                                reference_id=wo['id'], reference_type='work_order',
                                department=machine['department'], line=machine['line'])
    warning.pop('_id', None)
    return warning


class WarningCreate(BaseModel):
    machine_id: str
    description: str
    warning_type: str = 'MECHANICAL'
    reporter_name: Optional[str] = None
    wo_type: str = 'Inspection'  # Inspection | Corrective
    assigned_to: Optional[str] = None  # REQUIRED (validated) — technician who will attend


@router.post('/warnings')
async def create_warning(req: WarningCreate, user: dict = Depends(get_current_user)):
    reporter = req.reporter_name or user['username']
    if not req.description.strip():
        raise HTTPException(status_code=400, detail='Description is required')
    assigned_to = await _validate_technician(req.assigned_to)
    return await _create_warning_internal(req.machine_id, req.description.strip(), req.warning_type, reporter,
                                          req.wo_type, assigned_to=assigned_to)


@router.get('/warnings')
async def list_warnings(machine_id: Optional[str] = None, status: Optional[str] = None,
                        search: Optional[str] = None, limit: int = Query(200, le=2000), skip: int = 0,
                        user: dict = Depends(get_current_user)):
    q = {}
    if machine_id:
        q['machine_id'] = machine_id
    if status:
        q['status'] = status
    if search:
        q['$or'] = [{'tag_number': {'$regex': search, '$options': 'i'}}, {'machine_name': {'$regex': search, '$options': 'i'}}, {'description': {'$regex': search, '$options': 'i'}}]
    total = await db.warnings.count_documents(q)
    items = await db.warnings.find(q, {'_id': 0}).sort('created_at', -1).skip(skip).limit(limit).to_list(limit)
    return {'items': items, 'total': total}


class PublicWarningCreate(BaseModel):
    machine_id: str
    description: str
    warning_type: str = 'MECHANICAL'
    reporter_name: str
    wo_type: str = 'Inspection'
    assigned_to: Optional[str] = None  # REQUIRED (validated) — technician who will attend


@router.post('/public/warnings')
async def public_create_warning(req: PublicWarningCreate):
    """Public kiosk warning — same accountability rules as public breakdowns."""
    reporter = req.reporter_name.strip()
    if not reporter:
        raise HTTPException(status_code=400, detail='Reporter name is required')
    if not req.description.strip():
        raise HTTPException(status_code=400, detail='Description is required')
    assigned_to = await _validate_technician(req.assigned_to)
    return await _create_warning_internal(req.machine_id, req.description.strip(), req.warning_type, reporter,
                                          req.wo_type, submitted_via='public_kiosk', assigned_to=assigned_to)
