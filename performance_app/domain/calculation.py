from __future__ import annotations

from dataclasses import dataclass
from itertools import groupby
from operator import itemgetter

from performance_app.domain.grades import final_level_from_rank_pct, grade_to_score

WEIGHTS = {
    "MANAGEMENT": {
        "subjective_1": 0.20,
        "subjective_2": 0.30,
        "subjective_3": 0.30,
        "diligence": 0.10,
        "discipline": 0.05,
        "learning": 0.05,
    },
    "EMPLOYEE_P4_10": {
        "subjective_1": 0.30,
        "subjective_2": 0.25,
        "subjective_3": 0.30,
        "diligence": 0.05,
        "discipline": 0.05,
        "learning": 0.05,
    },
    "EMPLOYEE_P1_3": {
        "subjective_1": 0.30,
        "subjective_2": 0.20,
        "subjective_3": 0.30,
        "diligence": 0.10,
        "discipline": 0.05,
        "learning": 0.05,
    },
}


@dataclass(frozen=True)
class WeightedScoreResult:
    weighted_score: float
    contributions: dict[str, float]


def calculate_weighted_score(
    *,
    group_code: str,
    subjective_1: str,
    subjective_2: str,
    subjective_3: str,
    diligence: str,
    discipline: str,
    learning: str,
) -> WeightedScoreResult:
    if group_code not in WEIGHTS:
        raise ValueError(f"Unsupported group code: {group_code}")

    weights = WEIGHTS[group_code]
    grades = {
        "subjective_1": subjective_1,
        "subjective_2": subjective_2,
        "subjective_3": subjective_3,
        "diligence": diligence,
        "discipline": discipline,
        "learning": learning,
    }
    contributions = {
        key: round(grade_to_score(value) * weights[key], 1)
        for key, value in grades.items()
    }
    return WeightedScoreResult(
        weighted_score=round(sum(contributions.values()), 1),
        contributions=contributions,
    )


def rank_records(records: list[dict]) -> list[dict]:
    sorted_records = sorted(
        records,
        key=lambda item: (item["group_code"], -item["weighted_score"], item["emp_id"]),
    )
    ranked: list[dict] = []

    for group_code, group_items in groupby(sorted_records, key=itemgetter("group_code")):
        group = list(group_items)
        total = len(group)
        for index, item in enumerate(group, start=1):
            rank_pct = round(index / total * 100, 1)
            ranked.append(
                {
                    **item,
                    "rank_in_group": index,
                    "rank_total": total,
                    "rank_pct": rank_pct,
                    "suggested_level": final_level_from_rank_pct(rank_pct),
                }
            )

    return ranked
