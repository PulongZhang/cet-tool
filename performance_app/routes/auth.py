from __future__ import annotations

from flask import Blueprint, jsonify, request
from werkzeug.security import check_password_hash

from performance_app.repositories.accounts import find_by_id, find_by_username

bp = Blueprint("auth", __name__)


def public_user(user: dict) -> dict:
    return {
        "id": user["id"],
        "emp_id": user["emp_id"],
        "username": user["username"],
        "roles": user["roles"],
    }


@bp.post("/auth/login")
def login():
    payload = request.get_json(silent=True) or {}
    username = payload.get("username")
    password = payload.get("password")

    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    user = find_by_username(username)
    if (
        user is None
        or user.get("status") != "ACTIVE"
        or not check_password_hash(user["password_hash"], password)
    ):
        return jsonify({"error": "invalid username or password"}), 401

    return jsonify({"user": public_user(user)})


@bp.post("/auth/logout")
def logout():
    return jsonify({"status": "ok"})


@bp.get("/auth/me")
def me():
    user_id = request.headers.get("X-User-Id")
    if not user_id:
        return jsonify({"error": "X-User-Id header is required"}), 401

    try:
        parsed_user_id = int(user_id)
    except ValueError:
        return jsonify({"error": "X-User-Id header must be an integer"}), 400

    user = find_by_id(parsed_user_id)
    if user is None or user.get("status") != "ACTIVE":
        return jsonify({"error": "user not found"}), 404

    return jsonify({"user": public_user(user)})
