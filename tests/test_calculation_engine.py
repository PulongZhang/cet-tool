from performance_app.domain.calculation import calculate_weighted_score, rank_records


def test_calculate_weighted_score_for_employee_p4_10():
    result = calculate_weighted_score(
        group_code="EMPLOYEE_P4_10",
        subjective_1="A",
        subjective_2="A",
        subjective_3="B+",
        diligence="A",
        discipline="B",
        learning="B+",
    )

    assert result.weighted_score == 89.9
    assert result.contributions == {
        "subjective_1": 27.9,
        "subjective_2": 23.2,
        "subjective_3": 25.8,
        "diligence": 4.7,
        "discipline": 4.0,
        "learning": 4.3,
    }


def test_calculate_weighted_score_for_management():
    result = calculate_weighted_score(
        group_code="MANAGEMENT",
        subjective_1="A",
        subjective_2="B+",
        subjective_3="B+",
        diligence="A",
        discipline="A+",
        learning="A",
    )

    assert result.weighted_score == 89.2


def test_rank_records_sorts_by_group_score_and_uses_same_rank_for_ties():
    ranked = rank_records(
        [
            {"record_id": 1, "emp_id": "E002", "group_code": "EMPLOYEE_P1_3", "weighted_score": 90.0},
            {"record_id": 2, "emp_id": "E001", "group_code": "EMPLOYEE_P1_3", "weighted_score": 90.0},
            {"record_id": 3, "emp_id": "E003", "group_code": "EMPLOYEE_P4_10", "weighted_score": 95.0},
        ]
    )

    assert ranked == [
        {
            "record_id": 2,
            "emp_id": "E001",
            "group_code": "EMPLOYEE_P1_3",
            "weighted_score": 90.0,
            "rank_in_group": 1,
            "rank_total": 2,
            "rank_pct": 50.0,
            "suggested_level": "B+",
        },
        {
            "record_id": 1,
            "emp_id": "E002",
            "group_code": "EMPLOYEE_P1_3",
            "weighted_score": 90.0,
            "rank_in_group": 1,
            "rank_total": 2,
            "rank_pct": 50.0,
            "suggested_level": "B+",
        },
        {
            "record_id": 3,
            "emp_id": "E003",
            "group_code": "EMPLOYEE_P4_10",
            "weighted_score": 95.0,
            "rank_in_group": 1,
            "rank_total": 1,
            "rank_pct": 100.0,
            "suggested_level": "D",
        },
    ]
