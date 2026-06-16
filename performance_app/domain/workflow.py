TRANSITIONS = {
    ("SELF_PENDING", "save_self_draft"): "SELF_DRAFT",
    ("SELF_DRAFT", "save_self_draft"): "SELF_DRAFT",
    ("SELF_PENDING", "submit_self"): "DIRECT_PENDING",
    ("SELF_DRAFT", "submit_self"): "DIRECT_PENDING",
    ("DIRECT_PENDING", "save_manager_draft"): "DIRECT_DRAFT",
    ("DIRECT_DRAFT", "save_manager_draft"): "DIRECT_DRAFT",
    ("DIRECT_PENDING", "submit_manager"): "INDIRECT_PENDING",
    ("DIRECT_DRAFT", "submit_manager"): "INDIRECT_PENDING",
    ("INDIRECT_PENDING", "submit_indirect"): "DEPT_HEAD_PENDING",
    ("DEPT_HEAD_PENDING", "submit_dept_head"): "HR_PENDING",
    ("HR_PENDING", "calculate"): "COMPLETED",
}

WITHDRAW_TARGETS = {
    "DIRECT_PENDING": "SELF_DRAFT",
    "INDIRECT_PENDING": "DIRECT_DRAFT",
    "DEPT_HEAD_PENDING": "INDIRECT_PENDING",
    "HR_PENDING": "DEPT_HEAD_PENDING",
    "COMPLETED": "COMPLETED",
}


def next_status(current_status: str, action: str) -> str:
    key = (current_status, action)
    if key not in TRANSITIONS:
        raise ValueError(f"Invalid transition: {current_status} via {action}")
    return TRANSITIONS[key]


def withdraw_status(current_status: str) -> str:
    if current_status not in WITHDRAW_TARGETS:
        raise ValueError(f"Cannot withdraw from status: {current_status}")
    return WITHDRAW_TARGETS[current_status]
