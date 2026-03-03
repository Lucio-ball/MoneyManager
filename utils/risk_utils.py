from services.transaction_service import get_recent_average_month_expense


def build_emotion_light(month: str, total_expense: float, budget_data: dict) -> dict:
    total_budget_item = next(
        (item for item in budget_data.get("items", []) if item.get("category_main") is None),
        None,
    )

    if total_budget_item:
        execution_rate = float(total_budget_item.get("execution_rate", 0))
        if execution_rate >= 100:
            return {
                "level": "red",
                "label": "红灯",
                "reason": f"本月总预算执行率 {execution_rate:.2f}%（已超预算）",
            }
        if execution_rate >= 80:
            return {
                "level": "yellow",
                "label": "黄灯",
                "reason": f"本月总预算执行率 {execution_rate:.2f}%（接近预算）",
            }
        return {
            "level": "green",
            "label": "绿灯",
            "reason": f"本月总预算执行率 {execution_rate:.2f}%（处于合理区间）",
        }

    baseline = get_recent_average_month_expense(month, count=3)
    if baseline <= 0:
        return {
            "level": "green",
            "label": "绿灯",
            "reason": "历史样本不足，默认正常。",
        }

    if total_expense > baseline * 1.5:
        return {
            "level": "red",
            "label": "红灯",
            "reason": f"本月支出高于近3月均值（¥{baseline:.2f}）的 150%。",
        }
    if total_expense > baseline * 1.2:
        return {
            "level": "yellow",
            "label": "黄灯",
            "reason": f"本月支出高于近3月均值（¥{baseline:.2f}）的 120%。",
        }
    return {
        "level": "green",
        "label": "绿灯",
        "reason": f"本月支出低于近3月均值（¥{baseline:.2f}）的预警线。",
    }
