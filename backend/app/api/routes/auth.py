from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.core import rate_limit
from app.core.config import settings
from app.core.deps import get_current_user, get_db
from app.core.security import create_access_token, decode_access_token, hash_password, verify_dummy_password, verify_password
from app.models.user import User
from app.schemas.auth import ChangePasswordRequest, LoginRequest, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])

COOKIE_NAME = "access_token"


@router.post("/login", response_model=UserOut)
def login(payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else "unknown"
    if rate_limit.is_blocked(payload.email, ip):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many failed login attempts. Try again later.")

    user = db.query(User).filter(User.email == payload.email, User.is_active.is_(True)).first()
    if user is None:
        verify_dummy_password(payload.password)
    if user is None or not verify_password(payload.password, user.hashed_password):
        rate_limit.record_failure(payload.email, ip)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    rate_limit.reset(payload.email, ip)

    token = create_access_token(subject=user.email, token_version=user.token_version)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=settings.access_token_expire_minutes * 60,
    )
    return user


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    # Revoke server-side too: bumping token_version invalidates every token issued
    # to this user, including a copy someone may have captured.
    token = request.cookies.get(COOKIE_NAME)
    claims = decode_access_token(token) if token else None
    if claims:
        user = db.query(User).filter(User.email == claims[0]).first()
        if user is not None and user.token_version == claims[1]:
            user.token_version += 1
            db.commit()
    response.delete_cookie(COOKIE_NAME, httponly=True, samesite="lax", secure=settings.cookie_secure)
    return {"status": "logged_out"}


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect")
    if payload.new_password == payload.current_password:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "New password must differ from the current one")
    current_user.hashed_password = hash_password(payload.new_password)
    # Revoke every existing session (including any stolen one), then re-issue a
    # token for this browser so the user who just changed it stays logged in.
    current_user.token_version += 1
    db.commit()
    response.set_cookie(
        key=COOKIE_NAME,
        value=create_access_token(subject=current_user.email, token_version=current_user.token_version),
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=settings.access_token_expire_minutes * 60,
    )
    return {"status": "password_changed"}
