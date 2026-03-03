from datetime import date, datetime

from models.transaction import (
    get_calendar_daily_expense,
    get_calendar_day_details,
    create_transaction,
    get_category_trend,
    get_monthly_dashboard_data,
    get_monthly_stats,
    get_recent_average_month_expense,
    get_recent_transactions,
    get_tag_trend,
    get_today_expense,
    get_transactions_by_month,
)


def normalize_transaction_payload(data: dict, tags: list[str] | None = None) -> tuple[dict | None, str | None]:
    amount_raw = data.get("amount")
    try:
        amount = float(amount_raw) if amount_raw is not None else 0.0
    except (TypeError, ValueError):
        return None, "invalid amount"

    if amount <= 0:
        return None, "amount must be greater than 0"

    tx_type = str(data.get("type", "expense")).strip()
    if tx_type not in ("expense", "income"):
        tx_type = "expense"

    tx_date = str(data.get("date") or date.today().isoformat()).strip()
    try:
        datetime.strptime(tx_date, "%Y-%m-%d")
    except ValueError:
        return None, "invalid date"

    note = str(data.get("note", "")).strip()

    if tx_type == "income":
        income_source = str(data.get("income_source", "")).strip() or str(
            data.get("category_sub", "")
        ).strip()
        if not income_source:
            return None, "income_source is required for income"
        return (
            {
                "amount": amount,
                "type": "income",
                "date": tx_date,
                "category_main": "收入",
                "category_sub": income_source,
                "tags": [],
                "note": note,
            },
            None,
        )

    category_main = str(data.get("category_main", "")).strip()
    if not category_main:
        return None, "category_main is required for expense"

    category_sub = str(data.get("category_sub", "")).strip()
    normalized_tags = [str(tag).strip() for tag in (tags or []) if str(tag).strip()]

    return (
        {
            "amount": amount,
            "type": "expense",
            "date": tx_date,
            "category_main": category_main,
            "category_sub": category_sub,
            "tags": normalized_tags,
            "note": note,
        },
        None,
    )


__all__ = [
    "normalize_transaction_payload",
    "create_transaction",
    "get_recent_transactions",
    "get_monthly_dashboard_data",
    "get_monthly_stats",
    "get_category_trend",
    "get_tag_trend",
    "get_today_expense",
    "get_transactions_by_month",
    "get_recent_average_month_expense",
    "get_calendar_daily_expense",
    "get_calendar_day_details",
]
