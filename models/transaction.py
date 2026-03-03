import json
from datetime import date

from extensions.database import get_connection
from utils.date_utils import month_sequence
from utils.trend_utils import parse_tags


def create_transaction(transaction: dict) -> int:
    tags = transaction.get("tags", [])
    tags_json = json.dumps(tags, ensure_ascii=False)

    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO transactions (
                amount,
                type,
                date,
                category_main,
                category_sub,
                tags,
                note
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                float(transaction["amount"]),
                transaction["type"],
                transaction["date"],
                transaction["category_main"],
                transaction.get("category_sub") or None,
                tags_json,
                transaction.get("note") or None,
            ),
        )
        conn.commit()
        last_row_id = cursor.lastrowid
        if last_row_id is None:
            raise RuntimeError("failed to create transaction")
        return int(last_row_id)


def get_recent_transactions(limit: int = 10) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                id,
                amount,
                type,
                date,
                category_main,
                category_sub,
                tags,
                note,
                created_at
            FROM transactions
            ORDER BY date DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    result = []
    for row in rows:
        item = dict(row)
        item["tags"] = parse_tags(item.get("tags"))
        result.append(item)
    return result


def get_monthly_dashboard_data(month: str | None = None) -> dict:
    if not month:
        month = date.today().strftime("%Y-%m")

    with get_connection() as conn:
        totals_row = conn.execute(
            """
            SELECT
                COALESCE(SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END), 0) AS total_expense,
                COALESCE(SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END), 0) AS total_income
            FROM transactions
            WHERE substr(date, 1, 7) = ?
            """,
            (month,),
        ).fetchone()

        daily_rows = conn.execute(
            """
            SELECT date, ROUND(SUM(amount), 2) AS expense_amount
            FROM transactions
            WHERE type = 'expense' AND substr(date, 1, 7) = ?
            GROUP BY date
            ORDER BY date ASC
            """,
            (month,),
        ).fetchall()

        category_rows = conn.execute(
            """
            SELECT category_main, ROUND(SUM(amount), 2) AS expense_amount
            FROM transactions
            WHERE type = 'expense' AND substr(date, 1, 7) = ?
            GROUP BY category_main
            ORDER BY expense_amount DESC
            """,
            (month,),
        ).fetchall()

    total_expense = float(totals_row["total_expense"] or 0)
    total_income = float(totals_row["total_income"] or 0)
    balance = total_income - total_expense

    return {
        "month": month,
        "summary": {
            "total_expense": round(total_expense, 2),
            "total_income": round(total_income, 2),
            "balance": round(balance, 2),
        },
        "daily_expense": [
            {"date": row["date"], "amount": float(row["expense_amount"] or 0)} for row in daily_rows
        ],
        "category_share": [
            {"category": row["category_main"], "amount": float(row["expense_amount"] or 0)}
            for row in category_rows
        ],
    }


def get_transactions_by_month(month: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                id,
                amount,
                type,
                date,
                category_main,
                category_sub,
                tags,
                note,
                created_at
            FROM transactions
            WHERE substr(date, 1, 7) = ?
            ORDER BY date DESC, id DESC
            """,
            (month,),
        ).fetchall()

    records: list[dict] = []
    for row in rows:
        item = dict(row)
        item["amount"] = float(item["amount"])
        item["tags"] = parse_tags(item.get("tags"))
        records.append(item)
    return records


def get_monthly_stats(month: str) -> dict:
    records = get_transactions_by_month(month)

    total_expense = sum(record["amount"] for record in records if record["type"] == "expense")
    total_income = sum(record["amount"] for record in records if record["type"] == "income")
    balance = total_income - total_expense

    daily_map: dict[str, float] = {}
    category_map: dict[str, float] = {}
    tag_map: dict[str, float] = {}

    for record in records:
        if record["type"] != "expense":
            continue

        amount = float(record["amount"])
        day = record["date"]
        category = record["category_main"] or "其他"

        daily_map[day] = round(daily_map.get(day, 0) + amount, 2)
        category_map[category] = round(category_map.get(category, 0) + amount, 2)

        for tag in record["tags"]:
            tag_map[tag] = round(tag_map.get(tag, 0) + amount, 2)

    category_stats = []
    for category, amount in sorted(category_map.items(), key=lambda x: x[1], reverse=True):
        ratio = (amount / total_expense * 100) if total_expense > 0 else 0
        category_stats.append(
            {
                "name": category,
                "amount": round(amount, 2),
                "ratio": round(ratio, 2),
            }
        )

    tag_stats = []
    for tag, amount in sorted(tag_map.items(), key=lambda x: x[1], reverse=True):
        ratio = (amount / total_expense * 100) if total_expense > 0 else 0
        tag_stats.append(
            {
                "name": tag,
                "amount": round(amount, 2),
                "ratio": round(ratio, 2),
            }
        )

    daily_expense = [
        {"date": day, "amount": amount} for day, amount in sorted(daily_map.items(), key=lambda x: x[0])
    ]

    return {
        "month": month,
        "total_expense": round(total_expense, 2),
        "total_income": round(total_income, 2),
        "balance": round(balance, 2),
        "category_stats": category_stats,
        "tag_stats": tag_stats,
        "daily_expense": daily_expense,
    }


def get_category_trend(category_name: str, month: str) -> dict:
    months = month_sequence(month, count=3)

    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT substr(date, 1, 7) AS month, ROUND(SUM(amount), 2) AS amount
            FROM transactions
            WHERE type = 'expense'
              AND category_main = ?
              AND substr(date, 1, 7) IN (?, ?, ?)
            GROUP BY substr(date, 1, 7)
            """,
            (category_name, months[0], months[1], months[2]),
        ).fetchall()

    row_map = {row["month"]: float(row["amount"] or 0) for row in rows}
    points = [{"month": month_item, "amount": round(row_map.get(month_item, 0), 2)} for month_item in months]

    return {
        "name": category_name,
        "months": months,
        "trend": points,
    }


def get_tag_trend(tag_name: str, month: str) -> dict:
    months = month_sequence(month, count=3)

    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                id,
                amount,
                date,
                tags
            FROM transactions
            WHERE type = 'expense'
              AND substr(date, 1, 7) IN (?, ?, ?)
            """,
            (months[0], months[1], months[2]),
        ).fetchall()

    month_amount: dict[str, float] = {month_item: 0.0 for month_item in months}
    for row in rows:
        tags = parse_tags(row["tags"])
        if tag_name in tags:
            month_key = row["date"][:7]
            month_amount[month_key] = round(month_amount.get(month_key, 0) + float(row["amount"]), 2)

    points = [{"month": month_item, "amount": round(month_amount.get(month_item, 0), 2)} for month_item in months]

    return {
        "name": tag_name,
        "months": months,
        "trend": points,
    }


def get_month_expense_by_category(month: str) -> dict[str, float]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT category_main, ROUND(SUM(amount), 2) AS expense_amount
            FROM transactions
            WHERE type = 'expense' AND substr(date, 1, 7) = ?
            GROUP BY category_main
            """,
            (month,),
        ).fetchall()

    return {row["category_main"]: float(row["expense_amount"] or 0) for row in rows}


def get_today_expense(target_date: str | None = None) -> float:
    if not target_date:
        target_date = date.today().isoformat()

    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT COALESCE(SUM(amount), 0) AS total
            FROM transactions
            WHERE type = 'expense' AND date = ?
            """,
            (target_date,),
        ).fetchone()

    return round(float(row["total"] or 0), 2)


def get_recent_average_month_expense(month: str, count: int = 3) -> float:
    months = month_sequence(month, count=count)
    placeholders = ",".join("?" for _ in months)

    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT substr(date, 1, 7) AS month, ROUND(SUM(amount), 2) AS amount
            FROM transactions
            WHERE type = 'expense' AND substr(date, 1, 7) IN ({placeholders})
            GROUP BY substr(date, 1, 7)
            """,
            tuple(months),
        ).fetchall()

    month_amount_map = {row["month"]: float(row["amount"] or 0) for row in rows}
    amounts = [month_amount_map.get(month_item, 0.0) for month_item in months]
    if not amounts:
        return 0.0
    return round(sum(amounts) / len(amounts), 2)
