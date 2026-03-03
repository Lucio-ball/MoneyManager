import json

from models.analysis import create_ai_archive, get_ai_archives, get_ai_monthly_package


def build_ai_prompt_template(month: str) -> str:
    return f"""你是一名专业的个人财务教练，请基于我提供的月度财务数据，输出一份结构化复盘报告。\n\n【你的任务】\n1. 用简洁语言总结本月消费结构与现金流状态。\n2. 识别值得肯定的消费习惯（至少 2 条）。\n3. 识别需要警惕的问题（至少 2 条），并解释原因。\n4. 针对下月给出可执行建议（3-5 条，需具体可落地）。\n5. 对“冲动消费比例”和“学习投资比例”给出诊断结论。\n6. 输出“消费健康度分析”：解释总分、五个维度短板和优先改进项。\n7. 输出“消费性格描述”：说明当前画像类型、形成原因和具体纠偏建议。\n8. 结合订阅模块，分别从“结构成本”和“真实现金流”点评订阅压力。\n\n【数据口径说明】\n- monthly_stats: 月度收支、类别统计、标签统计、每日支出（仅真实入账）\n- insights: 行为模式识别结果（异常高支出日、长期高占比类别、冲动/学习投资比例、消费健康度、消费行为画像）\n- budgets: 预算执行与状态（正常/接近/超支）\n- subscriptions: 订阅口径（本月折算成本、本月实际扣费金额、本月新增/取消、下月即将扣费项目）\n\n【输出格式（严格按此结构）】\n# {month} 财务复盘\n## 1) 本月概览\n## 2) 消费结构分析\n## 3) 行为模式解读\n## 4) 消费健康度分析\n## 5) 消费性格描述\n## 6) 预算执行评价\n## 7) 订阅健康度\n## 8) 下月行动清单\n\n请使用中文输出，避免空泛建议，尽量引用数据中的金额、占比、趋势。"""


def build_ai_monthly_response(month: str) -> dict:
    package = get_ai_monthly_package(month)
    subscription_recap = package.get("subscriptions", {})
    response = dict(package)
    response["subscription_monthly_total_cost"] = subscription_recap.get("monthly_total_cost", 0)
    response["subscription_estimated_monthly_cost"] = subscription_recap.get("estimated_monthly_cost", 0)
    response["subscription_actual_charged_amount"] = subscription_recap.get("actual_charged_amount", 0)
    response["subscription_actual_charge_count"] = subscription_recap.get("actual_charge_count", 0)
    response["subscription_new_this_month"] = subscription_recap.get("new_subscriptions", 0)
    response["subscription_cancelled_this_month"] = subscription_recap.get("cancelled_subscriptions", 0)
    response["subscription_next_month_upcoming"] = subscription_recap.get("next_month_upcoming", [])
    consumption_health = package.get("consumption_health") or package.get("insights", {}).get("consumption_health", {})
    response["consumption_health"] = consumption_health
    response["consumption_health_score"] = consumption_health.get("score", 0)
    response["consumption_health_level"] = consumption_health.get("level", "一般")
    consumption_persona = package.get("consumption_persona") or package.get("insights", {}).get("consumption_persona", {})
    response["consumption_persona"] = consumption_persona
    response["consumption_persona_type"] = consumption_persona.get("type", "steady")
    response["consumption_persona_label"] = consumption_persona.get("label", "稳健型")
    response["prompt_template"] = build_ai_prompt_template(month)
    response["prompt_with_package"] = (
        build_ai_prompt_template(month)
        + "\n\n【本月数据包（JSON）】\n"
        + json.dumps(package, ensure_ascii=False, indent=2)
    )
    return response


__all__ = [
    "build_ai_prompt_template",
    "build_ai_monthly_response",
    "create_ai_archive",
    "get_ai_archives",
    "get_ai_monthly_package",
]
