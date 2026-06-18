create table if not exists schema_version (
    id integer primary key autoincrement,
    version integer not null,
    applied_at text not null
);

create table if not exists role_catalog (
    role_code text primary key,
    role_name text not null
);

insert or ignore into role_catalog (role_code, role_name) values
    ('EMPLOYEE', '被考核员工'),
    ('DIRECT_MANAGER', '直接上级'),
    ('INDIRECT_MANAGER', '间接上级'),
    ('DEPT_HEAD', '部门负责人'),
    ('HRBP', 'HR 数据处理员'),
    ('ADMIN', '管理员');

create table if not exists user_account (
    id integer primary key autoincrement,
    emp_id text unique not null,
    username text unique not null,
    password_hash text not null,
    status text not null default 'ACTIVE',
    last_login_at text,
    created_at text not null default (datetime('now'))
);

create table if not exists user_role (
    id integer primary key autoincrement,
    user_id integer not null references user_account(id),
    role_code text not null references role_catalog(role_code),
    unique(user_id, role_code)
);

create table if not exists evaluation_cycle (
    id integer primary key autoincrement,
    cycle_name text unique not null,
    start_date text not null,
    end_date text not null,
    status text not null default 'PREPARING',
    created_by text not null,
    created_at text not null default (datetime('now'))
);

create table if not exists cycle_employee_snapshot (
    id integer primary key autoincrement,
    cycle_id integer not null references evaluation_cycle(id) on delete cascade,
    emp_id text not null,
    emp_name text not null,
    sequence text not null,
    level text not null,
    group_code text not null,
    dept_name text not null,
    dept_level_1 text,
    dept_level_2 text,
    dept_level_3 text,
    dept_level_4 text,
    post text,
    direct_manager_id text not null,
    indirect_manager_id text not null,
    dept_head_id text not null,
    active integer not null default 1,
    unique(cycle_id, emp_id)
);

create table if not exists evaluation_record (
    id integer primary key autoincrement,
    cycle_id integer not null references evaluation_cycle(id) on delete cascade,
    emp_id text not null,
    status text not null default 'SELF_PENDING',
    self_summary text,
    self_score_1 text,
    self_score_2 text,
    self_score_3 text,
    manager_score_1 text,
    manager_score_2 text,
    manager_score_3 text,
    manager_comment text,
    initial_total_grade text,
    current_subjective_level text,
    final_subjective_grade_1 text,
    final_subjective_grade_2 text,
    final_subjective_grade_3 text,
    suggested_subjective_level text,
    weighted_score real,
    rank_in_group integer,
    rank_total integer,
    suggested_level text,
    final_level text,
    special_reason text,
    self_skipped_due_to_timeout integer not null default 0,
    submitted_at text,
    updated_at text not null default (datetime('now')),
    unique(cycle_id, emp_id)
);

create table if not exists grade_adjustment_log (
    id integer primary key autoincrement,
    cycle_id integer not null references evaluation_cycle(id),
    record_id integer not null references evaluation_record(id),
    stage text not null,
    adjustment_type text not null,
    field_name text not null,
    before_value text,
    after_value text,
    reason text not null,
    operator_id text not null,
    operator_name text not null,
    adjusted_at text not null default (datetime('now'))
);

create table if not exists objective_data (
    id integer primary key autoincrement,
    cycle_id integer not null references evaluation_cycle(id) on delete cascade,
    emp_id text not null,
    diligence_raw_total real not null,
    diligence_month_avg real not null,
    diligence_level text not null,
    discipline_raw_count integer not null,
    discipline_level text not null,
    learning_hours real not null,
    learning_rank_pct real,
    learning_level text,
    corrected integer not null default 0,
    correction_reason text,
    updated_at text not null default (datetime('now')),
    unique(cycle_id, emp_id)
);

create table if not exists import_batch (
    id integer primary key autoincrement,
    cycle_id integer references evaluation_cycle(id),
    import_type text not null,
    file_name text not null,
    total_count integer not null default 0,
    success_count integer not null default 0,
    failed_count integer not null default 0,
    operator_id text not null,
    imported_at text not null default (datetime('now'))
);

create table if not exists import_error (
    id integer primary key autoincrement,
    batch_id integer not null references import_batch(id) on delete cascade,
    row_number integer not null,
    emp_id text,
    field_name text not null,
    error_message text not null,
    raw_data text not null
);

create table if not exists audit_log (
    id integer primary key autoincrement,
    cycle_id integer,
    operator_id text not null,
    operator_name text not null,
    action text not null,
    target_type text not null,
    target_id text not null,
    before_snapshot text,
    after_snapshot text,
    reason text,
    ip_address text,
    user_agent text,
    created_at text not null default (datetime('now'))
);

create index if not exists idx_record_cycle_status on evaluation_record(cycle_id, status);
create index if not exists idx_snapshot_direct_manager on cycle_employee_snapshot(cycle_id, direct_manager_id);
create index if not exists idx_snapshot_indirect_manager on cycle_employee_snapshot(cycle_id, indirect_manager_id);
create index if not exists idx_snapshot_dept_head on cycle_employee_snapshot(cycle_id, dept_head_id);
create index if not exists idx_audit_target on audit_log(target_type, target_id);
