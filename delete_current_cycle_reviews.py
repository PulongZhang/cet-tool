from __future__ import annotations

from pathlib import Path

from reset_current_cycle_reviews import DEFAULT_DATABASE, reset_current_cycle_reviews


def delete_current_cycle_reviews(database_path: str | Path = DEFAULT_DATABASE) -> dict:
    return reset_current_cycle_reviews(database_path)


def main() -> None:
    result = delete_current_cycle_reviews()
    if result["cycle_id"] is None:
        print("没有找到进行中的周期，未重置任何评审记录。")
        return
    print("注意：该兼容脚本现在执行的是“重置评审记录”，不是留下空记录。")
    print(f"当前周期：{result['cycle_name']}（ID: {result['cycle_id']}）")
    print(f"备份文件：{result['backup_path']}")
    print(f"删除调整日志：{result['deleted_adjustment_logs']} 条")
    print(f"删除旧评审记录：{result['deleted_evaluation_records']} 条")
    print(f"新建初始评审记录：{result['created_evaluation_records']} 条")
    print("当前周期已恢复到员工可重新自评的初始状态。")


if __name__ == "__main__":
    main()
