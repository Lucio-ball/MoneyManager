import json
from datetime import date

from flask import Blueprint, jsonify, redirect, render_template, request, current_app, url_for

from services.ai_service import (
    build_ai_monthly_response,
    build_ai_prompt_template,
    create_ai_archive,
    get_ai_archives,
    get_ai_monthly_package,
)
from services.subscription_service import get_subscription_monthly_metrics

bp = Blueprint("ai_routes", __name__)


@bp.route("/ai", methods=["GET", "POST"], endpoint="ai_page")
def ai_page():
    month = request.values.get("month") or date.today().strftime("%Y-%m")

    if request.method == "POST":
        archive_month = request.form.get("month") or month
        content = request.form.get("content", "").strip()
        if content:
            create_ai_archive(archive_month, content)
            return redirect(url_for("ai_routes.ai_page", month=archive_month, success="1"))
        return redirect(url_for("ai_routes.ai_page", month=archive_month, success="0"))

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
    month = request.args.get("month") or date.today().strftime("%Y-%m")
    return jsonify(build_ai_monthly_response(month))


@bp.route("/api/ai/monthly/export", methods=["GET"], endpoint="ai_monthly_export_api")
def ai_monthly_export_api():
    month = request.args.get("month") or date.today().strftime("%Y-%m")
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
