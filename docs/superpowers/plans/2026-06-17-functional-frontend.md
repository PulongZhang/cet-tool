# Functional Frontend Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace placeholder Flask pages with a usable browser frontend that supports login, role-based navigation, page access control, data-backed pages, and browser-friendly workflow actions.

**Architecture:** Keep the existing Flask modular monolith and JSON APIs. Add a browser session layer for page routes only, reuse existing repositories/services for data access and mutations, and render Jinja pages from server-side view models. Keep JavaScript optional and minimal; page forms post to dedicated browser routes that redirect with status messages.

**Tech Stack:** Python 3, Flask sessions/Jinja, SQLite, pytest, openpyxl, plain CSS.

---

## Scope Check

This phase focuses on functional internal pages. It does not build a SPA framework, SSO, password reset, or production-grade CSRF middleware. Existing JSON APIs remain compatible.

## Files

- Modify: `tests/test_pages.py`
- Create: `tests/test_page_auth.py`
- Create: `tests/test_page_workflows.py`
- Modify: `performance_app/routes/pages.py`
- Create: `performance_app/routes/page_actions.py`
- Modify: `performance_app/__init__.py`
- Modify: `performance_app/templates/base.html`
- Modify: `performance_app/templates/login.html`
- Modify: `performance_app/templates/dashboard.html`
- Modify: `performance_app/templates/self_review.html`
- Modify: `performance_app/templates/direct_reports.html`
- Modify: `performance_app/templates/indirect_review.html`
- Modify: `performance_app/templates/dept_review.html`
- Modify: `performance_app/templates/objective_import.html`
- Modify: `performance_app/templates/results.html`
- Modify: `performance_app/static/app.css`
- Modify: `README.md`

---

### Task 1: Session login and role-based page access

- [ ] Add tests that anonymous users are redirected from protected pages to `/login`.
- [ ] Add tests that `POST /login` accepts a valid account, stores the user in session, redirects to `/`, and `POST /logout` clears the session.
- [ ] Add tests that role-specific pages return `403` for users without the required role.
- [ ] Verify RED with `python -m pytest tests/test_page_auth.py -q`.
- [ ] Implement session helpers, `login_required`, `role_required`, current-user context processor, and browser login/logout routes.
- [ ] Update base/login/dashboard templates to show current user and role-filtered navigation.
- [ ] Verify GREEN.
- [ ] Commit `feat: add frontend session login and page permissions`.

### Task 2: Data-backed dashboard and self/direct-manager pages

- [ ] Add tests that dashboard shows role-specific cards and current cycle selector.
- [ ] Add tests that self-review page renders the logged-in employee's record and form actions.
- [ ] Add tests that direct-manager page renders real direct reports and supports browser draft/submit forms.
- [ ] Verify RED with `python -m pytest tests/test_page_workflows.py -q`.
- [ ] Implement page view models for cycles, self record, and direct reports.
- [ ] Implement browser form actions for self draft/submit, manager draft, and direct-manager batch submit.
- [ ] Verify GREEN.
- [ ] Commit `feat: render employee and direct manager workflow pages`.

### Task 3: Data-backed review, objective, result, and export pages

- [ ] Add tests that indirect/dept-head pages render scoped records and distribution.
- [ ] Add tests that objective page renders upload/correction controls and recent import error feedback.
- [ ] Add tests that results page renders calculated records and exposes calculate/finalize/export actions.
- [ ] Verify RED.
- [ ] Implement view models and browser form actions for review submit, objective upload/correction, calculate, final-level adjustment, finalize, and export.
- [ ] Verify GREEN.
- [ ] Commit `feat: render HR and review workflow pages`.

### Task 4: Documentation and full verification

- [ ] Update README to explain browser login, role page access, and frontend start command.
- [ ] Run `uv run python -m pytest -q`.
- [ ] Run `git status --short --branch`.
- [ ] Commit `docs: document functional frontend`.

## Self-Review Notes

- The browser session layer is intentionally separate from existing header-based JSON API auth so API tests and integrations remain stable.
- Page permissions are enforced server-side; hiding menu items alone is not treated as security.
- No placeholder markers are present.
