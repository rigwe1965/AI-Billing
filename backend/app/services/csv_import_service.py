"""Parses a usage CSV into UsageRecord rows, ready for the costing engine.

Expected CSV columns (case-insensitive): provider_code, sku_code, quantity,
unit, period_start, period_end, department_code (optional), tag_value (optional).

This service only normalizes and validates rows into UsageRecord objects —
it never computes cost. That keeps CSV-imported and API-pulled usage flowing
through the exact same costing_engine code path.
"""

import csv
import io
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from app.models.department import Department
from app.models.provider import Provider
from app.models.user import User, UserRole
from app.models.usage_record import UsageRecord, UsageSourceType

REQUIRED_COLUMNS = {"provider_code", "sku_code", "quantity", "unit", "period_start", "period_end"}


class CsvImportError(ValueError):
    def __init__(self, row_number: int, message: str):
        self.row_number = row_number
        super().__init__(f"Row {row_number}: {message}")


def _parse_date(value: str) -> date:
    return datetime.strptime(value.strip(), "%Y-%m-%d").date()


def parse_csv(
    db: Session,
    file_content: bytes,
    source_reference: str,
    imported_by: User,
) -> list[UsageRecord]:
    text = file_content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))

    if reader.fieldnames is None:
        raise CsvImportError(0, "CSV has no header row")

    headers = {h.strip().lower() for h in reader.fieldnames}
    missing = REQUIRED_COLUMNS - headers
    if missing:
        raise CsvImportError(0, f"Missing required columns: {sorted(missing)}")

    provider_cache: dict[str, Provider] = {}
    department_cache: dict[str, Department] = {}
    records: list[UsageRecord] = []

    for i, raw_row in enumerate(reader, start=2):  # header is row 1
        row = {k.strip().lower(): (v.strip() if v else v) for k, v in raw_row.items()}

        provider_code = row.get("provider_code", "")
        if provider_code not in provider_cache:
            provider = db.query(Provider).filter(Provider.code == provider_code).first()
            if provider is None:
                raise CsvImportError(i, f"Unknown provider_code: {provider_code!r}")
            provider_cache[provider_code] = provider
        provider = provider_cache[provider_code]

        department_id = None
        department_code = row.get("department_code")
        if department_code:
            if department_code not in department_cache:
                dept = db.query(Department).filter(Department.code == department_code).first()
                if dept is None:
                    raise CsvImportError(i, f"Unknown department_code: {department_code!r}")
                department_cache[department_code] = dept
            department_id = department_cache[department_code].id

        if imported_by.role == UserRole.dept_lead:
            # A dept_lead can only import usage attributed to their own department --
            # either leave department_code blank (resolved later via key/tag mapping,
            # still ending up scoped to them at review time) or set it to their own.
            if department_id is not None and department_id != imported_by.department_id:
                raise CsvImportError(
                    i, "dept_lead users may only import usage for their own department"
                )
            if department_id is None:
                department_id = imported_by.department_id

        try:
            quantity = Decimal(row["quantity"])
        except (InvalidOperation, KeyError):
            raise CsvImportError(i, f"Invalid quantity: {row.get('quantity')!r}")

        try:
            period_start = _parse_date(row["period_start"])
            period_end = _parse_date(row["period_end"])
        except (ValueError, KeyError) as exc:
            raise CsvImportError(i, f"Invalid date: {exc}")

        records.append(
            UsageRecord(
                provider_id=provider.id,
                department_id=department_id,
                sku_code=row["sku_code"],
                quantity=quantity,
                unit=row["unit"],
                period_start=period_start,
                period_end=period_end,
                source_type=UsageSourceType.csv_import,
                source_reference=f"{source_reference}:row{i}",
                tag_value=row.get("tag_value") or None,
                api_key_label=row.get("api_key_label") or None,
                imported_by_user_id=imported_by.id,
            )
        )

    return records
