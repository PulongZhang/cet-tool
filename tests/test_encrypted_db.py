import sqlite3

from performance_app.db import connect


def test_connect_creates_encrypted_db_unreadable_by_plain_sqlite3(tmp_path):
    """加密后,普通 sqlite3 必须打不开文件。"""
    db = tmp_path / "enc.sqlite3"
    key = "a" * 64  # 32 字节 raw key 的 hex

    conn = connect(str(db), key)
    conn.execute("create table t(id integer, name text)")
    conn.execute("insert into t values (1, '机密绩效')")
    conn.commit()
    conn.close()

    plain = sqlite3.connect(str(db))
    try:
        plain.execute("select * from t").fetchone()
        raise AssertionError("普通 sqlite3 不应能读取加密库")
    except sqlite3.DatabaseError as e:
        assert "not a database" in str(e).lower() or "file is not" in str(e).lower()
    finally:
        plain.close()


def test_connect_wrong_key_raises_immediately(tmp_path):
    """错密钥在连接阶段即抛错,而非延迟到业务查询。"""
    import sqlcipher3

    db = tmp_path / "enc.sqlite3"
    key = "a" * 64
    wrong = "b" * 64

    conn = connect(str(db), key)
    conn.execute("create table t(id integer)")
    conn.commit()
    conn.close()

    try:
        connect(str(db), wrong)  # 应在内部 select count(*) 处抛错
        raise AssertionError("错密钥不应成功连接")
    except sqlcipher3.DatabaseError as e:
        assert "not a database" in str(e).lower()


def test_connect_correct_key_round_trips_chinese(tmp_path):
    """对密钥能正确读写中文。"""
    db = tmp_path / "enc.sqlite3"
    key = "a" * 64

    conn = connect(str(db), key)
    conn.execute("create table t(id integer, name text)")
    conn.execute("insert into t values (1, '机密绩效')")
    conn.commit()
    conn.close()

    conn = connect(str(db), key)
    row = conn.execute("select name from t").fetchone()
    conn.close()
    assert row[0] == "机密绩效"
