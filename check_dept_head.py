import sqlite3
conn = sqlite3.connect('data/performance_review.sqlite3')
conn.row_factory = sqlite3.Row

print('=== 所有员工详细信息 ===')
rows = conn.execute('''
    SELECT s.emp_id, s.emp_name, s.dept_level_4, s.direct_manager_id, s.indirect_manager_id, s.dept_head_id, r.status
    FROM evaluation_record r
    JOIN cycle_employee_snapshot s ON s.cycle_id = r.cycle_id AND s.emp_id = r.emp_id
    WHERE s.emp_id NOT IN ('employee', 'direct', 'indirect', 'dept')
    ORDER BY s.emp_id
''').fetchall()
for r in rows:
    print(f'{r["emp_id"]} | {r["emp_name"]} | {r["dept_level_4"]} | 直管:{r["direct_manager_id"]} | 间管:{r["indirect_manager_id"]} | 部门负责人:{r["dept_head_id"]} | 状态:{r["status"]}')

print('\n=== 000825作为部门负责人的员工 ===')
rows = conn.execute('''
    SELECT s.emp_id, s.emp_name, r.status
    FROM evaluation_record r
    JOIN cycle_employee_snapshot s ON s.cycle_id = r.cycle_id AND s.emp_id = r.emp_id
    WHERE s.dept_head_id = "000825" AND s.emp_id NOT IN ('employee', 'direct', 'indirect', 'dept')
    ORDER BY s.emp_id
''').fetchall()
print(f'共 {len(rows)} 人')
for r in rows:
    print(f'  {r["emp_id"]} | {r["emp_name"]} | {r["status"]}')

print('\n=== 部门负责人账号信息 ===')
users = conn.execute('''
    SELECT ua.emp_id, ua.username
    FROM user_account ua
    JOIN user_role ur ON ur.user_id = ua.id
    WHERE ur.role_code = "DEPT_HEAD"
    ORDER BY ua.emp_id
''').fetchall()
for u in users:
    # 获取对应的员工姓名
    emp = conn.execute('SELECT emp_name FROM cycle_employee_snapshot WHERE emp_id = ? LIMIT 1', (u["emp_id"],)).fetchone()
    emp_name = emp["emp_name"] if emp else "未知"
    print(f'  工号: {u["emp_id"]} | 用户名: {u["username"]} | 姓名: {emp_name}')

conn.close()
