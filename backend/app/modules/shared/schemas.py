"""Shared response shapes used by stub routers."""

from pydantic import BaseModel


class StubStatus(BaseModel):
    status: str = "not_implemented"
    module: str
    detail: str | None = None
