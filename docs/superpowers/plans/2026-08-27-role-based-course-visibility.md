# Role-Based Course Visibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Professional users see only published courses for their own role and `everyone`; buyers retain no course access, and inaccessible courses cannot be opened through nested or direct endpoints.

**Architecture:** Keep `Course.audience` as the single source of truth. Introduce a single `CourseAccessPolicy` that maps a viewer role to allowed audiences, apply it in SQL before ranking/pagination, and use scoped course/block/submission fetches in every user-facing route. Admin CRUD stays unrestricted.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2 async, Pydantic 2, Alembic, Pytest, HTTPX.

## Global Constraints

- `installer` sees only `{everyone, installer}`; `seller` only `{everyone, seller}`; `serviceman` only `{everyone, serviceman}`.
- `buyer` receives `403` from course, block and test APIs; anonymous users must not receive course entities through global search.
- A professional user receives `404` for an inaccessible or unpublished course, block, test attempt, enrollment or certificate-generation endpoint.
- Query parameter `audience` may only narrow the allowed set, never expand it.
- Existing `everyone` rows remain visible to every professional role. No data migration is needed.
- Existing `audience=buyer` rows remain readable by admin only; creating or updating a course to that audience returns `422`.
- Previously issued certificates remain downloadable by their owner after a role change, but current course content and new certificate issuance use the policy.
- Do not use `git add .`; preserve unrelated changes.

## Existing Context

- Roles are in `backend/Domain/Enums/user_role.py`: `administrator`, `installer`, `seller`, `serviceman`, `buyer`.
- `Course.audience` and the related enum already exist in `backend/core/models/course.py` and `backend/Domain/Enums/course.py`.
- `current_course_allowed_user` already rejects buyers for course/block/test routers, but repository queries do not yet scope data by professional role.
- Course search, direct course lookup, enrollment, block/test access, global search, profile activity and new certificate issuance must all use the same policy.

---

### Task 1: Create the canonical access policy

**Files:**

- Create: `backend/Services/course_access.py`
- Create: `backend/tests/services/test_course_access.py`
- Modify: `backend/core/schemas/course.py`

**Interfaces:** `CourseAccessPolicy(audiences, published_only)`, `get_course_access_policy(role, include_unpublished_for_admin=False) -> CourseAccessPolicy`, and `get_course_notification_roles(audience)`, which returns the applicable professional roles.

- [ ] **Step 1: Write failing policy tests**

```python
@pytest.mark.parametrize(
    ("role", "audiences"),
    [
        (UserRole.installer, {CourseAudience.everyone, CourseAudience.installer}),
        (UserRole.seller, {CourseAudience.everyone, CourseAudience.seller}),
        (UserRole.serviceman, {CourseAudience.everyone, CourseAudience.serviceman}),
        (UserRole.buyer, set()),
        (None, set()),
    ],
)
def test_professional_role_policy(role, audiences):
    assert get_course_access_policy(role).audiences == frozenset(audiences)
```

Also verify admin sees all published audiences, direct admin lookup can include unpublished courses, and notifications for `everyone` target all professional roles.

- [ ] **Step 2: Run the test to confirm RED**

Run: `PYTHONPATH=backend poetry run pytest backend/tests/services/test_course_access.py -q`

Expected: import failure for `Services.course_access`.

- [ ] **Step 3: Implement `CourseAccessPolicy`**

Use a fixed role-to-audience map. `audiences=None` means no audience filter for admin; an empty frozen set must return no courses. Policy must add `Course.is_published.is_(True)` for all user-facing reads, including admins in list/search views.

- [ ] **Step 4: Reject a new buyer-only course in input schemas**

```python
def validate_assignable_course_audience(value: CourseAudience) -> CourseAudience:
    if value == CourseAudience.buyer:
        raise ValueError("Buyer cannot be a course audience")
    return value
```

Use the validated type in `CourseCreate` and `CourseUpdate` only. Keep output schemas unchanged so legacy buyer rows remain readable by an admin.

- [ ] **Step 5: Run GREEN and commit**

Run: `PYTHONPATH=backend poetry run pytest backend/tests/services/test_course_access.py -q`

Commit:

```bash
git add backend/Services/course_access.py backend/core/schemas/course.py backend/tests/services/test_course_access.py
git commit -m "feat(courses): add role visibility policy"
```

---

### Task 2: Scope list, search, direct course access and enrollment

**Files:**

- Modify: `backend/Repository/course.py`
- Modify: `backend/Services/course.py`
- Modify: `backend/api/api_v1/course.py`
- Create: `backend/tests/api/api_v1/test_course_role_visibility.py`

**Interfaces:** `apply_course_access_policy(statement, policy) -> Select` and `get_accessible_course(session, course_id, policy, load_blocks=False) -> Course | None`.

- [ ] **Step 1: Write failing role-matrix API tests**

Seed one published course for each audience plus an unpublished `installer` course. For each professional role, assert both `GET /api/v1/courses/` and course search return only `everyone` and the matching role. Assert `?audience=seller` for installer returns an empty list; it must not override policy. Assert buyer returns `403` and an unpublished course is absent for professionals.

- [ ] **Step 2: Test direct-ID boundaries**

For an installer requesting a seller course, assert all return `404` and create no state:

```text
GET  /api/v1/courses/{course_id}
POST /api/v1/courses/{course_id}/enroll
GET  /api/v1/courses/{course_id}/progress
```

Assert own-role and `everyone` courses work. Admin can retrieve an unpublished course through the administrative/direct-management flow.

- [ ] **Step 3: Confirm RED**

Run: `PYTHONPATH=backend poetry run pytest backend/tests/api/api_v1/test_course_role_visibility.py -q`

Expected: foreign-audience courses are currently returned or accessible.

- [ ] **Step 4: Apply the policy at SQL level**

`apply_course_access_policy` must apply `Course.is_published`, membership in the policy audience set, or SQL `false()` for an empty audience set before sorting, filtering, ranking and pagination. Use it in repository `search_courses` and a new `get_accessible_course` query. Pass the resolved policy through the service; do not filter Python lists after retrieval.

- [ ] **Step 5: Switch user-facing course endpoints**

Pass `user.role` to list/search. Replace user-facing `get_course` calls for details, enrollment and progress with scoped lookup. Preserve unrestricted repository calls for admin create/update/delete/reset/complete routes.

- [ ] **Step 6: Run GREEN and commit**

Run:

```bash
PYTHONPATH=backend poetry run pytest \
  backend/tests/api/api_v1/test_course_role_visibility.py \
  backend/tests/api/api_v1/test_course_audience_filter_step6.py \
  backend/tests/api/api_v1/test_courses_extensive.py -q
```

Commit:

```bash
git add backend/Repository/course.py backend/Services/course.py backend/api/api_v1/course.py backend/tests/api/api_v1/test_course_role_visibility.py
git commit -m "feat(courses): scope course endpoints by user role"
```

---

### Task 3: Protect blocks, test attempts and results before side effects

**Files:**

- Modify: `backend/Repository/course.py`
- Modify: `backend/Services/course.py`
- Modify: `backend/api/api_v1/block.py`
- Modify: `backend/api/api_v1/tests.py`
- Create: `backend/tests/api/api_v1/test_course_role_nested_access.py`

**Interfaces:** `get_accessible_block(session, block_id, policy) -> Block | None` and `get_accessible_submission(session, submission_id, policy, owner_id=None) -> TestSubmission | None`.

- [ ] **Step 1: Write negative access tests**

For an installer and a block in a seller course, assert `404` for course block list/detail, test results/history, question list and test submit. Assert no `UserBlockProgress` and no pending `TestSubmission` is created. After changing a user’s role, their old foreign-audience submission must return `404` through `/tests/submissions/{id}`.

- [ ] **Step 2: Confirm RED**

Run: `PYTHONPATH=backend poetry run pytest backend/tests/api/api_v1/test_course_role_nested_access.py -q`

- [ ] **Step 3: Implement scoped nested fetches**

Join `Block -> Course` and `TestSubmission -> Block -> Course`, then reuse `apply_course_access_policy`. In `block.py` and `tests.py`, perform this check before reading/updating progress, creating a pending test attempt, or returning results. Keep admin question CRUD unrestricted.

- [ ] **Step 4: Run GREEN and commit**

Run:

```bash
PYTHONPATH=backend poetry run pytest \
  backend/tests/api/api_v1/test_course_role_nested_access.py \
  backend/tests/api/api_v1/test_blocks_extensive.py \
  backend/tests/api/api_v1/test_block_results.py \
  backend/tests/api/api_v1/test_submission_history.py \
  backend/tests/api/api_v1/test_questions_count_randomization.py -q
```

Commit:

```bash
git add backend/Repository/course.py backend/Services/course.py backend/api/api_v1/block.py backend/api/api_v1/tests.py backend/tests/api/api_v1/test_course_role_nested_access.py
git commit -m "fix(courses): protect nested resources by audience"
```

---

### Task 4: Scope global search and derive notification recipients

**Files:**

- Modify: `backend/api/api_v1/search.py`
- Modify: `backend/Services/search.py`
- Modify: `backend/Repository/search.py`
- Modify: `backend/Services/notifications.py`
- Modify: `backend/tests/api/api_v1/test_global_search.py`
- Modify: `backend/tests/api/api_v1/test_notifications.py`

- [ ] **Step 1: Write global-search tests**

Anonymous and buyer searches must return no courses (while preserving non-course search categories). Each professional role sees its `everyone` and own-role courses only. Admin sees all published audiences. An unpublished course must not enter global search for any role.

- [ ] **Step 2: Add optional authenticated user to global search**

```python
async def global_search(
    db: Session,
    user: User | None = Depends(current_optional_user),
    query: str | None = Query(default=None),
) -> SearchResponse:
    return await search_crud.global_search_entities(
        db,
        query=query,
        user_role=user.role if user else None,
    )
```

Apply the policy only to course candidates, before fuzzy ranking. Replace notification-specific role mapping with `get_course_notification_roles(course.audience)`.

- [ ] **Step 3: Run GREEN and commit**

Run:

```bash
PYTHONPATH=backend poetry run pytest \
  backend/tests/api/api_v1/test_global_search.py \
  backend/tests/api/api_v1/test_notifications.py -q
```

Commit `feat(search): filter courses by viewer role`, then commit `refactor(notifications): derive recipients from course policy`.

---

### Task 5: Filter profile activity and enforce policy on new certificates

**Files:**

- Modify: `backend/api/api_v1/profile.py`
- Modify: `backend/Services/profile.py`
- Modify: `backend/api/api_v1/certificates.py`
- Create: `backend/tests/api/api_v1/test_course_role_profile_access.py`
- Modify: `backend/tests/api/api_v1/test_certificate_pdf_and_profile.py`

- [ ] **Step 1: Write role-change tests**

Create installer progress and a submission. After role change to seller, it must disappear from test attempts, course progress and recent courses, without deleting database records. An `everyone` course remains visible; restoring installer makes prior data visible again. Buyer profile course lists are empty.

- [ ] **Step 2: Pass `user.role` into profile queries**

Update service signatures to include role and apply the policy in every query that joins `Course`: test attempts, course progress, recent courses and automatic certificate detection.

- [ ] **Step 3: Protect new certificate issuance**

`POST /certificates/courses/{course_id}/generate` must use an accessible course lookup and return `404` for a foreign audience. Do not revoke or hide previously issued owner certificates: they are immutable credentials, not course-access grants.

- [ ] **Step 4: Run GREEN and commit**

Run:

```bash
PYTHONPATH=backend poetry run pytest \
  backend/tests/api/api_v1/test_course_role_profile_access.py \
  backend/tests/api/api_v1/test_certificate_pdf_and_profile.py \
  backend/tests/api/api_v1/test_certification_bugs.py -q
```

Commit `fix(profile): hide inaccessible course activity` and `fix(certificates): enforce course audience on issuance`.

---

### Task 6: Verify all access boundaries

- [ ] **Step 1: Add buyer boundary assertions**

Buyer must receive `403` on list/search/detail/enroll/progress/blocks/questions/test submission/new certificate generation. Verify no progress or test rows appear after denied calls.

- [ ] **Step 2: Run the complete role-access regression suite**

```bash
PYTHONPATH=backend poetry run pytest \
  backend/tests/api/api_v1/test_course_role_visibility.py \
  backend/tests/api/api_v1/test_course_role_nested_access.py \
  backend/tests/api/api_v1/test_course_role_profile_access.py \
  backend/tests/api/api_v1/test_courses_extensive.py \
  backend/tests/api/api_v1/test_blocks_extensive.py \
  backend/tests/api/api_v1/test_global_search.py \
  backend/tests/api/api_v1/test_notifications.py -q
```

- [ ] **Step 3: Run final checks and commit only intended files**

```bash
PYTHONPATH=backend poetry run python -m compileall -q backend/Services backend/Repository backend/api backend/core
git diff --check
```

Run the full backend suite before release. No Alembic migration is expected for this feature because the audience column and enum values already exist.

## Decisions Required Before Implementation

1. Professional roles are currently selectable during public registration. If they must be verified by admin, that is a separate role-approval feature; without it, users can self-register as installer/seller/serviceman.
2. This plan supports one professional audience or `everyone` per course. Multi-role courses require a separate many-to-many model and migration.
3. Legacy buyer-audience courses remain admin-only; automatically changing them to `everyone` would leak content.
