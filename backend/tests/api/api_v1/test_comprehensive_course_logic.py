import uuid
import pytest
from datetime import datetime, timezone
from httpx import AsyncClient
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from core.models.user import User
from core.models.course import Course
from core.models.block import Block, BlockType
from core.models.test import Question, QuestionType, AnswerOption, TestSubmission, TestAnswer
from core.models.progress import UserBlockProgress



async def _create_user(session, email, is_superuser=False, role="user"):
    from fastapi_users.password import PasswordHelper
    ph = PasswordHelper()
    u = User(
        id=uuid.uuid4(),
        email=email,
        hashed_password=ph.hash("Password12345!"),
        is_active=True,
        is_superuser=is_superuser,
        is_verified=True,
        role=role,
        fullname=f"User {email}"
    )
    session.add(u)
    await session.flush()
    return u

async def _create_course_with_stages(session: AsyncSession, admin_id: uuid.UUID, n_stages: int):
    course = Course(id=uuid.uuid4(), title=f"Course {n_stages} Stages", created_by=admin_id, is_published=True)
    session.add(course)
    await session.flush()
    
    blocks = []
    questions = []
    options = []
    
    for i in range(n_stages):

        l = Block(id=uuid.uuid4(), course_id=course.id, title=f"L{i+1}", block_type=BlockType.lesson, order_index=i*2 + 1)

        t = Block(id=uuid.uuid4(), course_id=course.id, title=f"T{i+1}", block_type=BlockType.auto_test, order_index=i*2 + 2)
        blocks.extend([l, t])
        

        q = Question(id=uuid.uuid4(), block_id=t.id, text=f"Q{i+1}", question_type=QuestionType.single_choice, order_index=1)
        questions.append(q)
        o = AnswerOption(id=uuid.uuid4(), question_id=q.id, text="Correct", is_correct=True, order_index=1)
        options.append(o)
        
    for b in blocks: session.add(b)
    await session.flush()
    for q in questions: session.add(q)
    await session.flush()
    for o in options: session.add(o)
    await session.flush()
    
    await session.commit()
    return course, blocks, questions, options

async def _enroll_user(session: AsyncSession, user_id: uuid.UUID, course_id: uuid.UUID):
    from core.models.course import CourseEnrollment
    e = CourseEnrollment(user_id=user_id, course_id=course_id)
    session.add(e)
    await session.commit()
    return e



@pytest.mark.anyio
class TestUnlockingLogic:
    
    async def test_guest_sees_only_stage_1(self, client: AsyncClient, session: AsyncSession, create_user):
        admin = await _create_user(session, "adm1@test.com", is_superuser=True, role="administrator")
        course, blocks, _, _ = await _create_course_with_stages(session, admin.id, 3)
        
        resp = await client.get(f"/api/v1/courses/{course.id}/blocks/")
        data = resp.json()
        assert len(data["blocks"]) == 2
        assert data["all_blocks"] == 6
        assert data["all_stages"] == 3

    async def test_new_user_sees_only_stage_1(self, client: AsyncClient, session: AsyncSession, create_user):
        admin = await _create_user(session, "adm2@test.com", is_superuser=True, role="administrator")
        course, blocks, _, _ = await _create_course_with_stages(session, admin.id, 3)
        
        user = await _create_user(session, "u2@test.com")
        resp = await client.post("/api/v1/auth/login", data={"username": "u2@test.com", "password": "Password12345!"})
        
        resp = await client.get(f"/api/v1/courses/{course.id}/blocks/")
        assert len(resp.json()["blocks"]) == 2

    async def test_complete_lesson_only_unlocks_nothing(self, client: AsyncClient, session: AsyncSession):
        admin = await _create_user(session, "adm3@test.com", is_superuser=True, role="administrator")
        course, blocks, _, _ = await _create_course_with_stages(session, admin.id, 2)
        user = await _create_user(session, "u3@test.com")
        

        p = UserBlockProgress(id=uuid.uuid4(), user_id=user.id, block_id=blocks[0].id, is_completed=True)
        session.add(p)
        await session.commit()
        
        await client.post("/api/v1/auth/login", data={"username": "u3@test.com", "password": "Password12345!"})
        resp = await client.get(f"/api/v1/courses/{course.id}/blocks/")
        assert len(resp.json()["blocks"]) == 2

    async def test_complete_stage_1_unlocks_stage_2(self, client: AsyncClient, session: AsyncSession):
        admin = await _create_user(session, "adm4@test.com", is_superuser=True, role="administrator")
        course, blocks, _, _ = await _create_course_with_stages(session, admin.id, 3)
        user = await _create_user(session, "u4@test.com")
        

        for b in blocks[:2]:
            session.add(UserBlockProgress(id=uuid.uuid4(), user_id=user.id, block_id=b.id, is_completed=True))
        await session.commit()
        
        await client.post("/api/v1/auth/login", data={"username": "u4@test.com", "password": "Password12345!"})
        resp = await client.get(f"/api/v1/courses/{course.id}/blocks/")
        assert len(resp.json()["blocks"]) == 4

    async def test_full_completion_sees_everything(self, client: AsyncClient, session: AsyncSession):
        admin = await _create_user(session, "adm5@test.com", is_superuser=True, role="administrator")
        course, blocks, _, _ = await _create_course_with_stages(session, admin.id, 3)
        user = await _create_user(session, "u5@test.com")
        
        for b in blocks:
            session.add(UserBlockProgress(id=uuid.uuid4(), user_id=user.id, block_id=b.id, is_completed=True))
        await session.commit()
        
        await client.post("/api/v1/auth/login", data={"username": "u5@test.com", "password": "Password12345!"})
        resp = await client.get(f"/api/v1/courses/{course.id}/blocks/")
        assert len(resp.json()["blocks"]) == 6

    async def test_odd_number_of_blocks(self, client: AsyncClient, session: AsyncSession):
        admin = await _create_user(session, "adm6@test.com", is_superuser=True, role="administrator")
        course = Course(id=uuid.uuid4(), title="Odd Course", created_by=admin.id, is_published=True)
        session.add(course)
        b1 = Block(id=uuid.uuid4(), course_id=course.id, block_type=BlockType.lesson, order_index=1, title="L1")
        b2 = Block(id=uuid.uuid4(), course_id=course.id, block_type=BlockType.auto_test, order_index=2, title="T1")
        b3 = Block(id=uuid.uuid4(), course_id=course.id, block_type=BlockType.lesson, order_index=3, title="L2")
        session.add_all([b1, b2, b3])
        await session.commit()
        
        resp = await client.get(f"/api/v1/courses/{course.id}/blocks/")
        data = resp.json()
        assert data["all_stages"] == 2
        assert len(data["blocks"]) == 2
        

        user = await _create_user(session, "u6@test.com")
        session.add(UserBlockProgress(user_id=user.id, block_id=b1.id, is_completed=True))
        session.add(UserBlockProgress(user_id=user.id, block_id=b2.id, is_completed=True))
        await session.commit()
        
        await client.post("/api/v1/auth/login", data={"username": "u6@test.com", "password": "Password12345!"})
        resp = await client.get(f"/api/v1/courses/{course.id}/blocks/")
        assert len(resp.json()["blocks"]) == 3



@pytest.mark.anyio
class TestGradingLogic:
    
    async def _setup_multichoice(self, session, admin_id):
        course = Course(id=uuid.uuid4(), created_by=admin_id, is_published=True, title="MCQ Course")
        session.add(course)
        block = Block(id=uuid.uuid4(), course_id=course.id, block_type=BlockType.auto_test, title="MCQ Test")
        session.add(block)
        q1 = Question(id=uuid.uuid4(), block_id=block.id, question_type=QuestionType.multiple_choice, text="Q1")
        session.add(q1)
        o1 = AnswerOption(id=uuid.uuid4(), question_id=q1.id, is_correct=True, text="A")
        o2 = AnswerOption(id=uuid.uuid4(), question_id=q1.id, is_correct=True, text="B")
        o3 = AnswerOption(id=uuid.uuid4(), question_id=q1.id, is_correct=False, text="C")
        session.add_all([o1, o2, o3])
        await session.commit()
        return block, q1, [o1, o2, o3]

    async def test_mcq_full_match(self, client, session, create_user):
        admin = await _create_user(session, "admma@test.com", is_superuser=True)
        block, q1, opts = await self._setup_multichoice(session, admin.id)
        user = await _create_user(session, "student_mc1@test.com")
        await client.post("/api/v1/auth/login", data={"username": user.email, "password": "Password12345!"})
        
        payload = {"answers": [{"question_id": str(q1.id), "selected_answer_id": str(opts[0].id)},
                               {"question_id": str(q1.id), "selected_answer_id": str(opts[1].id)}]}
        resp = await client.post(f"/api/v1/tests/blocks/{block.id}/submit", json=payload)
        assert resp.json()["score"] == 1

    async def test_mcq_partial_match_is_zero(self, client, session, create_user):
        admin = await _create_user(session, "admmb@test.com", is_superuser=True)
        block, q1, opts = await self._setup_multichoice(session, admin.id)
        user = await _create_user(session, "student_mc2@test.com")
        await client.post("/api/v1/auth/login", data={"username": user.email, "password": "Password12345!"})
        
        payload = {"answers": [{"question_id": str(q1.id), "selected_answer_id": str(opts[0].id)}]}
        resp = await client.post(f"/api/v1/tests/blocks/{block.id}/submit", json=payload)
        assert resp.json()["score"] == 0

    async def test_mcq_over_selection_is_zero(self, client, session, create_user):
        admin = await _create_user(session, "admmc@test.com", is_superuser=True)
        block, q1, opts = await self._setup_multichoice(session, admin.id)
        user = await _create_user(session, "student_mc3@test.com")
        await client.post("/api/v1/auth/login", data={"username": user.email, "password": "Password12345!"})
        
        payload = {"answers": [{"question_id": str(q1.id), "selected_answer_id": str(opts[0].id)},
                               {"question_id": str(q1.id), "selected_answer_id": str(opts[1].id)},
                               {"question_id": str(q1.id), "selected_answer_id": str(opts[2].id)}]}
        resp = await client.post(f"/api/v1/tests/blocks/{block.id}/submit", json=payload)
        assert resp.json()["score"] == 0

    async def test_duplicate_answers_in_payload(self, client, session):
        admin = await _create_user(session, "admmd@test.com", is_superuser=True)
        block, q1, opts = await self._setup_multichoice(session, admin.id)
        user = await _create_user(session, "student_mc4@test.com")
        await client.post("/api/v1/auth/login", data={"username": user.email, "password": "Password12345!"})
        

        payload = {"answers": [{"question_id": str(q1.id), "selected_answer_id": str(opts[0].id)},
                               {"question_id": str(q1.id), "selected_answer_id": str(opts[0].id)}]}
        resp = await client.post(f"/api/v1/tests/blocks/{block.id}/submit", json=payload)

        assert resp.json()["score"] == 0

    async def test_empty_answers_is_zero(self, client, session):
        admin = await _create_user(session, "admme@test.com", is_superuser=True)
        block, q1, opts = await self._setup_multichoice(session, admin.id)
        user = await _create_user(session, "student_mc5@test.com")
        await client.post("/api/v1/auth/login", data={"username": user.email, "password": "Password12345!"})
        
        resp = await client.post(f"/api/v1/tests/blocks/{block.id}/submit", json={"answers": []})
        assert resp.json()["score"] == 0



@pytest.mark.anyio
class TestStatsProgress:
    
    async def test_percentage_calculation(self, client, session):
        admin = await _create_user(session, "admstat1@test.com", is_superuser=True)
        course, blocks, _, _ = await _create_course_with_stages(session, admin.id, 2)
        user = await _create_user(session, "stat_u1@test.com")
        await _enroll_user(session, user.id, course.id)
        

        session.add(UserBlockProgress(user_id=user.id, block_id=blocks[0].id, is_completed=True))
        session.add(UserBlockProgress(user_id=user.id, block_id=blocks[1].id, is_completed=True))
        await session.commit()
        
        await client.post("/api/v1/auth/login", data={"username": user.email, "password": "Password12345!"})
        resp = await client.get(f"/api/v1/courses/{course.id}/blocks/")
        data = resp.json()
        assert data["progress"]["percent"] == 50.0
        assert data["progress"]["completed"] == 1
        assert data["progress"]["total"] == 2

    async def test_all_blocks_constant_regardless_of_unlocking(self, client, session):
        admin = await _create_user(session, "admstat2@test.com", is_superuser=True)
        course, blocks, _, _ = await _create_course_with_stages(session, admin.id, 5)
        
        resp = await client.get(f"/api/v1/courses/{course.id}/blocks/")
        data = resp.json()
        assert data["all_blocks"] == 10
        assert len(data["blocks"]) == 2



@pytest.mark.anyio
class TestSecurityPermissions:
    
    async def test_cannot_submit_test_for_lesson_block(self, client, session):
        admin = await _create_user(session, "admsec1@test.com", is_superuser=True)
        course, blocks, _, _ = await _create_course_with_stages(session, admin.id, 1)
        user = await _create_user(session, "sec_u1@test.com")
        await client.post("/api/v1/auth/login", data={"username": user.email, "password": "Password12345!"})
        

        resp = await client.post(f"/api/v1/tests/blocks/{blocks[0].id}/submit", json={"answers": []})
        assert resp.status_code == 400
        assert "is not a test" in resp.json()["detail"]

    async def test_cannot_view_results_of_another_user(self, client, session, create_user):
        admin = await _create_user(session, "admsec2@test.com", is_superuser=True)
        course, blocks, _, _ = await _create_course_with_stages(session, admin.id, 1)
        u1 = await _create_user(session, "sec_u2@test.com")
        u2 = await _create_user(session, "sec_u3@test.com")
        

        s1 = TestSubmission(id=uuid.uuid4(), user_id=u1.id, block_id=blocks[1].id, score=1, max_score=1, is_graded=True)
        session.add(s1)
        await session.commit()
        

        await client.post("/api/v1/auth/login", data={"username": u2.email, "password": "Password12345!"})

        resp = await client.get(f"/api/v1/courses/{course.id}/blocks/{blocks[1].id}/test-results")
        assert resp.status_code == 404

    async def test_admin_pending_submissions_permission(self, client, session):
        admin = await _create_user(session, "admsec3@test.com", is_superuser=True, role="administrator")
        course, _, _, _ = await _create_course_with_stages(session, admin.id, 1)
        user = await _create_user(session, "sec_u4@test.com")
        

        await client.post("/api/v1/auth/login", data={"username": user.email, "password": "Password12345!"})
        resp = await client.get(f"/api/v1/tests/courses/{course.id}/pending-submissions")
        assert resp.status_code == 403
        



        await client.post("/api/v1/auth/login", data={"username": admin.email, "password": "Password12345!"})
        resp = await client.get(f"/api/v1/tests/courses/{course.id}/pending-submissions")
        assert resp.status_code == 200

    async def test_submit_with_invalid_uuids(self, client, session):
        admin = await _create_user(session, "admsec4@test.com", is_superuser=True)
        course, blocks, _, _ = await _create_course_with_stages(session, admin.id, 1)
        user = await _create_user(session, "sec_u5@test.com")
        await client.post("/api/v1/auth/login", data={"username": user.email, "password": "Password12345!"})
        

        payload = {"answers": [{"question_id": str(uuid.uuid4()), "selected_answer_id": str(uuid.uuid4())}]}
        resp = await client.post(f"/api/v1/tests/blocks/{blocks[1].id}/submit", json=payload)

        assert resp.status_code == 200
        assert resp.json()["score"] == 0

    async def test_submit_answers_from_different_block(self, client, session):
        admin = await _create_user(session, "admsec5@test.com", is_superuser=True)
        course, blocks, questions, options = await _create_course_with_stages(session, admin.id, 2)
        user = await _create_user(session, "sec_u6@test.com")
        await client.post("/api/v1/auth/login", data={"username": user.email, "password": "Password12345!"})
        

        payload = {"answers": [{"question_id": str(questions[0].id), "selected_answer_id": str(options[0].id)}]}
        resp = await client.post(f"/api/v1/tests/blocks/{blocks[3].id}/submit", json=payload)

        assert resp.json()["score"] == 0

    async def test_manual_test_result_excluded_from_counts(self, client, session):
        admin = await _create_user(session, "admfails1@test.com", is_superuser=True)
        course = Course(id=uuid.uuid4(), title="Manual Course", created_by=admin.id, is_published=True)
        session.add(course)
        b1 = Block(id=uuid.uuid4(), course_id=course.id, block_type=BlockType.manual_test, title="Manual Test")
        session.add(b1)

        q1 = Question(id=uuid.uuid4(), block_id=b1.id, text="Upload work", question_type=QuestionType.free_text)
        session.add(q1)
        await session.commit()
        
        user = await _create_user(session, "stat_u2_fail@test.com")
        await client.post("/api/v1/auth/login", data={"username": user.email, "password": "Password12345!"})
        

        await client.post(f"/api/v1/tests/blocks/{b1.id}/submit", json={"answers": [{"question_id": str(q1.id), "text_answer": "Done"}]})
        

        resp = await client.get(f"/api/v1/courses/{course.id}/blocks/{b1.id}/test-results")
        data = resp.json()
        assert data["correct_count"] == 0
        assert data["incorrect_count"] == 0

        assert data["questions"][0]["status"] == "Требует проверки"

    async def test_large_mcq_set(self, client, session):
        admin = await _create_user(session, "admfails2@test.com", is_superuser=True)
        course = Course(id=uuid.uuid4(), created_by=admin.id, is_published=True, title="Big MCQ")
        session.add(course)
        block = Block(id=uuid.uuid4(), course_id=course.id, block_type=BlockType.auto_test, title="Big Test")
        session.add(block)
        q1 = Question(id=uuid.uuid4(), block_id=block.id, question_type=QuestionType.multiple_choice, text="Q1")
        session.add(q1)
        opts = [AnswerOption(id=uuid.uuid4(), question_id=q1.id, is_correct=True, text=str(i)) for i in range(10)]
        for o in opts: session.add(o)
        await session.commit()
        
        user = await _create_user(session, "student_mc6_fail@test.com")
        await client.post("/api/v1/auth/login", data={"username": user.email, "password": "Password12345!"})
        
        payload = {"answers": [{"question_id": str(q1.id), "selected_answer_id": str(o.id)} for o in opts]}
        resp = await client.post(f"/api/v1/tests/blocks/{block.id}/submit", json=payload)
        assert resp.json()["score"] == 1

    async def test_stage_calculation_boundaries(self, client, session):
        admin = await _create_user(session, "admfails3@test.com", is_superuser=True)
        course = Course(id=uuid.uuid4(), title="5 Blocks Course", created_by=admin.id, is_published=True)
        session.add(course)
        blocks = []
        for i in range(5):
            bt = BlockType.lesson if i % 2 == 0 else BlockType.auto_test
            b = Block(id=uuid.uuid4(), course_id=course.id, order_index=i+1, title=str(i), block_type=bt)
            blocks.append(b)
            session.add(b)
        await session.commit()
        


        user = await _create_user(session, "stat_u_boundaries@test.com")
        for b in blocks:
             session.add(UserBlockProgress(user_id=user.id, block_id=b.id, is_completed=True))
        await session.commit()
        
        await client.post("/api/v1/auth/login", data={"username": user.email, "password": "Password12345!"})
        resp = await client.get(f"/api/v1/courses/{course.id}/blocks/")
        data = resp.json()
        assert data["all_stages"] == 3
        assert len(data["blocks"]) == 5
        assert data["blocks"][0]["stage"] == 1
        assert data["blocks"][4]["stage"] == 3

    async def test_root_progress_completed_stages_only(self, client, session):
        admin = await _create_user(session, "admfails4@test.com", is_superuser=True)
        course, blocks, _, _ = await _create_course_with_stages(session, admin.id, 2)
        user = await _create_user(session, "stat_u3_fail@test.com")
        await _enroll_user(session, user.id, course.id)
        
        await client.post("/api/v1/auth/login", data={"username": user.email, "password": "Password12345!"})
        

        resp = await client.get(f"/api/v1/courses/{course.id}/blocks/")
        assert resp.json()["progress"]["completed"] == 0
        

        session.add(UserBlockProgress(user_id=user.id, block_id=blocks[0].id, is_completed=True))
        await session.commit()
        resp = await client.get(f"/api/v1/courses/{course.id}/blocks/")
        assert resp.json()["progress"]["completed"] == 0
        

        session.add(UserBlockProgress(user_id=user.id, block_id=blocks[1].id, is_completed=True))
        await session.commit()
        resp = await client.get(f"/api/v1/courses/{course.id}/blocks/")
        assert resp.json()["progress"]["completed"] == 1

    async def test_next_block_id_navigation_across_stages(self, client, session):
        admin = await _create_user(session, "admstat6@test.com", is_superuser=True)
        course, blocks, _, _ = await _create_course_with_stages(session, admin.id, 2)
        

        resp = await client.get(f"/api/v1/courses/{course.id}/blocks/{blocks[1].id}")
        assert resp.json()["next_block_id"] == str(blocks[2].id)
        

        resp = await client.get(f"/api/v1/courses/{course.id}/blocks/{blocks[3].id}")
        assert resp.json()["next_block_id"] is None

    async def test_get_blocks_invalid_course_id(self, client):

        resp = await client.get(f"/api/v1/courses/{uuid.uuid4()}/blocks/")
        assert resp.status_code == 404

    async def test_get_block_details_wrong_course(self, client, session):
        admin = await _create_user(session, "admsec6@test.com", is_superuser=True)
        c1, blocks1, _, _ = await _create_course_with_stages(session, admin.id, 1)
        c2 = Course(id=uuid.uuid4(), title="Course 2", created_by=admin.id, is_published=True)
        session.add(c2)
        await session.commit()
        

        resp = await client.get(f"/api/v1/courses/{c2.id}/blocks/{blocks1[0].id}")
        assert resp.status_code == 404

    async def test_all_stages_all_blocks_consistency_for_different_users(self, client, session):
        admin = await _create_user(session, "admstat7@test.com", is_superuser=True)
        course, blocks, _, _ = await _create_course_with_stages(session, admin.id, 5)
        

        u1 = await _create_user(session, "stat_cons1@test.com")
        await client.post("/api/v1/auth/login", data={"username": u1.email, "password": "Password12345!"})
        data1 = (await client.get(f"/api/v1/courses/{course.id}/blocks/")).json()
        assert data1["all_stages"] == 5
        assert len(data1["blocks"]) == 2
        

        u2 = await _create_user(session, "stat_cons2@test.com")
        for b in blocks:
            session.add(UserBlockProgress(user_id=u2.id, block_id=b.id, is_completed=True))
        await session.commit()
        await client.post("/api/v1/auth/login", data={"username": u2.email, "password": "Password12345!"})
        data2 = (await client.get(f"/api/v1/courses/{course.id}/blocks/")).json()
        assert data2["all_stages"] == 5
        assert len(data2["blocks"]) == 10
