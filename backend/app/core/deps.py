from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User, UserRole

COOKIE_NAME = "access_token"

__all__ = ["get_db", "get_current_user", "require_admin", "department_scope", "ensure_department_access"]


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.removeprefix("Bearer ").strip()

    email = decode_access_token(token) if token else None
    if not email:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")

    user = db.query(User).filter(User.email == email, User.is_active.is_(True)).first()
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.admin_finance:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin/finance role required")
    return user


def department_scope(user: User = Depends(get_current_user)) -> int | None:
    """None means 'no restriction' (admin_finance sees all departments);
    otherwise the department_id every query for this user must be filtered to."""
    return None if user.role == UserRole.admin_finance else user.department_id


def ensure_department_access(user: User, department_id: int | None) -> None:
    """Raises 403 if a non-admin user is trying to act on/view a department
    that isn't their own. A None department_id (unallocated data) is always
    viewable -- it's exactly the kind of thing a dept_lead needs to flag."""
    if user.role == UserRole.admin_finance or department_id is None:
        return
    if department_id != user.department_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not authorized for this department")
