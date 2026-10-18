"""API keys for the reporting endpoints (spec 35). The raw key ("acm_" + 32 characters) is returned once, at
creation; only its SHA-256 and last four characters are stored."""
import secrets

from sqlalchemy.orm import Session

from core.errors import not_found
from core.security import sha256_hex
from core.time import iso_z, now
from models import ApiKey, User
from services import audit

PREFIX = "acm_"
SCOPES = {"reports:read": "Read reports"}


def mask(key: ApiKey) -> str:
    return f"{PREFIX}••••••••{key.last4}"


def key_out(key: ApiKey) -> dict:
    return {"id": key.id, "name": key.name, "mask": mask(key), "scope": key.scope, "createdAt": iso_z(key.created_at),
            "lastUsedAt": iso_z(key.last_used_at) if key.last_used_at else None}


def list_keys(db: Session) -> dict:
    keys = db.query(ApiKey).filter(ApiKey.revoked_at.is_(None)).order_by(ApiKey.created_at.desc(), ApiKey.id.desc())
    return {"keys": [key_out(key) for key in keys]}


def create(db: Session, admin: User, name: str, scope: str, ip: str | None = None) -> dict:
    raw = PREFIX + secrets.token_urlsafe(24)
    key = ApiKey(name=name, key_hash=sha256_hex(raw), last4=raw[-4:], scope=scope, created_by=admin.user_id)
    db.add(key)
    db.flush()
    audit.record(db, admin, "api_key.create", f"Created the API key {name} ({SCOPES[scope]})", ("api_key", key.id), ip=ip)
    db.commit()
    return {"id": key.id, "name": key.name, "key": raw, "mask": mask(key)}


def revoke(db: Session, admin: User, key_id: int, ip: str | None = None) -> None:
    key = db.get(ApiKey, key_id)
    if key is None or key.revoked_at is not None:
        raise not_found("API key")
    key.revoked_at = now()
    audit.record(db, admin, "api_key.revoke", f"Revoked the API key {key.name}", ("api_key", key.id), ip=ip)
    db.commit()


def verify(db: Session, header: str | None, scope: str) -> ApiKey | None:
    """The active key in an `Authorization: Bearer acm_…` header with `scope`, else None. Marks it used."""
    if not header or not header.lower().startswith("bearer "):
        return None
    raw = header[7:].strip()
    if not raw.startswith(PREFIX):
        return None
    key = db.query(ApiKey).filter(ApiKey.key_hash == sha256_hex(raw), ApiKey.revoked_at.is_(None)).one_or_none()
    if key is None or key.scope != scope:
        return None
    key.last_used_at = now()
    db.commit()
    return key
