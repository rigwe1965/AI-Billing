from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.core import rate_limit
from app.core.config import settings
from app.core.deps import get_current_user, get_db
from app.core.security import create_access_token, hash_password, verify_dummy_password, verify_password
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

    token = create_access_token(subject=user.email)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=settings.access_token_expire_minutes * 60,
    )
    return user


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME)
    return {"status": "logged_out"}


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect")
    if payload.new_password == payload.current_password:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "New password must differ from the current one")
    current_user.hashed_password = hash_password(payload.new_password)
    db.commit()
    return {"status": "password_changed"}
