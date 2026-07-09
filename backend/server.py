import logging
import os
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from pydantic import BaseModel
from starlette.middleware.cors import CORSMiddleware

from database import db, client
from auth import (hash_password, verify_password, create_token, decode_token,
                  get_current_user, require_admin, require_admin_or_tech, require_any)
from ws_manager import manager
from events import create_timeline_event, create_notification, broadcast_machine_update, next_counter, now_iso

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title='Factory Operations Platform')
api_router = APIRouter(prefix='/api')


# ------------------ POC SEED (minimal) ------------------
async def seed_poc():
    if await db.users.count_documents({}) > 0:
        return
    users = [
        {'id': str(uuid.uuid4()), 'username': 'admin', 'password': hash_password('admin123'), 'role': 'admin', 'name': 'System Admin', 'active': True, 'created_at': now_iso()},
        {'id': str(uuid.uuid4()), 'username': 'tech', 'password': hash_password('tech123'), 'role': 'technician', 'name': 'Maintenance Tech', 'active': True, 'created_at': now_iso()},
        {'id': str(uuid.uuid4()), 'username': 'operator', 'password': hash_password('operator123'), 'role': 'operator', 'name': 'Floor Operator', 'active': True, 'created_at': now_iso()},
    ]
    await db.users.insert_many(users)
    machines = [
        {'id': str(uuid.uuid4()), 'name': 'Main Oil Pump', 'code': 'PC21-FRY-002', 'department': 'PROCESS', 'line': 'PC21', 'process_group': 'Frying', 'status': 'running', 'health': 'healthy', 'criticality': 'high', 'created_at': now_iso()},
        {'id': str(uuid.uuid4()), 'name': 'Fryer', 'code': 'PC21-FRY-001', 'department': 'PROCESS', 'line': 'PC21', 'process_group': 'Frying', 'status': 'running', 'health': 'healthy', 'criticality': 'critical', 'created_at': now_iso()},
        {'id': str(uuid.uuid4()), 'name': 'Slicer 1', 'code': 'PC21-SLC-003', 'department': 'PROCESS', 'line': 'PC21', 'process_group': 'Slicing', 'status': 'idle', 'health': 'healthy', 'criticality': 'medium', 'created_at': now_iso()},
    ]
    await db.machines.insert_many(machines)
    logger.info('POC seed complete: 3 users, 3 machines')


@app.on_event('startup')
async def startup():
    await seed_poc()


# ------------------ AUTH ------------------
class LoginRequest(BaseModel):
    username: str
    password: str


@api_router.post('/auth/login')
async def login(req: LoginRequest):
    user = await db.users.find_one({'username': req.username}, {'_id': 0})
    if not user or not verify_password(req.password, user['password']):
        raise HTTPException(status_code=401, detail='Invalid username or password')
    token = create_token(user)
    return {'token': token, 'user': {'id': user['id'], 'username': user['username'], 'role': user['role'], 'name': user.get('name')}}


@api_router.get('/auth/me')
async def me(user: dict = Depends(get_current_user)):
    return user


# ------------------ MACHINES (POC) ------------------
@api_router.get('/machines')
async def list_machines(user: dict = Depends(get_current_user)):
    return await db.machines.find({}, {'_id': 0}).to_list(10000)


# ------------------ BREAKDOWNS (POC pipeline) ------------------
class BreakdownCreate(BaseModel):
    machine_id: str
    description: str
    failure_mode: str = 'Mechanical'


@api_router.post('/breakdowns')
async def create_breakdown(req: BreakdownCreate, user: dict = Depends(get_current_user)):
    machine = await db.machines.find_one({'id': req.machine_id}, {'_id': 0})
    if not machine:
        raise HTTPException(status_code=404, detail='Machine not found')
    ticket = await next_counter('breakdowns', 'BD')
    bd = {
        'id': str(uuid.uuid4()),
        'ticket_number': ticket,
        'machine_id': machine['id'],
        'machine_name': machine['name'],
        'department': machine['department'],
        'line': machine['line'],
        'failure_mode': req.failure_mode,
        'description': req.description,
        'reporter': user['username'],
        'status': 'OPEN',
        'start_time': now_iso(),
        'end_time': None,
        'downtime_minutes': None,
        'created_at': now_iso(),
    }
    await db.breakdowns.insert_one(dict(bd))
    # Update machine derived state
    await db.machines.update_one({'id': machine['id']}, {'$set': {'status': 'failed'}})
    machine['status'] = 'failed'
    await broadcast_machine_update(machine)
    # Timeline + notification
    await create_timeline_event('breakdown_created', machine_id=machine['id'], machine_name=machine['name'],
                                title=f"Breakdown {ticket} created", description=req.description,
                                user=user['username'], reference_id=bd['id'], reference_type='breakdown',
                                department=machine['department'], line=machine['line'])
    await create_notification('breakdown', f"Breakdown: {machine['name']}",
                              f"{ticket} — {req.description}", severity='critical',
                              machine_id=machine['id'], machine_name=machine['name'],
                              reference_id=bd['id'], reference_type='breakdown')
    bd.pop('_id', None)
    return bd


@api_router.get('/timeline')
async def get_timeline(user: dict = Depends(get_current_user)):
    return await db.timeline_events.find({}, {'_id': 0}).sort('created_at', -1).to_list(100)


@api_router.get('/notifications')
async def get_notifications(user: dict = Depends(get_current_user)):
    return await db.notifications.find({}, {'_id': 0}).sort('created_at', -1).to_list(100)


# ------------------ WEBSOCKET ------------------
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
            await ws.receive_text()  # keepalive / ignore client messages
    except WebSocketDisconnect:
        await manager.disconnect(conn_id)
    except Exception:
        await manager.disconnect(conn_id)


app.include_router(api_router)

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
