import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from core.models.course import Course
from core.models.block import Block, BlockType
from core.models.test import (
    AnswerOption,
    Question,
    QuestionType,
    TestSubmission,
    TestSubmissionQuestion,
)


@pytest.mark.anyio
async def test_questions_count_validation(client: AsyncClient, session: AsyncSession, create_user):
    admin = await create_user("adm_qc_val@test.com", is_superuser=True, role="administrator")
    await client.post("/api/v1/auth/login", data={"username": admin.email, "password": "Password12345!"})

    course = Course(id=uuid.uuid4(), title="QC Val Course", created_by=admin.id, is_published=True)
    session.add(course)
    await session.commit()

    # Add lesson block at index 0 first to satisfy block sequence
    resp_l = await client.post(
        f"/api/v1/courses/{course.id}/blocks/",
        json={
            "title": "Lesson 1",
            "block_type": "lesson",
            "order_index": 0,
            "text_content": "Lesson text",
        },
    )
    assert resp_l.status_code == 201

    # Test invalid values: negative, 0, > 1000
    for invalid_val in [-5, 0, 1001]:
        resp = await client.post(
            f"/api/v1/courses/{course.id}/blocks/",
            json={
                "title": "Invalid Block",
                "block_type": "auto_test",
                "order_index": 1,
                "questions_count": invalid_val,
            },
        )
        assert resp.status_code == 422

    # Test valid value: 5
    resp_valid = await client.post(
        f"/api/v1/courses/{course.id}/blocks/",
        json={
            "title": "Valid Block",
            "block_type": "auto_test",
            "order_index": 1,
            "questions_count": 5,
        },
    )
    assert resp_valid.status_code == 201
    assert resp_valid.json()["questions_count"] == 5


@pytest.mark.anyio
async def test_random_questions_limit_and_submission(client: AsyncClient, session: AsyncSession, create_user):
    admin = await create_user("adm_qc_rnd@test.com", is_superuser=True, role="administrator")
    course = Course(id=uuid.uuid4(), title="QC Rnd Course", created_by=admin.id, is_published=True)
    session.add(course)
    await session.flush()

    # Create a test block with questions_count = 3
    block = Block(
        id=uuid.uuid4(),
        course_id=course.id,
        title="Test 10 Qs",
        block_type=BlockType.auto_test,
        order_index=1,
        questions_count=3,
    )
    session.add(block)
    await session.flush()

    # Add 10 questions to the block
    questions = []
    options = []
    for i in range(10):
        q = Question(id=uuid.uuid4(), block_id=block.id, text=f"Question {i+1}", question_type=QuestionType.single_choice, order_index=i+1)
        session.add(q)
        await session.flush()
        opt = AnswerOption(id=uuid.uuid4(), question_id=q.id, text=f"Correct Opt {i+1}", is_correct=True)
        session.add(opt)
        questions.append(q)
        options.append(opt)

    await session.commit()

    # Student login
    student = await create_user("student_qc_rnd@test.com")
    await client.post("/api/v1/auth/login", data={"username": student.email, "password": "Password12345!"})

    # Student requests questions: should get exactly 3 random questions
    resp_student = await client.get(f"/api/v1/tests/blocks/{block.id}/questions")
    assert resp_student.status_code == 200
    student_qs = resp_student.json()
    assert len(student_qs) == 3

    # Admin login
    await client.post("/api/v1/auth/login", data={"username": admin.email, "password": "Password12345!"})

    # Admin requests questions: should get ALL 10 questions
    resp_admin = await client.get(f"/api/v1/tests/blocks/{block.id}/questions")
    assert resp_admin.status_code == 200
    admin_qs = resp_admin.json()
    assert len(admin_qs) == 10

    # Student submits answers to the 3 questions received
    await client.post("/api/v1/auth/login", data={"username": student.email, "password": "Password12345!"})

    too_many_answers = [
        {
            "question_id": str(question.id),
            "selected_answer_id": str(option.id),
        }
        for question, option in zip(questions[:4], options[:4])
    ]
    too_many_response = await client.post(
        f"/api/v1/tests/blocks/{block.id}/submit",
        json={"answers": too_many_answers},
    )
    assert too_many_response.status_code == 400

    answers_payload = []
    for q_data in student_qs:
        q_id = q_data["id"]
        # Find correct option ID
        opt_id = next(opt.id for opt in options if str(opt.question_id) == q_id)
        answers_payload.append({"question_id": q_id, "selected_answer_id": str(opt_id)})

    sub_resp = await client.post(
        f"/api/v1/tests/blocks/{block.id}/submit",
        json={"answers": answers_payload},
    )
    assert sub_resp.status_code == 200
    sub_data = sub_resp.json()
    assert sub_data["max_score"] == 3.0
    assert sub_data["score"] == 3.0
    assert sub_data["is_graded"] is True

    results_response = await client.get(
        f"/api/v1/courses/{course.id}/blocks/{block.id}/test-results"
    )
    assert results_response.status_code == 200
    results = results_response.json()
    assert results["total_score"] == 3.0
    assert results["max_score"] == 3.0
    assert len(results["questions"]) == 3
    assert results["correct_count"] == 3
    assert results["incorrect_count"] == 0
    assert results["completed_at"] is not None

    history_response = await client.get(
        f"/api/v1/courses/{course.id}/blocks/{block.id}/submission-history"
    )
    assert history_response.status_code == 200
    history_submission = history_response.json()["submissions"][0]
    assert history_submission["max_score"] == 3.0
    assert len(history_submission["questions"]) == 3

    block_response = await client.get(
        f"/api/v1/courses/{course.id}/blocks/{block.id}"
    )
    assert block_response.status_code == 200
    assert block_response.json()["progress"]["total"] == 3


@pytest.mark.anyio
async def test_attempt_keeps_its_question_selection_and_grades_only_it(
    client: AsyncClient,
    session: AsyncSession,
    create_user,
    monkeypatch,
):
    admin = await create_user(
        "attempt_selection_admin@test.com",
        is_superuser=True,
        role="administrator",
    )
    student = await create_user("attempt_selection_student@test.com")
    course = Course(
        id=uuid.uuid4(),
        title="Attempt selection course",
        created_by=admin.id,
        is_published=True,
    )
    block = Block(
        id=uuid.uuid4(),
        course_id=course.id,
        title="Mixed question bank",
        block_type=BlockType.mixed_test,
        order_index=1,
        questions_count=3,
    )
    session.add_all([course, block])
    await session.flush()

    questions = []
    options = []
    for index in range(3):
        question = Question(
            id=uuid.uuid4(),
            block_id=block.id,
            text=f"Choice question {index + 1}",
            question_type=QuestionType.single_choice,
            order_index=index,
        )
        option = AnswerOption(
            id=uuid.uuid4(),
            question_id=question.id,
            text="Correct",
            is_correct=True,
        )
        session.add_all([question, option])
        questions.append(question)
        options.append(option)

    unassigned_text_question = Question(
        id=uuid.uuid4(),
        block_id=block.id,
        text="Unassigned text question",
        question_type=QuestionType.free_text,
        order_index=3,
    )
    session.add(unassigned_text_question)
    await session.commit()

    import random

    monkeypatch.setattr(random, "sample", lambda _population, _limit: questions)
    await client.post(
        "/api/v1/auth/login",
        data={"username": student.email, "password": "Password12345!"},
    )

    first_questions_response = await client.get(
        f"/api/v1/tests/blocks/{block.id}/questions"
    )
    assert first_questions_response.status_code == 200
    assert {item["id"] for item in first_questions_response.json()} == {
        str(question.id) for question in questions
    }

    second_questions_response = await client.get(
        f"/api/v1/tests/blocks/{block.id}/questions"
    )
    assert second_questions_response.status_code == 200
    assert second_questions_response.json() == first_questions_response.json()

    attempt = await session.scalar(
        select(TestSubmission).where(
            TestSubmission.user_id == student.id,
            TestSubmission.block_id == block.id,
            TestSubmission.is_submitted.is_(False),
        )
    )
    assert attempt is not None
    assigned_question_ids = set(
        (
            await session.scalars(
                select(TestSubmissionQuestion.question_id).where(
                    TestSubmissionQuestion.submission_id == attempt.id
                )
            )
        ).all()
    )
    assert assigned_question_ids == {question.id for question in questions}

    unassigned_question_response = await client.post(
        f"/api/v1/tests/blocks/{block.id}/submit",
        json={
            "answers": [
                {
                    "question_id": str(unassigned_text_question.id),
                    "text_answer": "Not shown to the student",
                }
            ]
        },
    )
    assert unassigned_question_response.status_code == 400

    submitted_response = await client.post(
        f"/api/v1/tests/blocks/{block.id}/submit",
        json={
            "answers": [
                {
                    "question_id": str(question.id),
                    "selected_answer_id": str(option.id),
                }
                for question, option in zip(questions, options)
            ]
        },
    )
    assert submitted_response.status_code == 200
    assert submitted_response.json()["score"] == 3.0
    assert submitted_response.json()["max_score"] == 3.0
    assert submitted_response.json()["is_graded"] is True

    results_response = await client.get(
        f"/api/v1/courses/{course.id}/blocks/{block.id}/test-results"
    )
    assert results_response.status_code == 200
    assert len(results_response.json()["questions"]) == 3


@pytest.mark.anyio
async def test_default_questions_count_is_5(client: AsyncClient, session: AsyncSession, create_user):
    admin = await create_user("adm_qc_def@test.com", is_superuser=True, role="administrator")
    course = Course(id=uuid.uuid4(), title="QC Default Course", created_by=admin.id, is_published=True)
    session.add(course)
    await session.flush()

    # Block with questions_count = None
    block = Block(
        id=uuid.uuid4(),
        course_id=course.id,
        title="Test None Qs",
        block_type=BlockType.auto_test,
        order_index=1,
        questions_count=None,
    )
    session.add(block)
    await session.flush()

    # Add 10 questions to the block
    for i in range(10):
        q = Question(id=uuid.uuid4(), block_id=block.id, text=f"Q{i+1}", question_type=QuestionType.single_choice, order_index=i+1)
        session.add(q)
        await session.flush()
        opt = AnswerOption(id=uuid.uuid4(), question_id=q.id, text=f"Opt {i+1}", is_correct=True)
        session.add(opt)

    await session.commit()

    student = await create_user("student_qc_def@test.com")
    await client.post("/api/v1/auth/login", data={"username": student.email, "password": "Password12345!"})

    resp = await client.get(f"/api/v1/tests/blocks/{block.id}/questions")
    assert resp.status_code == 200
    qs = resp.json()
    assert len(qs) == 5
