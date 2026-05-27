import os
import bcrypt
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from database import get_db
from models import User, UserRole

JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 8

ALLOWED_DOMAINS = {"wavenet.com.tw"}
ALLOWED_EMAILS = {"joelou989@gmail.com"}


def is_allowed_email(email: str) -> bool:
    email = email.lower()
    if email in ALLOWED_EMAILS:
        return True
    domain = email.split("@")[-1]
    return domain in ALLOWED_DOMAINS


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(user_id: str, role: str) -> str:
    expire = datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS)
    payload = {"sub": user_id, "role": role, "exp": expire}
    return jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get("access_token")
    if not token:
        # Also check Authorization header as fallback
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_token(token)
    user = db.query(User).filter(User.id == payload["sub"]).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Admin only")
    return current_user


def require_admin_or_manager(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in (UserRole.admin, UserRole.manager):
        raise HTTPException(status_code=403, detail="Admin or Manager only")
    return current_user
