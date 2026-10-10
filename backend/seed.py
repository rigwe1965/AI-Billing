"""One-time/idempotent seed of reference data: providers, starter departments,
and an initial admin login. Run with: python seed.py
Safe to re-run — skips rows that already exist by unique code/email.
"""

import os
import secrets

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.department import Department
from app.models.provider import Provider, ProviderCode
from app.models.user import User, UserRole

STARTER_PROVIDERS = [
    ("Anthropic", ProviderCode.anthropic, "anthropic"),
    ("OpenAI", ProviderCode.openai, "openai"),
    ("Google", ProviderCode.google, "google_bigquery"),
    ("Custom / Other", ProviderCode.custom, "manual"),
]

STARTER_DEPARTMENTS = [
    ("Engineering", "ENG"),
    ("Marketing", "MKT"),
    ("Support", "SUP"),
]

ADMIN_EMAIL = os.environ.get("ADMIN_INITIAL_EMAIL", "admin@ai-billing.app")
# No well-known default: if ADMIN_INITIAL_PASSWORD is unset, a random one is
# generated and printed once when the admin is created.
ADMIN_PASSWORD = os.environ.get("ADMIN_INITIAL_PASSWORD") or secrets.token_urlsafe(16)


def seed():
    db = SessionLocal()
    try:
        for name, code, connector_type in STARTER_PROVIDERS:
            if not db.query(Provider).filter(Provider.code == code).first():
                db.add(Provider(name=name, code=code, connector_type=connector_type))

        for name, code in STARTER_DEPARTMENTS:
            if not db.query(Department).filter(Department.code == code).first():
                db.add(Department(name=name, code=code))

        db.commit()

        if not db.query(User).filter(User.email == ADMIN_EMAIL).first():
            db.add(
                User(
                    email=ADMIN_EMAIL,
                    hashed_password=hash_password(ADMIN_PASSWORD),
                    role=UserRole.admin_finance,
                    department_id=None,
                )
            )
            db.commit()
            print(f"Created initial admin user: {ADMIN_EMAIL} / {ADMIN_PASSWORD}  (shown once -- store it now)")

        print("Seed complete.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
