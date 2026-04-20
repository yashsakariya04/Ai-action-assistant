"""
backend/auth.py — Authentication routes.

POST /auth/register  — create account
POST /auth/login     — returns JWT access token
GET  /auth/me        — returns current user profile (requires token)
"""

import os
import logging
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from db.database import get_db
from db.models import User

log = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────
SECRET_KEY      = os.getenv("JWT_SECRET_KEY", "change-me-in-production-please")
ALGORITHM       = "HS256"
TOKEN_EXPIRE_H  = int(os.getenv("JWT_EXPIRE_HOURS", "72"))

router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# ── Schemas ───────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str
    name: str | None


class UserProfile(BaseModel):
    user_id: str
    email: str
    name: str | None
    avatar_url: str | None
    bio: str | None
    created_at: datetime


class UpdateProfileRequest(BaseModel):
    name: str | None = None
    bio: str | None = None
    avatar_url: str | None = None


# ── Helpers ───────────────────────────────────────────────────
def _hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def _verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def _create_token(user_id: str, email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_H)
    return jwt.encode({"sub": user_id, "email": email, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """FastAPI dependency — validates JWT and returns the User row."""
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload  = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id  = payload.get("sub")
        if not user_id:
            raise credentials_exc
    except JWTError:
        raise credentials_exc

    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise credentials_exc
    return user


# ── Routes ────────────────────────────────────────────────────
@router.post("/register", response_model=TokenResponse, status_code=201)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=409, detail="Email already registered.")

    user = User(
        email    = body.email,
        password = _hash_password(body.password),
        name     = body.name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    log.info("New user registered: %s", user.email)

    token = _create_token(str(user.id), user.email)
    return TokenResponse(access_token=token, user_id=str(user.id), email=user.email, name=user.name)


@router.post("/login", response_model=TokenResponse)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form.username, User.is_active == True).first()
    if not user or not _verify_password(form.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    token = _create_token(str(user.id), user.email)
    return TokenResponse(access_token=token, user_id=str(user.id), email=user.email, name=user.name)


@router.get("/me", response_model=UserProfile)
def me(current_user: User = Depends(get_current_user)):
    return UserProfile(
        user_id    = str(current_user.id),
        email      = current_user.email,
        name       = current_user.name,
        avatar_url = current_user.avatar_url,
        bio        = current_user.bio,
        created_at = current_user.created_at,
    )


@router.patch("/me", response_model=UserProfile)
def update_profile(
    body: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if body.name is not None:
        current_user.name = body.name
    if body.bio is not None:
        current_user.bio = body.bio
    if body.avatar_url is not None:
        current_user.avatar_url = body.avatar_url
    db.commit()
    db.refresh(current_user)
    return UserProfile(
        user_id    = str(current_user.id),
        email      = current_user.email,
        name       = current_user.name,
        avatar_url = current_user.avatar_url,
        bio        = current_user.bio,
        created_at = current_user.created_at,
    )
