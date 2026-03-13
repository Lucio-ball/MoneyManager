from datetime import date, datetime
from difflib import SequenceMatcher

from extensions.database import get_connection

from models.transaction import (
    get_calendar_daily_expense,
    get_calendar_day_details,
    create_transaction,
    delete_transaction,
    get_category_trend,
    get_monthly_dashboard_data,
    get_monthly_financial_summary,
    get_monthly_stats,
    get_recent_average_month_expense,
    get_recent_transactions,
    get_tag_trend,
    get_today_expense,
    get_transaction_by_id,
    get_transactions_by_month,
    query_transactions,
    update_transaction,
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


HIGH_REIMBURSEMENT_PROBABILITY_CATEGORIES = {
    "交通": 1.0,
    "通勤": 1.0,
    "差旅": 1.0,
    "办公": 0.9,
    "学习": 0.65,
    "医疗": 0.6,
    "餐饮": 0.55,
    "社交": 0.4,
}


def _tokenize_note(note: str | None) -> set[str]:
    content = str(note or "").strip().lower()
    if not content:
        return set()

    normalized = []
    for char in content:
        if char.isalnum() or "\u4e00" <= char <= "\u9fff":
            normalized.append(char)
        else:
            normalized.append(" ")

    tokens = {token for token in "".join(normalized).split() if len(token) >= 2}
    if not tokens and content:
        compact = "".join(ch for ch in content if ch.isalnum() or "\u4e00" <= ch <= "\u9fff")
        if len(compact) >= 2:
            tokens.add(compact)
    return tokens


def _build_note_similarity(target_note: str | None, candidate_note: str | None) -> float:
    target_tokens = _tokenize_note(target_note)
    candidate_tokens = _tokenize_note(candidate_note)

    if not target_tokens or not candidate_tokens:
        return 0.0

    overlap = len(target_tokens & candidate_tokens)
    union = len(target_tokens | candidate_tokens)
    token_ratio = overlap / union if union > 0 else 0.0
    text_ratio = SequenceMatcher(
        None,
        str(target_note or "").lower(),
        str(candidate_note or "").lower(),
    ).ratio()
    return round(max(token_ratio, text_ratio), 4)


def suggest_reimbursement_matches(
    reimbursement_amount: float,
    reimbursement_date: str,
    reimbursement_note: str | None = None,
    limit: int = 3,
) -> list[dict]:
    try:
        amount = round(float(reimbursement_amount), 2)
    except (TypeError, ValueError):
        return []

    if amount <= 0:
        return []

    try:
        target_date = datetime.strptime(str(reimbursement_date).strip(), "%Y-%m-%d").date()
    except ValueError:
        return []

    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                t.id,
                t.amount AS expense_amount,
                t.date,
                t.category_main,
                t.category_sub,
                t.note,
                marker.amount AS target_amount,
                marker.status AS marker_status,
                COALESCE((
                    SELECT SUM(amount)
                    FROM reimbursement_links rl
                    WHERE rl.expense_transaction_id = t.id
                      AND rl.reimbursement_transaction_id IS NOT NULL
                ), 0) AS reimbursed_amount
            FROM transactions t
            LEFT JOIN reimbursement_links marker
              ON marker.expense_transaction_id = t.id
             AND marker.reimbursement_transaction_id IS NULL
            WHERE t.type = 'expense'
              AND t.date <= ?
              AND julianday(?) - julianday(t.date) < 30
            ORDER BY t.date DESC, t.id DESC
            """,
            (target_date.isoformat(), target_date.isoformat()),
        ).fetchall()

    candidates: list[dict] = []
    for row in rows:
        expense_amount = round(float(row["expense_amount"] or 0), 2)
        target_amount = round(float(row["target_amount"] or expense_amount), 2)
        reimbursed_amount = round(float(row["reimbursed_amount"] or 0), 2)
        pending_amount = round(max(target_amount - reimbursed_amount, 0.0), 2)
        if pending_amount <= 0:
            continue

        expense_date = datetime.strptime(row["date"], "%Y-%m-%d").date()
        days_diff = (target_date - expense_date).days
        if days_diff < 0 or days_diff >= 30:
            continue

        amount_gap = abs(pending_amount - amount)
        amount_ratio = amount_gap / max(amount, pending_amount, 1.0)
        if amount_ratio <= 0.05:
            amount_score = 1.0
        elif amount_ratio <= 0.15:
            amount_score = 0.82
        elif amount_ratio <= 0.3:
            amount_score = 0.58
        elif amount_ratio <= 0.5:
            amount_score = 0.35
        else:
            amount_score = 0.12

        date_score = max(0.0, 1 - days_diff / 30)
        note_score = _build_note_similarity(reimbursement_note, row["note"])
        category_score = HIGH_REIMBURSEMENT_PROBABILITY_CATEGORIES.get(
            str(row["category_main"] or "").strip(),
            0.15,
        )

        total_score = round(
            amount_score * 0.45
            + date_score * 0.25
            + note_score * 0.2
            + category_score * 0.1,
            4,
        )

        candidates.append(
            {
                "id": int(row["id"]),
                "date": row["date"],
                "amount": expense_amount,
                "category_main": row["category_main"],
                "category_sub": row["category_sub"],
                "note": row["note"],
                "pending_amount": pending_amount,
                "days_diff": days_diff,
                "status": str(row["marker_status"] or ("partial" if reimbursed_amount > 0 else "pending")).strip()
                or "pending",
                "match_score": round(total_score, 3),
                "match_reasons": {
                    "amount_close": round(amount_score, 3),
                    "date_proximity": round(date_score, 3),
                    "note_similarity": round(note_score, 3),
                    "category_probability": round(category_score, 3),
                },
            }
        )

    candidates.sort(
        key=lambda item: (
            -float(item["match_score"]),
            abs(float(item["pending_amount"]) - amount),
            int(item["days_diff"]),
            -int(item["id"]),
        )
    )
    return candidates[: max(int(limit), 0)]


__all__ = [
    "normalize_transaction_payload",
    "suggest_reimbursement_matches",
    "create_transaction",
    "get_recent_transactions",
    "get_monthly_dashboard_data",
    "get_monthly_financial_summary",
    "get_monthly_stats",
    "get_category_trend",
    "get_tag_trend",
    "get_today_expense",
    "get_transactions_by_month",
    "get_recent_average_month_expense",
    "get_calendar_daily_expense",
    "get_calendar_day_details",
    "query_transactions",
    "get_transaction_by_id",
    "update_transaction",
    "delete_transaction",
]
