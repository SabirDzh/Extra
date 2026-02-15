import uuid

import pytest
from core.models.block import Block, BlockType
from core.models.course import Course
from core.models.test import AnswerOption, Question
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.anyio


# --- Helpers ---


async def create_course_db(session, user_id, title="Test Course"):
    c = Course(title=title, created_by=user_id, is_published=True)
    session.add(c)
    await session.commit()
    await session.refresh(c)
    return c


async def create_block_db(
    session, course_id, title="B1", btype=BlockType.auto_test, text="Content"
):
    b = Block(course_id=course_id, title=title, block_type=btype, text_content=text)
    session.add(b)
    await session.commit()
    await session.refresh(b)
    return b


async def create_question_db(session, block_id, text="Q1", qtype="single_choice"):
    q = Question(block_id=block_id, text=text, question_type=qtype)
    session.add(q)
    await session.commit()
    await session.refresh(q)
    return q


async def create_question_with_options_db(session, block_id):
    q = Question(block_id=block_id, text="Q1", question_type="single_choice")
    session.add(q)
    await session.commit()
    await session.refresh(q)
    opt1 = AnswerOption(question_id=q.id, text="Correct", is_correct=True)
    opt2 = AnswerOption(question_id=q.id, text="Incorrect", is_correct=False)
    session.add_all([opt1, opt2])
    await session.commit()
    return q, opt1, opt2


# --- Create Question Tests ---


async def test_create_question_success(
    client: AsyncClient, session: AsyncSession, create_user
):
    user = await create_user("admin@test.com", is_superuser=True, role="administrator")
    c = await create_course_db(session, user.id)
    b = await create_block_db(session, c.id)

    await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@test.com", "password": "Password12345!"},
    )

    response = await client.post(
        f"/api/v1/test/blocks/{b.id}/questions",
        json={
            "text": "What is 2+2?",
            "question_type": "single_choice",
            "order_index": 0,
            "options": [
                {"text": "3", "is_correct": False},
                {"text": "4", "is_correct": True},
            ],
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["text"] == "What is 2+2?"
    assert len(data["options"]) == 2


async def test_create_question_user_forbidden(
    client: AsyncClient, session: AsyncSession, create_user
):
    admin = await create_user("admin@t.com", is_superuser=True, role="administrator")
    user = await create_user("user@t.com", is_superuser=False)
    c = await create_course_db(session, admin.id)
    b = await create_block_db(session, c.id)

    await client.post(
        "/api/v1/auth/login",
        data={"username": "user@t.com", "password": "Password12345!"},
    )

    response = await client.post(
        f"/api/v1/test/blocks/{b.id}/questions",
        json={"text": "Hacked", "question_type": "free_text", "order_index": 0},
    )
    assert response.status_code == 403


async def test_create_question_unauth(
    client: AsyncClient, session: AsyncSession, create_user
):
    admin = await create_user(
        "admin@unauth.com", is_superuser=True, role="administrator"
    )
    c = await create_course_db(session, admin.id)
    b = await create_block_db(session, c.id)

    response = await client.post(
        f"/api/v1/test/blocks/{b.id}/questions",
        json={"text": "Anon", "question_type": "free_text", "order_index": 0},
    )
    assert response.status_code == 401


async def test_create_question_block_not_found(client: AsyncClient, create_user):
    await create_user("admin@qnf.com", is_superuser=True, role="administrator")
    await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@qnf.com", "password": "Password12345!"},
    )

    response = await client.post(
        f"/api/v1/test/blocks/{uuid.uuid4()}/questions",
        json={"text": "Ghost", "question_type": "free_text", "order_index": 0},
    )
    assert response.status_code == 404


async def test_create_question_invalid_data(
    client: AsyncClient, session: AsyncSession, create_user
):
    user = await create_user("admin@qval.com", is_superuser=True, role="administrator")
    c = await create_course_db(session, user.id)
    b = await create_block_db(session, c.id)

    await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@qval.com", "password": "Password12345!"},
    )

    response = await client.post(
        f"/api/v1/test/blocks/{b.id}/questions", json={"text": "No type"}
    )
    assert response.status_code == 422


# --- Update Question Tests ---


async def test_update_question_success(
    client: AsyncClient, session: AsyncSession, create_user
):
    user = await create_user("admin@upq.com", is_superuser=True, role="administrator")
    c = await create_course_db(session, user.id)
    b = await create_block_db(session, c.id)
    q = await create_question_db(session, b.id)

    await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@upq.com", "password": "Password12345!"},
    )

    response = await client.put(
        f"/api/v1/test/questions/{q.id}",
        json={"text": "Updated Question"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["text"] == "Updated Question"


async def test_update_question_user_forbidden(
    client: AsyncClient, session: AsyncSession, create_user
):
    admin = await create_user(
        "admin@upqf.com", is_superuser=True, role="administrator"
    )
    user = await create_user("user@upqf.com", is_superuser=False)
    c = await create_course_db(session, admin.id)
    b = await create_block_db(session, c.id)
    q = await create_question_db(session, b.id)

    await client.post(
        "/api/v1/auth/login",
        data={"username": "user@upqf.com", "password": "Password12345!"},
    )

    response = await client.put(
        f"/api/v1/test/questions/{q.id}",
        json={"text": "Hacked"},
    )
    assert response.status_code == 403


async def test_update_question_not_found(
    client: AsyncClient, session: AsyncSession, create_user
):
    await create_user("admin@upqnf.com", is_superuser=True, role="administrator")

    await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@upqnf.com", "password": "Password12345!"},
    )

    response = await client.put(
        f"/api/v1/test/questions/{uuid.uuid4()}",
        json={"text": "Ghost"},
    )
    assert response.status_code == 404


# --- Delete Question Tests ---


async def test_delete_question_success(
    client: AsyncClient, session: AsyncSession, create_user
):
    user = await create_user("admin@delq.com", is_superuser=True, role="administrator")
    c = await create_course_db(session, user.id)
    b = await create_block_db(session, c.id)
    q = await create_question_db(session, b.id)

    await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@delq.com", "password": "Password12345!"},
    )

    response = await client.delete(f"/api/v1/test/questions/{q.id}")
    assert response.status_code == 204


async def test_delete_question_user_forbidden(
    client: AsyncClient, session: AsyncSession, create_user
):
    admin = await create_user(
        "admin@delqf.com", is_superuser=True, role="administrator"
    )
    user = await create_user("user@delqf.com", is_superuser=False)
    c = await create_course_db(session, admin.id)
    b = await create_block_db(session, c.id)
    q = await create_question_db(session, b.id)

    await client.post(
        "/api/v1/auth/login",
        data={"username": "user@delqf.com", "password": "Password12345!"},
    )

    response = await client.delete(f"/api/v1/test/questions/{q.id}")
    assert response.status_code == 403


async def test_delete_question_not_found(
    client: AsyncClient, session: AsyncSession, create_user
):
    await create_user("admin@delqnf.com", is_superuser=True, role="administrator")
    await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@delqnf.com", "password": "Password12345!"},
    )

    response = await client.delete(f"/api/v1/test/questions/{uuid.uuid4()}")
    assert response.status_code == 404


# --- List Questions Tests ---


async def test_list_questions_admin_success(
    client: AsyncClient, session: AsyncSession, create_user
):
    user = await create_user(
        "admin@listq.com", is_superuser=True, role="administrator"
    )
    c = await create_course_db(session, user.id)
    b = await create_block_db(session, c.id)
    await create_question_db(session, b.id)

    await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@listq.com", "password": "Password12345!"},
    )

    response = await client.get(f"/api/v1/test/blocks/{b.id}/questions")
    assert response.status_code == 200
    assert len(response.json()) == 1


async def test_list_questions_user_success(
    client: AsyncClient, session: AsyncSession, create_user
):
    admin = await create_user(
        "admin@listqu.com", is_superuser=True, role="administrator"
    )
    user = await create_user("user@listqu.com", is_superuser=False)
    c = await create_course_db(session, admin.id)
    b = await create_block_db(session, c.id)
    await create_question_db(session, b.id)

    await client.post(
        "/api/v1/auth/login",
        data={"username": "user@listqu.com", "password": "Password12345!"},
    )

    response = await client.get(f"/api/v1/test/blocks/{b.id}/questions")
    assert response.status_code == 200
    assert len(response.json()) == 1


async def test_list_questions_block_not_found(
    client: AsyncClient, session: AsyncSession, create_user
):
    user = await create_user("user@listqnf.com", is_superuser=False)
    await client.post(
        "/api/v1/auth/login",
        data={"username": "user@listqnf.com", "password": "Password12345!"},
    )
    response = await client.get(f"/api/v1/test/blocks/{uuid.uuid4()}/questions")
    assert response.status_code == 404


async def test_list_questions_empty(
    client: AsyncClient, session: AsyncSession, create_user
):
    user = await create_user(
        "admin@listqe.com", is_superuser=True, role="administrator"
    )
    c = await create_course_db(session, user.id)
    b = await create_block_db(session, c.id)

    await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@listqe.com", "password": "Password12345!"},
    )

    response = await client.get(f"/api/v1/test/blocks/{b.id}/questions")
    assert response.status_code == 200
    assert response.json() == []


# --- Submit Test Tests ---


async def test_submit_test_success(
    client: AsyncClient, session: AsyncSession, create_user
):
    admin = await create_user(
        "admin@subt.com", is_superuser=True, role="administrator"
    )
    user = await create_user("user@subt.com", is_superuser=False)
    c = await create_course_db(session, admin.id)
    b = await create_block_db(session, c.id)

    await client.post(
        "/api/v1/auth/login",
        data={"username": "user@subt.com", "password": "Password12345!"},
    )

    response = await client.post(
        f"/api/v1/test/blocks/{b.id}/submit",
        json={"answers": []},
    )
    assert response.status_code == 200


async def test_submit_test_block_not_found(
    client: AsyncClient, session: AsyncSession, create_user
):
    user = await create_user("user@subtnf.com", is_superuser=False)
    await client.post(
        "/api/v1/auth/login",
        data={"username": "user@subtnf.com", "password": "Password12345!"},
    )
    response = await client.post(
        f"/api/v1/test/blocks/{uuid.uuid4()}/submit", json={"answers": []}
    )
    assert response.status_code == 404


async def test_submit_test_not_a_test_block(
    client: AsyncClient, session: AsyncSession, create_user
):
    admin = await create_user(
        "admin@subtnt.com", is_superuser=True, role="administrator"
    )
    user = await create_user("user@subtnt.com", is_superuser=False)
    c = await create_course_db(session, admin.id)
    b = await create_block_db(session, c.id, btype=BlockType.lesson)

    await client.post(
        "/api/v1/auth/login",
        data={"username": "user@subtnt.com", "password": "Password12345!"},
    )

    response = await client.post(
        f"/api/v1/test/blocks/{b.id}/submit", json={"answers": []}
    )
    assert response.status_code == 400


# --- Get Submission Tests ---


async def test_get_submission_success(
    client: AsyncClient, session: AsyncSession, create_user
):
    admin = await create_user(
        "admin@getsub.com", is_superuser=True, role="administrator"
    )
    user = await create_user("user@getsub.com", is_superuser=False)
    c = await create_course_db(session, admin.id)
    b = await create_block_db(session, c.id)

    await client.post(
        "/api/v1/auth/login",
        data={"username": "user@getsub.com", "password": "Password12345!"},
    )

    sub_res = await client.post(
        f"/api/v1/test/blocks/{b.id}/submit",
        json={"answers": []},
    )
    submission_id = sub_res.json()["id"]

    response = await client.get(f"/api/v1/test/submissions/{submission_id}")
    assert response.status_code == 200
    assert response.json()["id"] == submission_id


async def test_get_submission_admin_success(
    client: AsyncClient, session: AsyncSession, create_user
):
    admin = await create_user(
        "admin@getsuba.com", is_superuser=True, role="administrator"
    )
    user = await create_user("user@getsuba.com", is_superuser=False)
    c = await create_course_db(session, admin.id)
    b = await create_block_db(session, c.id)

    await client.post(
        "/api/v1/auth/login",
        data={"username": "user@getsuba.com", "password": "Password12345!"},
    )
    sub_res = await client.post(
        f"/api/v1/test/blocks/{b.id}/submit",
        json={"answers": []},
    )
    submission_id = sub_res.json()["id"]

    await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@getsuba.com", "password": "Password12345!"},
    )

    response = await client.get(f"/api/v1/test/submissions/{submission_id}")
    assert response.status_code == 200
    assert response.json()["id"] == submission_id


async def test_get_submission_forbidden(
    client: AsyncClient, session: AsyncSession, create_user
):
    admin = await create_user(
        "admin@getsubf.com", is_superuser=True, role="administrator"
    )
    user1 = await create_user("user1@getsubf.com", is_superuser=False)
    user2 = await create_user("user2@getsubf.com", is_superuser=False)
    c = await create_course_db(session, admin.id)
    b = await create_block_db(session, c.id)

    await client.post(
        "/api/v1/auth/login",
        data={"username": "user1@getsubf.com", "password": "Password12345!"},
    )
    sub_res = await client.post(
        f"/api/v1/test/blocks/{b.id}/submit",
        json={"answers": []},
    )
    submission_id = sub_res.json()["id"]

    await client.post(
        "/api/v1/auth/login",
        data={"username": "user2@getsubf.com", "password": "Password12345!"},
    )
    response = await client.get(f"/api/v1/test/submissions/{submission_id}")
    assert response.status_code == 403


async def test_get_submission_not_found(
    client: AsyncClient, session: AsyncSession, create_user
):
    user = await create_user("user@getsubnf.com", is_superuser=False)
    await client.post(
        "/api/v1/auth/login",
        data={"username": "user@getsubnf.com", "password": "Password12345!"},
    )
    response = await client.get(f"/api/v1/test/submissions/{uuid.uuid4()}")
    assert response.status_code == 404


# --- List Submissions Tests ---


async def test_list_submissions_success(
    client: AsyncClient, session: AsyncSession, create_user
):
    admin = await create_user(
        "admin@listsub.com", is_superuser=True, role="administrator"
    )
    user = await create_user("user@listsub.com", is_superuser=False)
    c = await create_course_db(session, admin.id)
    b = await create_block_db(session, c.id)

    await client.post(
        "/api/v1/auth/login",
        data={"username": "user@listsub.com", "password": "Password12345!"},
    )
    await client.post(
        f"/api/v1/test/blocks/{b.id}/submit",
        json={"answers": []},
    )

    await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@listsub.com", "password": "Password12345!"},
    )

    response = await client.get(f"/api/v1/test/blocks/{b.id}/submissions")
    assert response.status_code == 200
    assert len(response.json()) == 1


async def test_list_submissions_forbidden(
    client: AsyncClient, session: AsyncSession, create_user
):
    admin = await create_user(
        "admin@listsubf.com", is_superuser=True, role="administrator"
    )
    user = await create_user("user@listsubf.com", is_superuser=False)
    c = await create_course_db(session, admin.id)
    b = await create_block_db(session, c.id)

    await client.post(
        "/api/v1/auth/login",
        data={"username": "user@listsubf.com", "password": "Password12345!"},
    )

    response = await client.get(f"/api/v1/test/blocks/{b.id}/submissions")
    assert response.status_code == 403


# --- Grade Submission Tests ---


async def test_grade_submission_success(
    client: AsyncClient, session: AsyncSession, create_user
):
    admin = await create_user(
        "admin@gradesub.com", is_superuser=True, role="administrator"
    )
    user = await create_user("user@gradesub.com", is_superuser=False)
    c = await create_course_db(session, admin.id)
    b = await create_block_db(session, c.id, btype=BlockType.manual_test)
    q = await create_question_db(session, b.id, qtype="free_text")

    await client.post(
        "/api/v1/auth/login",
        data={"username": "user@gradesub.com", "password": "Password12345!"},
    )
    sub_res = await client.post(
        f"/api/v1/test/blocks/{b.id}/submit",
        json={"answers": [{"question_id": str(q.id), "text_answer": "My answer"}]},
    )
    submission_id = sub_res.json()["id"]

    await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@gradesub.com", "password": "Password12345!"},
    )

    response = await client.post(
        f"/api/v1/test/submissions/{submission_id}/grade",
        json={"score": 10, "admin_comment": "Good job!"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["score"] == 10
    assert data["is_graded"] is True


async def test_grade_submission_forbidden(
    client: AsyncClient, session: AsyncSession, create_user
):
    admin = await create_user(
        "admin@gradesubf.com", is_superuser=True, role="administrator"
    )
    user = await create_user("user@gradesubf.com", is_superuser=False)
    c = await create_course_db(session, admin.id)
    b = await create_block_db(session, c.id)

    await client.post(
        "/api/v1/auth/login",
        data={"username": "user@gradesubf.com", "password": "Password12345!"},
    )
    sub_res = await client.post(
        f"/api/v1/test/blocks/{b.id}/submit",
        json={"answers": []},
    )
    submission_id = sub_res.json()["id"]

    response = await client.post(
        f"/api/v1/test/submissions/{submission_id}/grade",
        json={"score": 10},
    )
    assert response.status_code == 403


async def test_grade_submission_not_found(
    client: AsyncClient, session: AsyncSession, create_user
):
    admin = await create_user(
        "admin@gradesubnf.com", is_superuser=True, role="administrator"
    )
    await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@gradesubnf.com", "password": "Password12345!"},
    )
    response = await client.post(
        f"/api/v1/test/submissions/{uuid.uuid4()}/grade",
        json={"score": 10},
    )
    assert response.status_code == 404


async def test_auto_grade_submission(
    client: AsyncClient, session: AsyncSession, create_user
):
    admin = await create_user(
        "admin@autograde.com", is_superuser=True, role="administrator"
    )
    user = await create_user("user@autograde.com", is_superuser=False)
    course = await create_course_db(session, admin.id)
    block = await create_block_db(session, course.id, btype=BlockType.auto_test)
    q, correct_opt, _ = await create_question_with_options_db(session, block.id)

    await client.post(
        "/api/v1/auth/login", data={"username": "user@autograde.com", "password": "Password12345!"}
    )

    submit_response = await client.post(
        f"/api/v1/test/blocks/{block.id}/submit",
        json={
            "answers": [
                {
                    "question_id": str(q.id),
                    "selected_answer_id": str(correct_opt.id),
                }
            ]
        },
    )
    assert submit_response.status_code == 200
    submission_data = submit_response.json()

    # Check if the submission was auto-graded correctly
    assert submission_data["is_graded"] is True
    assert submission_data["score"] == 1
    assert submission_data["max_score"] == 1


async def test_manual_grade_submission_flow(
    client: AsyncClient, session: AsyncSession, create_user
):
    admin = await create_user(
        "admin@manualgrade.com", is_superuser=True, role="administrator"
    )
    user = await create_user("user@manualgrade.com", is_superuser=False)
    course = await create_course_db(session, admin.id)
    block = await create_block_db(session, course.id, btype=BlockType.manual_test)
    q = await create_question_db(session, block.id, qtype="free_text")

    # User submits an answer
    await client.post(
        "/api/v1/auth/login", data={"username": "user@manualgrade.com", "password": "Password12345!"}
    )
    submit_response = await client.post(
        f"/api/v1/test/blocks/{block.id}/submit",
        json={
            "answers": [
                {"question_id": str(q.id), "text_answer": "It's complicated."}
            ]
        },
    )
    assert submit_response.status_code == 200
    submission_data = submit_response.json()
    submission_id = submission_data["id"]

    # Submission should not be graded yet
    assert submission_data["is_graded"] is False

    # Admin grades the submission
    await client.post(
        "/api/v1/auth/login", data={"username": "admin@manualgrade.com", "password": "Password12345!"}
    )
    grade_response = await client.post(
        f"/api/v1/test/submissions/{submission_id}/grade",
        json={"score": 5, "admin_comment": "Needs more detail."},
    )
    assert grade_response.status_code == 200
    graded_data = grade_response.json()

    assert graded_data["is_graded"] is True
    assert graded_data["score"] == 5
    assert graded_data["admin_comment"] == "Needs more detail."
