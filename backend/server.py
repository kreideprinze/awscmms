"""Factory Operations Platform - main server assembly.
FastAPI + Motor + JWT + WebSocket hub + PM background scheduler + first-startup seeding."""
import asyncio
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, APIRouter, WebSocket, WebSocketDisconnect, Query
from starlette.middleware.cors import CORSMiddleware

from database import db, client
from auth import decode_token
from ws_manager import manager
from events import create_timeline_event, create_notification, next_counter, now_iso
from seed import seed_all

import routers_core
import routers_maintenance
import routers_ops
import routers_spares
import routers_admin

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title='Factory Operations Platform', version='1.0')
api_router = APIRouter(prefix='/api')

api_router.include_router(routers_core.router, tags=['core'])
api_router.include_router(routers_maintenance.router, tags=['maintenance'])
api_router.include_router(routers_ops.router, tags=['ops'])
api_router.include_router(routers_spares.router, tags=['spares'])
api_router.include_router(routers_admin.router, tags=['admin'])


@api_router.get('/')
async def root():
    return {'app': 'Factory Operations Platform', 'status': 'online'}


app.include_router(api_router)


# ---------------- WEBSOCKET ----------------
@app.websocket('/api/ws')
async def websocket_endpoint(ws: WebSocket, token: str = Query(None)):
    payload = decode_token(token) if token else None
    if not payload:
        await ws.close(code=4001)
        return
    conn_id = str(uuid.uuid4())
    await manager.connect(conn_id, ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(conn_id)
    except Exception:
        await manager.disconnect(conn_id)


# ---------------- PM SCHEDULER (background) ----------------
FREQ_DAYS = {'daily': 1, 'weekly': 7, 'monthly': 30, 'quarterly': 91, 'yearly': 365, 'once': 0}


async def pm_scheduler_tick():
    today = datetime.now(timezone.utc).date()
    today_str = today.isoformat()
    # due tasks -> generate PM work orders
    cursor = db.pm_tasks.find({'active': True, 'status': {'$in': ['active', 'suggested']}, 'next_due_date': {'$lte': today_str}}, {'_id': 0})
    async for task in cursor:
        if task.get('last_generated_date') == task.get('next_due_date'):
            # already generated for this occurrence; check overdue notification
            if task.get('next_due_date') < today_str and task.get('overdue_sent_for') != task.get('next_due_date'):
                await db.pm_tasks.update_one({'id': task['id']}, {'$set': {'overdue_sent_for': task['next_due_date']}})
                await create_notification('pm_overdue', f"PM OVERDUE: {task['machine_name']}",
                                          f"\u201c{task['task_name']}\u201d was due {task['next_due_date']}", severity='critical',
                                          machine_id=task['machine_id'], machine_name=task['machine_name'],
                                          reference_id=task['id'], reference_type='pm_task')
            continue
        wo_num = await next_counter('work_orders', 'WO')
        wo = {
            'id': str(uuid.uuid4()), 'wo_number': wo_num, 'wo_type': 'Preventive',
            'title': f"PM: {task['task_name']}",
            'description': task.get('description') or f"Scheduled {task.get('frequency')} PM",
            'machine_id': task['machine_id'], 'machine_name': task['machine_name'],
            'department': task.get('department'), 'line': task.get('line'),
            'assigned_to': task.get('assigned_to'), 'priority': task.get('priority', 'medium'),
            'status': 'ASSIGNED' if task.get('assigned_to') else 'OPEN',
            'root_cause': None, 'action_taken': None, 'spare_parts': [],
            'duration_minutes': None, 'source': 'pm_scheduler', 'pm_task_id': task['id'],
            'checklist': task.get('checklist', []), 'auto_generated': True, 'created_at': now_iso(),
        }
        await db.work_orders.insert_one(dict(wo))
        await db.pm_tasks.update_one({'id': task['id']}, {'$set': {'last_generated_date': task['next_due_date']}})
        await create_timeline_event('pm_generated', machine_id=task['machine_id'], machine_name=task['machine_name'],
                                    title=f"PM WO {wo_num} generated: {task['task_name']}", user='scheduler',
                                    reference_id=wo['id'], reference_type='work_order',
                                    department=task.get('department'), line=task.get('line'))
        await create_notification('pm_due', f"PM Due: {task['machine_name']}",
                                  f"\u201c{task['task_name']}\u201d \u2014 WO {wo_num} generated", severity='warning',
                                  machine_id=task['machine_id'], machine_name=task['machine_name'],
                                  reference_id=wo['id'], reference_type='work_order')
    # reminders (due within reminder_offset_days)
    cursor = db.pm_tasks.find({'active': True, 'status': 'active', 'next_due_date': {'$gt': today_str}}, {'_id': 0})
    async for task in cursor:
        try:
            due = datetime.fromisoformat(task['next_due_date']).date()
        except (ValueError, TypeError):
            continue
        offset = int(task.get('reminder_offset_days', 1) or 0)
        if offset > 0 and (due - today).days <= offset and task.get('reminder_sent_for') != task['next_due_date']:
            await db.pm_tasks.update_one({'id': task['id']}, {'$set': {'reminder_sent_for': task['next_due_date']}})
            await create_notification('pm_due', f"PM Reminder: {task['machine_name']}",
                                      f"\u201c{task['task_name']}\u201d due {task['next_due_date']}", severity='warning',
                                      machine_id=task['machine_id'], machine_name=task['machine_name'],
                                      reference_id=task['id'], reference_type='pm_task')


async def pm_scheduler_loop():
    await asyncio.sleep(10)
    while True:
        try:
            await pm_scheduler_tick()
        except Exception as e:
            logger.error(f'PM scheduler error: {e}')
        await asyncio.sleep(60)


# ---------------- PLANT RUNTIME CLOCK (auto runtime accumulation) ----------------
async def runtime_clock_tick():
    """Accumulate Run/Calendar/Dark hours per machine off the single plant clock.
    Machines in running/watch/inspection_due accrue run hours; all accrue calendar hours."""
    from pymongo import UpdateOne
    from datetime import datetime as dt_cls
    now = datetime.now(timezone.utc)
    clock = await db.settings.find_one({'id': 'plant_clock'}, {'_id': 0})
    if not clock:
        await db.settings.insert_one({'id': 'plant_clock', 'started_at': now_iso(), 'last_tick_at': now_iso()})
        return
    try:
        last = dt_cls.fromisoformat(str(clock.get('last_tick_at')).replace('Z', '+00:00'))
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
    except Exception:
        last = now
    dt_hours = round(min(max((now - last).total_seconds() / 3600.0, 0), 0.25), 5)  # cap 15min catch-up
    await db.settings.update_one({'id': 'plant_clock'}, {'$set': {'last_tick_at': now_iso()}})
    if dt_hours <= 0:
        return
    today = now_iso()[:10]
    running_statuses = ['running', 'watch', 'inspection_due']
    machines = await db.machines.find({}, {'_id': 0, 'id': 1, 'name': 1, 'status': 1, 'department': 1, 'line': 1, 'process_group': 1}).to_list(20000)
    ops = []
    for m in machines:
        is_running = m.get('status') in running_statuses
        ops.append(UpdateOne(
            {'machine_id': m['id'], 'date': today},
            {'$inc': {'calendar_hours': dt_hours, 'run_hours': dt_hours if is_running else 0.0, 'dark_hours': 0.0 if is_running else dt_hours},
             '$setOnInsert': {'id': str(uuid.uuid4()), 'machine_id': m['id'], 'machine_name': m['name'],
                              'department': m.get('department'), 'line': m.get('line'), 'process_group': m.get('process_group'),
                              'date': today, 'entered_by': 'plant_clock', 'source': 'plant_clock', 'created_at': now_iso()},
             '$set': {'updated_at': now_iso()}},
            upsert=True))
    if ops:
        await db.runtime_logs.bulk_write(ops, ordered=False)
    await db.machines.update_many({'status': {'$in': running_statuses}}, {'$inc': {'total_run_hours': dt_hours}})


_clock_tick_count = 0


async def runtime_clock_loop():
    global _clock_tick_count
    await asyncio.sleep(20)
    while True:
        try:
            await runtime_clock_tick()
            _clock_tick_count += 1
            if _clock_tick_count % 15 == 0:  # refresh reliability life % every ~15 min
                from reliability import recompute_all
                await recompute_all(trigger='plant_clock')
        except Exception as e:
            logger.error(f'Plant clock ticker error: {e}')
        await asyncio.sleep(60)


@app.on_event('startup')
async def startup():
    try:
        from migrations import migrate_hierarchy_line_first
        result = await migrate_hierarchy_line_first()
        logger.info(f'Hierarchy migration: {result}')
    except Exception as e:
        logger.error(f'Hierarchy migration error: {e}')
    try:
        await seed_all()
    except Exception as e:
        logger.error(f'Seed error: {e}')
    asyncio.create_task(pm_scheduler_loop())
    asyncio.create_task(runtime_clock_loop())


app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=['*'],
    allow_headers=['*'],
)


@app.on_event('shutdown')
async def shutdown_db_client():
    client.close()
