import asyncio
import json
import logging
from typing import Dict, List

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Single-worker WebSocket hub. Broadcasts JSON events to all connected clients."""

    def __init__(self):
        self.connections: Dict[str, WebSocket] = {}
        self._lock = asyncio.Lock()

    async def connect(self, conn_id: str, ws: WebSocket):
        await ws.accept()
        async with self._lock:
            self.connections[conn_id] = ws
        logger.info(f"WS connected: {conn_id} (total {len(self.connections)})")

    async def disconnect(self, conn_id: str):
        async with self._lock:
            self.connections.pop(conn_id, None)

    async def broadcast(self, event: dict):
        """Send event to all connected clients; drop dead connections."""
        message = json.dumps(event, default=str)
        dead: List[str] = []
        for conn_id, ws in list(self.connections.items()):
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(conn_id)
        for conn_id in dead:
            await self.disconnect(conn_id)


manager = ConnectionManager()
