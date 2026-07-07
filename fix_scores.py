import openpyxl
import sqlite3
from datetime import datetime
import random

# 使用固定随机种子确保每次运行结果一致
random.seed(42)

# 读取Excel数据
wb = openpyxl.load_workbook(r'D:\绩效系统test\test-数据.xlsx')
ws = wb.active

# 构建工号到评分数据的映射
score_map = {}
for row in ws.iter_rows(min_row=2, values_only=True):
    if row[1]:  # 工号不为空
        emp_id = str(row[1]).strip()
        # H列(索引7)是老板初始总评，如果为空或"无"则随机生成
        boss_initial = str(row[7]).strip() if row[7] else None
        if not boss_initial or boss_initial in ['无', 'None', '', '无']:
            boss_initial = random.choice(['A', 'B+', 'B', 'B-', 'C'])

        score_map[emp_id] = {
            'manager_score_1': str(row[5]).strip() if row[5] else None,
            'manager_score_2': str(row[6]).strip() if row[6] else None,
            'manager_score_3': str(row[7]).strip() if len(row) > 7 and row[7] else None,
            'initial_total_grade': boss_initial,  # 从H列读取老板初始总评
        }

print(f"Excel中读取到 {len(score_map)} 条评分数据")

# 连接数据库
conn = sqlite3.connect(r'd:\AI工作台\cet-tool\data\performance_review.sqlite3')
cursor = conn.cursor()

cycle_id = 6

# 获取所有已评分的记录（DIRECT_DRAFT状态）
cursor.execute('''
    SELECT r.id, s.emp_id, s.emp_name, r.initial_total_grade, r.current_subjective_level,
           r.manager_score_1, r.manager_score_2, r.manager_score_3
    FROM cycle_employee_snapshot s
    JOIN evaluation_record r ON r.cycle_id = s.cycle_id AND r.emp_id = s.emp_id
    WHERE s.cycle_id = ? AND r.status = 'DIRECT_DRAFT'
    ORDER BY s.emp_id
''', (cycle_id,))

records = cursor.fetchall()
print(f"\n需要检查修正的记录数: {len(records)}")

total_updated = 0
for rec in records:
    record_id = rec[0]
    emp_id = rec[1]
    emp_name = rec[2]
    current_initial = rec[3]

    if emp_id not in score_map:
        print(f" [警告] {emp_id}({emp_name}) 在Excel中未找到")
        continue

    scores = score_map[emp_id]
    new_initial = scores['initial_total_grade']

    # 更新所有记录的初始总评（确保与Excel H列一致）
    cursor.execute('''
        UPDATE evaluation_record
        SET initial_total_grade = ?,
            current_subjective_level = ?,
            updated_at = datetime('now')
        WHERE id = ?
    ''', (new_initial, new_initial, record_id))
    total_updated += 1
    if current_initial != new_initial:
        print(f" [{emp_id}({emp_name})] 原初始总评:{current_initial} -> 新初始总评:{new_initial}")

conn.commit()
conn.close()

print("\n=== 修正完成 ===")
print(f"已更新: {total_updated} 条")
