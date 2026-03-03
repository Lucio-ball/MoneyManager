from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_DIR = BASE_DIR / "data"
DB_PATH = DB_DIR / "money_manager.db"

CATEGORY_OPTIONS = [
    "餐饮",
    "学习",
    "娱乐",
    "交通",
    "生活",
    "人际",
    "健康",
    "其他",
]

TAG_OPTIONS = [
    "冲动",
    "刚需",
    "投资自己",
    "社交",
    "情绪消费",
    "宿舍",
    "校外",
    "旅行",
    "约会",
    "学习投资",
]

SUBSCRIPTION_CYCLE_OPTIONS = [
    "monthly",
    "yearly",
    "weekly",
    "quarterly",
]
