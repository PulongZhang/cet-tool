# V2 Confirmed Backend Adjustments Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align the implemented backend with confirmed clarification points in `docs/superpowers/specs/V2.md` before building browser pages.

**Architecture:** Keep the existing Flask modular monolith. Retrofit behavior in the existing repositories/services/routes instead of introducing new abstractions. Preserve existing APIs where possible, but add explicit batch/finalization endpoints for clarified workflow behavior.

**Tech Stack:** Python 3, Flask, SQLite, pytest, openpyxl.

---

## Scope Check

This phase covers V2 confirmed points that affect backend behavior already built: personnel import atomicity, review submission readiness, objective correction/re-import invalidation, final-result confirmation, and query endpoints needed by pages. UI implementation remains a separate phase.

## Files

- Modify: `tests/test_employee_import_api.py`
- Modify: `tests/test_scoring_workflow_api.py`
- Modify: `tests/test_objective_calculation_export_api.py`
- Create: `tests/test_v2_backend_adjustments.py`
- Modify: `performance_app/services/employee_import.py`
- Modify: `performance_app/routes/records.py`
- Modify: `performance_app/routes/reviews.py`
- Modify: `performance_app/routes/objective.py`
- Modify: `performance_app/routes/results.py`
- Modify: `performance_app/services/objective_import.py`
- Modify: `performance_app/services/calculation_runner.py`
- Modify: `performance_app/repositories/records.py`
- Modify: `performance_app/domain/workflow.py`
- Modify: `README.md`

---

### Task 1: Personnel import atomicity and import query APIs

- [ ] Update employee import tests so invalid personnel import persists no valid rows, while still recording row errors.
- [ ] Add tests for `GET /imports/{batchId}/errors` and `GET /cycles/{cycleId}/employees`.
- [ ] Verify RED with `python -m pytest tests/test_employee_import_api.py tests/test_v2_backend_adjustments.py -q`.
- [ ] Change `import_employee_rows()` to validate the whole file before writing snapshots/accounts/records; if any row errors exist, write only the batch/errors and no employee business data.
- [ ] Add employee list and import error routes.
- [ ] Verify GREEN.
- [ ] Commit `feat: enforce atomic personnel import`.

### Task 2: V2 review submission readiness rules

- [ ] Add tests for direct-manager batch submit and indirect/dept-head submit blocking when any scoped record is not ready.
- [ ] Verify RED.
- [ ] Add `POST /records/direct-reports/submit` to submit a direct manager's scoped records only when all are scored/drafted.
- [ ] Update indirect/dept-head submit routes to reject the whole scope and return blocking records when any scoped record is not in the expected status.
- [ ] Verify existing per-record APIs remain usable for tests that already rely on them.
- [ ] Verify GREEN.
- [ ] Commit `feat: enforce review readiness before submission`.

### Task 3: Objective correction and recalculation invalidation

- [ ] Add tests for `POST /objective/{id}/correct` requiring reason and updating corrected levels.
- [ ] Add tests that re-importing objective data after `INITIAL_CALCULATED` invalidates calculated fields and returns records to `HR_PENDING`.
- [ ] Verify RED.
- [ ] Implement objective correction route with audit log.
- [ ] Update objective import to clear prior calculated result fields and status for affected calculated records in the same cycle.
- [ ] Verify GREEN.
- [ ] Commit `feat: correct objective data and invalidate stale results`.

### Task 4: Final confirmation status and lock semantics

- [ ] Add tests for `POST /cycles/{cycleId}/results/finalize` moving calculated records to `FINAL_CONFIRMED`.
- [ ] Add tests that HR final-level adjustment after final confirmation remains allowed but writes a `FINAL_LEVEL` adjustment log and does not recalculate weighted score.
- [ ] Verify RED.
- [ ] Implement finalization route and service function.
- [ ] Keep final-level adjustment focused on `final_level`; do not change rank or weighted score.
- [ ] Verify GREEN.
- [ ] Commit `feat: finalize performance results`.

### Task 5: Documentation and full verification

- [ ] Update README to remove completed V2 backend items from the pending list.
- [ ] Run `python -m pytest -q`.
- [ ] Run `git status --short --branch`.
- [ ] Commit `docs: document V2 backend adjustments`.

## Self-Review Notes

- This plan intentionally does not remove already committed legacy endpoints; it adds clarified endpoints and stricter aggregate submit behavior where safe.
- Result version tables are deferred because V1 can satisfy the confirmed behavior by invalidating calculated fields and requiring recalculation.
- No placeholder markers are present.
