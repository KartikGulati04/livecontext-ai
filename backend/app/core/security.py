"""Security utilities: password hashing, JWT generation and verification, and credential encryption."""
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import base64
import json
import hashlib
from jose import jwt, JWTError
from passlib.context import CryptContext
from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None


# Simple obfuscation/encryption for local dev credentials using HMAC-SHA256 key stream
# For production, an envelope KMS or Fernet can be swapped in seamlessly.
def encrypt_credentials(creds_dict: Dict[str, Any]) -> str:
    serialized = json.dumps(creds_dict).encode("utf-8")
    key = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()
    # XOR stream cipher with SHA256 keystream
    encrypted = bytearray()
    for i, b in enumerate(serialized):
        encrypted.append(b ^ key[i % len(key)])
    return base64.b64encode(encrypted).decode("utf-8")


def decrypt_credentials(encrypted_str: str) -> Dict[str, Any]:
    try:
        raw = base64.b64decode(encrypted_str.encode("utf-8"))
        key = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()
        decrypted = bytearray()
        for i, b in enumerate(raw):
            decrypted.append(b ^ key[i % len(key)])
        return json.loads(decrypted.decode("utf-8"))
    except Exception:
        return {}
