import sqlite3
from datetime import datetime

# 连接数据库
conn = sqlite3.connect(r'd:\AI工作台\cet-tool\data\performance_review.sqlite3')
cursor = conn.cursor()

cycle_id = 6

# 查找需要修复的记录：indirect_manager_id 为空但状态为 INDIRECT_PENDING
cursor.execute('''
    SELECT r.id, s.emp_id, s.emp_name, s.indirect_manager_id, s.dept_head_id
    FROM evaluation_record r
    JOIN cycle_employee_snapshot s ON s.cycle_id = r.cycle_id AND s.emp_id = r.emp_id
    WHERE r.cycle_id = ? AND r.status = 'INDIRECT_PENDING'
      AND (s.indirect_manager_id IS NULL OR s.indirect_manager_id = '')
''', (cycle_id,))

records_to_fix = cursor.fetchall()
print(f"找到 {len(records_to_fix)} 条需要修复的记录")

# 修复这些记录：将状态更新为 DEPT_HEAD_PENDING
for rec in records_to_fix:
    record_id = rec[0]
    emp_id = rec[1]
    emp_name = rec[2]
    indirect = rec[3]
    dept_head = rec[4]

    cursor.execute('''
        UPDATE evaluation_record
        SET status = 'DEPT_HEAD_PENDING',
            updated_at = datetime('now')
        WHERE id = ?
    ''', (record_id,))

    print(f"  [{emp_id} {emp_name}] INDIRECT_PENDING -> DEPT_HEAD_PENDING (indirect={indirect}, dept_head={dept_head})")

conn.commit()

# 验证修复结果
cursor.execute('''
    SELECT status, COUNT(*) as count
    FROM evaluation_record
    WHERE cycle_id = 6
    GROUP BY status
    ORDER BY status
''')

print(f"\n修复后的状态分布:")
for row in cursor.fetchall():
    print(f"  {row[0]}: {row[1]} 条")

conn.close()
print(f"\n=== 修复完成 ===")
