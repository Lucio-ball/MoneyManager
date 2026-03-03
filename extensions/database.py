import os
import sqlite3

from config import DB_DIR, DB_PATH


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
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
        transaction_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(transactions)").fetchall()
        }
        if "payment_method" in transaction_columns:
            conn.executescript(
                """
                CREATE TABLE transactions_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    amount REAL NOT NULL,
                    type TEXT CHECK(type IN ('income', 'expense')) NOT NULL,
                    date TEXT NOT NULL,
                    category_main TEXT NOT NULL,
                    category_sub TEXT,
                    tags TEXT,
                    note TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                INSERT INTO transactions_new (
                    id,
                    amount,
                    type,
                    date,
                    category_main,
                    category_sub,
                    tags,
                    note,
                    created_at
                )
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
                FROM transactions;

                DROP TABLE transactions;
                ALTER TABLE transactions_new RENAME TO transactions;
                """
            )
        conn.commit()
