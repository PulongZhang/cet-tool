import pytest

from performance_app.domain.employees import derive_group_code
from performance_app.domain.grades import final_level_from_rank_pct, grade_to_score
from performance_app.domain.objectives import (
    diligence_level_from_quarter_total,
    discipline_level_from_exception_count,
    learning_level_from_rank_pct,
)


def test_derive_group_code_uses_specific_p_level():
    assert derive_group_code("管理序列", "不适用") == "MANAGEMENT"
    assert derive_group_code("员工序列", "P1") == "EMPLOYEE_P1_3"
    assert derive_group_code("员工序列", "P3") == "EMPLOYEE_P1_3"
    assert derive_group_code("员工序列", "P4") == "EMPLOYEE_P4_10"
    assert derive_group_code("员工序列", "P10") == "EMPLOYEE_P4_10"


def test_derive_group_code_rejects_invalid_employee_level():
    with pytest.raises(ValueError, match="Unsupported employee level"):
        derive_group_code("员工序列", "P11")


def test_grade_to_score_mapping_matches_spec():
    assert grade_to_score("A+") == 100
    assert grade_to_score("A") == 93
    assert grade_to_score("B+") == 86
    assert grade_to_score("B") == 80
    assert grade_to_score("B-") == 70
    assert grade_to_score("C") == 60
    assert grade_to_score("D") == 50


def test_final_level_from_rank_pct_matches_spec_boundaries():
    assert final_level_from_rank_pct(5) == "A+"
    assert final_level_from_rank_pct(20) == "A"
    assert final_level_from_rank_pct(50) == "B+"
    assert final_level_from_rank_pct(85) == "B"
    assert final_level_from_rank_pct(95) == "B-"
    assert final_level_from_rank_pct(98) == "C"
    assert final_level_from_rank_pct(99) == "D"


def test_diligence_level_uses_month_average_from_quarter_total():
    assert diligence_level_from_quarter_total(30) == "D"
    assert diligence_level_from_quarter_total(33) == "C"
    assert diligence_level_from_quarter_total(120) == "B"
    assert diligence_level_from_quarter_total(180) == "A"


def test_discipline_level_uses_total_exception_count():
    assert discipline_level_from_exception_count(3) == "A+"
    assert discipline_level_from_exception_count(6) == "A"
    assert discipline_level_from_exception_count(9) == "B"
    assert discipline_level_from_exception_count(12) == "C"
    assert discipline_level_from_exception_count(13) == "D"


def test_learning_level_uses_rank_percent_boundaries():
    assert learning_level_from_rank_pct(5) == "A+"
    assert learning_level_from_rank_pct(20) == "A"
    assert learning_level_from_rank_pct(50) == "B+"
    assert learning_level_from_rank_pct(85) == "B"
    assert learning_level_from_rank_pct(95) == "B-"
    assert learning_level_from_rank_pct(98) == "C"
    assert learning_level_from_rank_pct(100) == "D"
