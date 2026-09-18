from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.deps import department_scope, get_db
from app.services.report_service import build_excel_report, build_pdf_report

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/excel")
def export_excel(db: Session = Depends(get_db), scope_department_id: int | None = Depends(department_scope)):
    content = build_excel_report(db, department_id=scope_department_id)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=ai_spend_report.xlsx"},
    )


@router.get("/pdf")
def export_pdf(db: Session = Depends(get_db), scope_department_id: int | None = Depends(department_scope)):
    content = build_pdf_report(db, department_id=scope_department_id)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=ai_spend_report.pdf"},
    )
