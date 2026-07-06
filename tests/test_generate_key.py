import re
import io
from contextlib import redirect_stdout

from performance_app import generate_key


def test_generate_key_prints_64_hex_chars():
    buf = io.StringIO()
    with redirect_stdout(buf):
        generate_key.main()
    out = buf.getvalue()
    match = re.search(r"DB_ENCRYPTION_KEY=([0-9a-f]{64})", out)
    assert match is not None, f"输出未包含合法密钥: {out!r}"


def test_generate_key_output_is_random():
    buf1, buf2 = io.StringIO(), io.StringIO()
    with redirect_stdout(buf1):
        generate_key.main()
    with redirect_stdout(buf2):
        generate_key.main()
    assert buf1.getvalue() != buf2.getvalue()
