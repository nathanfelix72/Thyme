"""Calendar / meal-plan API stubs."""

from fastapi import APIRouter

from app.modules.shared.schemas import StubStatus

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


@router.get("", response_model=StubStatus)
def calendar_root() -> StubStatus:
    return StubStatus(
        module="calendar",
        detail="Week meal-plan endpoints will live here.",
    )


@router.get("/week", response_model=StubStatus)
def week_plan() -> StubStatus:
    return StubStatus(
        module="calendar",
        detail="TODO: return meals spread across the week with recipe links.",
    )
