from datetime import date

from flask import Blueprint, abort, jsonify, redirect, render_template, request, url_for

from config import SUBSCRIPTION_CYCLE_OPTIONS
from services.subscription_service import (
    build_subscription_payload,
    create_subscription,
    delete_subscription,
    get_subscription_by_id,
    get_subscription_monthly_cost_summary,
    get_subscription_monthly_metrics,
    get_upcoming_subscriptions,
    list_subscriptions,
    update_subscription,
)

bp = Blueprint("subscription_routes", __name__)


@bp.route("/subscriptions", endpoint="subscriptions_page")
def subscriptions_page():
    summary = get_subscription_monthly_cost_summary()
    subscriptions = list_subscriptions()
    upcoming = get_upcoming_subscriptions(days=7)
    cycle_labels = {
        "monthly": "月付",
        "yearly": "年付",
        "weekly": "周付",
        "quarterly": "季付",
    }
    return render_template(
        "subscriptions.html",
        active_page="subscriptions",
        month=date.today().strftime("%Y-%m"),
        summary=summary,
        subscriptions=subscriptions,
        upcoming=upcoming,
        cycle_labels=cycle_labels,
        success=request.args.get("success"),
    )


@bp.route("/subscriptions/add", methods=["GET", "POST"], endpoint="add_subscription_page")
def add_subscription_page():
    if request.method == "POST":
        form_payload = build_subscription_payload(request.form)
        if not form_payload:
            return redirect(url_for("subscription_routes.add_subscription_page", success="0"))
        create_subscription(form_payload)
        return redirect(url_for("subscription_routes.subscriptions_page", success="created"))

    return render_template(
        "subscriptions_add.html",
        active_page="subscriptions",
        month=date.today().strftime("%Y-%m"),
        today=date.today().isoformat(),
        cycle_options=SUBSCRIPTION_CYCLE_OPTIONS,
        success=request.args.get("success"),
    )


@bp.route("/subscriptions/edit/<int:subscription_id>", methods=["GET", "POST"], endpoint="edit_subscription_page")
def edit_subscription_page(subscription_id: int):
    existing = get_subscription_by_id(subscription_id)
    if not existing:
        abort(404)

    if request.method == "POST":
        form_payload = build_subscription_payload(request.form)
        if not form_payload:
            return redirect(url_for("subscription_routes.edit_subscription_page", subscription_id=subscription_id, success="0"))

        updated = update_subscription(subscription_id, form_payload)
        if updated:
            return redirect(url_for("subscription_routes.subscriptions_page", success="updated"))
        return redirect(url_for("subscription_routes.edit_subscription_page", subscription_id=subscription_id, success="0"))

    return render_template(
        "subscriptions_edit.html",
        active_page="subscriptions",
        month=date.today().strftime("%Y-%m"),
        subscription=existing,
        cycle_options=SUBSCRIPTION_CYCLE_OPTIONS,
        success=request.args.get("success"),
    )


@bp.route("/api/subscriptions", methods=["POST"], endpoint="create_subscription_api")
def create_subscription_api():
    payload = request.get_json(silent=True) or {}
    data = build_subscription_payload(payload)
    if not data:
        return jsonify({"error": "invalid payload"}), 400

    created_id = create_subscription(data)
    return jsonify({"id": created_id}), 201


@bp.route("/api/subscriptions", methods=["GET"], endpoint="list_subscriptions_api")
def list_subscriptions_api():
    return jsonify(list_subscriptions())


@bp.route("/api/subscriptions/upcoming", methods=["GET"], endpoint="list_upcoming_subscriptions_api")
def list_upcoming_subscriptions_api():
    return jsonify(get_upcoming_subscriptions(days=7))


@bp.route("/api/subscriptions/monthly_cost", methods=["GET"], endpoint="subscriptions_monthly_cost_api")
def subscriptions_monthly_cost_api():
    month = request.args.get("month") or date.today().strftime("%Y-%m")
    summary = get_subscription_monthly_cost_summary()
    metrics = get_subscription_monthly_metrics(month)
    response = dict(summary)
    response.update(metrics)
    return jsonify(response)


@bp.route("/api/subscriptions/<int:subscription_id>", methods=["DELETE"], endpoint="delete_subscription_api")
def delete_subscription_api(subscription_id: int):
    deleted = delete_subscription(subscription_id)
    if not deleted:
        return jsonify({"error": "subscription not found"}), 404
    return jsonify({"success": True})


@bp.route("/api/subscriptions/<int:subscription_id>", methods=["PUT"], endpoint="update_subscription_api")
def update_subscription_api(subscription_id: int):
    existing = get_subscription_by_id(subscription_id)
    if not existing:
        return jsonify({"error": "subscription not found"}), 404

    payload = request.get_json(silent=True) or {}
    data = build_subscription_payload(payload)
    if not data:
        return jsonify({"error": "invalid payload"}), 400

    updated = update_subscription(subscription_id, data)
    if not updated:
        return jsonify({"error": "update failed"}), 400
    return jsonify({"success": True})
