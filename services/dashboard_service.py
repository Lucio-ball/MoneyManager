from calendar import monthrange
from datetime import date

from services.budget_service import get_budget_health_profile
from services.subscription_service import get_subscription_monthly_metrics


def _build_subscription_pressure(month: str, total_expense: float) -> dict:
    metrics = get_subscription_monthly_metrics(month)
    monthly_cost = round(float(metrics.get("estimated_monthly_cost", 0) or 0), 2)
    ratio = round((monthly_cost / total_expense * 100), 2) if total_expense > 0 else 0.0

    if ratio >= 25:
        risk_level = "高"
    elif ratio >= 12:
        risk_level = "中"
    else:
        risk_level = "低"

    return {
        "month": month,
        "monthly_cost": monthly_cost,
        "ratio": ratio,
        "risk_level": risk_level,
    }


def _build_budget_risk(month: str) -> dict:
    budget_health = get_budget_health_profile(month)
    execution_rate = round(float(budget_health.get("score", {}).get("execution_rate", 0) or 0), 2)

    overspending = budget_health.get("category_risks", {}).get("overspending", [])
    near_budget = budget_health.get("category_risks", {}).get("near_budget", [])
    risk_categories = []
    for item in overspending + near_budget:
        category = str(item.get("category") or "").strip()
        if category and category not in risk_categories:
            risk_categories.append(category)
    risk_categories = risk_categories[:3]

    today = date.today()
    current_month = today.strftime("%Y-%m")
    if month == current_month:
        days_in_month = monthrange(today.year, today.month)[1]
        elapsed_ratio = max(today.day / days_in_month, 1 / days_in_month)
        projected_execution_rate = round(execution_rate / elapsed_ratio, 2)
    else:
        projected_execution_rate = execution_rate

    will_overspend = projected_execution_rate > 100.0

    if projected_execution_rate >= 110 or execution_rate >= 100:
        risk_level = "高"
    elif projected_execution_rate >= 95 or execution_rate >= 85:
        risk_level = "中"
    else:
        risk_level = "低"

    return {
        "month": month,
        "execution_rate": execution_rate,
        "projected_execution_rate": projected_execution_rate,
        "risk_categories": risk_categories,
        "will_overspend": will_overspend,
        "risk_level": risk_level,
    }


def get_home_risk_cards(month: str, total_expense: float) -> dict:
    return {
        "subscription_pressure": _build_subscription_pressure(month, total_expense),
        "budget_risk": _build_budget_risk(month),
    }


__all__ = ["get_home_risk_cards"]
