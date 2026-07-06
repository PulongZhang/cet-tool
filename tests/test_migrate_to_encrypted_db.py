import sqlite3

import pytest

import migrate_to_encrypted_db as mig


def _seed_plain_db(path: str) -> None:
    """造一个含真实 schema 抽样的明文库(用标准 sqlite3 建库,模拟历史数据)。"""
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        create table user_account(id integer primary key, username text);
        create table evaluation_cycle(id integer primary key, cycle_name text);
        insert into user_account values (1, 'admin');
        insert into evaluation_cycle values (7, '2026-Q2 演示周期');
        """
    )
    conn.commit()
    conn.close()


def test_migrate_produces_encrypted_db_with_same_rows(tmp_path):
    plain = tmp_path / "plain.sqlite3"
    enc = tmp_path / "enc.sqlite3"
    _seed_plain_db(str(plain))

    rows_before = mig.table_row_counts(sqlite3.connect(str(plain)))

    mig.migrate(str(plain), str(enc), "a" * 64)

    # migrate 后:加密库就位到 source 路径(plain),target(enc)被移走
    assert plain.exists()
    assert not enc.exists()

    # 加密:普通 sqlite3 打不开 plain
    plain_open = sqlite3.connect(str(plain))
    try:
        plain_open.execute("select count(*) from user_account").fetchone()
        raise AssertionError("迁移后 plain 应加密,普通 sqlite3 不应能读取")
    except sqlite3.DatabaseError:
        pass
    finally:
        plain_open.close()

    # 行数一致(用项目 connect 读加密库)
    from performance_app.db import connect
    conn = connect(str(plain), "a" * 64)
    rows_after = mig.table_row_counts(conn)
    conn.close()
    assert rows_before == rows_after


def test_migrate_leaves_plain_backup(tmp_path):
    plain = tmp_path / "plain.sqlite3"
    enc = tmp_path / "enc.sqlite3"
    _seed_plain_db(str(plain))
    mig.migrate(str(plain), str(enc), "a" * 64)
    backups = list(tmp_path.glob("plain.sqlite3.bak-plaintext-*"))
    assert backups, "应保留明文备份"


def test_migrate_aborts_on_row_count_mismatch(tmp_path):
    """校验失败时不替换原文件。"""
    plain = tmp_path / "plain.sqlite3"
    enc = tmp_path / "enc.sqlite3"
    _seed_plain_db(str(plain))
    with pytest.raises(RuntimeError):
        mig.migrate(str(plain), str(enc), "a" * 64, fail_verification=True)
    # 原明文文件未被替换
    assert plain.exists()
