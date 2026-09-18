from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.routes.budgets import budget_status
from app.api.routes.costs import cost_summary, unpriced_usage
from app.core.config import settings
from app.core.deps import department_scope, get_current_user, get_db
from app.schemas.insights import AskInsightIn, AskInsightOut
from app.services.insights_service import InsightsUnavailableError, ask

router = APIRouter(prefix="/api/insights", tags=["insights"])


@router.post("/ask", response_model=AskInsightOut, dependencies=[Depends(get_current_user)])
def ask_insight(
    payload: AskInsightIn,
    db: Session = Depends(get_db),
    scope_department_id: int | None = Depends(department_scope),
):
    """Answers a natural-language question about already-computed spend data.

    The LLM only ever sees the same figures cost_summary/unpriced/budget_status
    already return to this caller -- a dept_lead's question is scoped to their
    own department exactly like those endpoints, and the answer is advisory
    commentary, never a source of truth for a cost figure.
    """
    context = {
        "cost_summary": [row.model_dump(mode="json") for row in cost_summary(db=db, scope_department_id=scope_department_id)],
        "unpriced_usage": [row.model_dump(mode="json") for row in unpriced_usage(db=db, scope_department_id=scope_department_id)],
        "budget_status": [row.model_dump(mode="json") for row in budget_status(db=db, scope_department_id=scope_department_id)],
    }

    try:
        answer = ask(payload.question, context, settings.anthropic_api_key)
    except InsightsUnavailableError as exc:
        raise HTTPException(503, str(exc)) from exc

    return AskInsightOut(answer=answer)
