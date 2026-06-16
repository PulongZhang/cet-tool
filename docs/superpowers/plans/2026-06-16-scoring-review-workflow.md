# Scoring and Review Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the core subjective workflow APIs: employee self-review, direct-manager scoring, indirect/dept-head review submission, adjustments, distribution checks, and withdraw.

**Architecture:** Keep route handlers thin. Add record repository functions for persistence, a small request-user helper that reads `X-User-Id`, and route modules for self/manager/review operations. Reuse existing workflow, permission, audit, and grade domain functions.

**Tech Stack:** Python 3, Flask, SQLite, pytest, standard-library `sqlite3`.

---

## Scope Check

This phase covers spec sections 5.4, 5.5, 5.6, 8.4, 8.5, 9, 20.4-20.7, 21, and 22 for backend APIs. It does not implement objective-data import, HR calculation persistence, Excel export, or browser templates.

## Files

- Create: `tests/test_scoring_workflow_api.py`
- Create: `performance_app/repositories/records.py`
- Create: `performance_app/routes/records.py`
- Create: `performance_app/routes/reviews.py`
- Modify: `performance_app/__init__.py`
- Modify: `README.md`

---

### Task 1: Self-review and direct-manager scoring APIs

- [ ] **Step 1: Write failing tests**

Create `tests/test_scoring_workflow_api.py` covering:

- employee gets `/records/my?cycle_id=1` using `X-User-Id`;
- self draft updates status to `SELF_DRAFT`;
- self submit updates status to `DIRECT_PENDING`;
- direct manager lists direct reports;
- manager submit writes manager scores, initializes final subjective fields, current subjective level, and status `INDIRECT_PENDING`;
- manager comment is required when `initial_total_grade` is A+, A, C, or D.

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_scoring_workflow_api.py -q`

Expected: route/import failures.

- [ ] **Step 3: Implement repository and routes**

Implement `performance_app/repositories/records.py` and `performance_app/routes/records.py`:

- `GET /records/my`
- `POST /records/{id}/self-draft`
- `POST /records/{id}/self-submit`
- `GET /records/direct-reports`
- `POST /records/{id}/manager-draft`
- `POST /records/{id}/manager-submit`

Use `X-User-Id` to load current user, then check data scope through snapshot manager IDs.

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest tests/test_scoring_workflow_api.py tests/test_employee_import_api.py -q`

Expected: all selected tests pass.

- [ ] **Step 5: Commit**

Run: `git commit -m "feat: add self review and manager scoring APIs"` after adding changed files.

---

### Task 2: Review, adjustment, distribution, and withdraw APIs

- [ ] **Step 1: Extend failing tests**

Extend `tests/test_scoring_workflow_api.py` covering:

- indirect manager list only `INDIRECT_PENDING` scoped records;
- adjustment changes `current_subjective_level` and writes `grade_adjustment_log`;
- indirect submit moves scoped records to `DEPT_HEAD_PENDING`;
- department submit moves scoped records to `HR_PENDING`;
- distribution endpoint returns counts by current subjective level;
- withdraw endpoint requires reason and moves status according to spec matrix.

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_scoring_workflow_api.py -q`

Expected: missing review/withdraw routes.

- [ ] **Step 3: Implement review routes**

Implement `performance_app/routes/reviews.py` and any needed `records.py` repository functions:

- `GET /reviews/indirect`
- `GET /reviews/indirect/distribution`
- `POST /records/{id}/adjustments`
- `POST /reviews/indirect/submit`
- `GET /reviews/dept-head`
- `GET /reviews/dept-head/distribution`
- `POST /reviews/dept-head/submit`
- `POST /records/{id}/withdraw`

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest tests/test_scoring_workflow_api.py -q`

Expected: scoring workflow tests pass.

- [ ] **Step 5: Commit**

Run: `git commit -m "feat: add review adjustment and withdraw APIs"` after adding changed files.

---

### Task 3: Documentation and full verification

- [ ] **Step 1: Update README implemented scope**

Add bullets for self-review, manager scoring, review lists/submits, adjustments, distribution checks, and withdraw.

- [ ] **Step 2: Full verification**

Run: `python -m pytest -q` and `git status --short --branch`.

Expected: all tests pass; only README modified plus ignored `.idea/` if present.

- [ ] **Step 3: Commit docs**

Run: `git commit -m "docs: document scoring workflow APIs"` after adding README.

## Self-Review Notes

- This plan implements backend workflow APIs needed before objective-data calculation and export.
- It reuses existing workflow transitions and audit persistence instead of duplicating rules in routes.
- No placeholder markers are present.
