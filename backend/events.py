"""Event pipeline: every significant action creates timeline events, notifications,
and broadcasts over WebSocket in one call."""
import uuid
from datetime import datetime, timezone

from database import db
from ws_manager import manager


def now_iso():
    return datetime.now(timezone.utc).isoformat()


async def create_timeline_event(event_type: str, machine_id: str = None, machine_name: str = None,
                                title: str = '', description: str = '', user: str = '',
                                reference_id: str = None, reference_type: str = None,
                                department: str = None, line: str = None, meta: dict = None):
    event = {
        'id': str(uuid.uuid4()),
        'event_type': event_type,
        'machine_id': machine_id,
        'machine_name': machine_name,
        'department': department,
        'line': line,
        'title': title,
        'description': description,
        'user': user,
        'reference_id': reference_id,
        'reference_type': reference_type,
        'meta': meta or {},
        'created_at': now_iso(),
    }
    await db.timeline_events.insert_one(dict(event))
    event.pop('_id', None)
    await manager.broadcast({'type': 'timeline_event', 'data': event})
    return event


async def create_notification(notif_type: str, title: str, message: str, severity: str = 'info',
                              machine_id: str = None, machine_name: str = None,
                              reference_id: str = None, reference_type: str = None,
                              target_role: str = None):
    notif = {
        'id': str(uuid.uuid4()),
        'notif_type': notif_type,
        'title': title,
        'message': message,
        'severity': severity,  # info | warning | critical | success
        'machine_id': machine_id,
        'machine_name': machine_name,
        'reference_id': reference_id,
        'reference_type': reference_type,
        'target_role': target_role,
        'read_by': [],
        'created_at': now_iso(),
    }
    await db.notifications.insert_one(dict(notif))
    notif.pop('_id', None)
    await manager.broadcast({'type': 'notification', 'data': notif})
    return notif


async def broadcast_machine_update(machine: dict):
    m = {k: v for k, v in machine.items() if k != '_id'}
    await manager.broadcast({'type': 'machine_update', 'data': m})


async def next_counter(name: str, prefix: str) -> str:
    doc = await db.counters.find_one_and_update(
        {'_id': name},
        {'$inc': {'seq': 1}},
        upsert=True,
        return_document=True,
    )
    seq = doc['seq'] if doc else 1
    return f"{prefix}-{seq:05d}"
