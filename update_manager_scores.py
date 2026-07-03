import openpyxl
import sqlite3
from datetime import datetime

# 读取Excel数据
wb = openpyxl.load_workbook(r'D:\绩效系统test\test-数据.xlsx')
ws = wb.active

# 构建工号到评分数据的映射（E/F/G/H列）
score_map = {}
for row in ws.iter_rows(min_row=2, values_only=True):
    if row[1]:  # 工号不为空
        emp_id = str(row[1]).strip()
        score_map[emp_id] = {
            'manager_score_1': str(row[4]).strip() if row[4] else None,  # E列：直接上级评分
            'manager_score_2': str(row[5]).strip() if row[5] else None,  # F列：团队协作/部门配合度
            'manager_score_3': str(row[6]).strip() if row[6] else None,  # G列：态度和可维护性/个人关键任务
            'initial_total_grade': str(row[7]).strip() if row[7] else None,  # H列：老板初始总评
        }

print(f"Excel中读取到 {len(score_map)} 条评分数据")

# 连接数据库
conn = sqlite3.connect(r'd:\AI工作台\cet-tool\data\performance_review.sqlite3')
cursor = conn.cursor()

cycle_id = 6
managers = ['002171', '002047']

for mgr in managers:
    print(f"\n=== 处理 {mgr} 的直接下属 ===")
    cursor.execute('''
        SELECT r.id, s.emp_id, s.emp_name, r.manager_score_1, r.manager_score_2, r.manager_score_3, r.initial_total_grade
        FROM cycle_employee_snapshot s
        JOIN evaluation_record r ON r.cycle_id = s.cycle_id AND r.emp_id = s.emp_id
        WHERE s.cycle_id = ? AND s.direct_manager_id = ?
        ORDER BY s.emp_id
    ''', (cycle_id, mgr))

    records = cursor.fetchall()
    for rec in records:
        record_id = rec[0]
        emp_id = rec[1]
        emp_name = rec[2]
        current_s1 = rec[3]
        current_s2 = rec[4]
        current_s3 = rec[5]
        current_init = rec[6]

        if emp_id not in score_map:
            print(f" [警告] {emp_id}({emp_name}) 在Excel中未找到")
            continue

        scores = score_map[emp_id]
        new_s1 = scores['manager_score_1']
        new_s2 = scores['manager_score_2']
        new_s3 = scores['manager_score_3']
        new_init = scores['initial_total_grade']

        # 检查是否有数据需要更新
        if new_s1 or new_s2 or new_s3 or new_init:
            cursor.execute('''
                UPDATE evaluation_record
                SET manager_score_1 = ?,
                    manager_score_2 = ?,
                    manager_score_3 = ?,
                    initial_total_grade = ?,
                    current_subjective_level = ?,
                    updated_at = datetime('now')
                WHERE id = ?
            ''', (new_s1, new_s2, new_s3, new_init, new_init, record_id))

            print(f" [{emp_id}({emp_name})]")
            if current_s1 != new_s1:
                print(f"   维度1: {current_s1} -> {new_s1}")
            if current_s2 != new_s2:
                print(f"   维度2: {current_s2} -> {new_s2}")
            if current_s3 != new_s3:
                print(f"   维度3: {current_s3} -> {new_s3}")
            if current_init != new_init:
                print(f"   初始总评: {current_init} -> {new_init}")

conn.commit()
conn.close()

print(f"\n=== 更新完成 ===")
