from flask import Blueprint, jsonify

health_bp = Blueprint("health", __name__)


@health_bp.get("")
def health_check():
    return jsonify({"success": True, "data": {"status": "ok"}, "message": None, "error": None})
