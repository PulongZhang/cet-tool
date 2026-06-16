from __future__ import annotations

import json
from typing import Any

from performance_app.db import get_db


def write_audit_log(
    *,
    action: str,
    target_type: str,
    target_id: str | int,
    operator_id: str,
    operator_name: str,
    cycle_id: int | None = None,
    before_snapshot: dict[str, Any] | None = None,
    after_snapshot: dict[str, Any] | None = None,
    reason: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    get_db().execute(
        """
        insert into audit_log
            (cycle_id, operator_id, operator_name, action, target_type, target_id,
             before_snapshot, after_snapshot, reason, ip_address, user_agent)
        values
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            cycle_id,
            operator_id,
            operator_name,
            action,
            target_type,
            str(target_id),
            json.dumps(before_snapshot, ensure_ascii=False) if before_snapshot else None,
            json.dumps(after_snapshot, ensure_ascii=False) if after_snapshot else None,
            reason,
            ip_address,
            user_agent,
        ),
    )
