from performance_app.domain.constants import (
    EMPLOYEE_LEVELS_P1_3,
    EMPLOYEE_LEVELS_P4_10,
    GROUP_EMPLOYEE_P1_3,
    GROUP_EMPLOYEE_P4_10,
    GROUP_MANAGEMENT,
    SEQUENCE_EMPLOYEE,
    SEQUENCE_MANAGEMENT,
)


def derive_group_code(sequence: str, level: str) -> str:
    normalized_sequence = sequence.strip()
    normalized_level = level.strip().upper()

    if normalized_sequence == SEQUENCE_MANAGEMENT:
        return GROUP_MANAGEMENT

    if normalized_sequence != SEQUENCE_EMPLOYEE:
        raise ValueError(f"Unsupported sequence: {sequence}")

    if normalized_level in EMPLOYEE_LEVELS_P1_3:
        return GROUP_EMPLOYEE_P1_3

    if normalized_level in EMPLOYEE_LEVELS_P4_10:
        return GROUP_EMPLOYEE_P4_10

    raise ValueError(f"Unsupported employee level: {level}")
