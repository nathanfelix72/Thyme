"""Grocery list / store-order API stubs."""

from fastapi import APIRouter

from app.modules.shared.schemas import StubStatus

router = APIRouter(prefix="/api/shop", tags=["shop"])


@router.get("", response_model=StubStatus)
def shop_root() -> StubStatus:
    return StubStatus(
        module="shop",
        detail="Grocery list and store-order adapters will live here.",
    )


@router.get("/list", response_model=StubStatus)
def grocery_list() -> StubStatus:
    return StubStatus(
        module="shop",
        detail="TODO: build grocery list from the week plan.",
    )


@router.post("/order", response_model=StubStatus)
def place_order() -> StubStatus:
    return StubStatus(
        module="shop",
        detail="TODO: place orders with Walmart, Amazon, or Sam's Club.",
    )
