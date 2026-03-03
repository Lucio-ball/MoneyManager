from extensions.database import get_connection
from models.budget import get_budget_execution
from models.subscription import get_subscription_monthly_metrics, get_subscription_monthly_recap
from models.transaction import get_monthly_stats, get_transactions_by_month
from utils.date_utils import month_sequence
from utils.trend_utils import parse_tags


def get_monthly_insights(month: str) -> dict:
    monthly_stats = get_monthly_stats(month)
    total_expense = monthly_stats["total_expense"]

    daily_amounts = [item["amount"] for item in monthly_stats["daily_expense"]]
    daily_avg = (sum(daily_amounts) / len(daily_amounts)) if daily_amounts else 0

    abnormal_days = [
        {"date": item["date"], "amount": item["amount"]}
        for item in monthly_stats["daily_expense"]
        if daily_avg > 0 and item["amount"] > daily_avg * 2
    ]

    months = month_sequence(month, count=3)
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT substr(date, 1, 7) AS month, category_main, amount
            FROM transactions
            WHERE type = 'expense' AND substr(date, 1, 7) IN (?, ?, ?)
            """,
            (months[0], months[1], months[2]),
        ).fetchall()

    month_total_map = {key: 0.0 for key in months}
    month_category_map: dict[str, dict[str, float]] = {key: {} for key in months}
    for row in rows:
        m = row["month"]
        category = row["category_main"] or "其他"
        amount = float(row["amount"])
        month_total_map[m] = round(month_total_map.get(m, 0) + amount, 2)
        existing = month_category_map[m].get(category, 0.0)
        month_category_map[m][category] = round(existing + amount, 2)

    all_categories = set()
    for value in month_category_map.values():
        all_categories.update(value.keys())

    long_term_high_categories = []
    for category in sorted(all_categories):
        ratios = []
        valid = True
        for month_item in months:
            total = month_total_map.get(month_item, 0)
            if total <= 0:
                valid = False
                break
            amount = month_category_map.get(month_item, {}).get(category, 0.0)
            ratios.append(amount / total)
        if valid and ratios and all(ratio > 0.3 for ratio in ratios):
            long_term_high_categories.append(
                {
                    "category": category,
                    "months": months,
                    "ratios": [round(ratio * 100, 2) for ratio in ratios],
                }
            )

    records = get_transactions_by_month(month)
    impulsive_amount = 0.0
    learning_amount = 0.0
    for record in records:
        if record["type"] != "expense":
            continue
        tags = set(record["tags"])
        amount = float(record["amount"])
        if "冲动" in tags:
            impulsive_amount += amount
        if "学习投资" in tags or "投资自己" in tags:
            learning_amount += amount

    impulsive_ratio = (impulsive_amount / total_expense * 100) if total_expense > 0 else 0
    learning_ratio = (learning_amount / total_expense * 100) if total_expense > 0 else 0

    return {
        "month": month,
        "abnormal_high_expense_days": abnormal_days,
        "long_term_high_ratio_categories": long_term_high_categories,
        "impulsive_spending_ratio": {
            "amount": round(impulsive_amount, 2),
            "ratio": round(impulsive_ratio, 2),
        },
        "learning_investment_ratio": {
            "amount": round(learning_amount, 2),
            "ratio": round(learning_ratio, 2),
        },
    }


def get_analysis_dashboard_data(month: str) -> dict:
    monthly_stats = get_monthly_stats(month)
    insights = get_monthly_insights(month)
    subscription_metrics = get_subscription_monthly_metrics(month)
    months = month_sequence(month, count=3)

    total_expense = float(monthly_stats.get("total_expense", 0) or 0)
    total_income = float(monthly_stats.get("total_income", 0) or 0)
    balance = float(monthly_stats.get("balance", 0) or 0)
    subscription_cost = float(subscription_metrics.get("estimated_monthly_cost", 0) or 0)
    subscription_ratio = (subscription_cost / total_expense * 100) if total_expense > 0 else 0.0
    impulsive_ratio = float(insights.get("impulsive_spending_ratio", {}).get("ratio", 0) or 0)
    learning_ratio = float(insights.get("learning_investment_ratio", {}).get("ratio", 0) or 0)

    top_category = (monthly_stats.get("category_stats") or [{}])[0].get("name", "其他")
    if balance >= 0:
        summary_sentence = (
            f"本月收支结余 ¥{balance:.2f}，支出主要集中在「{top_category}」，"
            f"冲动消费占比 {impulsive_ratio:.2f}%。"
        )
    else:
        summary_sentence = (
            f"本月收支为负 ¥{abs(balance):.2f}，支出主要集中在「{top_category}」，"
            f"建议优先控制高频非刚需消费。"
        )

    expense_records = [
        item for item in get_transactions_by_month(month) if item.get("type") == "expense"
    ]
    frequency_count = len(expense_records)
    avg_amount = (total_expense / frequency_count) if frequency_count > 0 else 0.0

    category_count_map: dict[str, int] = {}
    category_amount_map: dict[str, float] = {}
    tag_focus = ["冲动", "刚需", "投资自己", "情绪消费"]
    tag_amount_map: dict[str, float] = {key: 0.0 for key in tag_focus}
    for row in expense_records:
        category = row.get("category_main") or "其他"
        amount = float(row.get("amount") or 0)
        category_count_map[category] = category_count_map.get(category, 0) + 1
        category_amount_map[category] = round(category_amount_map.get(category, 0) + amount, 2)
        for tag in row.get("tags", []):
            if tag in tag_amount_map:
                tag_amount_map[tag] = round(tag_amount_map.get(tag, 0) + amount, 2)

    high_frequency_categories = []
    for category, count in sorted(category_count_map.items(), key=lambda item: item[1], reverse=True)[:3]:
        high_frequency_categories.append(
            {
                "name": category,
                "count": count,
                "amount": round(category_amount_map.get(category, 0), 2),
            }
        )

    this_month_tag_stats = []
    for tag in tag_focus:
        amount = round(tag_amount_map.get(tag, 0), 2)
        ratio = (amount / total_expense * 100) if total_expense > 0 else 0
        this_month_tag_stats.append({"name": tag, "amount": amount, "ratio": round(ratio, 2)})

    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT substr(date, 1, 7) AS month, amount, category_main, tags
            FROM transactions
            WHERE type = 'expense' AND substr(date, 1, 7) IN (?, ?, ?)
            """,
            (months[0], months[1], months[2]),
        ).fetchall()

    month_total_map: dict[str, float] = {m: 0.0 for m in months}
    month_category_amount_map: dict[str, dict[str, float]] = {m: {} for m in months}
    month_tag_amount_map: dict[str, dict[str, float]] = {m: {} for m in months}
    for row in rows:
        m = row["month"]
        amount = float(row["amount"] or 0)
        category = row["category_main"] or "其他"
        month_total_map[m] = round(month_total_map.get(m, 0) + amount, 2)
        month_category_amount_map[m][category] = round(
            month_category_amount_map[m].get(category, 0) + amount, 2
        )

        for tag in parse_tags(row["tags"]):
            month_tag_amount_map[m][tag] = round(month_tag_amount_map[m].get(tag, 0) + amount, 2)

    category_totals: dict[str, float] = {}
    for m in months:
        for category, amount in month_category_amount_map[m].items():
            category_totals[category] = round(category_totals.get(category, 0) + amount, 2)

    top_categories = [
        category for category, _amount in sorted(category_totals.items(), key=lambda x: x[1], reverse=True)[:6]
    ]
    category_trend_series = []
    for category in top_categories:
        points = [round(month_category_amount_map[m].get(category, 0), 2) for m in months]
        category_trend_series.append(
            {
                "name": category,
                "values": points,
                "total": round(sum(points), 2),
            }
        )

    tag_trend_series = []
    for tag in tag_focus:
        points = [round(month_tag_amount_map[m].get(tag, 0), 2) for m in months]
        tag_trend_series.append({"name": tag, "values": points, "total": round(sum(points), 2)})

    total_expense_trend = [{"month": m, "amount": round(month_total_map.get(m, 0), 2)} for m in months]
    subscription_cost_trend = []
    for m in months:
        metrics = get_subscription_monthly_metrics(m)
        subscription_cost_trend.append(
            {
                "month": m,
                "amount": round(float(metrics.get("estimated_monthly_cost", 0) or 0), 2),
            }
        )

    risk_items = []
    abnormal_days = insights.get("abnormal_high_expense_days", [])
    if abnormal_days:
        peak_day = sorted(abnormal_days, key=lambda x: float(x.get("amount", 0)), reverse=True)[0]
        risk_items.append(
            {
                "key": "abnormal_high_expense_days",
                "level": "high",
                "title": "异常高支出日",
                "message": f"{peak_day.get('date')} 单日支出 ¥{float(peak_day.get('amount', 0)):.2f}，波动偏高。",
            }
        )

    if impulsive_ratio >= 30:
        risk_items.append(
            {
                "key": "impulsive_spending_ratio",
                "level": "high",
                "title": "冲动消费比例过高",
                "message": f"冲动消费占总支出 {impulsive_ratio:.2f}%，建议设置上限并延迟购买。",
            }
        )

    long_term_categories = insights.get("long_term_high_ratio_categories", [])
    if long_term_categories:
        first_item = long_term_categories[0]
        risk_items.append(
            {
                "key": "long_term_high_ratio_categories",
                "level": "medium",
                "title": "长期高占比类别",
                "message": f"「{first_item.get('category', '其他')}」近 3 个月持续高占比，建议复盘必要性。",
            }
        )

    if learning_ratio < 10:
        risk_items.append(
            {
                "key": "learning_investment_ratio",
                "level": "medium",
                "title": "学习投资不足",
                "message": f"学习投资占比仅 {learning_ratio:.2f}%，可考虑稳定投入提升长期回报。",
            }
        )

    if subscription_ratio >= 20:
        risk_items.append(
            {
                "key": "subscription_ratio",
                "level": "medium",
                "title": "订阅占比过高",
                "message": f"订阅折算成本占总支出 {subscription_ratio:.2f}%，建议清理低使用率订阅。",
            }
        )

    return {
        "month": month,
        "kpi": {
            "total_expense": round(total_expense, 2),
            "total_income": round(total_income, 2),
            "balance": round(balance, 2),
            "subscription_estimated_cost": round(subscription_cost, 2),
            "subscription_ratio": round(subscription_ratio, 2),
            "summary_sentence": summary_sentence,
        },
        "structure": {
            "category_stats": monthly_stats.get("category_stats", []),
            "tag_stats": this_month_tag_stats,
        },
        "rhythm": {
            "daily_expense": monthly_stats.get("daily_expense", []),
            "frequency": {
                "count": frequency_count,
                "avg_amount": round(avg_amount, 2),
                "high_frequency_categories": high_frequency_categories,
            },
        },
        "trends": {
            "months": months,
            "category_trend": {
                "months": months,
                "series": category_trend_series,
            },
            "tag_trend": {
                "months": months,
                "series": tag_trend_series,
            },
            "total_expense_trend": total_expense_trend,
            "subscription_cost_trend": subscription_cost_trend,
        },
        "risks": {
            "abnormal_high_expense_days": abnormal_days,
            "impulsive_spending_ratio": insights.get("impulsive_spending_ratio", {}),
            "long_term_high_ratio_categories": long_term_categories,
            "learning_investment_ratio": insights.get("learning_investment_ratio", {}),
            "subscription_ratio": round(subscription_ratio, 2),
            "items": risk_items,
        },
        "raw": {
            "monthly_stats": monthly_stats,
            "insights": insights,
            "subscription_metrics": subscription_metrics,
        },
    }


def create_ai_archive(month: str, content: str) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO ai_archives (month, content)
            VALUES (?, ?)
            """,
            (month, content),
        )
        conn.commit()
        last_row_id = cursor.lastrowid
        if last_row_id is None:
            raise RuntimeError("failed to create ai archive")
        return int(last_row_id)


def get_ai_archives(month: str, limit: int = 10) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, month, content, created_at
            FROM ai_archives
            WHERE month = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (month, limit),
        ).fetchall()

    return [dict(row) for row in rows]


def get_ai_monthly_package(month: str) -> dict:
    return {
        "month": month,
        "monthly_stats": get_monthly_stats(month),
        "insights": get_monthly_insights(month),
        "budgets": get_budget_execution(month),
        "subscriptions": get_subscription_monthly_recap(month),
    }
