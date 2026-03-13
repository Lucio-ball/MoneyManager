import json
from datetime import date
from math import sqrt

from extensions.database import get_connection
from models.reimbursement import get_expense_reimbursement_map
from utils.date_utils import month_sequence
from utils.trend_utils import parse_tags


REIMBURSEMENT_CATEGORY = "\u62a5\u9500"


def _is_reimbursement_income_record(record: dict) -> bool:
    if record.get("type") != "income":
        return False
    source = str(record.get("category_sub") or "").strip()
    return source == REIMBURSEMENT_CATEGORY


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


def _map_transaction_row(row) -> dict:
    item = dict(row)
    item["amount"] = float(item["amount"])
    item["tags"] = parse_tags(item.get("tags"))
    return item


def _get_reimbursement_marker_id(conn, expense_transaction_id: int) -> int | None:
    row = conn.execute(
        """
        SELECT id
        FROM reimbursement_links
        WHERE expense_transaction_id = ?
          AND reimbursement_transaction_id IS NULL
        ORDER BY id DESC
        LIMIT 1
        """,
        (expense_transaction_id,),
    ).fetchone()
    return int(row["id"]) if row else None


def _sync_expense_reimbursement_status(conn, expense_transaction_id: int) -> None:
    marker_id = _get_reimbursement_marker_id(conn, expense_transaction_id)
    if marker_id is None:
        return

    marker_row = conn.execute(
        """
        SELECT amount
        FROM reimbursement_links
        WHERE id = ?
        """,
        (marker_id,),
    ).fetchone()
    if marker_row is None:
        return

    target_amount = round(float(marker_row["amount"] or 0), 2)
    linked_row = conn.execute(
        """
        SELECT COALESCE(SUM(amount), 0) AS total
        FROM reimbursement_links
        WHERE expense_transaction_id = ?
          AND reimbursement_transaction_id IS NOT NULL
        """,
        (expense_transaction_id,),
    ).fetchone()
    reimbursed_amount = round(float(linked_row["total"] or 0), 2)

    if reimbursed_amount <= 0:
        status = "pending"
    elif reimbursed_amount + 0.005 >= target_amount:
        status = "completed"
    else:
        status = "partial"

    conn.execute(
        """
        UPDATE reimbursement_links
        SET status = ?
        WHERE id = ?
        """,
        (status, marker_id),
    )


def get_transaction_by_id(transaction_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
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
            WHERE id = ?
            """,
            (transaction_id,),
        ).fetchone()

    if not row:
        return None
    return _attach_reimbursement_fields([_map_transaction_row(row)])[0]


def query_transactions(
    page: int = 1,
    per_page: int = 20,
    keyword: str | None = None,
    category: str | None = None,
    transaction_type: str | None = None,
    date_range: str | None = None,
    min_amount: float | None = None,
    max_amount: float | None = None,
) -> dict:
    page = max(int(page or 1), 1)
    per_page = max(int(per_page or 20), 1)
    offset = (page - 1) * per_page

    where_clauses: list[str] = []
    params: list = []

    keyword_value = str(keyword or "").strip()
    if keyword_value:
        like_value = f"%{keyword_value}%"
        where_clauses.append(
            """
            (
                COALESCE(category_main, '') LIKE ?
                OR COALESCE(category_sub, '') LIKE ?
                OR COALESCE(tags, '') LIKE ?
                OR COALESCE(note, '') LIKE ?
            )
            """
        )
        params.extend([like_value, like_value, like_value, like_value])

    category_value = str(category or "").strip()
    if category_value:
        where_clauses.append("category_main = ?")
        params.append(category_value)

    type_value = str(transaction_type or "").strip()
    if type_value in {"income", "expense"}:
        where_clauses.append("type = ?")
        params.append(type_value)
    else:
        type_value = ""

    start_date = ""
    end_date = ""
    date_range_value = str(date_range or "").strip()
    if date_range_value:
        parts = [part.strip() for part in date_range_value.split(",", 1)]
        if parts and parts[0]:
            start_date = parts[0]
            where_clauses.append("date >= ?")
            params.append(start_date)
        if len(parts) > 1 and parts[1]:
            end_date = parts[1]
            where_clauses.append("date <= ?")
            params.append(end_date)

    min_amount_value = None
    if min_amount not in (None, ""):
        min_amount_value = float(min_amount)
        where_clauses.append("amount >= ?")
        params.append(min_amount_value)

    max_amount_value = None
    if max_amount not in (None, ""):
        max_amount_value = float(max_amount)
        where_clauses.append("amount <= ?")
        params.append(max_amount_value)

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    with get_connection() as conn:
        total_row = conn.execute(
            f"""
            SELECT COUNT(*) AS total
            FROM transactions
            {where_sql}
            """,
            tuple(params),
        ).fetchone()
        rows = conn.execute(
            f"""
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
            {where_sql}
            ORDER BY date DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            (*params, per_page, offset),
        ).fetchall()

    total = int(total_row["total"] or 0)
    records = _attach_reimbursement_fields([_map_transaction_row(row) for row in rows])
    total_pages = max((total + per_page - 1) // per_page, 1)

    return {
        "items": records,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "has_prev": page > 1,
            "has_next": page < total_pages,
        },
        "filters": {
            "keyword": keyword_value,
            "category": category_value,
            "type": type_value,
            "date_range": date_range_value,
            "start_date": start_date,
            "end_date": end_date,
            "min_amount": min_amount_value,
            "max_amount": max_amount_value,
        },
    }


def update_transaction(transaction_id: int, transaction: dict) -> bool:
    existing = get_transaction_by_id(transaction_id)
    if not existing:
        return False

    tags_json = json.dumps(transaction.get("tags", []), ensure_ascii=False)
    old_type = str(existing.get("type") or "").strip()
    new_type = str(transaction.get("type") or "").strip()
    old_income_source = str(existing.get("category_sub") or "").strip()
    new_income_source = str(transaction.get("category_sub") or "").strip()

    with get_connection() as conn:
        linked_expense_rows = conn.execute(
            """
            SELECT DISTINCT expense_transaction_id
            FROM reimbursement_links
            WHERE reimbursement_transaction_id = ?
            """,
            (transaction_id,),
        ).fetchall()
        linked_expense_ids = [int(row["expense_transaction_id"]) for row in linked_expense_rows]

        conn.execute(
            """
            UPDATE transactions
            SET amount = ?, type = ?, date = ?, category_main = ?, category_sub = ?, tags = ?, note = ?
            WHERE id = ?
            """,
            (
                float(transaction["amount"]),
                transaction["type"],
                transaction["date"],
                transaction["category_main"],
                transaction.get("category_sub") or None,
                tags_json,
                transaction.get("note") or None,
                transaction_id,
            ),
        )

        if old_type != new_type:
            conn.execute(
                """
                DELETE FROM reimbursement_links
                WHERE expense_transaction_id = ?
                   OR reimbursement_transaction_id = ?
                """,
                (transaction_id, transaction_id),
            )
            for expense_id in linked_expense_ids:
                _sync_expense_reimbursement_status(conn, expense_id)
        elif new_type == "income" and old_income_source == REIMBURSEMENT_CATEGORY and new_income_source != REIMBURSEMENT_CATEGORY:
            conn.execute(
                """
                DELETE FROM reimbursement_links
                WHERE reimbursement_transaction_id = ?
                """,
                (transaction_id,),
            )
            for expense_id in linked_expense_ids:
                _sync_expense_reimbursement_status(conn, expense_id)
        elif new_type == "expense":
            marker_id = _get_reimbursement_marker_id(conn, transaction_id)
            if marker_id is not None:
                conn.execute(
                    """
                    UPDATE reimbursement_links
                    SET amount = MIN(amount, ?)
                    WHERE id = ?
                    """,
                    (float(transaction["amount"]), marker_id),
                )
                _sync_expense_reimbursement_status(conn, transaction_id)

        conn.commit()
        return True


def delete_transaction(transaction_id: int) -> bool:
    existing = get_transaction_by_id(transaction_id)
    if not existing:
        return False

    with get_connection() as conn:
        linked_expense_rows = conn.execute(
            """
            SELECT DISTINCT expense_transaction_id
            FROM reimbursement_links
            WHERE reimbursement_transaction_id = ?
            """,
            (transaction_id,),
        ).fetchall()
        linked_expense_ids = [int(row["expense_transaction_id"]) for row in linked_expense_rows]

        conn.execute(
            """
            DELETE FROM reimbursement_links
            WHERE expense_transaction_id = ?
               OR reimbursement_transaction_id = ?
            """,
            (transaction_id, transaction_id),
        )
        conn.execute(
            """
            DELETE FROM transactions
            WHERE id = ?
            """,
            (transaction_id,),
        )

        for expense_id in linked_expense_ids:
            _sync_expense_reimbursement_status(conn, expense_id)

        conn.commit()
        return True


def _attach_reimbursement_fields(records: list[dict]) -> list[dict]:
    expense_ids = [int(item["id"]) for item in records if item.get("type") == "expense"]
    reimbursement_map = get_expense_reimbursement_map(expense_ids)

    for item in records:
        if item.get("type") != "expense":
            continue
        reimbursement = reimbursement_map.get(int(item["id"]))
        if reimbursement:
            item["reimbursement"] = reimbursement
    return records


def _is_subscription_expense_record(record: dict) -> bool:
    if record.get("type") != "expense":
        return False
    tags = set(record.get("tags") or [])
    category_sub = str(record.get("category_sub") or "").strip()
    note = str(record.get("note") or "").strip()
    return "订阅" in tags or category_sub == "订阅扣费" or note.startswith("[订阅自动扣费]")


def _is_reimbursable_expense_record(record: dict) -> bool:
    return record.get("type") == "expense" and bool(record.get("reimbursement"))


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

    return _attach_reimbursement_fields([_map_transaction_row(row) for row in rows])


def get_monthly_financial_summary(month: str) -> dict:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT
                COALESCE(SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END), 0) AS gross_income,
                COALESCE(SUM(CASE WHEN type = 'income' AND TRIM(COALESCE(category_sub, '')) = ? THEN amount ELSE 0 END), 0) AS reimbursement_income,
                COALESCE(SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END), 0) AS gross_expense
            FROM transactions
            WHERE substr(date, 1, 7) = ?
            """,
            (REIMBURSEMENT_CATEGORY, month),
        ).fetchone()

    gross_income = float(row["gross_income"] or 0)
    reimbursement_income = float(row["reimbursement_income"] or 0)
    gross_expense = float(row["gross_expense"] or 0)
    real_income = gross_income - reimbursement_income
    net_expense = gross_expense - reimbursement_income
    balance = real_income - net_expense

    return {
        "month": month,
        "gross_income": round(gross_income, 2),
        "reimbursement_income": round(reimbursement_income, 2),
        "real_income": round(real_income, 2),
        "gross_expense": round(gross_expense, 2),
        "net_expense": round(net_expense, 2),
        "balance": round(balance, 2),
        "total_income": round(gross_income, 2),
        "total_expense": round(gross_expense, 2),
    }


def get_monthly_dashboard_data(month: str | None = None) -> dict:
    if not month:
        month = date.today().strftime("%Y-%m")

    financial_summary = get_monthly_financial_summary(month)

    with get_connection() as conn:
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

    return {
        "month": month,
        "summary": financial_summary,
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

    return _attach_reimbursement_fields([_map_transaction_row(row) for row in rows])


def get_monthly_stats(month: str) -> dict:
    records = get_transactions_by_month(month)
    financial_summary = get_monthly_financial_summary(month)

    gross_expense = float(financial_summary["gross_expense"])

    daily_map: dict[str, float] = {}
    category_map: dict[str, float] = {}
    tag_map: dict[str, float] = {}

    for record in records:
        if record["type"] != "expense":
            continue

        amount = float(record["amount"])
        day = record["date"]
        category = record["category_main"] or "鍏朵粬"

        daily_map[day] = round(daily_map.get(day, 0) + amount, 2)
        category_map[category] = round(category_map.get(category, 0) + amount, 2)

        for tag in record["tags"]:
            tag_map[tag] = round(tag_map.get(tag, 0) + amount, 2)

    category_stats = []
    for category, amount in sorted(category_map.items(), key=lambda x: x[1], reverse=True):
        ratio = (amount / gross_expense * 100) if gross_expense > 0 else 0
        category_stats.append(
            {
                "name": category,
                "amount": round(amount, 2),
                "ratio": round(ratio, 2),
            }
        )

    tag_stats = []
    for tag, amount in sorted(tag_map.items(), key=lambda x: x[1], reverse=True):
        ratio = (amount / gross_expense * 100) if gross_expense > 0 else 0
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
        **financial_summary,
        "category_stats": category_stats,
        "tag_stats": tag_stats,
        "daily_expense": daily_expense,
    }


def get_month_reimbursement_income(month: str) -> float:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT COALESCE(SUM(amount), 0) AS total
            FROM transactions
            WHERE type = 'income'
              AND TRIM(COALESCE(category_sub, '')) = ?
              AND substr(date, 1, 7) = ?
            """,
            (REIMBURSEMENT_CATEGORY, month),
        ).fetchone()

    return round(float(row["total"] or 0), 2)


def get_reimbursement_income_by_months(months: list[str]) -> dict[str, float]:
    if not months:
        return {}

    placeholders = ",".join("?" for _ in months)
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT substr(date, 1, 7) AS month, ROUND(SUM(amount), 2) AS total
            FROM transactions
            WHERE type = 'income'
              AND TRIM(COALESCE(category_sub, '')) = ?
              AND substr(date, 1, 7) IN ({placeholders})
            GROUP BY substr(date, 1, 7)
            """,
            (REIMBURSEMENT_CATEGORY, *months),
        ).fetchall()

    month_amount_map = {month: 0.0 for month in months}
    for row in rows:
        month_amount_map[row["month"]] = round(float(row["total"] or 0), 2)

    return month_amount_map


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


def get_calendar_daily_expense(month: str) -> dict:
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
                note
            FROM transactions
            WHERE substr(date, 1, 7) = ?
            ORDER BY date ASC, id DESC
            """,
            (month,),
        ).fetchall()

    records: list[dict] = []
    for row in rows:
        item = dict(row)
        item["amount"] = round(float(item["amount"] or 0), 2)
        item["tags"] = parse_tags(item.get("tags"))
        records.append(item)

    records = _attach_reimbursement_fields(records)

    day_map: dict[str, dict] = {}
    expense_amounts: list[float] = []
    for item in records:
        day = item["date"]
        day_info = day_map.setdefault(
            day,
            {
                "date": day,
                "total_expense": 0.0,
                "expense_count": 0,
                "income_count": 0,
                "markers": {
                    "subscription": False,
                    "reimbursement": False,
                    "high_spending": False,
                    "budget_warning": False,
                },
            },
        )

        if item.get("type") == "expense":
            day_info["total_expense"] = round(day_info["total_expense"] + float(item["amount"] or 0), 2)
            day_info["expense_count"] += 1
            if _is_subscription_expense_record(item):
                day_info["markers"]["subscription"] = True
            if _is_reimbursable_expense_record(item):
                day_info["markers"]["reimbursement"] = True
        else:
            day_info["income_count"] += 1
            if _is_reimbursement_income_record(item):
                day_info["markers"]["reimbursement"] = True

    budget_warning_categories: set[str] = set()
    try:
        from models.budget import get_budget_execution

        budget_execution = get_budget_execution(month)
        budget_warning_categories = {
            str(item.get("category_main") or "").strip()
            for item in (budget_execution.get("items") or [])
            if item.get("category_main") and float(item.get("execution_rate") or 0) >= 80
        }
    except Exception:
        budget_warning_categories = set()

    max_expense = 0.0
    for item in records:
        if item.get("type") != "expense":
            continue
        day = item["date"]
        day_info = day_map[day]
        max_expense = max(max_expense, float(day_info["total_expense"] or 0))
        if str(item.get("category_main") or "").strip() in budget_warning_categories:
            day_info["markers"]["budget_warning"] = True

    for day_info in day_map.values():
        if float(day_info["total_expense"] or 0) > 0:
            expense_amounts.append(float(day_info["total_expense"] or 0))

    if expense_amounts:
        avg_expense = sum(expense_amounts) / len(expense_amounts)
        variance = sum((amount - avg_expense) ** 2 for amount in expense_amounts) / len(expense_amounts)
        std_dev = sqrt(variance)
        high_spending_threshold = max(avg_expense * 1.5, avg_expense + std_dev)
    else:
        high_spending_threshold = 0.0

    days = []
    for day in sorted(day_map.keys()):
        day_info = day_map[day]
        total_expense = round(float(day_info["total_expense"] or 0), 2)
        day_info["markers"]["high_spending"] = total_expense > 0 and total_expense >= high_spending_threshold
        marker_names = [name for name, enabled in day_info["markers"].items() if enabled]
        days.append(
            {
                "date": day_info["date"],
                "total_expense": total_expense,
                "expense_count": int(day_info["expense_count"] or 0),
                "income_count": int(day_info["income_count"] or 0),
                "markers": day_info["markers"],
                "marker_names": marker_names,
            }
        )

    return {
        "month": month,
        "max_expense": round(max_expense, 2),
        "high_spending_threshold": round(high_spending_threshold, 2),
        "days": days,
    }


def get_calendar_day_details(target_date: str) -> dict:
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
            WHERE date = ?
            ORDER BY type ASC, id DESC
            """,
            (target_date,),
        ).fetchall()

    records: list[dict] = []
    total_expense = 0.0
    total_income = 0.0
    for row in rows:
        item = dict(row)
        item["amount"] = round(float(item["amount"] or 0), 2)
        item["tags"] = parse_tags(item.get("tags"))
        if item.get("type") == "expense":
            total_expense += item["amount"]
        elif item.get("type") == "income":
            total_income += item["amount"]
        records.append(item)

    records = _attach_reimbursement_fields(records)

    grouped_transactions = {
        "normal_expense": [],
        "reimbursable_expense": [],
        "subscription": [],
        "income": [],
    }
    transactions = []
    for item in records:
        if item.get("type") == "income":
            group_key = "income"
        elif _is_subscription_expense_record(item):
            group_key = "subscription"
        elif _is_reimbursable_expense_record(item):
            group_key = "reimbursable_expense"
        else:
            group_key = "normal_expense"

        item["group"] = group_key
        grouped_transactions[group_key].append(item)
        transactions.append(item)

    return {
        "date": target_date,
        "total_expense": round(total_expense, 2),
        "total_income": round(total_income, 2),
        "expense_count": sum(1 for item in transactions if item.get("type") == "expense"),
        "transaction_count": len(transactions),
        "grouped_transactions": grouped_transactions,
        "transactions": transactions,
    }

