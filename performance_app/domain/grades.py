from performance_app.domain.constants import GRADE_SCORES


def grade_to_score(grade: str) -> int:
    try:
        return GRADE_SCORES[grade]
    except KeyError as exc:
        raise ValueError(f"Unsupported grade: {grade}") from exc


def final_level_from_rank_pct(rank_pct: float) -> str:
    if rank_pct <= 5:
        return "A+"
    if rank_pct <= 20:
        return "A"
    if rank_pct <= 50:
        return "B+"
    if rank_pct <= 85:
        return "B"
    if rank_pct <= 95:
        return "B-"
    if rank_pct <= 98:
        return "C"
    return "D"
