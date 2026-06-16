# Auth and Employee Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the next spec slice: account/password authentication, current-user lookup, employee import into cycle snapshots, automatic evaluation-record creation, and automatic account/role assignment.

**Architecture:** Keep the Flask modular monolith. Add small repository modules for accounts and employee snapshots, pure import validation/service logic for JSON rows, and route modules for `/auth/*` and `/cycles/{cycleId}/employees/import`. Excel parsing is deferred to the next import/export phase; this phase implements the validated row ingestion that the Excel parser will call.

**Tech Stack:** Python 3, Flask, SQLite, pytest, Werkzeug password hashing, standard-library `sqlite3`.

---

## Scope Check

This phase covers spec sections 5.1, 5.3, 6.1, 6.3, 8.1, 8.3, 20.1, and 24.6 for the backend foundation. It intentionally does not implement browser UI, real `.xlsx` parsing, self-review submission, manager scoring, review submit APIs, objective data import, calculation persistence, or Excel export.

## Files

- Create: `tests/test_auth_api.py`
- Create: `tests/test_employee_import_api.py`
- Create: `performance_app/repositories/accounts.py`
- Create: `performance_app/repositories/employees.py`
- Create: `performance_app/services/__init__.py`
- Create: `performance_app/services/employee_import.py`
- Create: `performance_app/routes/auth.py`
- Create: `performance_app/routes/employees.py`
- Modify: `performance_app/__init__.py`
- Modify: `README.md`

---

### Task 1: Authentication API

**Files:**
- Create: `tests/test_auth_api.py`
- Create: `performance_app/repositories/accounts.py`
- Create: `performance_app/routes/auth.py`
- Modify: `performance_app/__init__.py`

- [ ] **Step 1: Write failing auth API tests**

Create `tests/test_auth_api.py` with tests that insert a user account and roles, assert `/auth/login` accepts the correct password, rejects a wrong password, and `/auth/me` returns the user identified by `X-User-Id`.

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_auth_api.py -q`

Expected: 404 or import failure because auth routes/repository are missing.

- [ ] **Step 3: Implement account repository and auth routes**

Implement:

- `create_account(emp_id, username, password, roles)` using `generate_password_hash`.
- `find_by_username(username)`.
- `find_by_id(user_id)` including roles.
- `POST /auth/login` returning `{user: {id, emp_id, username, roles}}`.
- `GET /auth/me` reading `X-User-Id` and returning the same user shape.

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest tests/test_auth_api.py tests/test_database_initialization.py -q`

Expected: all selected tests pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add performance_app tests/test_auth_api.py
git commit -m "feat: add account authentication APIs"
```

---

### Task 2: Employee import service and API

**Files:**
- Create: `tests/test_employee_import_api.py`
- Create: `performance_app/repositories/employees.py`
- Create: `performance_app/services/__init__.py`
- Create: `performance_app/services/employee_import.py`
- Create: `performance_app/routes/employees.py`
- Modify: `performance_app/__init__.py`

- [ ] **Step 1: Write failing employee import tests**

Create `tests/test_employee_import_api.py` with tests that create a PREPARING cycle, post rows to `/cycles/1/employees/import`, and verify:

- valid rows create `cycle_employee_snapshot` records with derived `group_code`;
- valid rows create `evaluation_record` rows with `SELF_PENDING`;
- valid rows create user accounts with default password and roles;
- duplicate employee IDs in the same payload are rejected with import errors;
- invalid P-levels are rejected with import errors.

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_employee_import_api.py -q`

Expected: 404 or import failure because employee import route/service is missing.

- [ ] **Step 3: Implement repositories, service, and route**

Implement row validation for required fields: `emp_id`, `emp_name`, `sequence`, `level`, `dept_name`, `direct_manager_id`, `indirect_manager_id`, `dept_head_id`. Use `derive_group_code()` for `group_code`. Insert an `import_batch`, `import_error` rows for invalid rows, snapshots and evaluation records for valid rows, and account/role records for valid rows.

Role derivation:

- every imported employee gets `EMPLOYEE`;
- any `direct_manager_id` referenced by another row gets `DIRECT_MANAGER`;
- any `indirect_manager_id` referenced by another row gets `INDIRECT_MANAGER`;
- any `dept_head_id` referenced by another row gets `DEPT_HEAD`;
- if a manager ID exists in imported rows, assign the role to that account.

Use default initial password `ChangeMe123!` for auto-created accounts.

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest tests/test_employee_import_api.py tests/test_auth_api.py tests/test_domain_rules.py -q`

Expected: all selected tests pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add performance_app tests/test_employee_import_api.py
git commit -m "feat: import employees and initialize accounts"
```

---

### Task 3: Documentation and full verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README current scope**

Add bullets for:

- account creation and login APIs;
- current-user lookup API;
- JSON-row employee import service for the Excel parser to reuse;
- automatic employee snapshot and evaluation-record creation;
- automatic account and manager role assignment.

- [ ] **Step 2: Run full verification**

Run:

```bash
python -m pytest -q
git status --short
```

Expected: all tests pass and only README is modified, aside from ignored `.idea/` if present.

- [ ] **Step 3: Commit docs**

Run:

```bash
git add README.md
git commit -m "docs: document auth and employee import scope"
```

## Self-Review Notes

- This plan maps to the spec's account/password login, `/auth/login`, `/auth/me`, employee import, snapshot, record initialization, and account/role bootstrapping requirements.
- It deliberately keeps real Excel file parsing out of scope; the service accepts validated row dictionaries so XLSX parsing can be added without changing business logic.
- No placeholder markers are present; every task has concrete behavior, commands, and commit points.
