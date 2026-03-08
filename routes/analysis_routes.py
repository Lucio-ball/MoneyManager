from flask import Blueprint, jsonify, render_template, request

from services.analysis_service import get_analysis_dashboard_data, get_monthly_insights
from utils.date_utils import normalize_month

bp = Blueprint("analysis_routes", __name__)


@bp.route("/analysis", endpoint="analysis_page")
def analysis_page():
    month = normalize_month(request.args.get("month"))
    analysis_data = get_analysis_dashboard_data(month)

    return render_template(
        "analysis.html",
        active_page="analysis",
        month=month,
        analysis_data=analysis_data,
    )


@bp.route("/api/insights/monthly", methods=["GET"], endpoint="monthly_insights_api")
def monthly_insights_api():
    month = normalize_month(request.args.get("month"))
    return jsonify(get_monthly_insights(month))


@bp.route("/api/stats/analysis", methods=["GET"], endpoint="analysis_dashboard_api")
def analysis_dashboard_api():
    month = normalize_month(request.args.get("month"))
    return jsonify(get_analysis_dashboard_data(month))
