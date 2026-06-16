def can_view_record(user: dict, record: dict) -> bool:
    roles = set(user.get("roles", []))
    emp_id = user.get("emp_id")

    if "HRBP" in roles or "ADMIN" in roles:
        return True
    if "EMPLOYEE" in roles and record.get("emp_id") == emp_id:
        return True
    if "DIRECT_MANAGER" in roles and record.get("direct_manager_id") == emp_id:
        return True
    if "INDIRECT_MANAGER" in roles and record.get("indirect_manager_id") == emp_id:
        return True
    if "DEPT_HEAD" in roles and record.get("dept_head_id") == emp_id:
        return True
    return False
