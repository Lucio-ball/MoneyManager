from datetime import date, datetime

from flask import Blueprint, jsonify, render_template, request

from services.analysis_service import get_monthly_insights
from services.budget_service import get_budget_execution, get_budget_health_profile
from services.dashboard_service import get_home_risk_cards
from services.goal_service import get_goal_dashboard_summary
from services.subscription_service import (
    get_subscription_monthly_cost_summary,
    get_subscription_monthly_metrics,
    get_upcoming_subscriptions,
)
from services.transaction_service import (
    get_calendar_daily_expense,
    get_calendar_day_details,
    create_transaction,
    get_category_trend,
    get_monthly_dashboard_data,
    get_monthly_stats,
    get_recent_transactions,
    get_tag_trend,
    get_today_expense,
    get_transactions_by_month,
    normalize_transaction_payload,
)
from utils.risk_utils import build_emotion_light

bp = Blueprint("transaction_routes", __name__)


@bp.route("/", endpoint="index")
def index():
    category_palette = ["#2563EB", "#0EA5E9", "#14B8A6", "#22C55E", "#F59E0B", "#EF4444"]
    month = request.args.get("month") or date.today().strftime("%Y-%m")
    dashboard = get_monthly_dashboard_data(month=month)
    monthly_stats = get_monthly_stats(month)
    budget_data = get_budget_execution(month)
    budget_health = get_budget_health_profile(month)

    current_month = date.today().strftime("%Y-%m")
    today_expense = get_today_expense() if month == current_month else 0.0
    top_categories = [
        {
            **item,
            "color": category_palette[index % len(category_palette)],
        }
        for index, item in enumerate(monthly_stats.get("category_stats", [])[:3])
    ]
    emotion_light = build_emotion_light(month, monthly_stats.get("total_expense", 0), budget_data)
    subscription_summary = get_subscription_monthly_cost_summary()
    subscription_metrics = get_subscription_monthly_metrics(month)
    subscription_upcoming = get_upcoming_subscriptions(days=7)[:3]
    recent_records = get_recent_transactions(limit=10)
    consumption_health = get_monthly_insights(month).get("consumption_health", {})
    goal_summary = get_goal_dashboard_summary()
    home_risk_cards = get_home_risk_cards(
        month=month,
        total_expense=float(dashboard["summary"].get("total_expense", 0) or 0),
    )

    return render_template(
        "index.html",
        active_page="index",
        month=dashboard["month"],
        summary=dashboard["summary"],
        daily_expense=dashboard["daily_expense"],
        category_share=dashboard["category_share"],
        today_expense=today_expense,
        top_categories=top_categories,
        emotion_light=emotion_light,
        subscription_summary=subscription_summary,
        subscription_metrics=subscription_metrics,
        subscription_upcoming=subscription_upcoming,
        recent_records=recent_records,
        consumption_health=consumption_health,
        budget_health=budget_health,
        goal_summary=goal_summary,
        home_risk_cards=home_risk_cards,
    )


@bp.route("/calendar", endpoint="calendar_page")
def calendar_page():
    month = request.args.get("month") or date.today().strftime("%Y-%m")
    return render_template(
        "calendar.html",
        active_page="calendar",
        month=month,
    )


@bp.route("/api/transactions", methods=["POST"], endpoint="create_transaction_api")
def create_transaction_api():
    payload = request.get_json(silent=True) or {}
    if payload.get("amount") in (None, "") or payload.get("date") in (None, ""):
        return jsonify({"error": "amount and date are required"}), 400

    tags = payload.get("tags", [])
    if not isinstance(tags, list):
        tags = []

    transaction_data, error = normalize_transaction_payload(payload, tags)
    if not transaction_data:
        return jsonify({"error": error or "invalid payload"}), 400

    created_id = create_transaction(transaction_data)
    return jsonify({"id": created_id}), 201


@bp.route("/api/transactions", methods=["GET"], endpoint="list_transactions_api")
def list_transactions_api():
    month = request.args.get("month") or date.today().strftime("%Y-%m")
    return jsonify(get_transactions_by_month(month))


@bp.route("/api/stats/monthly", methods=["GET"], endpoint="monthly_stats_api")
def monthly_stats_api():
    month = request.args.get("month") or date.today().strftime("%Y-%m")
    return jsonify(get_monthly_stats(month))


@bp.route("/api/dashboard/risk-cards", methods=["GET"], endpoint="dashboard_risk_cards_api")
def dashboard_risk_cards_api():
    month = request.args.get("month") or date.today().strftime("%Y-%m")
    dashboard = get_monthly_dashboard_data(month=month)
    total_expense = float(dashboard.get("summary", {}).get("total_expense", 0) or 0)
    return jsonify(get_home_risk_cards(month=month, total_expense=total_expense))


@bp.route("/api/stats/category", methods=["GET"], endpoint="category_trend_api")
def category_trend_api():
    category_name = request.args.get("name")
    month = request.args.get("month") or date.today().strftime("%Y-%m")
    if not category_name:
        return jsonify({"error": "name is required"}), 400
    return jsonify(get_category_trend(category_name, month))


@bp.route("/api/stats/tags", methods=["GET"], endpoint="tag_trend_api")
def tag_trend_api():
    tag_name = request.args.get("name")
    month = request.args.get("month") or date.today().strftime("%Y-%m")
    if not tag_name:
        return jsonify({"error": "name is required"}), 400
    return jsonify(get_tag_trend(tag_name, month))


@bp.route("/api/calendar", methods=["GET"], endpoint="calendar_summary_api")
def calendar_summary_api():
    month = request.args.get("month") or date.today().strftime("%Y-%m")
    return jsonify(get_calendar_daily_expense(month))


@bp.route("/api/calendar/day", methods=["GET"], endpoint="calendar_day_details_api")
def calendar_day_details_api():
    target_date = (request.args.get("date") or "").strip()
    if not target_date:
        return jsonify({"error": "date is required"}), 400

    try:
        datetime.strptime(target_date, "%Y-%m-%d")
    except ValueError:
        return jsonify({"error": "date format must be YYYY-MM-DD"}), 400

    return jsonify(get_calendar_day_details(target_date))
