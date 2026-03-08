from datetime import date, datetime

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
from models.transaction import get_monthly_financial_summary
from utils.date_utils import parse_date


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


def _days_until(target_date: str | None) -> int | None:
    billing_date = parse_date(target_date)
    if not billing_date:
        return None
    return (billing_date - date.today()).days


def _safe_ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator * 100, 2)


def get_subscription_alerts(month: str) -> dict:
    monthly_metrics = get_subscription_monthly_metrics(month)
    upcoming_7_days = get_upcoming_subscriptions(days=7)
    upcoming_30_days = get_upcoming_subscriptions(days=30)

    return {
        "month": month,
        "upcoming_7_days": upcoming_7_days,
        "upcoming_30_days": upcoming_30_days,
        "monthly_subscription_cost": round(float(monthly_metrics.get("estimated_monthly_cost", 0) or 0), 2),
        "actual_charged_amount": round(float(monthly_metrics.get("actual_charged_amount", 0) or 0), 2),
        "upcoming_7_days_count": len(upcoming_7_days),
        "upcoming_30_days_count": len(upcoming_30_days),
    }


def evaluate_subscription_health(month: str) -> dict:
    subscriptions = list_subscriptions()
    alerts = get_subscription_alerts(month)
    financial_summary = get_monthly_financial_summary(month)
    total_expense = float(financial_summary.get("gross_expense", 0) or 0)
    monthly_cost = float(alerts.get("monthly_subscription_cost", 0) or 0)
    subscription_pressure = _safe_ratio(monthly_cost, total_expense)

    same_month_bucket: dict[str, list[dict]] = {}
    for item in subscriptions:
        month_key = str(item.get("next_billing_date") or "")[:7]
        if month_key:
            same_month_bucket.setdefault(month_key, []).append(item)

    high_pressure_items = []
    low_cost_stable_items = []
    annualized_high_items = []
    cancel_candidates = []
    value_insights: list[str] = []

    for item in subscriptions:
        monthly_cost_item = float(item.get("monthly_cost", 0) or 0)
        item_pressure = _safe_ratio(monthly_cost_item, total_expense)
        created_at = str(item.get("created_at") or "")
        created_date = parse_date(created_at[:10]) if created_at else None
        stable_days = (date.today() - created_date).days if created_date else 0
        days_until_billing = _days_until(item.get("next_billing_date"))
        same_month_count = len(same_month_bucket.get(str(item.get("next_billing_date") or "")[:7], []))

        if item_pressure >= 8 or monthly_cost_item >= 80:
            high_pressure_items.append(
                {
                    "id": item["id"],
                    "name": item["name"],
                    "monthly_cost": round(monthly_cost_item, 2),
                    "pressure": item_pressure,
                    "days_until_billing": days_until_billing,
                }
            )

        if monthly_cost_item <= 20 and stable_days >= 180:
            low_cost_stable_items.append(
                {
                    "id": item["id"],
                    "name": item["name"],
                    "monthly_cost": round(monthly_cost_item, 2),
                    "stable_days": stable_days,
                }
            )

        if item.get("cycle") == "yearly" and monthly_cost_item >= 50:
            annualized_high_items.append(
                {
                    "id": item["id"],
                    "name": item["name"],
                    "monthly_cost": round(monthly_cost_item, 2),
                    "amount": round(float(item.get("amount", 0) or 0), 2),
                    "days_until_billing": days_until_billing,
                }
            )

        if (monthly_cost_item >= 35 and same_month_count >= 3) or (item_pressure >= 5 and stable_days < 90):
            cancel_candidates.append(
                {
                    "id": item["id"],
                    "name": item["name"],
                    "monthly_cost": round(monthly_cost_item, 2),
                    "pressure": item_pressure,
                    "cycle": item.get("cycle"),
                    "days_until_billing": days_until_billing,
                    "same_month_count": same_month_count,
                }
            )

    high_pressure_items.sort(key=lambda row: (row["pressure"], row["monthly_cost"]), reverse=True)
    low_cost_stable_items.sort(key=lambda row: (row["stable_days"], row["monthly_cost"]), reverse=True)
    annualized_high_items.sort(key=lambda row: row["monthly_cost"], reverse=True)
    cancel_candidates.sort(key=lambda row: (row["same_month_count"], row["pressure"], row["monthly_cost"]), reverse=True)

    if alerts["upcoming_7_days"]:
        first_item = alerts["upcoming_7_days"][0]
        value_insights.append(
            f"未来 7 天有 {len(alerts['upcoming_7_days'])} 个订阅即将扣费，最近的是 {first_item['name']}。"
        )
    if alerts["upcoming_30_days_count"] >= 4:
        value_insights.append(
            f"未来 30 天将迎来 {alerts['upcoming_30_days_count']} 个订阅扣费，短期固定支出较密集。"
        )
    if subscription_pressure >= 15:
        value_insights.append(f"本月订阅压力为 {subscription_pressure:.2f}%，订阅固定成本已明显抬高总支出。")
    elif subscription_pressure > 0:
        value_insights.append(f"本月订阅压力为 {subscription_pressure:.2f}%，整体仍在可控区间。")
    if annualized_high_items:
        value_insights.append(
            f"{annualized_high_items[0]['name']} 的年费折算月成本为 {annualized_high_items[0]['monthly_cost']:.2f} 元，属于年费摊销偏高项目。"
        )
    if cancel_candidates:
        value_insights.append(
            f"{cancel_candidates[0]['name']} 位于可考虑取消候选，原因是成本和续费月份压力偏高。"
        )

    return {
        "month": month,
        "monthly_subscription_cost": round(monthly_cost, 2),
        "subscription_pressure": subscription_pressure,
        "subscription_count": len(subscriptions),
        "upcoming_7_days": alerts["upcoming_7_days"],
        "upcoming_30_days": alerts["upcoming_30_days"],
        "high_pressure_items": high_pressure_items[:5],
        "low_cost_stable_items": low_cost_stable_items[:5],
        "annualized_high_items": annualized_high_items[:5],
        "value_insights": value_insights[:5],
        "cancel_candidates": cancel_candidates[:5],
    }


__all__ = [
    "build_subscription_payload",
    "create_subscription",
    "delete_subscription",
    "evaluate_subscription_health",
    "get_subscription_by_id",
    "get_subscription_alerts",
    "get_subscription_monthly_cost_summary",
    "get_subscription_monthly_metrics",
    "get_upcoming_subscriptions",
    "list_subscriptions",
    "process_due_subscription_charges",
    "update_subscription",
]
