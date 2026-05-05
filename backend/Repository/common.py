import uuid
import re
import unicodedata
from typing import Any, Type

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


def sanitize_import_text(
    value: Any,
    *,
    normalize_slashes: bool = True,
) -> str:
    """
    Normalize imported text values for stable storage/search:
    - normalize unicode (NFKC)
    - remove line breaks/tabs/control chars
    - collapse repeated whitespace
    - optional backslash normalization
    """
    if value is None:
        return ""

    text = unicodedata.normalize("NFKC", str(value))
    text = text.replace("\\r\\n", " ").replace("\\n", " ").replace("\\r", " ").replace("\\t", " ")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\n", " ").replace("\t", " ")
    text = "".join(ch for ch in text if unicodedata.category(ch) not in {"Cc", "Cf"})

    if normalize_slashes:
        text = text.replace("\\", "/")
        text = re.sub(r"(?<!:)/{2,}", "/", text)

    text = re.sub(r"\s+", " ", text).strip()
    return text


async def ensure_unique_field(
    session: AsyncSession,
    model: Type[Any],
    field_name: str,
    value: str,
    exclude_id: uuid.UUID | None = None,
    error_msg: str | None = None,
):
    field = getattr(model, field_name)
    stmt = select(model).where(func.lower(field) == value.lower())

    if exclude_id:
        stmt = stmt.where(model.id != exclude_id)

    result = await session.execute(stmt)
    if result.scalar_one_or_none():
        if not error_msg:
            error_msg = f"{model.__name__} with {field_name} '{value}' already exists"

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=error_msg,
        )
