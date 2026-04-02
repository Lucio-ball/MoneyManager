import tempfile
import unittest
from pathlib import Path

import extensions.database as database_ext
from models.reimbursement import (
    get_expense_reimbursement_map,
    get_month_reimbursement_progress,
    link_reimbursement_to_expenses,
    mark_expense_as_reimbursable,
)
from models.transaction import create_transaction


class ReimbursementLinkingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = database_ext.DB_PATH
        self.original_db_dir = database_ext.DB_DIR
        database_ext.DB_PATH = Path(self.temp_dir.name) / "test_money_manager.db"
        database_ext.DB_DIR = database_ext.DB_PATH.parent
        database_ext.init_db()

    def tearDown(self) -> None:
        database_ext.DB_PATH = self.original_db_path
        database_ext.DB_DIR = self.original_db_dir
        self.temp_dir.cleanup()

    def _create_expense(self, amount: float, date: str) -> int:
        expense_id = create_transaction(
            {
                "amount": amount,
                "type": "expense",
                "date": date,
                "category_main": "健康",
                "category_sub": "医院",
                "tags": [],
                "note": None,
            }
        )
        mark_expense_as_reimbursable(expense_id, amount)
        return expense_id

    def _create_reimbursement_income(self, amount: float, date: str) -> int:
        return create_transaction(
            {
                "amount": amount,
                "type": "income",
                "date": date,
                "category_main": "收入",
                "category_sub": "报销",
                "tags": [],
                "note": None,
            }
        )

    def test_link_reimbursement_to_expenses_allocates_amount_across_selected_expenses(self) -> None:
        expense_ids = [
            self._create_expense(70.00, "2026-03-07"),
            self._create_expense(766.41, "2026-03-07"),
            self._create_expense(217.29, "2026-03-07"),
        ]
        reimbursement_id = self._create_reimbursement_income(981.82, "2026-03-25")

        link_reimbursement_to_expenses(expense_ids, reimbursement_id)

        progress = get_month_reimbursement_progress("2026-03")
        reimbursement_map = get_expense_reimbursement_map(expense_ids)

        self.assertAlmostEqual(progress["reimbursed_amount"], 981.82)
        self.assertAlmostEqual(progress["pending_amount"], 71.88)
        self.assertEqual(progress["completed_count"], 2)
        self.assertEqual(progress["partial_count"], 1)
        self.assertEqual(progress["pending_count"], 0)
        self.assertAlmostEqual(reimbursement_map[expense_ids[0]]["reimbursed_amount"], 70.00)
        self.assertEqual(reimbursement_map[expense_ids[0]]["status"], "completed")
        self.assertAlmostEqual(reimbursement_map[expense_ids[1]]["reimbursed_amount"], 766.41)
        self.assertEqual(reimbursement_map[expense_ids[1]]["status"], "completed")
        self.assertAlmostEqual(reimbursement_map[expense_ids[2]]["reimbursed_amount"], 145.41)
        self.assertAlmostEqual(reimbursement_map[expense_ids[2]]["pending_amount"], 71.88)
        self.assertEqual(reimbursement_map[expense_ids[2]]["status"], "partial")

    def test_month_reimbursement_progress_repairs_legacy_zero_amount_links(self) -> None:
        expense_ids = [
            self._create_expense(70.00, "2026-03-07"),
            self._create_expense(766.41, "2026-03-07"),
            self._create_expense(217.29, "2026-03-07"),
        ]
        reimbursement_id = self._create_reimbursement_income(981.82, "2026-03-25")

        with database_ext.get_connection() as conn:
            for expense_id in expense_ids:
                conn.execute(
                    """
                    INSERT INTO reimbursement_links (
                        expense_transaction_id,
                        reimbursement_transaction_id,
                        amount,
                        status
                    ) VALUES (?, ?, 0, 'pending')
                    """,
                    (expense_id, reimbursement_id),
                )
            conn.commit()

        progress = get_month_reimbursement_progress("2026-03")

        self.assertAlmostEqual(progress["reimbursed_amount"], 981.82)
        self.assertAlmostEqual(progress["pending_amount"], 71.88)
        self.assertEqual(progress["completed_count"], 2)
        self.assertEqual(progress["partial_count"], 1)

        with database_ext.get_connection() as conn:
            repaired_amounts = conn.execute(
                """
                SELECT amount
                FROM reimbursement_links
                WHERE reimbursement_transaction_id = ?
                ORDER BY id ASC
                """,
                (reimbursement_id,),
            ).fetchall()

        self.assertEqual([round(float(row["amount"]), 2) for row in repaired_amounts], [70.00, 766.41, 145.41])


if __name__ == "__main__":
    unittest.main()
