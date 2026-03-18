from typing import Literal

from pydantic import BaseModel, Field


class PaginationParams(BaseModel):
    limit: int = Field(10, ge=1, le=100, description="Number of items to return")
    offset: int = Field(0, ge=0, description="Number of item to skip")


class ListParams(PaginationParams):
    sorted: Literal["asc", "desc"] = "asc"
