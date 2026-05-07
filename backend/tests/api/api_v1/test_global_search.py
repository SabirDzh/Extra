import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.product import Product
from core.models.recommendation import Recommendation
from core.models.term import Term


@pytest.mark.anyio
async def test_global_search_exact_match_is_relevance_first_and_order_independent(
    client: AsyncClient,
    session: AsyncSession,
    create_user,
):
    user = await create_user("global-search-exact@example.com")
    session.add_all(
        [
            Product(
                title="ЭБУН-10-1.6",
                description="Плавный пуск для насоса",
                image_url=[],
                attributes={},
            ),
            Recommendation(
                title="Особенности работы с ЭБУН",
                description="Подробное описание семейства ЭБУН",
                created_by=user.id,
                is_published=True,
            ),
        ]
    )
    await session.commit()

    resp_asc = await client.get("/api/v1/search/?q=ЭБУН-10-1.6&sort_by=all&order=asc")
    resp_desc = await client.get("/api/v1/search/?q=ЭБУН-10-1.6&sort_by=all&order=desc")

    assert resp_asc.status_code == 200
    assert resp_desc.status_code == 200

    body_asc = resp_asc.json()
    body_desc = resp_desc.json()

    assert body_asc["products"]
    assert body_desc["products"]
    assert body_asc["products"][0]["title"] == "ЭБУН-10-1.6"
    assert body_desc["products"][0]["title"] == "ЭБУН-10-1.6"
    assert body_asc["products"][0]["id"] == body_desc["products"][0]["id"]
    assert body_asc["recommendations"] == []
    assert body_desc["recommendations"] == []


@pytest.mark.anyio
async def test_global_search_prefix_query_prioritizes_products_over_text_noise(
    client: AsyncClient,
    session: AsyncSession,
    create_user,
):
    user = await create_user("global-search-prefix@example.com")
    session.add(
        Product(
            title="ЭБУН-10-1.6",
            description="Устройство управления насосом",
            image_url=[],
            attributes={},
        )
    )
    await session.flush()
    session.add(
        Product(
            title="ЭБУН-10-3.0",
            description="Устройство управления насосом, расширенная версия",
            image_url=[],
            attributes={},
        )
    )
    await session.flush()
    session.add(
        Recommendation(
            title="Преимущества плавного включения",
            description="ЭБУН используется для плавного пуска насоса и защиты",
            created_by=user.id,
            is_published=True,
        )
    )
    await session.commit()

    resp_prefix = await client.get("/api/v1/search/?q=эбун-10&sort_by=all&order=asc")
    resp_partial = await client.get("/api/v1/search/?q=эбун-10-1.&sort_by=all&order=asc")

    assert resp_prefix.status_code == 200
    assert resp_partial.status_code == 200

    body_prefix = resp_prefix.json()
    body_partial = resp_partial.json()

    assert body_prefix["products"]
    assert body_prefix["products"][0]["title"].startswith("ЭБУН-10")
    assert body_prefix["recommendations"] == []

    assert body_partial["products"]
    assert body_partial["products"][0]["title"] == "ЭБУН-10-1.6"


@pytest.mark.anyio
async def test_global_search_empty_query_returns_five_per_category_with_browse_order(
    client: AsyncClient,
    session: AsyncSession,
):
    product_titles = ["A-product", "B-product", "C-product", "D-product", "E-product", "F-product"]
    term_titles = ["A-term", "B-term", "C-term", "D-term", "E-term", "F-term"]

    for title in product_titles:
        session.add(
            Product(
                title=title,
                description=f"description for {title}",
                image_url=[],
                attributes={},
            )
        )
        await session.flush()
    for title in term_titles:
        session.add(Term(title=title, description=f"description for {title}"))
        await session.flush()

    await session.commit()

    resp_asc = await client.get("/api/v1/search/?q=&limit=5&sort_by=all&order=asc")
    resp_desc = await client.get("/api/v1/search/?q=&limit=5&sort_by=all&order=desc")

    assert resp_asc.status_code == 200
    assert resp_desc.status_code == 200

    body_asc = resp_asc.json()
    body_desc = resp_desc.json()

    assert len(body_asc["products"]) == 5
    assert len(body_asc["terms"]) == 5
    assert len(body_desc["products"]) == 5
    assert len(body_desc["terms"]) == 5

    product_titles_asc = [item["title"] for item in body_asc["products"]]
    product_titles_desc = [item["title"] for item in body_desc["products"]]
    term_titles_asc = [item["title"] for item in body_asc["terms"]]
    term_titles_desc = [item["title"] for item in body_desc["terms"]]

    assert product_titles_asc == sorted(product_titles_asc, key=str.lower)
    assert term_titles_asc == sorted(term_titles_asc, key=str.lower)
    assert product_titles_desc == sorted(product_titles_desc, key=str.lower, reverse=True)
    assert term_titles_desc == sorted(term_titles_desc, key=str.lower, reverse=True)


@pytest.mark.anyio
async def test_global_search_sort_by_description_uses_description_signal(
    client: AsyncClient,
    session: AsyncSession,
):
    session.add(
        Product(
            title="Alpha in title only",
            description="generic content",
            image_url=[],
            attributes={},
        )
    )
    await session.flush()
    session.add(
        Product(
            title="Unrelated title",
            description="alpha unique phrase in description",
            image_url=[],
            attributes={},
        )
    )
    await session.commit()

    resp = await client.get(
        "/api/v1/search/?q=alpha unique phrase&sort_by=description&order=desc"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["products"]
    assert body["products"][0]["title"] == "Unrelated title"
