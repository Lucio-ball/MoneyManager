from extensions.database import get_connection


VALID_REIMBURSEMENT_STATUS = {"pending", "partial", "completed"}


def _normalize_status(status: str | None) -> str:
    status_value = str(status or "").strip().lower()
    if status_value in VALID_REIMBURSEMENT_STATUS:
        return status_value
    return "pending"


def _get_transaction(transaction_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, amount, type, date, category_main, category_sub, note
            FROM transactions
            WHERE id = ?
            """,
            (transaction_id,),
        ).fetchone()

    if not row:
        return None
    item = dict(row)
    item["amount"] = round(float(item["amount"] or 0), 2)
    return item


def _get_marker(conn, expense_transaction_id: int):
    return conn.execute(
        """
        SELECT id, expense_transaction_id, reimbursement_transaction_id, amount, status
        FROM reimbursement_links
        WHERE expense_transaction_id = ?
          AND reimbursement_transaction_id IS NULL
        ORDER BY id DESC
        LIMIT 1
        """,
        (expense_transaction_id,),
    ).fetchone()


def _get_linked_total(conn, expense_transaction_id: int) -> float:
    row = conn.execute(
        """
        SELECT COALESCE(SUM(amount), 0) AS total
        FROM reimbursement_links
        WHERE expense_transaction_id = ?
          AND reimbursement_transaction_id IS NOT NULL
        """,
        (expense_transaction_id,),
    ).fetchone()
    return round(float(row["total"] or 0), 2)


def _compute_status(target_amount: float, reimbursed_amount: float) -> str:
    if reimbursed_amount <= 0:
        return "pending"
    if reimbursed_amount + 0.005 >= target_amount:
        return "completed"
    return "partial"


def _sync_marker_status(conn, expense_transaction_id: int) -> dict:
    marker = _get_marker(conn, expense_transaction_id)
    if not marker:
        raise ValueError("expense is not marked as reimbursable")

    target_amount = round(float(marker["amount"] or 0), 2)
    reimbursed_amount = _get_linked_total(conn, expense_transaction_id)
    capped_reimbursed = min(reimbursed_amount, target_amount)
    pending_amount = max(target_amount - capped_reimbursed, 0.0)
    status = _compute_status(target_amount, reimbursed_amount)

    conn.execute(
        """
        UPDATE reimbursement_links
        SET status = ?
        WHERE id = ?
        """,
        (status, marker["id"]),
    )

    return {
        "expense_transaction_id": int(expense_transaction_id),
        "target_amount": round(target_amount, 2),
        "reimbursed_amount": round(capped_reimbursed, 2),
        "pending_amount": round(pending_amount, 2),
        "status": status,
        "progress": round((capped_reimbursed / target_amount * 100), 2) if target_amount > 0 else 0.0,
    }


def mark_expense_as_reimbursable(expense_transaction_id: int, amount: float | None = None) -> dict:
    expense = _get_transaction(expense_transaction_id)
    if not expense or expense.get("type") != "expense":
        raise ValueError("expense transaction not found")

    target_amount = round(float(amount if amount is not None else expense["amount"]), 2)
    if target_amount <= 0:
        raise ValueError("reimbursement amount must be greater than 0")
    if target_amount - expense["amount"] > 0.005:
        raise ValueError("reimbursement amount cannot exceed expense amount")

    with get_connection() as conn:
        marker = _get_marker(conn, expense_transaction_id)
        if marker:
            conn.execute(
                """
                UPDATE reimbursement_links
                SET amount = ?
                WHERE id = ?
                """,
                (target_amount, marker["id"]),
            )
        else:
            conn.execute(
                """
                INSERT INTO reimbursement_links (
                    expense_transaction_id,
                    reimbursement_transaction_id,
                    amount,
                    status
                ) VALUES (?, NULL, ?, 'pending')
                """,
                (expense_transaction_id, target_amount),
            )

        summary = _sync_marker_status(conn, expense_transaction_id)
        conn.commit()
        return summary


def validate_reimbursement_link_amount(
    expense_transaction_id: int,
    reimbursement_amount: float,
    link_amount: float | None = None,
) -> dict:
    expense = _get_transaction(expense_transaction_id)
    if not expense or expense.get("type") != "expense":
        raise ValueError("expense transaction not found")

    with get_connection() as conn:
        marker = _get_marker(conn, expense_transaction_id)
        target_amount = round(float(marker["amount"] or 0), 2) if marker else round(float(expense["amount"]), 2)
        reimbursed_before = _get_linked_total(conn, expense_transaction_id)

    remaining_amount = max(target_amount - reimbursed_before, 0.0)
    if remaining_amount <= 0:
        raise ValueError("expense reimbursement is already completed")

    resolved_link_amount = round(float(link_amount if link_amount is not None else reimbursement_amount), 2)
    if resolved_link_amount <= 0:
        raise ValueError("link amount must be greater than 0")
    if resolved_link_amount - reimbursement_amount > 0.005:
        raise ValueError("link amount cannot exceed reimbursement income amount")
    if resolved_link_amount - remaining_amount > 0.005:
        raise ValueError("link amount cannot exceed pending reimbursement amount")

    return {
        "target_amount": target_amount,
        "remaining_amount": round(remaining_amount, 2),
        "link_amount": resolved_link_amount,
    }


def link_reimbursement_to_expense(
    expense_transaction_id: int,
    reimbursement_transaction_id: int,
    amount: float | None = None,
) -> dict:
    expense = _get_transaction(expense_transaction_id)
    if not expense or expense.get("type") != "expense":
        raise ValueError("expense transaction not found")

    reimbursement = _get_transaction(reimbursement_transaction_id)
    if not reimbursement or reimbursement.get("type") != "income":
        raise ValueError("reimbursement transaction not found")

    with get_connection() as conn:
        marker = _get_marker(conn, expense_transaction_id)
        if not marker:
            conn.execute(
                """
                INSERT INTO reimbursement_links (
                    expense_transaction_id,
                    reimbursement_transaction_id,
                    amount,
                    status
                ) VALUES (?, NULL, ?, 'pending')
                """,
                (expense_transaction_id, round(float(expense["amount"]), 2)),
            )
            marker = _get_marker(conn, expense_transaction_id)

        existing_link = conn.execute(
            """
            SELECT id
            FROM reimbursement_links
            WHERE expense_transaction_id = ?
              AND reimbursement_transaction_id = ?
            LIMIT 1
            """,
            (expense_transaction_id, reimbursement_transaction_id),
        ).fetchone()
        if existing_link:
            raise ValueError("reimbursement is already linked to this expense")

        target_amount = round(float(marker["amount"] or 0), 2)
        reimbursed_before = _get_linked_total(conn, expense_transaction_id)
        remaining_amount = max(target_amount - reimbursed_before, 0.0)
        if remaining_amount <= 0:
            raise ValueError("expense reimbursement is already completed")

        link_amount = round(float(amount if amount is not None else reimbursement["amount"]), 2)
        if link_amount <= 0:
            raise ValueError("link amount must be greater than 0")
        if link_amount - reimbursement["amount"] > 0.005:
            raise ValueError("link amount cannot exceed reimbursement income amount")
        if link_amount - remaining_amount > 0.005:
            raise ValueError("link amount cannot exceed pending reimbursement amount")

        status_after_link = _compute_status(target_amount, reimbursed_before + link_amount)
        conn.execute(
            """
            INSERT INTO reimbursement_links (
                expense_transaction_id,
                reimbursement_transaction_id,
                amount,
                status
            ) VALUES (?, ?, ?, ?)
            """,
            (expense_transaction_id, reimbursement_transaction_id, link_amount, status_after_link),
        )

        summary = _sync_marker_status(conn, expense_transaction_id)
        conn.commit()
        return summary


def list_open_reimbursable_expenses(limit: int = 100) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                t.id,
                t.date,
                t.amount AS expense_amount,
                t.category_main,
                t.category_sub,
                t.note,
                marker.amount AS target_amount,
                marker.status AS status,
                COALESCE((
                    SELECT SUM(amount)
                    FROM reimbursement_links rl
                    WHERE rl.expense_transaction_id = t.id
                      AND rl.reimbursement_transaction_id IS NOT NULL
                ), 0) AS reimbursed_amount
            FROM reimbursement_links marker
            JOIN transactions t ON t.id = marker.expense_transaction_id
            WHERE marker.reimbursement_transaction_id IS NULL
              AND marker.status != 'completed'
            ORDER BY t.date DESC, t.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    result = []
    for row in rows:
        target_amount = round(float(row["target_amount"] or 0), 2)
        reimbursed_amount = min(round(float(row["reimbursed_amount"] or 0), 2), target_amount)
        pending_amount = max(target_amount - reimbursed_amount, 0.0)
        result.append(
            {
                "id": int(row["id"]),
                "date": row["date"],
                "expense_amount": round(float(row["expense_amount"] or 0), 2),
                "category_main": row["category_main"],
                "category_sub": row["category_sub"],
                "note": row["note"],
                "target_amount": target_amount,
                "reimbursed_amount": reimbursed_amount,
                "pending_amount": round(pending_amount, 2),
                "status": _normalize_status(row["status"]),
                "progress": round((reimbursed_amount / target_amount * 100), 2) if target_amount > 0 else 0.0,
            }
        )
    return result


def get_month_reimbursement_progress(month: str) -> dict:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                t.id,
                marker.amount AS target_amount,
                marker.status AS status,
                COALESCE((
                    SELECT SUM(amount)
                    FROM reimbursement_links rl
                    WHERE rl.expense_transaction_id = t.id
                      AND rl.reimbursement_transaction_id IS NOT NULL
                ), 0) AS reimbursed_amount
            FROM reimbursement_links marker
            JOIN transactions t ON t.id = marker.expense_transaction_id
            WHERE marker.reimbursement_transaction_id IS NULL
              AND substr(t.date, 1, 7) = ?
            ORDER BY t.date DESC, t.id DESC
            """,
            (month,),
        ).fetchall()

    tracked_count = 0
    tracked_amount = 0.0
    reimbursed_amount = 0.0
    pending_amount = 0.0
    completed_count = 0
    partial_count = 0
    pending_count = 0

    for row in rows:
        tracked_count += 1
        target_amount = round(float(row["target_amount"] or 0), 2)
        current_reimbursed = min(round(float(row["reimbursed_amount"] or 0), 2), target_amount)
        current_pending = max(target_amount - current_reimbursed, 0.0)
        status = _normalize_status(row["status"])

        tracked_amount += target_amount
        reimbursed_amount += current_reimbursed
        pending_amount += current_pending

        if status == "completed":
            completed_count += 1
        elif status == "partial":
            partial_count += 1
        else:
            pending_count += 1

    completion_rate = round((reimbursed_amount / tracked_amount * 100), 2) if tracked_amount > 0 else 0.0

    return {
        "month": month,
        "tracked_count": tracked_count,
        "tracked_amount": round(tracked_amount, 2),
        "reimbursed_amount": round(reimbursed_amount, 2),
        "pending_amount": round(pending_amount, 2),
        "completion_rate": completion_rate,
        "completed_count": completed_count,
        "partial_count": partial_count,
        "pending_count": pending_count,
    }


def get_expense_reimbursement_map(expense_transaction_ids: list[int]) -> dict[int, dict]:
    if not expense_transaction_ids:
        return {}

    placeholders = ",".join("?" for _ in expense_transaction_ids)
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT
                marker.expense_transaction_id,
                marker.amount AS target_amount,
                marker.status AS status,
                COALESCE((
                    SELECT SUM(amount)
                    FROM reimbursement_links rl
                    WHERE rl.expense_transaction_id = marker.expense_transaction_id
                      AND rl.reimbursement_transaction_id IS NOT NULL
                ), 0) AS reimbursed_amount
            FROM reimbursement_links marker
            WHERE marker.reimbursement_transaction_id IS NULL
              AND marker.expense_transaction_id IN ({placeholders})
            """,
            tuple(expense_transaction_ids),
        ).fetchall()

    result: dict[int, dict] = {}
    for row in rows:
        expense_transaction_id = int(row["expense_transaction_id"])
        target_amount = round(float(row["target_amount"] or 0), 2)
        reimbursed_amount = min(round(float(row["reimbursed_amount"] or 0), 2), target_amount)
        pending_amount = max(target_amount - reimbursed_amount, 0.0)
        result[expense_transaction_id] = {
            "target_amount": target_amount,
            "reimbursed_amount": reimbursed_amount,
            "pending_amount": round(pending_amount, 2),
            "status": _normalize_status(row["status"]),
            "progress": round((reimbursed_amount / target_amount * 100), 2) if target_amount > 0 else 0.0,
        }
    return result
