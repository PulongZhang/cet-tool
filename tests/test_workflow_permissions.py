import pytest

from performance_app.domain.permissions import can_view_record
from performance_app.domain.workflow import next_status, withdraw_status


def test_next_status_allows_core_review_flow():
    assert next_status("SELF_PENDING", "save_self_draft") == "SELF_DRAFT"
    assert next_status("SELF_DRAFT", "submit_self") == "DIRECT_PENDING"
    assert next_status("DIRECT_PENDING", "submit_manager") == "INDIRECT_PENDING"
    assert next_status("INDIRECT_PENDING", "submit_indirect") == "DEPT_HEAD_PENDING"
    assert next_status("DEPT_HEAD_PENDING", "submit_dept_head") == "HR_PENDING"
    assert next_status("HR_PENDING", "calculate") == "COMPLETED"


def test_next_status_rejects_invalid_transition():
    with pytest.raises(ValueError, match="Invalid transition"):
        next_status("SELF_PENDING", "submit_manager")


def test_withdraw_status_matches_spec_matrix():
    assert withdraw_status("DIRECT_PENDING") == "SELF_DRAFT"
    assert withdraw_status("INDIRECT_PENDING") == "DIRECT_DRAFT"
    assert withdraw_status("DEPT_HEAD_PENDING") == "INDIRECT_PENDING"
    assert withdraw_status("HR_PENDING") == "DEPT_HEAD_PENDING"
    assert withdraw_status("COMPLETED") == "COMPLETED"


def test_can_view_record_uses_roles_and_data_scope():
    record = {
        "emp_id": "E001",
        "direct_manager_id": "M001",
        "indirect_manager_id": "M002",
        "dept_head_id": "M003",
    }

    assert can_view_record({"emp_id": "E001", "roles": ["EMPLOYEE"]}, record)
    assert can_view_record({"emp_id": "M001", "roles": ["DIRECT_MANAGER"]}, record)
    assert can_view_record({"emp_id": "M002", "roles": ["INDIRECT_MANAGER"]}, record)
    assert can_view_record({"emp_id": "M003", "roles": ["DEPT_HEAD"]}, record)
    assert can_view_record({"emp_id": "HR001", "roles": ["HRBP"]}, record)
    assert can_view_record({"emp_id": "ADMIN001", "roles": ["ADMIN"]}, record)
    assert not can_view_record({"emp_id": "E999", "roles": ["EMPLOYEE"]}, record)
