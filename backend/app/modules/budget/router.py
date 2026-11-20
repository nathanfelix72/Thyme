"""Budget / Plaid API stubs."""

from fastapi import APIRouter

from app.modules.shared.schemas import StubStatus

router = APIRouter(prefix="/api/budget", tags=["budget"])


@router.get("", response_model=StubStatus)
def budget_root() -> StubStatus:
    return StubStatus(
        module="budget",
        detail="Budget-aware planning and Plaid adapters will live here.",
    )


@router.get("/summary", response_model=StubStatus)
def budget_summary() -> StubStatus:
    return StubStatus(
        module="budget",
        detail="TODO: return weekly food spend vs budget (Plaid).",
    )
