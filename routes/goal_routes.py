from datetime import date

from flask import Blueprint, jsonify, redirect, render_template, request, url_for

from services.goal_service import (
    create_goal,
    get_goal_progress_list,
    validate_goal_payload,
)
from utils.date_utils import normalize_month

bp = Blueprint("goal_routes", __name__)


@bp.route("/goals", methods=["GET", "POST"], endpoint="goals_page")
def goals_page():
    month = normalize_month(request.values.get("month"))
    if request.method == "POST":
        payload = {
            "name": request.form.get("name"),
            "target_amount": request.form.get("target_amount"),
            "deadline": request.form.get("deadline"),
            "note": request.form.get("note"),
        }
        normalized_data, error = validate_goal_payload(payload)
        if not normalized_data:
            return redirect(url_for("goal_routes.goals_page", month=month, success="0", error=error))

        create_goal(**normalized_data)
        return redirect(url_for("goal_routes.goals_page", month=month, success="1"))

    success = request.args.get("success")
    error = request.args.get("error")
    goals = get_goal_progress_list()
    return render_template(
        "goals.html",
        active_page="goals",
        month=month,
        today=date.today().isoformat(),
        success=success,
        error=error,
        goals=goals,
    )


@bp.route("/api/goals", methods=["POST"], endpoint="create_goal_api")
def create_goal_api():
    payload = request.get_json(silent=True) or {}
    normalized_data, error = validate_goal_payload(payload)
    if not normalized_data:
        return jsonify({"error": error or "invalid payload"}), 400

    goal_id = create_goal(**normalized_data)
    return jsonify({"id": goal_id}), 201


@bp.route("/api/goals", methods=["GET"], endpoint="list_goals_api")
def list_goals_api():
    return jsonify(get_goal_progress_list())
