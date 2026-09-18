from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_admin
from app.core.security import hash_password
from app.models.department import Department
from app.models.user import User, UserRole
from app.schemas.auth import UserCreate, UserOut

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=list[UserOut], dependencies=[Depends(require_admin)])
def list_users(db: Session = Depends(get_db)):
    return db.query(User).all()


@router.post("", response_model=UserOut, dependencies=[Depends(require_admin)])
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(400, "A user with this email already exists")

    if payload.role == UserRole.dept_lead:
        if payload.department_id is None:
            raise HTTPException(400, "dept_lead users must have a department_id")
        if not db.query(Department).filter(Department.id == payload.department_id).first():
            raise HTTPException(404, f"Unknown department_id: {payload.department_id}")

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=payload.role,
        department_id=payload.department_id if payload.role == UserRole.dept_lead else None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
