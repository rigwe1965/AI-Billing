"""Excel and PDF export builders. Both read from the same aggregate/detail
queries the dashboard API uses (live_cost_line_items) so a report and the
in-app numbers can never silently disagree.
"""

import io
from decimal import Decimal

from openpyxl import Workbook
from openpyxl.styles import Font
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.cost_line_item import CostLineItem
from app.models.department import Department
from app.models.pricing_rate import PricingRate
from app.models.provider import Provider
from app.models.usage_record import UsageRecord
from app.services.budget_engine import current_spend_for_budget
from app.services.costing_engine import live_cost_line_items


def _cell(value):
    """Neutralizes spreadsheet formula injection: openpyxl stores a string that
    starts with = as a formula, and +, -, @ (and tab/CR) are treated the same by
    Excel. Usage CSVs are user-supplied, so every text cell is escaped."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", chr(9), chr(13)):
        return "'" + value
    return value


def _summary_rows(db: Session, department_id: int | None):
    query = (
        live_cost_line_items(db)
        .join(UsageRecord, CostLineItem.usage_record_id == UsageRecord.id)
        .join(Provider, UsageRecord.provider_id == Provider.id)
        .outerjoin(Department, CostLineItem.department_id == Department.id)
        .filter(CostLineItem.computed_amount.isnot(None))
    )
    if department_id is not None:
        query = query.filter(CostLineItem.department_id == department_id)

    return (
        query.with_entities(
            func.strftime("%Y-%m", UsageRecord.period_start).label("period"),
            Department.name.label("department"),
            Provider.name.label("provider"),
            func.sum(CostLineItem.computed_amount).label("total_amount"),
            CostLineItem.currency.label("currency"),
        )
        .group_by("period", "department", "provider", CostLineItem.currency)
        .order_by("period")
        .all()
    )


def _detail_rows(db: Session, department_id: int | None):
    query = (
        live_cost_line_items(db)
        .join(UsageRecord, CostLineItem.usage_record_id == UsageRecord.id)
        .join(Provider, UsageRecord.provider_id == Provider.id)
        .outerjoin(Department, CostLineItem.department_id == Department.id)
        .outerjoin(PricingRate, CostLineItem.pricing_rate_id == PricingRate.id)
    )
    if department_id is not None:
        query = query.filter(CostLineItem.department_id == department_id)

    return (
        query.with_entities(
            UsageRecord.period_start,
            Provider.name.label("provider"),
            Department.name.label("department"),
            UsageRecord.sku_code,
            UsageRecord.quantity,
            CostLineItem.computed_amount,
            CostLineItem.currency,
            CostLineItem.allocation_method,
            UsageRecord.source_type,
            PricingRate.id.label("pricing_rate_id"),
            PricingRate.effective_from.label("pricing_rate_effective_from"),
            CostLineItem.computed_at,
            CostLineItem.needs_pricing_rule,
        )
        .order_by(UsageRecord.period_start)
        .all()
    )


def build_excel_report(db: Session, department_id: int | None = None) -> bytes:
    wb = Workbook()

    summary_ws = wb.active
    summary_ws.title = "Summary"
    header_font = Font(bold=True)
    summary_ws.append(["Period", "Department", "Provider", "Total Amount", "Currency"])
    for cell in summary_ws[1]:
        cell.font = header_font
    for row in _summary_rows(db, department_id):
        summary_ws.append(
            [_cell(row.period), _cell(row.department or "(unallocated)"), _cell(row.provider), float(row.total_amount), _cell(row.currency)]
        )

    detail_ws = wb.create_sheet("Detail")
    detail_headers = [
        "Period Start", "Provider", "Department", "SKU", "Quantity", "Amount", "Currency",
        "Allocation Method", "Source Type", "Pricing Rate ID", "Pricing Rate Effective From",
        "Computed At", "Needs Pricing Rule",
    ]
    detail_ws.append(detail_headers)
    for cell in detail_ws[1]:
        cell.font = header_font
    for row in _detail_rows(db, department_id):
        detail_ws.append(
            [
                row.period_start.isoformat(),
                _cell(row.provider),
                _cell(row.department or "(unallocated)"),
                _cell(row.sku_code),
                float(row.quantity),
                float(row.computed_amount) if row.computed_amount is not None else None,
                _cell(row.currency),
                row.allocation_method.value,
                row.source_type.value,
                row.pricing_rate_id,
                row.pricing_rate_effective_from.isoformat() if row.pricing_rate_effective_from else None,
                row.computed_at.isoformat(),
                row.needs_pricing_rule,
            ]
        )

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def build_pdf_report(db: Session, department_id: int | None = None) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter)
    styles = getSampleStyleSheet()
    elements = [Paragraph("AI Spend Summary Report", styles["Title"]), Spacer(1, 12)]

    summary_rows = _summary_rows(db, department_id)
    table_data = [["Period", "Department", "Provider", "Amount", "Currency"]]
    for r in summary_rows:
        table_data.append([r.period, r.department or "(unallocated)", r.provider, f"{r.total_amount:.2f}", r.currency])

    table = Table(table_data, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#333333")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
            ]
        )
    )
    elements.append(table)
    elements.append(Spacer(1, 24))

    elements.append(Paragraph("Budget Status", styles["Heading2"]))
    from app.models.budget import Budget

    budget_query = db.query(Budget)
    if department_id is not None:
        budget_query = budget_query.filter(Budget.department_id == department_id)
    budgets = budget_query.all()

    if not budgets:
        elements.append(Paragraph("No budgets configured.", styles["Normal"]))
    else:
        budget_data = [["Department", "Period", "Budget", "Spent", "% Used"]]
        for budget in budgets:
            department = db.query(Department).filter(Department.id == budget.department_id).first()
            spend = current_spend_for_budget(db, budget)
            pct = (spend / budget.amount * 100) if budget.amount else Decimal("0")
            budget_data.append(
                [
                    department.name if department else "Unknown",
                    budget.period,
                    f"{budget.amount:.2f}",
                    f"{spend:.2f}",
                    f"{pct:.1f}%",
                ]
            )
        budget_table = Table(budget_data, repeatRows=1)
        budget_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#333333")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ]
            )
        )
        elements.append(budget_table)

    doc.build(elements)
    return buf.getvalue()
