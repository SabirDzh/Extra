import uuid
import re
from pathlib import Path
from typing import Annotated, Literal

from core.config import BASE_DIR, settings
from core.models.db_helper import db_helper
from core.models.user import User
from core.schemas.base import PaginationParams
from core.schemas.product import (
    ProductCreate,
    ProductListRead,
    ProductRead,
    ProductSummaryInfo,
    ProductUpdate,
)
from Services import product as product_crud
from Repository.search_engine import SearchIn
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi_cache.decorator import cache
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from Services.product_analytics import (
    get_multiple_product_views,
    get_product_views,
    get_top_product_ids,
    track_product_view,
)
from api.dependencies.authorization import current_admin

from api.dependencies.redis import get_redis

router = APIRouter(
    prefix=settings.api.v1.product,
    tags=["Products"],
)

Session = Annotated[AsyncSession, Depends(db_helper.session_getter)]
AdminUser = Annotated[User, Depends(current_admin)]
RedisDep = Annotated[Redis, Depends(get_redis)]
SCHEMA_MEDIA_DIR = BASE_DIR / "media" / "product_schema_connect"


def _get_client_identifier(request: Request) -> str:
    user = getattr(request.state, "user", None)
    if user and hasattr(user, "id"):
        return str(user.id)

    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _schema_url_to_file_path(schema_url: str) -> Path:
    media_prefix = "/media/"
    if not schema_url.startswith(media_prefix):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="schema_connect must point to /media",
        )
    relative_path = schema_url[len(media_prefix) :]
    return (BASE_DIR / "media" / relative_path).resolve()


def _extract_detail_attributes(
    raw_attributes: dict | None,
) -> tuple[dict[str, object], str | None]:
    if not raw_attributes:
        return {}, None

    article = raw_attributes.get("article") or raw_attributes.get("Артикул")

    active_keys = sorted(
        key
        for key, value in raw_attributes.items()
        if isinstance(value, bool) and value is True
    )

    filtered: dict[str, object] = {}
    range_suffixes = ("_min", "_max", "_from", "_to")
    grouped_numeric: dict[tuple[str, str], list[float]] = {}

    # Example we collapse:
    # "Максимальное давление в системе 10 бар"
    # "Максимальное давление в системе 6 бар"
    # -> "Максимальное давление в системе", + _min/_max
    numeric_tail_pattern = re.compile(
        r"^(?P<base>.*?\D)\s*(?P<value>\d+(?:[.,]\d+)?)\s*(?P<unit>[A-Za-zА-Яа-я%°/]+)$"
    )

    for key in active_keys:
        if key in {"article", "Артикул"}:
            continue

        match = numeric_tail_pattern.match(key)
        if match:
            base = match.group("base").strip()
            unit = match.group("unit").strip()
            raw_num = match.group("value").replace(",", ".")
            try:
                num = float(raw_num)
            except ValueError:
                num = None

            if num is not None and base:
                grouped_numeric.setdefault((base, unit), []).append(num)
                continue

        filtered[key] = True
        for suffix in range_suffixes:
            range_key = f"{key}{suffix}"
            if range_key in raw_attributes:
                filtered[range_key] = raw_attributes[range_key]

    for (base, unit), values in grouped_numeric.items():
        if not values:
            continue
        if len(values) == 1:
            value_text = str(values[0]).rstrip("0").rstrip(".")
            filtered[f"{base} {value_text} {unit}"] = True
            continue
        filtered[base] = True
        min_val = min(values)
        max_val = max(values)
        filtered[f"{base}_min"] = min_val
        filtered[f"{base}_max"] = max_val
        filtered[f"{base}_unit"] = unit
        min_text = str(min_val).rstrip("0").rstrip(".")
        max_text = str(max_val).rstrip("0").rstrip(".")
        filtered[f"{base}_range"] = f"{min_text}-{max_text} {unit}"

    return filtered, str(article) if article is not None else None


@router.get("/", response_model=list[ProductListRead])
@cache(expire=60)
async def list_products(
    db: Session,
    redis: RedisDep,
    limit: int | None = Query(None, ge=1, le=9000),
    page: int | None = Query(None, ge=1),
    sort_by: Literal["title", "created_at", "description"] = Query("title"),
    order: Literal["asc", "desc"] = Query("asc"),
    features: list[str] | None = Query(
        None, description="Filter by product attributes (e.g. 'Модуль Wi-Fi')"
    ),
):
    if limit is None and page is None:
        calculated_limit = None
        offset = 0
    else:
        calculated_limit = limit or 9000
        calculated_page = page or 1
        offset = (calculated_page - 1) * calculated_limit

    products = await product_crud.get_products(
        db,
        offset=offset,
        limit=calculated_limit,
        sort_by=sort_by,
        order=order,
        features=features,
    )

    return products


@router.get("/search", response_model=list[ProductListRead])
@cache(expire=60)
async def search_products(
    db: Session,
    redis: RedisDep,
    limit: int | None = Query(None, ge=1, le=9000),
    page: int | None = Query(None, ge=1),
    q: str | None = Query(None, description="Search query"),
    order: Literal["asc", "desc"] = Query("asc"),
    sort_by: SearchIn = Query("all"),
    features: list[str] | None = Query(
        None, description="Filter by product attributes"
    ),
):
    if limit is None and page is None:
        calculated_limit = None
        offset = 0
    else:
        calculated_limit = limit or 9000
        calculated_page = page or 1
        offset = (calculated_page - 1) * calculated_limit

    products = await product_crud.search_products(
        db,
        q=q,
        offset=offset,
        limit=calculated_limit,
        sort="alphabet_desc" if order == "desc" else "alphabet_asc",
        search_in=sort_by,
        features=features,
    )

    return products


@router.post("/", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
async def create_product(
    data: ProductCreate,
    db: Session,
    admin: AdminUser,
    redis: RedisDep,
):
    product = await product_crud.create_product(db, data)
    product.views = 0
    try:
        await redis.zadd("products:popularity", {str(product.id): 0})
    except Exception:
        pass
    return product


@router.delete("/all/clear", status_code=status.HTTP_200_OK)
async def clear_all_products(
    db: Session,
    admin: AdminUser,
    redis: RedisDep,
):
    """Очищает всю таблицу товаров и сбрасывает рейтинги в Redis."""
    count = await product_crud.delete_all_products(db)

    try:
        keys = await redis.keys("product:*:unique_views")
        if keys:
            await redis.delete(*keys)
        await redis.delete("products:popularity")
    except Exception:
        pass

    return {
        "msg": f"Успешно удалено товаров: {count}. Данные в Redis сброшены.",
        "status": "OK",
    }


@router.get("/{product_id}", response_model=ProductRead)
async def get_product(
    product_id: uuid.UUID,
    db: Session,
    redis: RedisDep,
    request: Request,
):
    product = await product_crud.get_product(db, product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
        )


    identifier = _get_client_identifier(request)
    await track_product_view(redis, product_id, identifier)


    views = await get_product_views(redis, product_id)
    product_data = ProductRead.model_validate(product).model_dump()
    filtered_attributes, article = _extract_detail_attributes(
        product_data.get("attributes")
    )
    product_data["views"] = views
    product_data["attributes"] = filtered_attributes
    product_data["article"] = article

    return product_data


@router.patch("/{product_id}", response_model=ProductRead)
async def update_product(
    product_id: uuid.UUID,
    data: ProductUpdate,
    db: Session,
    admin: AdminUser,
    redis: RedisDep,
):
    product = await product_crud.get_product(db, product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
        )

    updated_product = await product_crud.update_product(db, product, data)
    updated_product.views = await get_product_views(redis, product_id)
    return updated_product


@router.post(
    "/{product_id}/schema-connect/upload",
    response_model=ProductRead,
    status_code=status.HTTP_200_OK,
)
async def upload_product_schema_connect_file(
    product_id: uuid.UUID,
    db: Session,
    admin: AdminUser,
    redis: RedisDep,
    file: UploadFile = File(...),
):
    product = await product_crud.get_product(db, product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
        )

    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Filename is required"
        )

    SCHEMA_MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    ext = Path(file.filename).suffix
    stored_filename = f"{uuid.uuid4()}{ext}"
    destination = SCHEMA_MEDIA_DIR / stored_filename

    content = await file.read()
    destination.write_bytes(content)
    schema_url = f"/media/product_schema_connect/{stored_filename}"

    if product.schema_connect:
        try:
            old_file_path = _schema_url_to_file_path(product.schema_connect)
            old_media_root = (BASE_DIR / "media").resolve()
            if old_media_root in old_file_path.parents and old_file_path.exists():
                old_file_path.unlink()
        except Exception:
            pass

    updated_product = await product_crud.update_product(
        db, product, ProductUpdate(schema_connect=schema_url)
    )
    updated_product.views = await get_product_views(redis, product_id)
    return updated_product


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: uuid.UUID,
    db: Session,
    admin: AdminUser,
    redis: RedisDep,
):
    product = await product_crud.get_product(db, product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
        )

    await product_crud.delete_product(db, product)

    try:
        await redis.delete(f"product:{product_id}:unique_views")
        await redis.zrem("products:popularity", str(product_id))
    except Exception:
        pass


@router.delete("/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_products(
    products_id: Annotated[list[uuid.UUID], Query()],
    db: Session,
    admin: AdminUser,
    redis: RedisDep,
):
    await product_crud.delete_products(db, products_id)
    if products_id:
        keys = [f"product:{pid}:unique_views" for pid in products_id]
        try:
            await redis.delete(*keys)
            await redis.zrem("products:popularity", *[str(pid) for pid in products_id])
        except Exception:
            pass


@router.get("/summary/", response_model=list[ProductSummaryInfo])
async def get_product_summary(db: Session, pagination: PaginationParams = Depends()):
    return await product_crud.get_product_summary(
        db, pagination.limit, pagination.offset
    )


@router.get("/filters/", response_model=list[str])
async def get_product_filters(db: Session):
    return await product_crud.get_product_attributes_list(db)


@router.post("/import", status_code=status.HTTP_201_CREATED)
async def import_products(
    db: Session,
    admin: AdminUser,
    file: UploadFile = File(),
):
    return await product_crud.import_products(db, file)


@router.get("/popular/", response_model=list[ProductListRead])
@cache(expire=60)
async def get_popular_product(
    db: Session,
    redis: RedisDep,
    pagination: PaginationParams = Depends(),
):
    """
    Returns products sorted by unique views (popularity).
    Uses Redis Sorted Set for efficient ranking.
    """
    top_ids_str = await get_top_product_ids(
        redis, limit=pagination.limit, offset=pagination.offset
    )

    if not top_ids_str:
        return []

    product_ids = [uuid.UUID(pid) for pid in top_ids_str]

    products = await product_crud.get_products_by_ids(db, product_ids)

    return products
