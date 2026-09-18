import json
from datetime import date
from decimal import Decimal

import httpx
import pytest
import respx

from app.api.routes.insights import ask_insight
from app.core.config import settings
from app.models.department import Department
from app.models.pricing_rate import PricingRate
from app.models.usage_record import UsageRecord, UsageSourceType
from app.schemas.insights import AskInsightIn
from app.services.costing_engine import price_usage_records
from app.services.insights_service import InsightsUnavailableError, ask


def _mock_messages_response(text: str) -> httpx.Response:
    return httpx.Response(200, json={"content": [{"type": "text", "text": text}]})


def test_ask_raises_when_no_api_key():
    with pytest.raises(InsightsUnavailableError):
        ask("How much did we spend?", {"cost_summary": []}, api_key=None)


@respx.mock
def test_ask_sends_context_and_returns_model_text():
    route = respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=_mock_messages_response("Engineering spent $3.00 in January.")
    )

    answer = ask("How much did Engineering spend?", {"cost_summary": [{"total_amount": "3.00"}]}, api_key="sk-ant-test")

    assert answer == "Engineering spent $3.00 in January."
    sent_body = json.loads(route.calls.last.request.content)
    assert sent_body["model"] == "claude-haiku-4-5"
    assert "3.00" in sent_body["messages"][0]["content"]


@respx.mock
def test_ask_insight_scopes_context_to_caller_department(db_session, anthropic_provider, engineering_dept, monkeypatch):
    marketing = Department(name="Marketing", code="MKT")
    db_session.add(marketing)
    db_session.commit()

    rate = PricingRate(
        provider_id=anthropic_provider.id,
        sku_code="claude-sonnet-input-tokens",
        unit="per_1m_tokens",
        rate_amount=Decimal("3.00"),
        effective_from=date(2026, 1, 1),
        source="manual_admin_entry",
    )
    db_session.add(rate)
    db_session.commit()

    eng_usage = UsageRecord(
        provider_id=anthropic_provider.id,
        department_id=engineering_dept.id,
        sku_code="claude-sonnet-input-tokens",
        quantity=Decimal("2000000"),
        unit="tokens",
        period_start=date(2026, 1, 15),
        period_end=date(2026, 1, 15),
        source_type=UsageSourceType.csv_import,
        source_reference="test",
    )
    mkt_usage = UsageRecord(
        provider_id=anthropic_provider.id,
        department_id=marketing.id,
        sku_code="claude-sonnet-input-tokens",
        quantity=Decimal("4000000"),
        unit="tokens",
        period_start=date(2026, 1, 15),
        period_end=date(2026, 1, 15),
        source_type=UsageSourceType.csv_import,
        source_reference="test",
    )
    db_session.add_all([eng_usage, mkt_usage])
    db_session.commit()
    price_usage_records(db_session, [eng_usage, mkt_usage])

    monkeypatch.setattr(settings, "anthropic_api_key", "sk-ant-test")
    route = respx.post("https://api.anthropic.com/v1/messages").mock(return_value=_mock_messages_response("ok"))

    ask_insight(payload=AskInsightIn(question="What did we spend?"), db=db_session, scope_department_id=engineering_dept.id)

    sent_body = json.loads(route.calls.last.request.content)
    sent_context = sent_body["messages"][0]["content"]
    assert "6.00" in sent_context  # Engineering's $6.00, from the context JSON
    assert "12.00" not in sent_context  # Marketing's $12.00 must never leak in


def test_ask_insight_returns_503_when_unavailable(db_session, monkeypatch):
    from fastapi import HTTPException

    monkeypatch.setattr(settings, "anthropic_api_key", None)
    with pytest.raises(HTTPException) as exc_info:
        ask_insight(payload=AskInsightIn(question="anything"), db=db_session, scope_department_id=None)
    assert exc_info.value.status_code == 503
