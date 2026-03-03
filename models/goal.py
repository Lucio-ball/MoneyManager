from datetime import date

from extensions.database import get_connection
from utils.date_utils import parse_date


def create_goal(name: str, target_amount: float, deadline: str, note: str = "") -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO goals (name, target_amount, deadline, note)
            VALUES (?, ?, ?, ?)
            """,
            (name.strip(), float(target_amount), deadline, note.strip()),
        )
        conn.commit()
        last_row_id = cursor.lastrowid
        if last_row_id is None:
            raise RuntimeError("failed to create goal")
        return int(last_row_id)


def get_all_goals() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, name, target_amount, deadline, note, created_at
            FROM goals
            ORDER BY deadline ASC, created_at DESC
            """
        ).fetchall()

    return [dict(row) for row in rows]


def _sum_savings_in_period(start_date: date, end_date: date) -> float:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT ROUND(
                COALESCE(SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END), 0)
                - COALESCE(SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END), 0),
                2
            ) AS net_saving
            FROM transactions
            WHERE date >= ? AND date <= ?
            """,
            (start_date.isoformat(), end_date.isoformat()),
        ).fetchone()

    if not row:
        return 0.0
    return round(float(row["net_saving"] or 0), 2)


def _months_remaining(today: date, deadline: date) -> int:
    if deadline < today:
        return 0

    month_diff = (deadline.year - today.year) * 12 + (deadline.month - today.month)
    return max(1, month_diff + 1)


def _build_goal_progress_item(goal_row: dict, today: date) -> dict:
    created_at = str(goal_row.get("created_at") or "")
    start_date = parse_date(created_at[:10]) or today
    deadline = parse_date(str(goal_row.get("deadline") or "")) or today

    target_amount = round(float(goal_row.get("target_amount") or 0), 2)
    net_saving = _sum_savings_in_period(start_date, today)
    current_saved = max(0.0, round(net_saving, 2))

    progress_rate = round((current_saved / target_amount * 100), 2) if target_amount > 0 else 0.0
    progress_rate = min(100.0, progress_rate)

    remaining_amount = max(0.0, round(target_amount - current_saved, 2))
    months_remaining = _months_remaining(today, deadline)
    monthly_required = round(remaining_amount / months_remaining, 2) if months_remaining > 0 else remaining_amount

    total_days = max((deadline - start_date).days, 1)
    elapsed_days = max(0, min((today - start_date).days, total_days))
    expected_progress_rate = round(elapsed_days / total_days * 100, 2)

    is_overdue = deadline < today and remaining_amount > 0
    is_behind = is_overdue or (progress_rate + 0.01 < expected_progress_rate)

    return {
        "id": int(goal_row["id"]),
        "name": str(goal_row.get("name") or ""),
        "target_amount": target_amount,
        "deadline": str(goal_row.get("deadline") or ""),
        "note": str(goal_row.get("note") or ""),
        "created_at": created_at,
        "current_saved": round(current_saved, 2),
        "progress_rate": progress_rate,
        "remaining_amount": remaining_amount,
        "months_remaining": months_remaining,
        "monthly_required": monthly_required,
        "expected_progress_rate": expected_progress_rate,
        "is_behind": is_behind,
        "is_overdue": is_overdue,
        "is_completed": remaining_amount <= 0,
    }


def get_goal_progress_list(today: date | None = None) -> list[dict]:
    current_day = today or date.today()
    goals = get_all_goals()
    return [_build_goal_progress_item(goal, current_day) for goal in goals]
