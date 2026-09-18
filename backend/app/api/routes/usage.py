from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.services.budget_engine import evaluate_all_active_budgets
from app.services.costing_engine import price_usage_records
from app.services.csv_import_service import CsvImportError, parse_csv
from app.schemas.common import CsvImportResult

router = APIRouter(prefix="/api/usage", tags=["usage"])


@router.post("/import-csv", response_model=CsvImportResult)
async def import_csv(
    file: UploadFile,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    content = await file.read()
    try:
        usage_records = parse_csv(
            db, content, source_reference=file.filename or "upload.csv", imported_by=current_user
        )
    except CsvImportError as exc:
        raise HTTPException(400, str(exc))

    if not usage_records:
        return CsvImportResult(usage_records_created=0, cost_line_items_created=0, needs_pricing_rule_count=0)

    db.add_all(usage_records)
    db.commit()
    for ur in usage_records:
        db.refresh(ur)

    line_items = price_usage_records(db, usage_records)
    needs_pricing = sum(1 for li in line_items if li.needs_pricing_rule)

    evaluate_all_active_budgets(db)

    return CsvImportResult(
        usage_records_created=len(usage_records),
        cost_line_items_created=len(line_items),
        needs_pricing_rule_count=needs_pricing,
    )
