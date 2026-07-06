"""把现有明文 SQLite 数据库迁移为 SQLCipher 加密数据库。

流程(官方 sqlcipher_export 推荐):
    1. 用 sqlcipher3 打开明文源(不设 key,按明文格式读写)
    2. ATTACH 新的加密库(raw key,与 performance_app.db.connect 一致)
    3. SELECT sqlcipher_export('enc')  复制全部 schema + 数据
    4. 逐表行数校验,不一致则中止(不替换原文件)
    5. 备份原文件为 .bak-plaintext-<时间戳>,用加密库替换原路径

用法:
    DB_ENCRYPTION_KEY=<密钥> python migrate_to_encrypted_db.py
    DB_ENCRYPTION_KEY=<密钥> python migrate_to_encrypted_db.py --source <path> --target <path>
"""
from __future__ import annotations

import argparse
import datetime as _dt
import gc
import os
import sys
import time
from pathlib import Path

import sqlcipher3


def table_row_counts(conn) -> dict[str, int]:
    """返回 {表名: 行数},用于迁移前后比对。"""
    tables = [
        r[0]
        for r in conn.execute(
            "select name from sqlite_master where type='table' and name not like 'sqlite_%'"
        ).fetchall()
    ]
    return {t: conn.execute(f"select count(*) from \"{t}\"").fetchone()[0] for t in tables}


def _replace_file(src: str, dst: str, retries: int = 20, delay: float = 0.1) -> None:
    """os.replace 的 Windows 友好版。

    sqlcipher3 连接 close() 后,底层文件句柄释放有延迟,立即 rename 会触发
    PermissionError(WinError 32)。显式 gc + 短暂重试以等待句柄释放。
    """
    last_err: Exception | None = None
    for _ in range(retries):
        gc.collect()
        try:
            os.replace(src, dst)
            return
        except PermissionError as exc:
            last_err = exc
            time.sleep(delay)
    assert last_err is not None
    raise last_err


def migrate(
    source: str,
    target: str,
    key: str,
    *,
    fail_verification: bool = False,
) -> None:
    """把 source(明文)迁移到 target(加密)。成功后 source 被重命名为 .bak-plaintext-<ts>。"""
    if not Path(source).exists():
        raise FileNotFoundError(f"源数据库不存在: {source}")

    # 明文源:sqlcipher3 不设 key 即按明文格式读写
    conn = sqlcipher3.connect(source)
    before = table_row_counts(conn)

    if Path(target).exists():
        Path(target).unlink()

    # ATTACH 必须用 raw key(x'..')与 db.connect() 一致;
    # 绑定参数会把 key 当 passphrase,导致迁移后 connect() 打不开。路径转正斜杠避免 Windows 转义。
    target_sql = str(target).replace("\\", "/")
    conn.execute(f"ATTACH DATABASE '{target_sql}' AS enc KEY \"x'{key}'\"")
    conn.execute("SELECT sqlcipher_export('enc')")
    conn.execute("DETACH DATABASE enc")

    # 校验:在同一连接读取已导出的加密库行数
    conn.execute(f"ATTACH DATABASE '{target_sql}' AS enc2 KEY \"x'{key}'\"")
    after = {
        t: conn.execute(f'SELECT count(*) FROM enc2."{t}"').fetchone()[0] for t in before
    }
    conn.execute("DETACH DATABASE enc2")
    conn.close()
    gc.collect()

    if fail_verification:
        after = {k: v + 9999 for k, v in after.items()}  # 仅测试用,制造不一致

    if before != after:
        raise RuntimeError(
            f"行数校验不一致,迁移中止(未替换原文件)。before={before} after={after}"
        )

    # 备份原明文,用加密库替换原路径
    ts = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = f"{source}.bak-plaintext-{ts}"
    _replace_file(source, backup)
    _replace_file(target, source)
    print(f"迁移成功。原明文已备份: {backup}")
    print(f"加密库已就位: {source}")
    print(f"行数校验通过: {before}")
    print("请确认无误后,手动删除明文备份。")


def main() -> int:
    parser = argparse.ArgumentParser(description="迁移明文 SQLite 为 SQLCipher 加密库")
    parser.add_argument("--source", default="data/performance_review.sqlite3")
    parser.add_argument("--target", default="data/performance_review.enc.sqlite3")
    args = parser.parse_args()

    key = os.environ.get("DB_ENCRYPTION_KEY")
    if not key:
        print("错误:未设置 DB_ENCRYPTION_KEY 环境变量", file=sys.stderr)
        return 2
    migrate(args.source, args.target, key)
    return 0


if __name__ == "__main__":
    sys.exit(main())
