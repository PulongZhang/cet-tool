"""一次性生成数据库加密密钥的工具。

用法:
    python -m performance_app.generate_key

将输出的 DB_ENCRYPTION_KEY 配置到环境变量(建议写入不入库的 .env)。
密钥丢失则加密数据库不可恢复,请妥善保管(密码本/1Password)。
"""
from __future__ import annotations

import secrets


def main() -> None:
    key = secrets.token_hex(32)  # 32 字节 = 256 bit,AES-256 raw key(hex 编码)
    print(f"DB_ENCRYPTION_KEY={key}")
    print(
        "请妥善保管此密钥(丢失则数据库不可恢复)。"
        "配置方式:设置系统环境变量 DB_ENCRYPTION_KEY,或写入不入库的 .env。",
        flush=True,
    )


if __name__ == "__main__":
    main()
