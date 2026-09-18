"""Loads pricing_rate snapshots from app/pricing_configs/*.yaml.
Run with: python load_pricing_configs.py
Idempotent/safe to re-run: each rate goes through the same versioned
upsert_pricing_rate() rule used by POST /api/pricing, so re-running a file
with unchanged rates is a no-op and re-running one with new rate_amounts
correctly closes the old row and opens a new one -- never overwrites history.
"""

from datetime import date
from decimal import Decimal
from pathlib import Path

import yaml

from app.db.session import SessionLocal
from app.models.provider import Provider, ProviderCode
from app.services.costing_engine import upsert_pricing_rate

CONFIG_DIR = Path(__file__).parent / "app" / "pricing_configs"


def load_configs():
    db = SessionLocal()
    try:
        for path in sorted(CONFIG_DIR.glob("*.yaml")):
            config = yaml.safe_load(path.read_text())
            provider = (
                db.query(Provider).filter(Provider.code == ProviderCode(config["provider_code"])).first()
            )
            if provider is None:
                print(f"Skipping {path.name}: unknown provider_code {config['provider_code']!r}")
                continue

            effective_from = date.fromisoformat(str(config["effective_from"]))
            for entry in config["rates"]:
                upsert_pricing_rate(
                    db,
                    provider_id=provider.id,
                    sku_code=entry["sku_code"],
                    unit=entry["unit"],
                    rate_amount=Decimal(str(entry["rate_amount"])),
                    currency=entry.get("currency", "USD"),
                    effective_from=effective_from,
                    source=config["source"],
                )
            print(f"Loaded {len(config['rates'])} rate(s) from {path.name}")

        print("Pricing config load complete.")
    finally:
        db.close()


if __name__ == "__main__":
    load_configs()
