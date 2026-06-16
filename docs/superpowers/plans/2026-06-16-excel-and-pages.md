# Excel Upload and Browser Pages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete V1 usability by adding Excel template/upload flows and lightweight browser pages on top of the implemented APIs.

**Architecture:** Keep business logic in existing services. Add thin Excel parser/template helpers that convert workbooks to the same row dictionaries used by JSON import APIs. Add server-rendered Flask templates with progressive forms and small inline JavaScript only where needed.

**Tech Stack:** Python 3, Flask, SQLite, pytest, openpyxl, Jinja templates, plain CSS/JavaScript.

---

## Scope Check

This phase covers file template/download and real `.xlsx` upload parsing for personnel/objective imports, plus browser pages listed in the spec. It does not add external notifications, production backup scheduling, or SSO.

## Files

- Create: `tests/test_excel_import_api.py`
- Create: `tests/test_pages.py`
- Create: `performance_app/services/excel_import.py`
- Modify: `performance_app/routes/employees.py`
- Modify: `performance_app/routes/objective.py`
- Create: `performance_app/routes/pages.py`
- Modify: `performance_app/__init__.py`
- Create: `performance_app/templates/base.html`
- Create: `performance_app/templates/login.html`
- Create: `performance_app/templates/dashboard.html`
- Create: `performance_app/templates/self_review.html`
- Create: `performance_app/templates/direct_reports.html`
- Create: `performance_app/templates/indirect_review.html`
- Create: `performance_app/templates/dept_review.html`
- Create: `performance_app/templates/objective_import.html`
- Create: `performance_app/templates/results.html`
- Create: `performance_app/static/app.css`
- Modify: `README.md`

---

### Task 1: Excel template and upload APIs

- [ ] Write tests for `GET /cycles/{cycleId}/employees/template`, `POST /cycles/{cycleId}/employees/upload`, `GET /objective/template`, and `POST /objective/upload`.
- [ ] Verify RED with `python -m pytest tests/test_excel_import_api.py -q`.
- [ ] Implement `excel_import.py` to build templates and parse uploaded workbooks into existing row dicts.
- [ ] Add upload routes that call existing `import_employee_rows()` and `import_objective_rows()` services.
- [ ] Verify GREEN and run related import tests.
- [ ] Commit `feat: import performance data from Excel`.

### Task 2: Browser pages

- [ ] Write tests that the main pages render and contain the core forms/tables for each role flow.
- [ ] Verify RED with `python -m pytest tests/test_pages.py -q`.
- [ ] Add `pages.py`, templates, and CSS for login, dashboard, self review, direct manager, indirect manager, department head, objective import, results, and export pages.
- [ ] Keep page actions wired to existing JSON APIs or form endpoints through minimal JavaScript/fetch snippets.
- [ ] Verify GREEN and run page tests.
- [ ] Commit `feat: add browser pages for performance workflow`.

### Task 3: Documentation and full verification

- [ ] Update README with Excel upload/template and page implementation status.
- [ ] Run `python -m pytest -q`.
- [ ] Run `git status --short --branch`.
- [ ] Commit `docs: document Excel upload and pages`.

## Self-Review Notes

- The pages are intentionally lightweight; the static prototype remains the visual reference, but this phase creates functional Flask pages.
- Excel upload parsing reuses current JSON-row services, so validation and audit behavior stays consistent.
- No placeholder markers are present.
