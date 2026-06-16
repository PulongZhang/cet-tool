from __future__ import annotations

from performance_app.db import get_db
from performance_app.domain.calculation import calculate_weighted_score, rank_records
from performance_app.domain.constants import GRADES
from performance_app.repositories.audit import write_audit_log
from performance_app.repositories.records import get_record

CALCULATED_STATUS = "INITIAL_CALCULATED"
FINAL_STATUS = "FINAL_CONFIRMED"


class CalculationPrerequisiteError(ValueError):
    def __init__(self, missing: list[dict]):
        super().__init__("calculation prerequisites not met")
        self.missing = missing


def calculate_cycle(cycle_id: int, operator_id: str, operator_name: str) -> dict:
    records = calculation_candidates(cycle_id)
    missing = missing_prerequisites(records)
    if missing:
        raise CalculationPrerequisiteError(missing)

    calculated: list[dict] = []
    for record in records:
        objective = objective_for_record(record["cycle_id"], record["emp_id"])
        score = calculate_weighted_score(
            group_code=record["group_code"],
            subjective_1=record["final_subjective_grade_1"],
            subjective_2=record["final_subjective_grade_2"],
            subjective_3=record["final_subjective_grade_3"],
            diligence=objective["diligence_level"],
            discipline=objective["discipline_level"],
            learning=objective["learning_level"],
        )
        calculated.append(
            {
                "record_id": record["id"],
                "emp_id": record["emp_id"],
                "group_code": record["group_code"],
                "weighted_score": score.weighted_score,
            }
        )

    ranked = rank_records(calculated)
    for item in ranked:
        persist_calculation_result(item)

    write_audit_log(
        action="CALCULATE_RESULTS",
        target_type="evaluation_cycle",
        target_id=cycle_id,
        operator_id=operator_id,
        operator_name=operator_name,
        cycle_id=cycle_id,
        after_snapshot={"calculated_count": len(ranked)},
    )
    get_db().commit()
    return {"summary": {"calculated_count": len(ranked)}, "records": list_cycle_results(cycle_id)}


def calculation_candidates(cycle_id: int) -> list[dict]:
    rows = get_db().execute(
        """
        select r.*, s.emp_name, s.dept_name, s.group_code, s.level
        from evaluation_record r
        join cycle_employee_snapshot s on s.cycle_id = r.cycle_id and s.emp_id = r.emp_id
        where r.cycle_id = ? and r.status = 'HR_PENDING'
        order by r.emp_id
        """,
        (cycle_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def missing_prerequisites(records: list[dict]) -> list[dict]:
    missing: list[dict] = []
    for record in records:
        for field in ("final_subjective_grade_1", "final_subjective_grade_2", "final_subjective_grade_3"):
            if not record.get(field):
                missing.append({"record_id": record["id"], "emp_id": record["emp_id"], "field_name": field})
        objective = objective_for_record(record["cycle_id"], record["emp_id"])
        if objective is None:
            missing.append({"record_id": record["id"], "emp_id": record["emp_id"], "field_name": "objective_data"})
        elif not objective.get("learning_level"):
            missing.append({"record_id": record["id"], "emp_id": record["emp_id"], "field_name": "learning_level"})
    return missing


def objective_for_record(cycle_id: int, emp_id: str) -> dict | None:
    row = get_db().execute(
        "select * from objective_data where cycle_id = ? and emp_id = ?",
        (cycle_id, emp_id),
    ).fetchone()
    return dict(row) if row else None


def persist_calculation_result(item: dict) -> None:
    get_db().execute(
        """
        update evaluation_record
        set weighted_score = ?, rank_in_group = ?, rank_total = ?, suggested_level = ?,
            final_level = ?, status = ?, updated_at = datetime('now')
        where id = ?
        """,
        (
            item["weighted_score"],
            item["rank_in_group"],
            item["rank_total"],
            item["suggested_level"],
            item["suggested_level"],
            CALCULATED_STATUS,
            item["record_id"],
        ),
    )


def list_cycle_results(cycle_id: int) -> list[dict]:
    rows = get_db().execute(
        """
        select r.*, s.emp_name, s.dept_name, s.group_code, s.level
        from evaluation_record r
        join cycle_employee_snapshot s on s.cycle_id = r.cycle_id and s.emp_id = r.emp_id
        where r.cycle_id = ? and r.weighted_score is not null
        order by s.group_code, r.rank_in_group, r.emp_id
        """,
        (cycle_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def calculation_detail(record_id: int) -> dict | None:
    record = get_record(record_id)
    if record is None:
        return None
    objective = objective_for_record(record["cycle_id"], record["emp_id"])
    if objective is None:
        raise CalculationPrerequisiteError(
            [{"record_id": record_id, "emp_id": record["emp_id"], "field_name": "objective_data"}]
        )
    score = calculate_weighted_score(
        group_code=record["group_code"],
        subjective_1=record["final_subjective_grade_1"],
        subjective_2=record["final_subjective_grade_2"],
        subjective_3=record["final_subjective_grade_3"],
        diligence=objective["diligence_level"],
        discipline=objective["discipline_level"],
        learning=objective["learning_level"],
    )
    return {
        "record": record,
        "objective": objective,
        "contributions": score.contributions,
        "weighted_score": score.weighted_score,
    }


def adjust_final_level(record_id: int, final_level: str, reason: str, operator_id: str, operator_name: str) -> dict:
    if final_level not in GRADES:
        raise ValueError(f"Unsupported grade: {final_level}")
    record = get_record(record_id)
    if record is None:
        raise LookupError("record not found")
    before_value = record.get("final_level")
    get_db().execute(
        "update evaluation_record set final_level = ?, updated_at = datetime('now') where id = ?",
        (final_level, record_id),
    )
    write_audit_log(
        action="ADJUST_FINAL_LEVEL",
        target_type="evaluation_record",
        target_id=record_id,
        operator_id=operator_id,
        operator_name=operator_name,
        cycle_id=record["cycle_id"],
        before_snapshot={"final_level": before_value, "suggested_level": record.get("suggested_level")},
        after_snapshot={"final_level": final_level, "suggested_level": record.get("suggested_level")},
        reason=reason,
    )
    get_db().execute(
        """
        insert into grade_adjustment_log
            (cycle_id, record_id, stage, adjustment_type, field_name, before_value, after_value, reason, operator_id, operator_name)
        values
            (?, ?, 'HR', 'FINAL_LEVEL', 'final_level', ?, ?, ?, ?, ?)
        """,
        (record["cycle_id"], record_id, before_value, final_level, reason, operator_id, operator_name),
    )
    get_db().commit()
    return get_record(record_id)
