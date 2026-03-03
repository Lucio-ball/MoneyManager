import json
from datetime import date, timedelta

from extensions.database import get_connection
from utils.date_utils import next_billing_date, parse_date
from utils.math_utils import monthly_cost


def _build_subscription_charge_transaction(subscription: dict, billing_date: date) -> dict:
    return {
        "amount": round(float(subscription["amount"]), 2),
        "type": "expense",
        "date": billing_date.isoformat(),
        "category_main": subscription.get("category") or "其他",
        "category_sub": "订阅扣费",
        "tags": ["订阅", "自动扣费"],
        "note": f"[订阅自动扣费] {subscription.get('name', '')}",
    }


def _create_subscription_charge_if_needed(conn, subscription: dict, billing_date: date) -> bool:
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

    if not charge_row or charge_row["transaction_id"]:
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
            note
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            transaction["amount"],
            transaction["type"],
            transaction["date"],
            transaction["category_main"],
            transaction["category_sub"],
            json.dumps(transaction["tags"], ensure_ascii=False),
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
    billing_day = parse_date(target_date) if target_date else date.today()
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
            due_date = parse_date(item.get("next_billing_date"))
            if not due_date:
                continue

            charged_any = False
            while due_date <= billing_day:
                created = _create_subscription_charge_if_needed(conn, item, due_date)
                if created:
                    created_transactions += 1
                charged_any = True
                due_date = next_billing_date(due_date, item.get("cycle") or "monthly")

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
        last_row_id = cursor.lastrowid
        if last_row_id is None:
            raise RuntimeError("failed to create subscription")
        return int(last_row_id)


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
    item["monthly_cost"] = monthly_cost(item["amount"], item["cycle"])

    today = date.today()
    next_billing = parse_date(item.get("next_billing_date"))
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
        item["monthly_cost"] = monthly_cost(item["amount"], item["cycle"])

        next_billing = parse_date(item.get("next_billing_date"))
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
        item["monthly_cost"] = monthly_cost(item["amount"], item["cycle"])
        next_billing = parse_date(item.get("next_billing_date"))
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
        item["monthly_cost"] = monthly_cost(item["amount"], item["cycle"])
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
