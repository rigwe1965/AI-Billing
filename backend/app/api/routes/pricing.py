from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_admin
from app.models.pricing_rate import PricingRate
from app.models.provider import Provider
from app.schemas.common import PricingRateIn, PricingRateOut
from app.services.costing_engine import upsert_pricing_rate

router = APIRouter(prefix="/api/pricing", tags=["pricing"])


@router.get("", response_model=list[PricingRateOut], dependencies=[Depends(get_current_user)])
def list_pricing_rates(db: Session = Depends(get_db)):
    return db.query(PricingRate).order_by(PricingRate.effective_from.desc()).all()


@router.post("", response_model=PricingRateOut, dependencies=[Depends(require_admin)])
def create_pricing_rate(payload: PricingRateIn, db: Session = Depends(get_db)):
    """Adds a new versioned rate. If an active rate exists for the same
    provider/sku, its effective_to is closed the day before this one starts —
    old rows are never overwritten, only superseded. Admin/finance only: rates
    are a global, cross-department source of truth."""
    provider = db.query(Provider).filter(Provider.code == payload.provider_code).first()
    if provider is None:
        raise HTTPException(404, f"Unknown provider_code: {payload.provider_code}")

    return upsert_pricing_rate(
        db,
        provider_id=provider.id,
        sku_code=payload.sku_code,
        unit=payload.unit,
        rate_amount=payload.rate_amount,
        currency=payload.currency,
        effective_from=payload.effective_from,
        source=payload.source,
    )
