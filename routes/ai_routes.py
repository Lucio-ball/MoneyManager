import json

from flask import Blueprint, jsonify, redirect, render_template, request, current_app, url_for

from services.ai_service import (
    build_ai_monthly_response,
    build_ai_prompt_template,
    create_ai_archive,
    get_ai_archives,
    get_ai_monthly_package,
)
from services.monthly_review_service import generate_monthly_review
from services.subscription_service import get_subscription_monthly_metrics
from utils.date_utils import normalize_month

bp = Blueprint("ai_routes", __name__)


@bp.route("/ai/monthly-review", methods=["GET"], endpoint="ai_monthly_review_page")
def ai_monthly_review_page():
    month = normalize_month(request.args.get("month"))
    review = generate_monthly_review(month)

    return render_template(
        "ai_monthly_review.html",
        active_page="ai",
        month=month,
        review=review,
    )


@bp.route("/ai", methods=["GET"], endpoint="ai_page")
def ai_page():
    month = normalize_month(request.args.get("month"))
    return redirect(url_for("ai_routes.ai_monthly_review_page", month=month))


@bp.route("/ai/workbench", methods=["GET", "POST"], endpoint="ai_workbench_page")
def ai_workbench_page():
    month = normalize_month(request.values.get("month"))

    if request.method == "POST":
        archive_month = request.form.get("month") or month
        content = request.form.get("content", "").strip()
        if content:
            create_ai_archive(archive_month, content)
            return redirect(url_for("ai_routes.ai_workbench_page", month=archive_month, success="1"))
        return redirect(url_for("ai_routes.ai_workbench_page", month=archive_month, success="0"))

    success = request.args.get("success")
    ai_package = get_ai_monthly_package(month)
    ai_prompt_template = build_ai_prompt_template(month)
    archives = get_ai_archives(month)
    subscription_metrics = get_subscription_monthly_metrics(month)

    return render_template(
        "ai.html",
        active_page="ai",
        month=month,
        success=success,
        ai_package=ai_package,
        ai_prompt_template=ai_prompt_template,
        archives=archives,
        subscription_metrics=subscription_metrics,
    )


@bp.route("/api/ai/monthly", methods=["GET"], endpoint="ai_monthly_api")
def ai_monthly_api():
    month = normalize_month(request.args.get("month"))
    return jsonify(build_ai_monthly_response(month))


@bp.route("/api/ai/monthly/export", methods=["GET"], endpoint="ai_monthly_export_api")
def ai_monthly_export_api():
    month = normalize_month(request.args.get("month"))
    package = get_ai_monthly_package(month)
    payload = {
        "month": month,
        "prompt_template": build_ai_prompt_template(month),
        "data_package": package,
    }
    content = json.dumps(payload, ensure_ascii=False, indent=2)
    filename = f"ai_package_{month}.json"

    return current_app.response_class(
        response=content,
        mimetype="application/json",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
