import sqlite3
from datetime import datetime

# 连接数据库
conn = sqlite3.connect(r'd:\AI工作台\cet-tool\data\performance_review.sqlite3')
cursor = conn.cursor()

cycle_id = 6

# 查找需要修复的记录：状态为 DEPT_HEAD_PENDING 但没有部门负责人
cursor.execute('''
    SELECT r.id, s.emp_id, s.emp_name, s.dept_head_id, r.initial_total_grade,
           r.manager_score_1, r.manager_score_2, r.manager_score_3
    FROM evaluation_record r
    JOIN cycle_employee_snapshot s ON s.cycle_id = r.cycle_id AND s.emp_id = r.emp_id
    WHERE r.cycle_id = ? AND r.status = 'DEPT_HEAD_PENDING'
      AND (s.dept_head_id IS NULL OR s.dept_head_id = '')
''', (cycle_id,))

records_to_fix = cursor.fetchall()
print(f"找到 {len(records_to_fix)} 条需要修复的记录")

# 修复这些记录：将状态更新为 HR_PENDING，并设置最终等级
for rec in records_to_fix:
    record_id = rec[0]
    emp_id = rec[1]
    emp_name = rec[2]
    dept_head = rec[3]
    initial_grade = rec[4]
    score_1 = rec[5]
    score_2 = rec[6]
    score_3 = rec[7]

    cursor.execute('''
        UPDATE evaluation_record
        SET status = 'HR_PENDING',
            final_subjective_grade_1 = manager_score_1,
            final_subjective_grade_2 = manager_score_2,
            final_subjective_grade_3 = manager_score_3,
            final_level = initial_total_grade,
            updated_at = datetime('now')
        WHERE id = ?
    ''', (record_id,))

    print(f"  [{emp_id} {emp_name}] DEPT_HEAD_PENDING -> HR_PENDING (final_level={initial_grade})")

conn.commit()

# 验证修复结果
cursor.execute('''
    SELECT status, COUNT(*) as count
    FROM evaluation_record
    WHERE cycle_id = 6
    GROUP BY status
    ORDER BY status
''')

print("\n修复后的状态分布:")
for row in cursor.fetchall():
    print(f"  {row[0]}: {row[1]} 条")

# 确认没有 DEPT_HEAD_PENDING 且没有部门负责人的记录
cursor.execute('''
    SELECT COUNT(*)
    FROM evaluation_record r
    JOIN cycle_employee_snapshot s ON s.cycle_id = r.cycle_id AND s.emp_id = r.emp_id
    WHERE r.cycle_id = 6 AND r.status = 'DEPT_HEAD_PENDING'
      AND (s.dept_head_id IS NULL OR s.dept_head_id = '')
''')

count = cursor.fetchone()[0]
print(f"\n剩余 DEPT_HEAD_PENDING 且无部门负责人的记录: {count} 条")

if count == 0:
    print('验证通过：所有记录已正确处理')

conn.close()
print("\n=== 修复完成 ===")
