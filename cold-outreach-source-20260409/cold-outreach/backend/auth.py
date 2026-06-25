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
TOKEN_EXPIRE_HOURS = 168   # 7 天，避免操作中途 token 過期被登出

ALLOWED_DOMAINS = {"wavenet.com.tw", "partner.wavenet.com.tw"}
ALLOWED_EMAILS = {
    "joelou989@gmail.com",
    "gr920418@gmail.com",
    "liuchery10922@gmail.com",
    "xhes.we.17@gmail.com",
    "hsin64michelle@gmail.com",
    "960012jeffery@gmail.com",
    "kejichen20241017@gmail.com",
    "wolf19387@gmail.com",
    "jiaweihu34@gmail.com",
    "rouyuuz901210@gmail.com",
    "prototype55194158@gmail.com",
    "luffy880327@gmail.com",
}


def get_visible_user_ids(current_user, db) -> list | None:
    """None = unrestricted. Otherwise returns list of visible user IDs."""
    if current_user.role == UserRole.admin:
        return None  # admin 看全部
    if current_user.role == UserRole.manager:
        # 主管：看「可管理的組（ManagerScope）」所有成員；未設定 → 看全部（相容）
        from models import ManagerScope
        team_ids = [m.team_id for m in db.query(ManagerScope).filter(ManagerScope.manager_id == current_user.id).all()]
        if not team_ids:
            return None
        ids = [u.id for u in db.query(User).filter(User.team_id.in_(team_ids)).all()]
        ids.append(current_user.id)
        return ids
    if current_user.role == UserRole.team_lead:
        # 小組長：看自己組所有成員（含自己）
        return [u.id for u in db.query(User).filter(User.team_id == current_user.team_id).all()]
    return [current_user.id]  # sales：只看自己


def is_allowed_email(email: str) -> bool:
    email = email.lower()
    if email in ALLOWED_EMAILS:
        return True
    domain = email.split("@")[-1]
    return domain in ALLOWED_DOMAINS


def validate_password(plain: str) -> None:
    """密碼規則：至少 8 碼，且必須同時包含英文字母與數字。"""
    if len(plain) < 8:
        raise ValueError("密碼至少需要 8 個字元")
    if not any(c.isalpha() for c in plain):
        raise ValueError("密碼必須包含至少一個英文字母")
    if not any(c.isdigit() for c in plain):
        raise ValueError("密碼必須包含至少一個數字")


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(user_id: str, role: str) -> str:
    # JWT exp 必須是 UTC（jose 將 naive datetime 視為 UTC）
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
