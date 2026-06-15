import pytest
import uuid
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from core.models.block import Block, BlockType
from core.models.course import Course
from core.models.test import Question, QuestionType, AnswerOption, TestSubmission, TestAnswer
from tests.api.api_v1.test_mixed_grading_50_cases import _create_course, _create_block, _get_auth_cookies

@pytest.mark.anyio
async def test_admin_pending_and_text_crud_flow(client: AsyncClient, session: AsyncSession, create_user):
    # Setup users
    admin = await create_user("ref_admin@test.com", is_superuser=True, role="administrator")
    user = await create_user("ref_user@test.com")
    cookies_admin = await _get_auth_cookies(client, admin)
    cookies_user = await _get_auth_cookies(client, user)

    # Setup course and manual test block
    course = await _create_course(session, admin.id)
    block = await _create_block(session, course.id, BlockType.manual_test)

    # Setup free-text question
    q = Question(block_id=block.id, text="Reference question", question_type=QuestionType.free_text, order_index=1)
    session.add(q)
    await session.commit()
    await session.refresh(q)

    # 1. GET correct answer (initially not found)
    resp = await client.get(f"/api/v1/tests/questions/{q.id}/correct-text-answer", cookies=cookies_admin)
    assert resp.status_code == 404

    # 2. POST correct answer
    resp = await client.post(
        f"/api/v1/tests/questions/{q.id}/correct-text-answer",
        json={"text": "Approximate correct answer reference"},
        cookies=cookies_admin
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["text"] == "Approximate correct answer reference"
    assert "id" in data

    # 3. GET correct answer again (now found)
    resp = await client.get(f"/api/v1/tests/questions/{q.id}/correct-text-answer", cookies=cookies_admin)
    assert resp.status_code == 200
    assert resp.json()["text"] == "Approximate correct answer reference"

    # 4. PATCH correct answer
    resp = await client.patch(
        f"/api/v1/tests/questions/{q.id}/correct-text-answer",
        json={"text": "Updated correct answer reference"},
        cookies=cookies_admin
    )
    assert resp.status_code == 200
    assert resp.json()["text"] == "Updated correct answer reference"

    # 5. Non-admin authorization check
    resp = await client.get(f"/api/v1/tests/questions/{q.id}/correct-text-answer", cookies=cookies_user)
    assert resp.status_code == 403

    resp = await client.post(
        f"/api/v1/tests/questions/{q.id}/correct-text-answer",
        json={"text": "Fail"},
        cookies=cookies_user
    )
    assert resp.status_code == 403

    # 6. GET pending review courses (initially none/empty or at least doesn't contain our course)
    resp = await client.get("/api/v1/courses/pending-review", cookies=cookies_admin)
    assert resp.status_code == 200
    pending_courses = resp.json()
    assert not any(c["id"] == str(course.id) for c in pending_courses)

    # 7. User submits the test (creates an ungraded submission)
    sub_resp = await client.post(
        f"/api/v1/tests/blocks/{block.id}/submit",
        json={"answers": [{"question_id": str(q.id), "text_answer": "My answer"}]},
        cookies=cookies_user
    )
    assert sub_resp.status_code == 200
    submission_id = sub_resp.json()["id"]

    # 8. GET pending review courses (now should contain our course!)
    resp = await client.get("/api/v1/courses/pending-review", cookies=cookies_admin)
    assert resp.status_code == 200
    pending_courses = resp.json()
    assert any(c["id"] == str(course.id) for c in pending_courses)

    # 9. Non-admin cannot view pending review courses
    resp = await client.get("/api/v1/courses/pending-review", cookies=cookies_user)
    assert resp.status_code == 403

    # 10. Admin grades the submission
    grade_resp = await client.post(
        f"/api/v1/tests/submissions/{submission_id}/grade",
        json={"score": 1, "admin_comment": "Verified"},
        cookies=cookies_admin
    )
    assert grade_resp.status_code == 200

    # 11. GET pending review courses (should no longer contain our course since it's graded!)
    resp = await client.get("/api/v1/courses/pending-review", cookies=cookies_admin)
    assert resp.status_code == 200
    pending_courses = resp.json()
    assert not any(c["id"] == str(course.id) for c in pending_courses)

    # 12. DELETE correct answer
    resp = await client.delete(f"/api/v1/tests/questions/{q.id}/correct-text-answer", cookies=cookies_admin)
    assert resp.status_code == 204

    # 13. GET correct answer (should be 404 again)
    resp = await client.get(f"/api/v1/tests/questions/{q.id}/correct-text-answer", cookies=cookies_admin)
    assert resp.status_code == 404
