from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.department import Department
from app.schemas.common import DepartmentOut

router = APIRouter(prefix="/api/departments", tags=["departments"])


@router.get("", response_model=list[DepartmentOut], dependencies=[Depends(get_current_user)])
def list_departments(db: Session = Depends(get_db)):
    return db.query(Department).all()
