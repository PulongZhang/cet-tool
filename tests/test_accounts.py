import re

from performance_app import create_app
from performance_app.repositories.accounts import ensure_account, generate_random_password


def make_app(tmp_path):
    return create_app({"TESTING": True, "DATABASE": str(tmp_path / "app.sqlite3")})


def test_generate_random_password_has_expected_format():
    password = generate_random_password()
    assert len(password) == 10
    assert re.fullmatch(r"[A-Za-z0-9]{10}", password)


def test_generate_random_password_is_unique_across_calls():
    passwords = {generate_random_password() for _ in range(20)}
    assert len(passwords) == 20


def test_ensure_account_marks_new_account_as_created(tmp_path):
    app = make_app(tmp_path)
    with app.app_context():
        user, created = ensure_account("NEW001", "NEW001", "whatever", ["EMPLOYEE"])
        assert created is True
        assert user["emp_id"] == "NEW001"


def test_ensure_account_marks_existing_account_as_not_created(tmp_path):
    app = make_app(tmp_path)
    with app.app_context():
        ensure_account("NEW001", "NEW001", "first", ["EMPLOYEE"])
        user, created = ensure_account("NEW001", "NEW001", "second", ["EMPLOYEE"])
        assert created is False
        assert user["emp_id"] == "NEW001"
