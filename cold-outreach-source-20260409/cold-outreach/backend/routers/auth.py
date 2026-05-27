import os
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from database import get_db
from models import User, UserRole
from schemas import LoginRequest, UserOut
from auth import verify_password, hash_password, validate_password, create_access_token, get_current_user, is_allowed_email, require_admin

# HTTPS 環境（Railway/Vercel）啟用 secure cookie
_COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
def login(body: LoginRequest, response: Response, db: Session = Depends(get_db)):
    if not is_allowed_email(body.email):
        raise HTTPException(status_code=403, detail="Email domain not allowed")

    user = db.query(User).filter(User.email == body.email.lower()).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(str(user.id), user.role.value)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=8 * 3600,
        samesite="none" if _COOKIE_SECURE else "lax",
        secure=_COOKIE_SECURE,
    )
    return {"message": "ok", "user": UserOut.model_validate(user)}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("access_token")
    return {"message": "logged out"}


class SetupRequest(BaseModel):
    name: str
    email: str
    password: str

@router.post("/setup")
def setup_first_admin(body: SetupRequest, db: Session = Depends(get_db)):
    """只在資料庫沒有任何使用者時，建立第一個 admin 帳號"""
    if db.query(User).count() > 0:
        raise HTTPException(status_code=403, detail="Setup already completed")
    if not is_allowed_email(body.email):
        raise HTTPException(status_code=403, detail="Email domain not allowed")
    try:
        validate_password(body.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    user = User(
        name=body.name,
        email=body.email.lower(),
        hashed_password=hash_password(body.password),
        role=UserRole.admin,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"message": "Admin account created", "email": user.email}


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("/users", response_model=List[UserOut])
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return db.query(User).order_by(User.name).all()


class CreateUserBody(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: UserRole = UserRole.sales


class UpdateUserBody(BaseModel):
    name: Optional[str] = None
    role: Optional[UserRole] = None
    password: Optional[str] = None


@router.post("/users", response_model=UserOut)
def create_user(
    body: CreateUserBody,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    existing = db.query(User).filter(User.email == body.email.lower()).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already exists")
    try:
        validate_password(body.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    user = User(
        email=body.email.lower(),
        name=body.name,
        hashed_password=hash_password(body.password),
        role=body.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.put("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: str,
    body: UpdateUserBody,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if body.name is not None:
        user.name = body.name
    if body.role is not None:
        user.role = body.role
    if body.password is not None:
        try:
            validate_password(body.password)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        user.hashed_password = hash_password(body.password)
    db.commit()
    db.refresh(user)
    return user


@router.delete("/users/{user_id}")
def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    if str(current_user.id) == user_id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
    return {"message": "deleted"}
