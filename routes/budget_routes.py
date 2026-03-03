from datetime import date

from flask import Blueprint, jsonify, redirect, render_template, request, url_for

from config import CATEGORY_OPTIONS
from services.budget_service import get_budget_execution, get_budget_health_profile, upsert_budget

bp = Blueprint("budget_routes", __name__)


@bp.route("/budget", methods=["GET", "POST"], endpoint="budget_page")
def budget_page():
    month = request.values.get("month") or date.today().strftime("%Y-%m")

    if request.method == "POST":
        budget_month = request.form.get("month") or month
        category_main = request.form.get("category_main") or None
        budget_amount = request.form.get("budget_amount", type=float)
        if budget_amount and budget_amount > 0:
            upsert_budget(budget_month, category_main, budget_amount)
            return redirect(url_for("budget_routes.budget_page", month=budget_month, success="1"))
        return redirect(url_for("budget_routes.budget_page", month=budget_month, success="0"))

    success = request.args.get("success")
    budget_data = get_budget_execution(month)
    budget_health = get_budget_health_profile(month)
    return render_template(
        "budget.html",
        active_page="budget",
        month=month,
        success=success,
        category_options=CATEGORY_OPTIONS,
        budget_data=budget_data,
        budget_health=budget_health,
    )


@bp.route("/api/budgets", methods=["POST"], endpoint="create_budget_api")
def create_budget_api():
    payload = request.get_json(silent=True) or {}
    month = payload.get("month")
    budget_amount = payload.get("budget_amount")
    if not month or budget_amount in (None, ""):
        return jsonify({"error": "month and budget_amount are required"}), 400

    category_main = payload.get("category_main") or None
    budget_id = upsert_budget(month, category_main, float(budget_amount))
    return jsonify({"id": budget_id}), 201


@bp.route("/api/budgets", methods=["GET"], endpoint="list_budget_api")
def list_budget_api():
    month = request.args.get("month") or date.today().strftime("%Y-%m")
    execution = get_budget_execution(month)
    health = get_budget_health_profile(month)
    return jsonify(
        {
            **execution,
            "health_score": health.get("score", {}),
            "category_risks": health.get("category_risks", {}),
            "risk_hints": health.get("risk_hints", []),
            "budget_trends": health.get("trends", {}),
        }
    )


@bp.route("/api/budgets/health", methods=["GET"], endpoint="budget_health_api")
def budget_health_api():
    month = request.args.get("month") or date.today().strftime("%Y-%m")
    return jsonify(get_budget_health_profile(month))
