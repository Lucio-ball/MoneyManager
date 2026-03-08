from __future__ import annotations

from calendar import monthrange

from models.analysis import get_monthly_insights
from models.budget import get_budget_execution, get_budget_health_profile
from models.reimbursement import get_month_pending_reimbursement_summary, get_month_reimbursement_progress
from models.subscription import get_subscription_monthly_cost_summary, get_subscription_monthly_recap
from models.transaction import get_monthly_financial_summary, get_monthly_stats
from utils.date_utils import month_sequence


def _fmt_amount(value: float) -> str:
    return f"{round(float(value or 0), 2):.2f}"


def _top_category_text(category_stats: list[dict]) -> str:
    if not category_stats:
        return "本月暂无线下可分析的支出类别。"

    top_items = category_stats[:3]
    parts = [
        f"{item.get('name', '其他')} {_fmt_amount(item.get('amount', 0))} 元，占比 {float(item.get('ratio', 0) or 0):.2f}%"
        for item in top_items
    ]
    return "；".join(parts)


def _build_summary(financial_summary: dict, category_stats: list[dict], risk_items: list[str]) -> dict:
    real_income = float(financial_summary.get("real_income", 0) or 0)
    net_expense = float(financial_summary.get("net_expense", 0) or 0)
    balance = float(financial_summary.get("balance", 0) or 0)
    top_category = category_stats[0]["name"] if category_stats else "其他"

    if real_income <= 0 and net_expense <= 0:
        overview = "本月暂无有效收支数据，建议先保持完整记账，再观察复盘结果。"
    elif balance >= 0:
        overview = (
            f"本月真实收入 {_fmt_amount(real_income)} 元，净支出 {_fmt_amount(net_expense)} 元，"
            f"结余 {_fmt_amount(balance)} 元，整体维持正向结余，支出重点集中在 {top_category}。"
        )
    else:
        overview = (
            f"本月真实收入 {_fmt_amount(real_income)} 元，净支出 {_fmt_amount(net_expense)} 元，"
            f"收支缺口 {_fmt_amount(abs(balance))} 元，当前月度现金结余承压，支出重点集中在 {top_category}。"
        )

    highlights = [
        f"真实收入 = 收入 - 报销，当前为 {_fmt_amount(real_income)} 元。",
        f"净支出 = 支出 - 报销，当前为 {_fmt_amount(net_expense)} 元。",
        f"头部消费类别：{_top_category_text(category_stats)}",
    ]
    if risk_items:
        highlights.append(risk_items[0])

    return {
        "title": "本月总结",
        "overview": overview,
        "highlights": highlights,
    }


def _build_kpi(financial_summary: dict) -> dict:
    gross_income = float(financial_summary.get("gross_income", 0) or 0)
    gross_expense = float(financial_summary.get("gross_expense", 0) or 0)
    reimbursement_income = float(financial_summary.get("reimbursement_income", 0) or 0)
    real_income = float(financial_summary.get("real_income", 0) or 0)
    net_expense = float(financial_summary.get("net_expense", 0) or 0)
    balance = float(financial_summary.get("balance", 0) or 0)

    return {
        "gross_income": round(gross_income, 2),
        "gross_expense": round(gross_expense, 2),
        "reimbursement_income": round(reimbursement_income, 2),
        "real_income": round(real_income, 2),
        "net_expense": round(net_expense, 2),
        "balance": round(balance, 2),
    }


def _build_structure_analysis(monthly_stats: dict) -> dict:
    category_stats = monthly_stats.get("category_stats", [])
    tag_stats = monthly_stats.get("tag_stats", [])
    top_category = category_stats[0] if category_stats else None
    secondary_category = category_stats[1] if len(category_stats) > 1 else None

    if top_category:
        overview = (
            f"{top_category['name']} 是本月第一大支出项，金额 {_fmt_amount(top_category['amount'])} 元，"
            f"占总支出的 {float(top_category.get('ratio', 0) or 0):.2f}%。"
        )
    else:
        overview = "本月暂无可分析的消费结构数据。"

    insights = []
    if top_category and float(top_category.get("ratio", 0) or 0) >= 35:
        insights.append(f"头部类别集中度较高，{top_category['name']} 已成为本月预算治理重点。")
    if secondary_category:
        insights.append(
            f"第二大支出为 {secondary_category['name']}，金额 {_fmt_amount(secondary_category['amount'])} 元。"
        )
    if tag_stats:
        top_tag = tag_stats[0]
        insights.append(
            f"标签层面占比最高的是 {top_tag['name']}，金额 {_fmt_amount(top_tag['amount'])} 元。"
        )

    return {
        "title": "消费结构分析",
        "overview": overview,
        "top_categories": category_stats[:5],
        "top_tags": tag_stats[:4],
        "insights": insights,
    }


def _build_behavior_analysis(insights: dict, monthly_stats: dict) -> dict:
    persona = insights.get("consumption_persona", {}) or {}
    health = insights.get("consumption_health", {}) or {}
    metrics = health.get("metrics", {}) or {}
    daily_expense = monthly_stats.get("daily_expense", [])
    frequency = len(daily_expense)

    habits = [
        f"消费画像：{persona.get('label', '稳健型')}。",
        f"冲动消费占比 {float(metrics.get('impulsive_ratio', 0) or 0):.2f}%，学习投资占比 {float(metrics.get('learning_ratio', 0) or 0):.2f}%。",
        f"本月有支出记录的天数为 {frequency} 天，消费节奏{('偏分散' if frequency >= 12 else '偏集中')}。",
    ]

    return {
        "title": "消费行为画像",
        "label": persona.get("label", "稳健型"),
        "description": persona.get("description", "本月消费行为整体平稳。"),
        "reasons": persona.get("reasons", [])[:3],
        "habits": habits,
    }


def _build_risk_analysis(
    financial_summary: dict,
    monthly_stats: dict,
    insights: dict,
    subscription_recap: dict,
    reimbursement_progress: dict,
    budget_health: dict,
) -> dict:
    risk_radar = insights.get("risk_radar", {}) or {}
    risk_items: list[dict] = []
    category_stats = monthly_stats.get("category_stats", [])
    metrics = risk_radar.get("metrics", {}) or {}
    balance = float(financial_summary.get("balance", 0) or 0)

    if balance < 0:
        risk_items.append(
            {
                "level": "high",
                "title": "本月收支倒挂",
                "detail": f"结余为 -{_fmt_amount(abs(balance))} 元，说明当前月度现金流为负。",
            }
        )
    if category_stats and float(category_stats[0].get("ratio", 0) or 0) >= 40:
        risk_items.append(
            {
                "level": "medium",
                "title": "支出过度集中",
                "detail": (
                    f"{category_stats[0]['name']} 占总支出 {float(category_stats[0].get('ratio', 0) or 0):.2f}%，"
                    "单一类别波动会明显影响全月表现。"
                ),
            }
        )
    if float(metrics.get("impulsive_ratio", 0) or 0) >= 25:
        risk_items.append(
            {
                "level": "high",
                "title": "冲动消费偏高",
                "detail": f"冲动消费占比达到 {float(metrics.get('impulsive_ratio', 0) or 0):.2f}%。",
            }
        )
    subscription_ratio = (
        float(subscription_recap.get("estimated_monthly_cost", 0) or 0)
        / max(float(financial_summary.get("net_expense", 0) or 0), 1.0)
        * 100
    )
    if subscription_ratio >= 15:
        risk_items.append(
            {
                "level": "medium",
                "title": "订阅固定成本偏高",
                "detail": f"订阅折算月成本约占净支出的 {subscription_ratio:.2f}%。",
            }
        )
    if float(reimbursement_progress.get("pending_amount", 0) or 0) > 0:
        risk_items.append(
            {
                "level": "medium",
                "title": "报销未完全回收",
                "detail": f"仍有 {_fmt_amount(reimbursement_progress.get('pending_amount', 0))} 元待报销，短期会抬高现金支出压力。",
            }
        )

    for hint in (budget_health.get("risk_hints") or [])[:2]:
        risk_items.append(
            {
                "level": "medium",
                "title": "预算执行提醒",
                "detail": hint,
            }
        )

    return {
        "title": "风险识别",
        "level": risk_radar.get("level", "低风险"),
        "score": round(float(risk_radar.get("score", 0) or 0), 2),
        "items": risk_items[:6],
        "summary": risk_radar.get("explanations", [])[:3],
    }


def _build_budget_analysis(budget_execution: dict, budget_health: dict) -> dict:
    items = budget_execution.get("items") or []
    total_item = next((item for item in items if item.get("category_main") is None), None)
    category_items = [item for item in items if item.get("category_main")]
    overspending = [item for item in category_items if float(item.get("execution_rate", 0) or 0) >= 100]
    near_limit = [item for item in category_items if 80 <= float(item.get("execution_rate", 0) or 0) < 100]

    if total_item:
        overview = (
            f"本月总预算执行率为 {float(total_item.get('execution_rate', 0) or 0):.2f}%，"
            f"预算口径基于净支出 {_fmt_amount(total_item.get('actual_expense', 0))} 元。"
        )
    else:
        overview = "本月未设置总预算，预算分析基于已配置分类预算生成。"

    return {
        "title": "预算执行情况",
        "overview": overview,
        "score": budget_health.get("score", {}),
        "overspending": overspending[:4],
        "near_limit": near_limit[:4],
        "hints": budget_health.get("risk_hints", [])[:3],
    }


def _build_subscription_analysis(financial_summary: dict, subscription_recap: dict, subscription_summary: dict) -> dict:
    estimated_cost = float(subscription_recap.get("estimated_monthly_cost", 0) or 0)
    actual_cost = float(subscription_recap.get("actual_charged_amount", 0) or 0)
    net_expense = float(financial_summary.get("net_expense", 0) or 0)
    pressure_ratio = estimated_cost / max(net_expense, 1.0) * 100 if net_expense > 0 else 0.0

    if pressure_ratio >= 20:
        level = "高"
    elif pressure_ratio >= 10:
        level = "中"
    else:
        level = "低"

    return {
        "title": "订阅压力分析",
        "overview": (
            f"订阅折算月成本 {_fmt_amount(estimated_cost)} 元，实际扣费 {_fmt_amount(actual_cost)} 元，"
            f"约占净支出的 {pressure_ratio:.2f}%。"
        ),
        "pressure_level": level,
        "estimated_monthly_cost": round(estimated_cost, 2),
        "actual_charged_amount": round(actual_cost, 2),
        "top_subscriptions": subscription_summary.get("top_monthly_cost", [])[:4],
        "next_month_upcoming": (subscription_recap.get("next_month_upcoming") or [])[:4],
    }


def _build_reimbursement_analysis(financial_summary: dict, reimbursement_progress: dict, pending_summary: dict) -> dict:
    reimbursement_income = float(financial_summary.get("reimbursement_income", 0) or 0)
    pending_amount = float(reimbursement_progress.get("pending_amount", 0) or 0)

    return {
        "title": "报销分析",
        "overview": (
            f"本月已入账报销 {_fmt_amount(reimbursement_income)} 元，"
            f"已回收 {_fmt_amount(reimbursement_progress.get('reimbursed_amount', 0))} 元，"
            f"仍待回收 {_fmt_amount(pending_amount)} 元。"
        ),
        "tracked_count": int(reimbursement_progress.get("tracked_count", 0) or 0),
        "completion_rate": round(float(reimbursement_progress.get("completion_rate", 0) or 0), 2),
        "pending_amount": round(pending_amount, 2),
        "pending_count": int(pending_summary.get("pending_count", 0) or 0),
        "category_pending_amount": pending_summary.get("category_pending_amount", {}),
    }


def _build_next_month_suggestions(
    financial_summary: dict,
    monthly_stats: dict,
    insights: dict,
    budget_analysis: dict,
    subscription_analysis: dict,
    reimbursement_analysis: dict,
) -> list[str]:
    suggestions: list[str] = []
    balance = float(financial_summary.get("balance", 0) or 0)
    category_stats = monthly_stats.get("category_stats", [])
    metrics = (insights.get("consumption_health", {}) or {}).get("metrics", {}) or {}

    if balance < 0:
        suggestions.append(f"下月先把净支出压回真实收入以内，至少补齐 {_fmt_amount(abs(balance))} 元收支缺口。")
    if category_stats:
        top_category = category_stats[0]
        suggestions.append(
            f"为 {top_category['name']} 单独设置月上限，优先管理占比 {float(top_category.get('ratio', 0) or 0):.2f}% 的头部支出。"
        )
    if float(metrics.get("impulsive_ratio", 0) or 0) >= 20:
        suggestions.append("为冲动类消费增加 24 小时冷静期，并设一个单月封顶额度。")
    if budget_analysis.get("overspending"):
        category = budget_analysis["overspending"][0].get("category_main", "重点分类")
        suggestions.append(f"下月优先修正 {category} 的预算，避免继续超支。")
    if subscription_analysis.get("top_subscriptions"):
        name = subscription_analysis["top_subscriptions"][0].get("name", "高成本订阅")
        suggestions.append(f"检查 {name} 的使用频率，低频就停用或降级套餐。")
    if float(reimbursement_analysis.get("pending_amount", 0) or 0) > 0:
        suggestions.append("待报销项目在下月上旬前完成提交，避免现金流长期被占用。")

    if not suggestions:
        suggestions.append("下月继续保持当前记账和预算节奏，重点观察大额支出日。")

    return suggestions[:5]


def generate_monthly_review(month: str) -> dict:
    monthly_stats = get_monthly_stats(month)
    financial_summary = get_monthly_financial_summary(month)
    insights = get_monthly_insights(month)
    budget_execution = get_budget_execution(month)
    budget_health = get_budget_health_profile(month)
    subscription_recap = get_subscription_monthly_recap(month)
    subscription_summary = get_subscription_monthly_cost_summary()
    reimbursement_progress = get_month_reimbursement_progress(month)
    pending_summary = get_month_pending_reimbursement_summary(month)
    recent_months = month_sequence(month, count=3)

    year, mon = map(int, month.split("-"))
    days_in_month = monthrange(year, mon)[1]
    active_spending_days = len(monthly_stats.get("daily_expense", []))

    risk_analysis = _build_risk_analysis(
        financial_summary=financial_summary,
        monthly_stats=monthly_stats,
        insights=insights,
        subscription_recap=subscription_recap,
        reimbursement_progress=reimbursement_progress,
        budget_health=budget_health,
    )
    summary = _build_summary(financial_summary, monthly_stats.get("category_stats", []), [
        item.get("detail", "") for item in risk_analysis.get("items", [])
    ])
    budget_analysis = _build_budget_analysis(budget_execution, budget_health)
    subscription_analysis = _build_subscription_analysis(financial_summary, subscription_recap, subscription_summary)
    reimbursement_analysis = _build_reimbursement_analysis(financial_summary, reimbursement_progress, pending_summary)

    return {
        "month": month,
        "summary": summary,
        "kpi": _build_kpi(financial_summary),
        "structure_analysis": _build_structure_analysis(monthly_stats),
        "behavior_analysis": _build_behavior_analysis(insights, monthly_stats),
        "risk_analysis": risk_analysis,
        "budget_analysis": budget_analysis,
        "subscription_analysis": subscription_analysis,
        "reimbursement_analysis": reimbursement_analysis,
        "next_month_suggestions": _build_next_month_suggestions(
            financial_summary,
            monthly_stats,
            insights,
            budget_analysis,
            subscription_analysis,
            reimbursement_analysis,
        ),
        "meta": {
            "recent_months": recent_months,
            "active_spending_days": active_spending_days,
            "days_in_month": days_in_month,
        },
    }

