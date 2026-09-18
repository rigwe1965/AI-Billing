from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.connectors.base import ConnectorUnavailableError
from app.connectors.registry import get_connector
from app.core.deps import get_db, require_admin
from app.models.provider import Provider
from app.schemas.connectors import ConnectionTestOut, ConnectorStatusOut, PullRequest, PullResult
from app.services.ingestion_service import ProviderNotFoundError, run_connector_pull

router = APIRouter(prefix="/api/connectors", tags=["connectors"], dependencies=[Depends(require_admin)])


@router.get("", response_model=list[ConnectorStatusOut])
def list_connector_status(db: Session = Depends(get_db)):
    """Capability status for every provider that has a connector -- lets the
    UI show 'connect' vs 'CSV only' per provider instead of a user discovering
    it only when a pull fails."""
    out = []
    for provider in db.query(Provider).all():
        connector = get_connector(provider.code.value)
        if connector is None:
            continue
        caps = connector.capabilities()
        out.append(
            ConnectorStatusOut(
                provider_code=provider.code.value,
                configured=caps.supports_usage_pull or caps.unavailable_reason is None,
                supports_usage_pull=caps.supports_usage_pull,
                supports_cost_reconciliation=caps.supports_cost_reconciliation,
                requires_prerequisite=caps.requires_prerequisite,
                unavailable_reason=caps.unavailable_reason,
            )
        )
    return out


@router.post("/{provider_code}/test-connection", response_model=ConnectionTestOut)
def test_connection(provider_code: str):
    connector = get_connector(provider_code)
    if connector is None:
        raise HTTPException(404, f"No connector available for provider_code: {provider_code}")
    status = connector.test_connection()
    return ConnectionTestOut(provider_code=provider_code, ok=status.ok, detail=status.detail)


@router.post("/{provider_code}/pull", response_model=PullResult)
def trigger_pull(provider_code: str, payload: PullRequest, db: Session = Depends(get_db)):
    """Manually triggers an API usage pull for one provider/date range. The
    scheduled job (app/jobs/scheduler.py) calls the same run_connector_pull
    function nightly -- this endpoint exists for on-demand/backfill pulls and
    for testing a newly configured connector before trusting the schedule."""
    try:
        result = run_connector_pull(db, provider_code, payload.period_start, payload.period_end)
    except ProviderNotFoundError as exc:
        raise HTTPException(404, str(exc))
    except ConnectorUnavailableError as exc:
        raise HTTPException(
            409, f"Connector unavailable for {provider_code}: {exc}. Use CSV import instead."
        )
    return PullResult(**result)
