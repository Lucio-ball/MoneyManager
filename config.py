import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

DEFAULT_DB_DIR = BASE_DIR / "data"
DEFAULT_DB_PATH = DEFAULT_DB_DIR / "money_manager.db"

_db_path_env = os.getenv("MONEY_MANAGER_DB_PATH")
if _db_path_env:
    DB_PATH = Path(_db_path_env).expanduser()
    if not DB_PATH.is_absolute():
        DB_PATH = (BASE_DIR / DB_PATH).resolve()
    DB_DIR = DB_PATH.parent
else:
    DB_DIR = DEFAULT_DB_DIR
    DB_PATH = DEFAULT_DB_PATH

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
