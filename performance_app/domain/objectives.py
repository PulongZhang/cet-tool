from performance_app.domain.grades import final_level_from_rank_pct


def diligence_level_from_quarter_total(quarter_total: float) -> str:
    if quarter_total < 0:
        raise ValueError("Diligence total cannot be negative")

    month_average = quarter_total / 3
    if month_average < 11:
        return "D"
    if month_average < 40:
        return "C"
    if month_average < 60:
        return "B"
    return "A"


def discipline_level_from_exception_count(exception_count: int) -> str:
    if exception_count < 0:
        raise ValueError("Exception count cannot be negative")

    if exception_count <= 3:
        return "A+"
    if exception_count <= 6:
        return "A"
    if exception_count <= 9:
        return "B"
    if exception_count <= 12:
        return "C"
    return "D"


def learning_level_from_rank_pct(rank_pct: float) -> str:
    return final_level_from_rank_pct(rank_pct)
