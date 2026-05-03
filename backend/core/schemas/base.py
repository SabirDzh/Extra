from typing import Literal

from pydantic import BaseModel, Field


class PaginationParams(BaseModel):
    page: int = Field(1, ge=1, description="Page number (1-based)")
    limit: int = Field(35, ge=1, le=100, description="Number of items to return")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.limit


class ListParams(PaginationParams):
    sorted: Literal["asc", "desc"] = "asc"
