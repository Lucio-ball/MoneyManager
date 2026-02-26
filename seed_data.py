import argparse
import random
import sqlite3
from calendar import monthrange
from datetime import date

from database import create_ai_archive, create_transaction, get_connection, init_db, upsert_budget

CATEGORY_SUB_MAP = {
    "餐饮": ["早餐", "午餐", "晚餐", "外卖", "奶茶", "咖啡"],
    "学习": ["书籍", "课程", "打印", "资料"],
    "娱乐": ["电影", "游戏", "KTV", "演出"],
    "交通": ["地铁", "打车", "公交", "高铁"],
    "生活": ["日用品", "宿舍", "衣物", "家居"],
    "人际": ["聚餐", "礼物", "约会", "社交"],
    "健康": ["药品", "体检", "运动", "保健"],
    "其他": ["杂项", "手续费", "意外"],
}

EXPENSE_CATEGORY_WEIGHT = {
    "餐饮": 0.30,
    "学习": 0.12,
    "娱乐": 0.10,
    "交通": 0.12,
    "生活": 0.16,
    "人际": 0.08,
    "健康": 0.06,
    "其他": 0.06,
}

TAGS = [
    "冲动",
    "刚需",
    "投资自己",
    "社交压力",
    "情绪消费",
    "宿舍",
    "校外",
    "旅行",
    "约会",
    "学习投资",
]


def weighted_category() -> str:
    categories = list(EXPENSE_CATEGORY_WEIGHT.keys())
    weights = list(EXPENSE_CATEGORY_WEIGHT.values())
    return random.choices(categories, weights=weights, k=1)[0]


def gen_tags(category: str, amount: float) -> list[str]:
    tags: list[str] = []

    if category in ("学习", "健康"):
        tags.append("投资自己")
        if random.random() < 0.65:
            tags.append("学习投资")

    if category in ("餐饮", "娱乐") and random.random() < 0.22:
        tags.append("冲动")

    if category in ("娱乐", "人际") and random.random() < 0.25:
        tags.append("情绪消费")

    if category in ("人际", "餐饮") and random.random() < 0.18:
        tags.append("社交压力")

    if random.random() < 0.45:
        tags.append(random.choice(["宿舍", "校外", "约会", "旅行", "刚需"]))

    if amount >= 120 and "冲动" not in tags and random.random() < 0.12:
        tags.append("冲动")

    return list(dict.fromkeys(tags))[:3]


def reset_tables() -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM transactions")
        conn.execute("DELETE FROM sqlite_sequence WHERE name='transactions'")
        conn.execute("DELETE FROM budgets")
        conn.execute("DELETE FROM sqlite_sequence WHERE name='budgets'")
        conn.execute("DELETE FROM ai_archives")
        conn.execute("DELETE FROM sqlite_sequence WHERE name='ai_archives'")
        conn.commit()


def month_start_by_offset(base_month: date, offset: int) -> date:
    total = base_month.year * 12 + (base_month.month - 1) + offset
    year = total // 12
    month = total % 12 + 1
    return date(year, month, 1)


def create_income(month_str: str, day: int, amount: float, note: str) -> None:
    create_transaction(
        {
            "amount": amount,
            "type": "income",
            "date": f"{month_str}-{day:02d}",
            "category_main": "其他",
            "category_sub": "收入",
            "tags": ["刚需"],
            "payment_method": "bank",
            "note": note,
        }
    )


def create_month_data(month_date: date) -> int:
    month_str = month_date.strftime("%Y-%m")
    year, month = month_date.year, month_date.month
    days = monthrange(year, month)[1]

    monthly_total_budget = random.uniform(4200, 6000)
    upsert_budget(month_str, None, round(monthly_total_budget, 2))

    for category in CATEGORY_SUB_MAP:
        ratio = EXPENSE_CATEGORY_WEIGHT.get(category, 0.05)
        category_budget = monthly_total_budget * ratio * random.uniform(0.85, 1.15)
        upsert_budget(month_str, category, round(max(category_budget, 180), 2))

    create_income(month_str, 5, round(random.uniform(2600, 3600), 2), "兼职收入")
    create_income(month_str, 20, round(random.uniform(1200, 2500), 2), "生活费到账")

    created = 0
    for day in range(1, days + 1):
        tx_count = random.choices([0, 1, 2, 3], weights=[0.08, 0.48, 0.30, 0.14], k=1)[0]
        for _ in range(tx_count):
            category = weighted_category()
            sub = random.choice(CATEGORY_SUB_MAP[category])

            base = {
                "餐饮": (12, 75),
                "学习": (18, 160),
                "娱乐": (20, 200),
                "交通": (4, 80),
                "生活": (8, 130),
                "人际": (20, 220),
                "健康": (10, 180),
                "其他": (5, 100),
            }[category]

            amount = round(random.uniform(*base), 2)
            tags = gen_tags(category, amount)
            payment_method = random.choices(
                ["wechat", "alipay_family", "bank"],
                weights=[0.62, 0.23, 0.15],
                k=1,
            )[0]

            note_pool = {
                "餐饮": ["吃饭", "外卖", "奶茶", "咖啡"],
                "学习": ["买书", "课程", "资料"],
                "娱乐": ["电影", "游戏", "休闲"],
                "交通": ["出行", "通勤"],
                "生活": ["日用品", "生活开销"],
                "人际": ["聚餐", "礼物", "社交"],
                "健康": ["药品", "运动", "体检"],
                "其他": ["杂费", "临时支出"],
            }

            create_transaction(
                {
                    "amount": amount,
                    "type": "expense",
                    "date": f"{month_str}-{day:02d}",
                    "category_main": category,
                    "category_sub": sub,
                    "tags": tags,
                    "payment_method": payment_method,
                    "note": random.choice(note_pool[category]),
                }
            )
            created += 1

    create_ai_archive(
        month_str,
        (
            f"{month_str} 复盘：整体消费结构较稳定，需关注冲动支出与娱乐占比。"
            "下月建议：提升学习投资预算执行率，降低非必要即时消费。"
        ),
    )

    return created


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate mock data for MoneyManager UI evaluation")
    parser.add_argument("--months", type=int, default=6, help="How many recent months to generate")
    parser.add_argument("--seed", type=int, default=20260226, help="Random seed for reproducible data")
    parser.add_argument("--reset", action="store_true", help="Reset existing transactions/budgets/archives before seeding")
    args = parser.parse_args()

    random.seed(args.seed)
    init_db()

    if args.reset:
        reset_tables()

    current_month = date.today().replace(day=1)
    offsets = list(range(-(args.months - 1), 1))

    total_created = 0
    for offset in offsets:
        month_date = month_start_by_offset(current_month, offset)
        total_created += create_month_data(month_date)

    with get_connection() as conn:
        tx_count = conn.execute("SELECT COUNT(*) AS c FROM transactions").fetchone()["c"]
        budget_count = conn.execute("SELECT COUNT(*) AS c FROM budgets").fetchone()["c"]
        archive_count = conn.execute("SELECT COUNT(*) AS c FROM ai_archives").fetchone()["c"]

    print("✅ Mock data generation completed")
    print(f"- Months generated: {args.months}")
    print(f"- New expense transactions generated: {total_created}")
    print(f"- Total transactions in DB: {tx_count}")
    print(f"- Total budgets in DB: {budget_count}")
    print(f"- Total AI archives in DB: {archive_count}")


if __name__ == "__main__":
    main()
