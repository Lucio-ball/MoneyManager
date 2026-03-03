from datetime import date, datetime

from models.goal import create_goal, get_goal_progress_list


def validate_goal_payload(payload: dict) -> tuple[dict | None, str | None]:
    name = str(payload.get("name") or "").strip()
    if not name:
        return None, "name is required"

    target_amount_raw = payload.get("target_amount", "")
    try:
        target_amount = float(str(target_amount_raw).strip())
    except (TypeError, ValueError):
        return None, "target_amount must be a number"

    if target_amount <= 0:
        return None, "target_amount must be greater than 0"

    deadline = str(payload.get("deadline") or "").strip()
    if not deadline:
        return None, "deadline is required"

    try:
        deadline_date = datetime.strptime(deadline, "%Y-%m-%d").date()
    except ValueError:
        return None, "deadline format must be YYYY-MM-DD"

    if deadline_date < date.today():
        return None, "deadline cannot be earlier than today"

    note = str(payload.get("note") or "").strip()

    return (
        {
            "name": name,
            "target_amount": target_amount,
            "deadline": deadline,
            "note": note,
        },
        None,
    )


def get_goal_dashboard_summary() -> dict:
    goals = get_goal_progress_list()
    active_goals = [goal for goal in goals if not goal.get("is_completed")]

    if not goals:
        return {
            "total_count": 0,
            "active_count": 0,
            "behind_count": 0,
            "next_goal": None,
            "items": [],
        }

    active_sorted = sorted(active_goals, key=lambda item: item["deadline"])
    next_goal = active_sorted[0] if active_sorted else sorted(goals, key=lambda item: item["deadline"])[0]

    return {
        "total_count": len(goals),
        "active_count": len(active_goals),
        "behind_count": sum(1 for goal in active_goals if goal.get("is_behind")),
        "next_goal": next_goal,
        "items": goals[:3],
    }


__all__ = [
    "validate_goal_payload",
    "create_goal",
    "get_goal_progress_list",
    "get_goal_dashboard_summary",
]
