# Objective Data Calculation and Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement HR objective-data import, weighted calculation persistence, result review/final adjustment, and Excel export/download APIs.

**Architecture:** Add objective, calculation, and export services that reuse existing pure domain functions. Keep route handlers thin and persist results in existing `objective_data`, `evaluation_record`, `grade_adjustment_log`, and `audit_log` tables. Add `openpyxl` only for `.xlsx` export generation.

**Tech Stack:** Python 3, Flask, SQLite, pytest, openpyxl, standard-library `sqlite3`.

---

## Scope Check

This phase covers spec sections 5.7, 5.8, 8.6, 8.7, 10, 11.3, 20.2, 20.8, 20.9, and 23.2. It does not build browser templates; UI integration is the next phase.

## Files

- Modify: `requirements.txt`
- Create: `tests/test_objective_calculation_export_api.py`
- Create: `performance_app/services/objective_import.py`
- Create: `performance_app/services/calculation_runner.py`
- Create: `performance_app/services/export_files.py`
- Create: `performance_app/routes/objective.py`
- Create: `performance_app/routes/results.py`
- Create: `performance_app/routes/exports.py`
- Modify: `performance_app/__init__.py`
- Modify: `README.md`

---

### Task 1: Objective-data import API

- [ ] Write failing tests for `POST /objective/import` with rows containing three diligence months, attendance/log exception counts, and training hours.
- [ ] Verify RED with `python -m pytest tests/test_objective_calculation_export_api.py -q`.
- [ ] Implement `objective_import.py` and `routes/objective.py`: validate rows, compute diligence/discipline/learning levels, store `objective_data`, record batch/errors.
- [ ] Verify GREEN with objective tests.
- [ ] Commit `feat: import objective data`.

### Task 2: Calculation and result APIs

- [ ] Extend tests for `POST /cycles/{cycleId}/calculate`, `GET /cycles/{cycleId}/results`, `GET /records/{id}/calculation-detail`, and `POST /records/{id}/final-level`.
- [ ] Verify RED.
- [ ] Implement calculation runner: join records + snapshots + objective data, compute weighted score, rank by group, write ranks/suggested/final levels, and mark records `COMPLETED`.
- [ ] Implement result routes and HR final-level adjustment route with required reason.
- [ ] Verify GREEN.
- [ ] Commit `feat: calculate and review performance results`.

### Task 3: Excel export and download APIs

- [ ] Add tests for `POST /cycles/{cycleId}/exports/initial`, `POST /cycles/{cycleId}/exports/final`, and `GET /exports/{exportId}/download` that verify an `.xlsx` file is created and contains expected sheets.
- [ ] Verify RED.
- [ ] Add `openpyxl` dependency and implement export service with result, subjective, objective, adjustment, and instructions sheets.
- [ ] Verify GREEN.
- [ ] Commit `feat: export performance results to Excel`.

### Task 4: Documentation and full verification

- [ ] Update README current scope for objective import, calculation, final adjustment, Excel export.
- [ ] Run `python -m pytest -q` and `git status --short --branch`.
- [ ] Commit `docs: document calculation and export APIs`.

## Self-Review Notes

- This phase completes the non-UI backend loop from objective data to final Excel output.
- It still leaves browser pages/templates as a separate final phase.
- No placeholder markers are present.
