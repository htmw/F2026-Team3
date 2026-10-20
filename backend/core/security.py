"""Password hashing, opaque tokens and secret encryption (integration secrets, spec 35). TOTP helpers are added
with spec 02."""
import base64
import hashlib
import logging
import secrets

import bcrypt
from cryptography.fernet import Fernet, InvalidToken

from core.config import settings

log = logging.getLogger(__name__)

DEV_ENCRYPTION_SECRET = "acadmate-dev-encryption-secret"  # used only when SECRET_KEY is unset
_warned = False


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:  # stored value isn't a bcrypt hash
        return False


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def new_token() -> tuple[str, str]:
    """(raw, hash): send the raw token to the user, store only the hash."""
    raw = secrets.token_urlsafe(32)
    return raw, sha256_hex(raw)


def _fernet() -> Fernet:
    global _warned
    secret = settings.SECRET_KEY
    if not secret:
        if not _warned:
            log.warning("SECRET_KEY is not set; integration secrets use a development-only key.")
            _warned = True
        secret = DEV_ENCRYPTION_SECRET
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest()))


def encrypt(text: str) -> str:
    return _fernet().encrypt(text.encode()).decode()


def decrypt(token: str) -> str:
    """Raises ValueError when the token is damaged or SECRET_KEY changed since it was encrypted."""
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        raise ValueError("The stored secret can't be decrypted (SECRET_KEY changed?).") from None
