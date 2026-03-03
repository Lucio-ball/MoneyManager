from extensions.database import get_connection
from models.transaction import get_month_expense_by_category


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
