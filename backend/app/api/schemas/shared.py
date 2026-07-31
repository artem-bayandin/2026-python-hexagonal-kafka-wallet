from typing import Any

from pydantic import BaseModel, Field


class DataList[T](BaseModel):
    items: list[T] = Field(default_factory=list)


class ErrorEnvelope(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
