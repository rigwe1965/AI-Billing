from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import rate_limit
from app.core.deps import get_db
from app.db.base import Base
from app.main import app
from app.models.department import Department
from app.models.pricing_rate import PricingRate
from app.models.provider import Provider, ProviderCode
from app.models.user import User, UserRole
from app.core.security import hash_password


@pytest.fixture()
def client():
    rate_limit.clear_all()
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestSessionLocal = sessionmaker(bind=engine)

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    setup_db = TestSessionLocal()
    provider = Provider(name="Anthropic", code=ProviderCode.anthropic, connector_type="anthropic")
    eng_dept = Department(name="Engineering", code="ENG")
    mkt_dept = Department(name="Marketing", code="MKT")
    setup_db.add_all([provider, eng_dept, mkt_dept])
    setup_db.commit()

    setup_db.add(
        PricingRate(
            provider_id=provider.id,
            sku_code="claude-sonnet-input-tokens",
            unit="per_1m_tokens",
            rate_amount=Decimal("3.00"),
            effective_from=date(2026, 1, 1),
            source="manual_admin_entry",
        )
    )
    admin = User(
        email="admin@test-org.com",
        hashed_password=hash_password("adminpass123"),
        role=UserRole.admin_finance,
    )
    eng_lead = User(
        email="englead@test-org.com",
        hashed_password=hash_password("engpass123"),
        role=UserRole.dept_lead,
        department_id=eng_dept.id,
    )
    mkt_lead = User(
        email="mktlead@test-org.com",
        hashed_password=hash_password("mktpass123"),
        role=UserRole.dept_lead,
        department_id=mkt_dept.id,
    )
    setup_db.add_all([admin, eng_lead, mkt_lead])
    setup_db.commit()
    setup_db.close()

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


def login(client, email, password):
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return client


def test_unauthenticated_request_is_rejected(client):
    resp = client.get("/api/costs/summary")
    assert resp.status_code == 401


def test_dept_lead_cannot_create_pricing_rate(client):
    login(client, "englead@test-org.com", "engpass123")
    resp = client.post(
        "/api/pricing",
        json={
            "provider_code": "anthropic",
            "sku_code": "x",
            "unit": "per_token",
            "rate_amount": "1.0",
            "effective_from": "2026-01-01",
        },
    )
    assert resp.status_code == 403


def test_dept_lead_cannot_reprocess_unpriced(client):
    login(client, "englead@test-org.com", "engpass123")
    resp = client.post("/api/costs/reprocess-unpriced")
    assert resp.status_code == 403


def test_dept_lead_csv_import_rejects_other_departments_code(client, tmp_path):
    login(client, "englead@test-org.com", "engpass123")
    csv_path = tmp_path / "bad.csv"
    csv_path.write_text(
        "provider_code,sku_code,quantity,unit,period_start,period_end,department_code\n"
        "anthropic,claude-sonnet-input-tokens,1000000,tokens,2026-01-05,2026-01-05,MKT\n"
    )
    with open(csv_path, "rb") as f:
        resp = client.post("/api/usage/import-csv", files={"file": ("bad.csv", f, "text/csv")})
    assert resp.status_code == 400
    assert "own department" in resp.text


def test_dept_lead_never_sees_other_departments_cost_summary(client, tmp_path):
    # Admin imports usage for both departments.
    login(client, "admin@test-org.com", "adminpass123")
    csv_path = tmp_path / "both.csv"
    csv_path.write_text(
        "provider_code,sku_code,quantity,unit,period_start,period_end,department_code\n"
        "anthropic,claude-sonnet-input-tokens,2000000,tokens,2026-01-05,2026-01-05,ENG\n"
        "anthropic,claude-sonnet-input-tokens,1000000,tokens,2026-01-05,2026-01-05,MKT\n"
    )
    with open(csv_path, "rb") as f:
        resp = client.post("/api/usage/import-csv", files={"file": ("both.csv", f, "text/csv")})
    assert resp.status_code == 200, resp.text
    assert resp.json()["cost_line_items_created"] == 2

    # Admin sees both departments.
    admin_summary = client.get("/api/costs/summary").json()
    depts_seen = {row["department"] for row in admin_summary}
    assert depts_seen == {"Engineering", "Marketing"}

    client.post("/api/auth/logout")

    # Engineering lead sees only Engineering.
    login(client, "englead@test-org.com", "engpass123")
    eng_summary = client.get("/api/costs/summary").json()
    assert {row["department"] for row in eng_summary} == {"Engineering"}
    assert eng_summary[0]["total_amount"] == "6.0000"

    client.post("/api/auth/logout")

    # Marketing lead sees only Marketing -- never Engineering's numbers.
    login(client, "mktlead@test-org.com", "mktpass123")
    mkt_summary = client.get("/api/costs/summary").json()
    assert {row["department"] for row in mkt_summary} == {"Marketing"}
    assert mkt_summary[0]["total_amount"] == "3.0000"


def test_reprocess_unpriced_resolves_usage_once_a_matching_rate_exists(client, tmp_path):
    login(client, "admin@test-org.com", "adminpass123")

    # This sku has no pricing_rate yet, so it lands in needs-pricing limbo.
    csv_path = tmp_path / "unpriced.csv"
    csv_path.write_text(
        "provider_code,sku_code,quantity,unit,period_start,period_end,department_code\n"
        "anthropic,claude-sonnet-output-tokens,500000,tokens,2026-01-05,2026-01-05,ENG\n"
    )
    with open(csv_path, "rb") as f:
        resp = client.post("/api/usage/import-csv", files={"file": ("unpriced.csv", f, "text/csv")})
    assert resp.status_code == 200, resp.text
    assert resp.json()["needs_pricing_rule_count"] == 1
    assert len(client.get("/api/costs/unpriced").json()) == 1

    # Adding the rate alone doesn't retroactively fix the already-created line item.
    resp = client.post(
        "/api/pricing",
        json={
            "provider_code": "anthropic",
            "sku_code": "claude-sonnet-output-tokens",
            "unit": "per_1m_tokens",
            "rate_amount": "15.00",
            "effective_from": "2026-01-01",
        },
    )
    assert resp.status_code == 200, resp.text
    assert len(client.get("/api/costs/unpriced").json()) == 1

    # Reprocessing re-derives it using the now-active rate.
    resp = client.post("/api/costs/reprocess-unpriced")
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"checked": 1, "resolved": 1}

    assert client.get("/api/costs/unpriced").json() == []
    summary = client.get("/api/costs/summary").json()
    eng_row = next(r for r in summary if r["department"] == "Engineering")
    assert eng_row["total_amount"] == "7.5000"  # 500,000 / 1,000,000 * $15.00

    # Idempotent: nothing left to reprocess on a second call.
    resp = client.post("/api/costs/reprocess-unpriced")
    assert resp.json() == {"checked": 0, "resolved": 0}


def test_change_password_requires_auth(client):
    resp = client.post("/api/auth/change-password", json={"current_password": "x", "new_password": "a-new-long-password"})
    assert resp.status_code == 401


def test_change_password_rejects_wrong_current_and_short_new(client):
    login(client, "englead@test-org.com", "engpass123")
    bad = client.post("/api/auth/change-password", json={"current_password": "nope", "new_password": "a-new-long-password"})
    assert bad.status_code == 400
    short = client.post("/api/auth/change-password", json={"current_password": "engpass123", "new_password": "short"})
    assert short.status_code == 422


def test_change_password_success_swaps_credentials(client):
    login(client, "englead@test-org.com", "engpass123")
    resp = client.post(
        "/api/auth/change-password",
        json={"current_password": "engpass123", "new_password": "a-new-long-password"},
    )
    assert resp.status_code == 200
    client.post("/api/auth/logout")
    assert client.post("/api/auth/login", json={"email": "englead@test-org.com", "password": "engpass123"}).status_code == 401
    login(client, "englead@test-org.com", "a-new-long-password")


def test_login_is_throttled_after_repeated_failures(client):
    for _ in range(rate_limit.MAX_FAILURES):
        r = client.post("/api/auth/login", json={"email": "englead@test-org.com", "password": "wrong"})
        assert r.status_code == 401
    blocked = client.post("/api/auth/login", json={"email": "englead@test-org.com", "password": "engpass123"})
    assert blocked.status_code == 429


def test_create_user_rejects_short_password(client):
    login(client, "admin@test-org.com", "adminpass123")
    r = client.post("/api/users", json={"email": "x@test-org.com", "password": "short", "role": "admin_finance"})
    assert r.status_code == 422


def test_csv_upload_over_limit_is_rejected(client):
    from app.api.routes import usage

    login(client, "englead@test-org.com", "engpass123")
    big = b"a" * (usage.MAX_UPLOAD_BYTES + 1)
    r = client.post("/api/usage/import-csv", files={"file": ("big.csv", big, "text/csv")})
    assert r.status_code == 413


def test_insights_question_length_is_capped(client):
    login(client, "englead@test-org.com", "engpass123")
    r = client.post("/api/insights/ask", json={"question": "x" * 2001})
    assert r.status_code == 422


def test_excel_export_escapes_formula_cells():
    from app.services.report_service import _cell

    assert _cell("=HYPERLINK(\"http://evil\")") == "'=HYPERLINK(\"http://evil\")"
    assert _cell("@SUM(1)") == "'@SUM(1)"
    assert _cell("claude-sonnet") == "claude-sonnet"


def test_logout_revokes_the_token_server_side(client):
    login(client, "englead@test-org.com", "engpass123")
    stolen = client.cookies.get("access_token")
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {stolen}"}).status_code == 200
    client.post("/api/auth/logout")
    client.cookies.clear()
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {stolen}"}).status_code == 401


def test_change_password_revokes_other_sessions_but_keeps_current(client):
    login(client, "englead@test-org.com", "engpass123")
    old_token = client.cookies.get("access_token")
    client.post(
        "/api/auth/change-password",
        json={"current_password": "engpass123", "new_password": "a-new-long-password"},
    )
    assert client.get("/api/auth/me").status_code == 200  # this browser got a fresh cookie
    client.cookies.clear()
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {old_token}"}).status_code == 401
