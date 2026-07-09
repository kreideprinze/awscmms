import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

JWT_SECRET = os.environ.get('JWT_SECRET', 'factory-ops-secret-key-change-in-prod')
JWT_ALGO = 'HS256'
JWT_EXPIRE_HOURS = 24 * 7

security = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except Exception:
        return False


def create_token(user: dict) -> str:
    payload = {
        'sub': user['id'],
        'username': user['username'],
        'role': user['role'],
        'name': user.get('name', user['username']),
        'exp': datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    except Exception:
        return None


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    if not credentials:
        raise HTTPException(status_code=401, detail='Not authenticated')
    payload = decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail='Invalid or expired token')
    return payload


def require_roles(*roles):
    async def checker(user: dict = Depends(get_current_user)) -> dict:
        if user.get('role') not in roles:
            raise HTTPException(status_code=403, detail='Insufficient permissions')
        return user
    return checker


require_admin = require_roles('admin')
require_admin_or_tech = require_roles('admin', 'technician')
require_any = require_roles('admin', 'technician', 'operator')
