"""
Authentication & Session Security Module
Maritime Defense Command Center
Enforces single authorized operator login ID, 30-minute session lifespan, and auto-lock state.
"""

import os
import secrets
import time
from typing import Optional, Dict, Any
from pydantic import BaseModel

# Configuration for Authorized Single Login ID
AUTHORIZED_OPERATOR_ID = os.getenv("AUTH_OPERATOR_ID", "ICG-COMMAND-01")
AUTHORIZED_PASSWORD = os.getenv("AUTH_PASSWORD", "Maritime@2026")
# Secondary alias allowed for convenience
AUTHORIZED_ALIASES = {AUTHORIZED_OPERATOR_ID.lower(), "admin", "commander"}

# Session duration: 30 minutes in seconds
SESSION_DURATION_SECONDS = 30 * 60  # 1800 seconds

# In-memory single active session store
active_session: Dict[str, Any] = {
    "token": None,
    "operator_id": None,
    "operator_name": "Commander V. Sharma (ICG)",
    "role": "Chief Tactical Maritime Officer",
    "created_at": 0,
    "expires_at": 0,
    "is_locked": False,
    "last_activity": 0
}


class LoginRequest(BaseModel):
    operator_id: str
    password: str


class UnlockRequest(BaseModel):
    token: str
    password: str


class TokenRequest(BaseModel):
    token: str


def verify_credentials(operator_id: str, password: str) -> bool:
    clean_id = (operator_id or "").strip().lower()
    clean_pw = (password or "").strip()
    return (clean_id in AUTHORIZED_ALIASES or clean_id == AUTHORIZED_OPERATOR_ID.lower()) and clean_pw == AUTHORIZED_PASSWORD


def create_session(operator_id: str) -> Dict[str, Any]:
    now = time.time()
    token = secrets.token_hex(24)
    active_session["token"] = token
    active_session["operator_id"] = AUTHORIZED_OPERATOR_ID
    active_session["created_at"] = now
    active_session["expires_at"] = now + SESSION_DURATION_SECONDS
    active_session["last_activity"] = now
    active_session["is_locked"] = False
    return {
        "success": True,
        "token": token,
        "operator_id": AUTHORIZED_OPERATOR_ID,
        "operator_name": active_session["operator_name"],
        "role": active_session["role"],
        "expires_in_seconds": SESSION_DURATION_SECONDS,
        "expires_at": active_session["expires_at"]
    }


def validate_session(token: Optional[str]) -> Dict[str, Any]:
    if not token or token != active_session.get("token"):
        return {"valid": False, "reason": "No active session or invalid token"}

    now = time.time()
    if now > active_session.get("expires_at", 0):
        # Session expired
        terminate_session()
        return {"valid": False, "reason": "Session expired (30-minute limit exceeded)"}

    remaining = max(0, int(active_session["expires_at"] - now))
    return {
        "valid": True,
        "is_locked": active_session.get("is_locked", False),
        "operator_id": active_session.get("operator_id"),
        "operator_name": active_session.get("operator_name"),
        "remaining_seconds": remaining
    }


def lock_session(token: str) -> Dict[str, Any]:
    validation = validate_session(token)
    if not validation["valid"]:
        return validation
    active_session["is_locked"] = True
    return {"success": True, "message": "Terminal locked", "is_locked": True}


def unlock_session(token: str, password: str) -> Dict[str, Any]:
    if not token or token != active_session.get("token"):
        return {"success": False, "message": "Invalid session token"}
    
    if (password or "").strip() != AUTHORIZED_PASSWORD:
        return {"success": False, "message": "Invalid clearance password"}

    now = time.time()
    if now > active_session.get("expires_at", 0):
        terminate_session()
        return {"success": False, "message": "Session expired during lock state. Please log in again."}

    active_session["is_locked"] = False
    active_session["last_activity"] = now
    remaining = max(0, int(active_session["expires_at"] - now))
    return {
        "success": True,
        "message": "Terminal unlocked successfully",
        "is_locked": False,
        "remaining_seconds": remaining
    }


def terminate_session() -> Dict[str, Any]:
    active_session["token"] = None
    active_session["operator_id"] = None
    active_session["created_at"] = 0
    active_session["expires_at"] = 0
    active_session["is_locked"] = False
    active_session["last_activity"] = 0
    return {"success": True, "message": "Session terminated successfully"}
