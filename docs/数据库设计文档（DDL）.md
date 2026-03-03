## 2.1 数据库：SQLite

------

## 2.2 表：`transactions`（交易表）

```sql
CREATE TABLE transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    amount REAL NOT NULL,
    type TEXT CHECK(type IN ('income', 'expense')) NOT NULL,
    date TEXT NOT NULL,
    category_main TEXT NOT NULL,
    category_sub TEXT,
    tags TEXT, -- JSON array string
    payment_method TEXT CHECK(payment_method IN ('wechat', 'alipay_family', 'bank')),
    note TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

------

## 2.3 表：`budgets`（预算表）

```sql
CREATE TABLE budgets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    month TEXT NOT NULL,
    category_main TEXT, -- NULL = total budget
    budget_amount REAL NOT NULL
);
```

------

## 2.4 表：`tags_config`（可选）

```sql
CREATE TABLE tags_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type TEXT CHECK(type IN ('nature', 'scene')),
    description TEXT
);
```

------

# 