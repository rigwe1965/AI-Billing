from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.provider import Provider
from app.schemas.common import ProviderOut

router = APIRouter(prefix="/api/providers", tags=["providers"])


@router.get("", response_model=list[ProviderOut], dependencies=[Depends(get_current_user)])
def list_providers(db: Session = Depends(get_db)):
    return db.query(Provider).all()
