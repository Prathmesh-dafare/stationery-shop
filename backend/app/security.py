import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError

SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-this-secret-key-before-deployment")
ALGORITHM = "HS256"
ACCESS_TOKEN_MINUTES = 8 * 60

def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 260_000)
    return salt.hex() + "$" + digest.hex()

def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, digest_hex = stored.split("$", 1)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), 260_000).hex()
        return hmac.compare_digest(actual, digest_hex)
    except (ValueError, TypeError):
        return False

def create_access_token(subject: str) -> str:
    expires = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_MINUTES)
    return jwt.encode({"sub": subject, "exp": expires}, SECRET_KEY, algorithm=ALGORITHM)

def read_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None
