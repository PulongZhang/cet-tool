import sqlite3
from datetime import datetime

# 连接数据库
conn = sqlite3.connect(r'd:\AI工作台\cet-tool\data\performance_review.sqlite3')
cursor = conn.cursor()

cycle_id = 6

# 修复缺少final_subjective_grade的记录
# 将manager_score复制到final_subjective_grade
cursor.execute('''
    UPDATE evaluation_record
    SET final_subjective_grade_1 = manager_score_1,
        final_subjective_grade_2 = manager_score_2,
        final_subjective_grade_3 = manager_score_3,
        updated_at = datetime('now')
    WHERE cycle_id = ?
      AND status = 'HR_PENDING'
      AND (final_subjective_grade_1 IS NULL OR final_subjective_grade_1 = '')
''', (cycle_id,))

count = cursor.rowcount
print(f"修复了 {count} 条记录的final_subjective_grade字段")

conn.commit()

# 验证修复结果
cursor.execute('''
    SELECT
        COUNT(CASE WHEN final_subjective_grade_1 IS NULL OR final_subjective_grade_1 = '' THEN 1 END) as missing
    FROM evaluation_record
    WHERE cycle_id = 6 AND status = 'HR_PENDING'
''')

missing = cursor.fetchone()[0]
print(f"\n修复后仍缺少final_subjective_grade的记录数: {missing}")

if missing == 0:
    print('验证通过：所有HR_PENDING记录都有final_subjective_grade数据')

conn.close()
print("\n=== 修复完成 ===")
