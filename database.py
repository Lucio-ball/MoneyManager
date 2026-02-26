import os
import json
import calendar
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_DIR = BASE_DIR / "data"
DB_PATH = DB_DIR / "money_manager.db"


def get_connection() -> sqlite3.Connection:
    """Create a SQLite connection with dict-like row access."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Initialize SQLite database and required tables."""
    os.makedirs(DB_DIR, exist_ok=True)

    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                amount REAL NOT NULL,
                type TEXT CHECK(type IN ('income', 'expense')) NOT NULL,
                date TEXT NOT NULL,
                category_main TEXT NOT NULL,
                category_sub TEXT,
                tags TEXT,
                payment_method TEXT CHECK(payment_method IN ('wechat', 'alipay_family', 'bank')),
                note TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS budgets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                month TEXT NOT NULL,
                category_main TEXT,
                budget_amount REAL NOT NULL
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ai_archives (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                month TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                amount REAL NOT NULL,
                cycle TEXT CHECK(cycle IN ('monthly', 'yearly', 'weekly', 'quarterly')) NOT NULL,
                next_billing_date TEXT NOT NULL,
                category TEXT,
                payment_method TEXT,
                note TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS subscription_cancellations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subscription_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                amount REAL NOT NULL,
                cycle TEXT NOT NULL,
                next_billing_date TEXT NOT NULL,
                category TEXT,
                payment_method TEXT,
                note TEXT,
                cancelled_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS subscription_charges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subscription_id INTEGER NOT NULL,
                billing_date TEXT NOT NULL,
                amount REAL NOT NULL,
                transaction_id INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(subscription_id, billing_date)
            );
            """
        )
        conn.commit()


def create_transaction(transaction: dict) -> int:
    """Insert one transaction and return created row id."""
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
                payment_method,
                note
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                float(transaction["amount"]),
                transaction["type"],
                transaction["date"],
                transaction["category_main"],
                transaction.get("category_sub") or None,
                tags_json,
                transaction.get("payment_method") or None,
                transaction.get("note") or None,
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)


def get_recent_transactions(limit: int = 10) -> list[dict]:
    """Get latest transactions ordered by date and id desc."""
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
                payment_method,
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
        item["tags"] = json.loads(item["tags"]) if item.get("tags") else []
        result.append(item)
    return result


def get_monthly_dashboard_data(month: str | None = None) -> dict:
    """Get monthly totals + daily expense trend + category expense share."""
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


def _parse_tags(tags_text: str | None) -> list[str]:
    if not tags_text:
        return []
    try:
        tags = json.loads(tags_text)
        return tags if isinstance(tags, list) else []
    except json.JSONDecodeError:
        return []


def _month_sequence(month: str, count: int = 3) -> list[str]:
    year, mon = map(int, month.split("-"))
    result: list[str] = []
    current_year = year
    current_mon = mon
    for _ in range(count):
        result.append(f"{current_year:04d}-{current_mon:02d}")
        current_mon -= 1
        if current_mon == 0:
            current_mon = 12
            current_year -= 1
    result.reverse()
    return result


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _monthly_cost(amount: float, cycle: str) -> float:
    if cycle == "yearly":
        return round(amount / 12, 2)
    if cycle == "quarterly":
        return round(amount / 3, 2)
    if cycle == "weekly":
        return round(amount * 52 / 12, 2)
    return round(amount, 2)


def _add_months(base_date: date, months: int) -> date:
    month_index = (base_date.month - 1) + months
    target_year = base_date.year + month_index // 12
    target_month = month_index % 12 + 1
    target_day = min(base_date.day, calendar.monthrange(target_year, target_month)[1])
    return date(target_year, target_month, target_day)


def _next_billing_date(current_date: date, cycle: str) -> date:
    if cycle == "weekly":
        return current_date + timedelta(days=7)
    if cycle == "monthly":
        return _add_months(current_date, 1)
    if cycle == "quarterly":
        return _add_months(current_date, 3)
    if cycle == "yearly":
        return _add_months(current_date, 12)
    return _add_months(current_date, 1)


def _build_subscription_charge_transaction(subscription: dict, billing_date: date) -> dict:
    return {
        "amount": round(float(subscription["amount"]), 2),
        "type": "expense",
        "date": billing_date.isoformat(),
        "category_main": subscription.get("category") or "其他",
        "category_sub": "订阅扣费",
        "tags": ["订阅", "自动扣费"],
        "payment_method": subscription.get("payment_method") or None,
        "note": f"[订阅自动扣费] {subscription.get('name', '')}",
    }


def _create_subscription_charge_if_needed(conn: sqlite3.Connection, subscription: dict, billing_date: date) -> bool:
    conn.execute(
        """
        INSERT OR IGNORE INTO subscription_charges (
            subscription_id,
            billing_date,
            amount
        ) VALUES (?, ?, ?)
        """,
        (
            int(subscription["id"]),
            billing_date.isoformat(),
            round(float(subscription["amount"]), 2),
        ),
    )

    charge_row = conn.execute(
        """
        SELECT id, transaction_id
        FROM subscription_charges
        WHERE subscription_id = ? AND billing_date = ?
        """,
        (int(subscription["id"]), billing_date.isoformat()),
    ).fetchone()

    if not charge_row:
        return False

    if charge_row["transaction_id"]:
        return False

    transaction = _build_subscription_charge_transaction(subscription, billing_date)
    cursor = conn.execute(
        """
        INSERT INTO transactions (
            amount,
            type,
            date,
            category_main,
            category_sub,
            tags,
            payment_method,
            note
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            transaction["amount"],
            transaction["type"],
            transaction["date"],
            transaction["category_main"],
            transaction["category_sub"],
            json.dumps(transaction["tags"], ensure_ascii=False),
            transaction["payment_method"],
            transaction["note"],
        ),
    )

    transaction_id = cursor.lastrowid
    if transaction_id is None:
        return False

    conn.execute(
        """
        UPDATE subscription_charges
        SET transaction_id = ?
        WHERE id = ?
        """,
        (int(transaction_id), int(charge_row["id"])),
    )
    return True


def process_due_subscription_charges(target_date: str | None = None) -> dict:
    billing_day = _parse_date(target_date) if target_date else date.today()
    if not billing_day:
        billing_day = date.today()

    created_transactions = 0
    updated_subscriptions = 0

    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                id,
                name,
                amount,
                cycle,
                next_billing_date,
                category,
                payment_method
            FROM subscriptions
            ORDER BY id ASC
            """
        ).fetchall()

        for row in rows:
            item = dict(row)
            due_date = _parse_date(item.get("next_billing_date"))
            if not due_date:
                continue

            charged_any = False
            while due_date <= billing_day:
                created = _create_subscription_charge_if_needed(conn, item, due_date)
                if created:
                    created_transactions += 1
                charged_any = True
                due_date = _next_billing_date(due_date, item.get("cycle") or "monthly")

            if charged_any:
                conn.execute(
                    """
                    UPDATE subscriptions
                    SET next_billing_date = ?
                    WHERE id = ?
                    """,
                    (due_date.isoformat(), int(item["id"])),
                )
                updated_subscriptions += 1

        conn.commit()

    return {
        "processed_date": billing_day.isoformat(),
        "created_transactions": created_transactions,
        "updated_subscriptions": updated_subscriptions,
    }


def get_subscription_actual_charge_summary(month: str) -> dict:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT
                COALESCE(SUM(amount), 0) AS total_amount,
                COUNT(*) AS charge_count
            FROM subscription_charges
            WHERE substr(billing_date, 1, 7) = ?
            """,
            (month,),
        ).fetchone()

    return {
        "month": month,
        "actual_charged_amount": round(float(row["total_amount"] or 0), 2),
        "charge_count": int(row["charge_count"] or 0),
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
                payment_method,
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
        item["tags"] = _parse_tags(item.get("tags"))
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
    months = _month_sequence(month, count=3)

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
    months = _month_sequence(month, count=3)

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
        tags = _parse_tags(row["tags"])
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
        return int(cursor.lastrowid)


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

    months = _month_sequence(month, count=3)
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
        return int(cursor.lastrowid)


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


def create_subscription(subscription: dict) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO subscriptions (
                name,
                amount,
                cycle,
                next_billing_date,
                category,
                payment_method,
                note
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                subscription["name"],
                float(subscription["amount"]),
                subscription["cycle"],
                subscription["next_billing_date"],
                subscription.get("category") or None,
                subscription.get("payment_method") or None,
                subscription.get("note") or None,
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)


def get_subscription_by_id(subscription_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT
                id,
                name,
                amount,
                cycle,
                next_billing_date,
                category,
                payment_method,
                note,
                created_at
            FROM subscriptions
            WHERE id = ?
            """,
            (subscription_id,),
        ).fetchone()

    if not row:
        return None

    item = dict(row)
    item["amount"] = round(float(item["amount"]), 2)
    item["monthly_cost"] = _monthly_cost(item["amount"], item["cycle"])

    today = date.today()
    next_billing = _parse_date(item.get("next_billing_date"))
    if next_billing:
        item["is_expired"] = next_billing < today
        item["is_upcoming"] = today <= next_billing <= today + timedelta(days=7)
        item["days_until_billing"] = (next_billing - today).days
    else:
        item["is_expired"] = False
        item["is_upcoming"] = False
        item["days_until_billing"] = None

    return item


def list_subscriptions() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                id,
                name,
                amount,
                cycle,
                next_billing_date,
                category,
                payment_method,
                note,
                created_at
            FROM subscriptions
            ORDER BY next_billing_date ASC, id DESC
            """
        ).fetchall()

    today = date.today()
    in_seven_days = today + timedelta(days=7)
    result: list[dict] = []
    for row in rows:
        item = dict(row)
        item["amount"] = round(float(item["amount"]), 2)
        item["monthly_cost"] = _monthly_cost(item["amount"], item["cycle"])

        next_billing = _parse_date(item.get("next_billing_date"))
        if next_billing:
            item["is_expired"] = next_billing < today
            item["is_upcoming"] = today <= next_billing <= in_seven_days
            item["days_until_billing"] = (next_billing - today).days
        else:
            item["is_expired"] = False
            item["is_upcoming"] = False
            item["days_until_billing"] = None

        result.append(item)

    return result


def update_subscription(subscription_id: int, subscription: dict) -> bool:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE subscriptions
            SET
                name = ?,
                amount = ?,
                cycle = ?,
                next_billing_date = ?,
                category = ?,
                payment_method = ?,
                note = ?
            WHERE id = ?
            """,
            (
                subscription["name"],
                float(subscription["amount"]),
                subscription["cycle"],
                subscription["next_billing_date"],
                subscription.get("category") or None,
                subscription.get("payment_method") or None,
                subscription.get("note") or None,
                subscription_id,
            ),
        )
        conn.commit()
        return cursor.rowcount > 0


def delete_subscription(subscription_id: int) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT
                id,
                name,
                amount,
                cycle,
                next_billing_date,
                category,
                payment_method,
                note
            FROM subscriptions
            WHERE id = ?
            """,
            (subscription_id,),
        ).fetchone()

        if not row:
            return False

        item = dict(row)
        conn.execute(
            """
            INSERT INTO subscription_cancellations (
                subscription_id,
                name,
                amount,
                cycle,
                next_billing_date,
                category,
                payment_method,
                note
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(item["id"]),
                item["name"],
                float(item["amount"]),
                item["cycle"],
                item["next_billing_date"],
                item.get("category"),
                item.get("payment_method"),
                item.get("note"),
            ),
        )

        cursor = conn.execute(
            "DELETE FROM subscriptions WHERE id = ?",
            (subscription_id,),
        )
        conn.commit()
        return cursor.rowcount > 0


def get_upcoming_subscriptions(days: int = 7) -> list[dict]:
    today = date.today().isoformat()
    deadline = (date.today() + timedelta(days=days)).isoformat()

    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                id,
                name,
                amount,
                cycle,
                next_billing_date,
                category,
                payment_method,
                note,
                created_at
            FROM subscriptions
            WHERE next_billing_date >= ? AND next_billing_date <= ?
            ORDER BY next_billing_date ASC, id DESC
            """,
            (today, deadline),
        ).fetchall()

    result: list[dict] = []
    for row in rows:
        item = dict(row)
        item["amount"] = round(float(item["amount"]), 2)
        item["monthly_cost"] = _monthly_cost(item["amount"], item["cycle"])
        next_billing = _parse_date(item.get("next_billing_date"))
        item["days_until_billing"] = (next_billing - date.today()).days if next_billing else None
        result.append(item)
    return result


def get_subscription_monthly_cost_summary() -> dict:
    subscriptions = list_subscriptions()
    total_monthly_cost = round(sum(item["monthly_cost"] for item in subscriptions), 2)
    upcoming_count = sum(1 for item in subscriptions if item.get("is_upcoming"))
    expired_count = sum(1 for item in subscriptions if item.get("is_expired"))

    cycle_map: dict[str, int] = {"monthly": 0, "yearly": 0, "weekly": 0, "quarterly": 0}
    for item in subscriptions:
        cycle_map[item["cycle"]] = cycle_map.get(item["cycle"], 0) + 1

    top_monthly_cost = sorted(subscriptions, key=lambda x: x["monthly_cost"], reverse=True)[:5]

    return {
        "total_count": len(subscriptions),
        "total_monthly_cost": total_monthly_cost,
        "upcoming_count": upcoming_count,
        "expired_count": expired_count,
        "cycle_distribution": cycle_map,
        "top_monthly_cost": [
            {
                "id": item["id"],
                "name": item["name"],
                "monthly_cost": item["monthly_cost"],
            }
            for item in top_monthly_cost
        ],
    }


def get_subscription_monthly_metrics(month: str) -> dict:
    summary = get_subscription_monthly_cost_summary()
    actual = get_subscription_actual_charge_summary(month)
    return {
        "month": month,
        "estimated_monthly_cost": round(float(summary.get("total_monthly_cost", 0)), 2),
        "actual_charged_amount": round(float(actual.get("actual_charged_amount", 0)), 2),
        "actual_charge_count": int(actual.get("charge_count", 0)),
    }


def get_subscription_monthly_recap(month: str) -> dict:
    with get_connection() as conn:
        created_row = conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM subscriptions
            WHERE substr(created_at, 1, 7) = ?
            """,
            (month,),
        ).fetchone()
        cancelled_row = conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM subscription_cancellations
            WHERE substr(cancelled_at, 1, 7) = ?
            """,
            (month,),
        ).fetchone()

    year, mon = map(int, month.split("-"))
    if mon == 12:
        next_month = f"{year + 1:04d}-01"
    else:
        next_month = f"{year:04d}-{mon + 1:02d}"

    with get_connection() as conn:
        next_month_rows = conn.execute(
            """
            SELECT
                id,
                name,
                amount,
                cycle,
                next_billing_date,
                category,
                payment_method
            FROM subscriptions
            WHERE substr(next_billing_date, 1, 7) = ?
            ORDER BY next_billing_date ASC, id DESC
            """,
            (next_month,),
        ).fetchall()

    next_month_upcoming = []
    for row in next_month_rows:
        item = dict(row)
        item["amount"] = round(float(item["amount"]), 2)
        item["monthly_cost"] = _monthly_cost(item["amount"], item["cycle"])
        next_month_upcoming.append(item)

    summary = get_subscription_monthly_cost_summary()
    metrics = get_subscription_monthly_metrics(month)

    return {
        "month": month,
        "monthly_total_cost": summary["total_monthly_cost"],
        "estimated_monthly_cost": metrics["estimated_monthly_cost"],
        "actual_charged_amount": metrics["actual_charged_amount"],
        "actual_charge_count": metrics["actual_charge_count"],
        "new_subscriptions": int(created_row["total"] or 0),
        "cancelled_subscriptions": int(cancelled_row["total"] or 0),
        "next_month_upcoming": next_month_upcoming,
    }


def get_ai_monthly_package(month: str) -> dict:
    return {
        "month": month,
        "monthly_stats": get_monthly_stats(month),
        "insights": get_monthly_insights(month),
        "budgets": get_budget_execution(month),
        "subscriptions": get_subscription_monthly_recap(month),
    }


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
    months = _month_sequence(month, count=count)
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
