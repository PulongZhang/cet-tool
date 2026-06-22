import sqlite3
conn = sqlite3.connect('data/performance_review.sqlite3')
conn.row_factory = sqlite3.Row

# 模拟查询：dept_head_id = 000825 且 emp_id != 000825
print('=== 模拟查询结果 (dept_head_id = 000825 且 emp_id != 000825) ===')
rows = conn.execute('''
    SELECT s.emp_id, s.emp_name, s.dept_head_id, r.status
    FROM evaluation_record r
    JOIN cycle_employee_snapshot s ON s.cycle_id = r.cycle_id AND s.emp_id = r.emp_id
    WHERE s.dept_head_id = "000825" AND s.emp_id != "000825"
    ORDER BY s.emp_id
''').fetchall()
print(f'共 {len(rows)} 人')
for r in rows:
    print(f'{r["emp_id"]} | {r["emp_name"]} | dept_head_id:{r["dept_head_id"]} | 状态:{r["status"]}')

print('\n=== 检查 000825 和 000010 的 dept_head_id ===')
for emp_id in ['000825', '000010']:
    row = conn.execute('SELECT emp_id, emp_name, dept_head_id FROM cycle_employee_snapshot WHERE emp_id = ?', (emp_id,)).fetchone()
    if row:
        print(f'{row["emp_id"]} | {row["emp_name"]} | dept_head_id:{row["dept_head_id"]}')

print('\n=== 检查王鹏(000825)账号的角色 ===')
user = conn.execute('SELECT ua.emp_id, ur.role_code FROM user_account ua JOIN user_role ur ON ur.user_id = ua.id WHERE ua.emp_id = "000825"').fetchall()
for u in user:
    print(f'  {u["emp_id"]} | {u["role_code"]}')

print('\n=== 所有 dept_head_id = 000825 的记录（不过滤 emp_id） ===')
rows = conn.execute('''
    SELECT s.emp_id, s.emp_name, s.dept_head_id, r.status
    FROM evaluation_record r
    JOIN cycle_employee_snapshot s ON s.cycle_id = r.cycle_id AND s.emp_id = r.emp_id
    WHERE s.dept_head_id = "000825"
    ORDER BY s.emp_id
''').fetchall()
print(f'共 {len(rows)} 人')
for r in rows:
    print(f'{r["emp_id"]} | {r["emp_name"]} | 状态:{r["status"]}')

conn.close()
