from datetime import datetime

from config import SUBSCRIPTION_CYCLE_OPTIONS
from models.subscription import (
    create_subscription,
    delete_subscription,
    get_subscription_by_id,
    get_subscription_monthly_cost_summary,
    get_subscription_monthly_metrics,
    get_upcoming_subscriptions,
    list_subscriptions,
    process_due_subscription_charges,
    update_subscription,
)


def build_subscription_payload(data: dict) -> dict | None:
    required = ["name", "amount", "cycle", "next_billing_date"]
    for key in required:
        if data.get(key) in (None, ""):
            return None

    cycle = data.get("cycle")
    if cycle not in SUBSCRIPTION_CYCLE_OPTIONS:
        return None

    amount_value = data.get("amount")
    try:
        amount = float(amount_value) if amount_value is not None else 0.0
    except (TypeError, ValueError):
        return None
    if amount <= 0:
        return None

    next_billing_date = str(data.get("next_billing_date"))
    try:
        datetime.strptime(next_billing_date, "%Y-%m-%d")
    except ValueError:
        return None

    name = str(data.get("name", "")).strip()
    if not name:
        return None

    return {
        "name": name,
        "amount": amount,
        "cycle": cycle,
        "next_billing_date": next_billing_date,
        "category": str(data.get("category", "")).strip(),
        "payment_method": str(data.get("payment_method", "")).strip(),
        "note": str(data.get("note", "")).strip(),
    }


__all__ = [
    "build_subscription_payload",
    "create_subscription",
    "delete_subscription",
    "get_subscription_by_id",
    "get_subscription_monthly_cost_summary",
    "get_subscription_monthly_metrics",
    "get_upcoming_subscriptions",
    "list_subscriptions",
    "process_due_subscription_charges",
    "update_subscription",
]
