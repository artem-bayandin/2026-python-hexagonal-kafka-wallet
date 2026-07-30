from pydantic import BaseModel, Field


class DataList[T](BaseModel):
    items: list[T] = Field(default_factory=list)
