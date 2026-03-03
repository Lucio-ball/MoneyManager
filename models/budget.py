from statistics import mean

from extensions.database import get_connection
from models.subscription import get_subscription_monthly_metrics
from models.transaction import get_month_expense_by_category
from models.transaction import get_transactions_by_month
from utils.date_utils import month_sequence


def upsert_budget(month: str, category_main: str | None, budget_amount: float) -> int:
    with get_connection() as conn:
        if category_main:
            conn.execute(
                "DELETE FROM budgets WHERE month = ? AND category_main = ?",
                (month, category_main),
            )
        else:
            conn.execute(
                "DELETE FROM budgets WHERE month = ? AND category_main IS NULL",
                (month,),
            )

        cursor = conn.execute(
            """
            INSERT INTO budgets (month, category_main, budget_amount)
            VALUES (?, ?, ?)
            """,
            (month, category_main, float(budget_amount)),
        )
        conn.commit()
        last_row_id = cursor.lastrowid
        if last_row_id is None:
            raise RuntimeError("failed to upsert budget")
        return int(last_row_id)


def get_budget_execution(month: str) -> dict:
    with get_connection() as conn:
        budget_rows = conn.execute(
            """
            SELECT id, month, category_main, budget_amount
            FROM budgets
            WHERE month = ?
            ORDER BY category_main IS NULL DESC, category_main ASC
            """,
            (month,),
        ).fetchall()

    category_expense = get_month_expense_by_category(month)
    total_expense = round(sum(category_expense.values()), 2)

    items = []
    for row in budget_rows:
        category = row["category_main"]
        budget_amount = float(row["budget_amount"])
        actual = total_expense if category is None else category_expense.get(category, 0.0)
        execution_rate = round((actual / budget_amount * 100), 2) if budget_amount > 0 else 0.0

        if execution_rate >= 100:
            status = "超支"
        elif execution_rate >= 80:
            status = "接近"
        else:
            status = "正常"

        items.append(
            {
                "id": row["id"],
                "month": row["month"],
                "category_main": category,
                "budget_amount": round(budget_amount, 2),
                "actual_expense": round(actual, 2),
                "execution_rate": execution_rate,
                "status": status,
            }
        )

    return {
        "month": month,
        "total_expense": total_expense,
        "items": items,
    }


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _build_budget_month_map(months: list[str]) -> dict[str, float]:
    placeholders = ",".join("?" for _ in months)
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT month, budget_amount
            FROM budgets
            WHERE category_main IS NULL
              AND month IN ({placeholders})
            """,
            tuple(months),
        ).fetchall()

    month_budget_map = {m: 0.0 for m in months}
    for row in rows:
        month_budget_map[row["month"]] = round(float(row["budget_amount"] or 0), 2)
    return month_budget_map


def _calculate_execution_component(execution_rate: float) -> dict:
    score = round(100 - _clamp(abs(execution_rate - 100), 0, 100), 2)
    return {
        "name": "budget_execution",
        "weight": 0.4,
        "value": round(execution_rate, 2),
        "score": score,
    }


def _calculate_deviation_component(category_items: list[dict]) -> dict:
    if not category_items:
        return {
            "name": "category_deviation",
            "weight": 0.25,
            "value": 0.0,
            "score": 100.0,
        }

    deviation_rates = [
        abs(float(item["actual_expense"]) - float(item["budget_amount"]))
        / float(item["budget_amount"])
        * 100
        for item in category_items
        if float(item["budget_amount"]) > 0
    ]

    avg_deviation = round(mean(deviation_rates), 2) if deviation_rates else 0.0
    score = round(100 - _clamp(avg_deviation, 0, 100), 2)
    return {
        "name": "category_deviation",
        "weight": 0.25,
        "value": avg_deviation,
        "score": score,
    }


def _calculate_subscription_component(month: str, total_expense: float) -> dict:
    subscription_metrics = get_subscription_monthly_metrics(month)
    subscription_cost = float(subscription_metrics.get("estimated_monthly_cost", 0) or 0)
    pressure_ratio = round((subscription_cost / total_expense * 100), 2) if total_expense > 0 else 0.0
    score = round(100 - _clamp(pressure_ratio * 2.0, 0, 100), 2)
    return {
        "name": "subscription_pressure",
        "weight": 0.2,
        "value": pressure_ratio,
        "score": score,
    }


def _calculate_impulsive_component(month: str, total_expense: float) -> dict:
    expense_records = [
        item for item in get_transactions_by_month(month) if item.get("type") == "expense"
    ]
    impulsive_amount = 0.0
    for item in expense_records:
        tags = set(item.get("tags") or [])
        if "冲动" in tags:
            impulsive_amount += float(item.get("amount") or 0)

    impulsive_ratio = round((impulsive_amount / total_expense * 100), 2) if total_expense > 0 else 0.0
    score = round(100 - _clamp(impulsive_ratio * 2.0, 0, 100), 2)
    return {
        "name": "impulsive_ratio",
        "weight": 0.15,
        "value": impulsive_ratio,
        "score": score,
    }


def _build_category_risks(month: str, execution_items: list[dict]) -> dict:
    category_items = [item for item in execution_items if item.get("category_main")]
    overspending = [
        {
            "category": item["category_main"],
            "budget_amount": item["budget_amount"],
            "actual_expense": item["actual_expense"],
            "execution_rate": item["execution_rate"],
            "deviation_amount": round(float(item["actual_expense"]) - float(item["budget_amount"]), 2),
        }
        for item in category_items
        if float(item.get("execution_rate", 0)) >= 100
    ]

    near_budget = [
        {
            "category": item["category_main"],
            "budget_amount": item["budget_amount"],
            "actual_expense": item["actual_expense"],
            "execution_rate": item["execution_rate"],
            "remaining_amount": round(float(item["budget_amount"]) - float(item["actual_expense"]), 2),
        }
        for item in category_items
        if 85 <= float(item.get("execution_rate", 0)) < 100
    ]

    unreasonable_budget = []
    months = month_sequence(month, count=4)
    history_months = [m for m in months if m != month]
    placeholders = ",".join("?" for _ in history_months)
    with get_connection() as conn:
        history_rows = conn.execute(
            f"""
            SELECT substr(date, 1, 7) AS month, category_main, ROUND(SUM(amount), 2) AS amount
            FROM transactions
            WHERE type = 'expense'
              AND substr(date, 1, 7) IN ({placeholders})
            GROUP BY substr(date, 1, 7), category_main
            """,
            tuple(history_months),
        ).fetchall()

    category_history_map: dict[str, list[float]] = {}
    for row in history_rows:
        category = row["category_main"] or "其他"
        category_history_map.setdefault(category, []).append(float(row["amount"] or 0))

    for item in category_items:
        category = item["category_main"]
        budget_amount = float(item["budget_amount"])
        if budget_amount <= 0:
            continue

        history_values = category_history_map.get(category, [])
        if not history_values:
            continue

        historical_avg = round(mean(history_values), 2)
        deviation_rate = round(abs(budget_amount - historical_avg) / budget_amount * 100, 2)
        if deviation_rate >= 40:
            unreasonable_budget.append(
                {
                    "category": category,
                    "budget_amount": round(budget_amount, 2),
                    "historical_avg_expense": historical_avg,
                    "historical_deviation_rate": deviation_rate,
                }
            )

    overspending.sort(key=lambda x: x["execution_rate"], reverse=True)
    near_budget.sort(key=lambda x: x["execution_rate"], reverse=True)
    unreasonable_budget.sort(key=lambda x: x["historical_deviation_rate"], reverse=True)

    return {
        "overspending": overspending,
        "near_budget": near_budget,
        "unreasonable_budget": unreasonable_budget,
    }


def get_budget_health_profile(month: str) -> dict:
    execution = get_budget_execution(month)
    total_expense = float(execution.get("total_expense") or 0)
    items = execution.get("items") or []

    total_budget_item = next((item for item in items if item.get("category_main") is None), None)
    if total_budget_item:
        execution_rate = float(total_budget_item.get("execution_rate") or 0)
        total_budget = float(total_budget_item.get("budget_amount") or 0)
    else:
        category_total_budget = sum(float(item.get("budget_amount") or 0) for item in items if item.get("category_main"))
        total_budget = round(category_total_budget, 2)
        execution_rate = round((total_expense / total_budget * 100), 2) if total_budget > 0 else 0.0

    category_items = [item for item in items if item.get("category_main")]
    execution_component = _calculate_execution_component(execution_rate)
    deviation_component = _calculate_deviation_component(category_items)
    subscription_component = _calculate_subscription_component(month, total_expense)
    impulsive_component = _calculate_impulsive_component(month, total_expense)

    components = [
        execution_component,
        deviation_component,
        subscription_component,
        impulsive_component,
    ]
    final_score = round(sum(item["score"] * item["weight"] for item in components), 2)

    if final_score >= 80:
        level = "优秀"
    elif final_score >= 60:
        level = "稳健"
    elif final_score >= 40:
        level = "预警"
    else:
        level = "高风险"

    category_risks = _build_category_risks(month, items)
    risk_hints = []
    if category_risks["overspending"]:
        top_item = category_risks["overspending"][0]
        risk_hints.append(
            f"「{top_item['category']}」已超预算 {top_item['execution_rate']:.2f}%，为本月主要超支来源。"
        )
    if category_risks["near_budget"]:
        top_item = category_risks["near_budget"][0]
        risk_hints.append(
            f"「{top_item['category']}」预算执行率 {top_item['execution_rate']:.2f}%，接近上限。"
        )
    if category_risks["unreasonable_budget"]:
        top_item = category_risks["unreasonable_budget"][0]
        risk_hints.append(
            f"「{top_item['category']}」预算与历史偏差 {top_item['historical_deviation_rate']:.2f}%，建议重设。"
        )

    months = month_sequence(month, count=6)
    month_budget_map = _build_budget_month_map(months)
    monthly_expense_map = {m: 0.0 for m in months}
    with get_connection() as conn:
        expense_rows = conn.execute(
            """
            SELECT substr(date, 1, 7) AS month, ROUND(SUM(amount), 2) AS total_expense
            FROM transactions
            WHERE type = 'expense'
              AND substr(date, 1, 7) IN (?, ?, ?, ?, ?, ?)
            GROUP BY substr(date, 1, 7)
            """,
            tuple(months),
        ).fetchall()

    for row in expense_rows:
        monthly_expense_map[row["month"]] = round(float(row["total_expense"] or 0), 2)

    execution_trend = []
    for m in months:
        budget_amount = month_budget_map.get(m, 0.0)
        actual = monthly_expense_map.get(m, 0.0)
        trend_execution_rate = round((actual / budget_amount * 100), 2) if budget_amount > 0 else 0.0
        execution_trend.append(
            {
                "month": m,
                "budget": round(budget_amount, 2),
                "actual": round(actual, 2),
                "execution_rate": trend_execution_rate,
            }
        )

    category_deviation = []
    for item in category_items:
        deviation_amount = round(float(item["actual_expense"]) - float(item["budget_amount"]), 2)
        category_deviation.append(
            {
                "category": item["category_main"],
                "budget": item["budget_amount"],
                "actual": item["actual_expense"],
                "deviation_amount": deviation_amount,
                "deviation_rate": round(
                    abs(deviation_amount) / float(item["budget_amount"]) * 100 if float(item["budget_amount"]) > 0 else 0,
                    2,
                ),
            }
        )
    category_deviation.sort(key=lambda x: abs(float(x["deviation_amount"])), reverse=True)

    return {
        "month": month,
        "score": {
            "value": final_score,
            "level": level,
            "components": components,
            "total_budget": round(total_budget, 2),
            "total_expense": round(total_expense, 2),
            "execution_rate": round(execution_rate, 2),
        },
        "category_risks": category_risks,
        "risk_hints": risk_hints,
        "trends": {
            "execution": execution_trend,
            "category_deviation": category_deviation,
        },
    }
