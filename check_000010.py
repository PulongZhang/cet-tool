import sqlite3
conn = sqlite3.connect('data/performance_review.sqlite3')
conn.row_factory = sqlite3.Row

print('=== 检查 dept_head_id = 000010 的记录 ===')
rows = conn.execute('''
    SELECT s.emp_id, s.emp_name, s.dept_head_id, r.status
    FROM evaluation_record r
    JOIN cycle_employee_snapshot s ON s.cycle_id = r.cycle_id AND s.emp_id = r.emp_id
    WHERE s.dept_head_id = "000010" AND s.emp_id != "000010"
    ORDER BY s.emp_id
''').fetchall()
print(f'共 {len(rows)} 人')
for r in rows:
    print(f'{r["emp_id"]} | {r["emp_name"]} | dept_head_id:{r["dept_head_id"]} | 状态:{r["status"]}')

print('\n=== 检查 dept_head_id = 000010 的记录（不过滤 emp_id） ===')
rows = conn.execute('''
    SELECT s.emp_id, s.emp_name, s.dept_head_id, r.status
    FROM evaluation_record r
    JOIN cycle_employee_snapshot s ON s.cycle_id = r.cycle_id AND s.emp_id = r.emp_id
    WHERE s.dept_head_id = "000010"
    ORDER BY s.emp_id
''').fetchall()
print(f'共 {len(rows)} 人')
for r in rows:
    print(f'{r["emp_id"]} | {r["emp_name"]} | dept_head_id:{r["dept_head_id"]} | 状态:{r["status"]}')

print('\n=== 检查 000010 账号的角色 ===')
user = conn.execute('SELECT ua.emp_id, ur.role_code FROM user_account ua JOIN user_role ur ON ur.user_id = ua.id WHERE ua.emp_id = "000010"').fetchall()
if user:
    for u in user:
        print(f'  {u["emp_id"]} | {u["role_code"]}')
else:
    print('  000010 账号不存在')

print('\n=== 检查所有以000010为dept_head_id的员工快照 ===')
rows = conn.execute('''
    SELECT emp_id, emp_name, dept_head_id
    FROM cycle_employee_snapshot
    WHERE dept_head_id = "000010"
''').fetchall()
for r in rows:
    print(f'{r["emp_id"]} | {r["emp_name"]} | dept_head_id:{r["dept_head_id"]}')

conn.close()
