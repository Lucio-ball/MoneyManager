import math
from calendar import monthrange
from datetime import datetime

from extensions.database import get_connection
from models.budget import get_budget_execution, get_budget_health_profile
from models.subscription import get_subscription_monthly_metrics, get_subscription_monthly_recap
from models.transaction import get_monthly_financial_summary, get_monthly_stats, get_transactions_by_month
from utils.date_utils import month_sequence
from utils.trend_utils import parse_tags


def _clamp_score(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 2)


def _health_level(score: float) -> str:
    if score >= 80:
        return "优秀"
    if score >= 60:
        return "良好"
    if score >= 40:
        return "一般"
    return "需关注"


def _calculate_consumption_health(
    month: str,
    total_expense: float,
    daily_expense: list[dict],
    records: list[dict],
    category_stats: list[dict],
    impulsive_amount: float,
    learning_amount: float,
) -> dict:
    if total_expense <= 0:
        neutral_score = 80.0
        return {
            "score": neutral_score,
            "level": _health_level(neutral_score),
            "dimensions": [
                {"key": "impulse_control", "label": "冲动控制", "value": neutral_score},
                {"key": "need_structure", "label": "刚需结构", "value": neutral_score},
                {"key": "learning_investment", "label": "学习投资", "value": neutral_score},
                {"key": "category_balance", "label": "类别分散", "value": neutral_score},
                {"key": "spending_stability", "label": "消费稳定", "value": neutral_score},
            ],
            "breakdown": {
                "impulse_control": neutral_score,
                "need_structure": neutral_score,
                "learning_investment": neutral_score,
                "category_balance": neutral_score,
                "spending_stability": neutral_score,
            },
            "metrics": {
                "impulsive_ratio": 0.0,
                "rigid_ratio": 0.0,
                "non_rigid_ratio": 0.0,
                "learning_ratio": 0.0,
                "category_hhi": 0.0,
                "daily_variance": 0.0,
                "daily_std_dev": 0.0,
                "daily_cv": 0.0,
            },
        }

    impulsive_ratio = (impulsive_amount / total_expense * 100) if total_expense > 0 else 0.0
    impulsive_score = _clamp_score((40 - impulsive_ratio) / 40 * 100)

    rigid_amount = 0.0
    for record in records:
        if record.get("type") != "expense":
            continue
        tags = set(record.get("tags", []))
        if "刚需" in tags:
            rigid_amount += float(record.get("amount") or 0)

    rigid_ratio = (rigid_amount / total_expense * 100) if total_expense > 0 else 0.0
    non_rigid_ratio = 100 - rigid_ratio if total_expense > 0 else 0.0
    need_structure_score = _clamp_score(100 - abs(rigid_ratio - 60) * 2)

    learning_ratio = (learning_amount / total_expense * 100) if total_expense > 0 else 0.0
    learning_score = _clamp_score((learning_ratio / 15) * 100)

    category_amounts = [float(item.get("amount") or 0) for item in category_stats if float(item.get("amount") or 0) > 0]
    if len(category_amounts) <= 1:
        category_hhi = 1.0
        category_balance_score = 0.0
    else:
        shares = [amount / total_expense for amount in category_amounts]
        category_hhi = sum(share * share for share in shares)
        hhi_min = 1 / len(category_amounts)
        concentration_norm = (category_hhi - hhi_min) / (1 - hhi_min)
        category_balance_score = _clamp_score((1 - concentration_norm) * 100)

    try:
        year_str, month_str = month.split("-")
        year_num = int(year_str)
        month_num = int(month_str)
        days_count = monthrange(year_num, month_num)[1]
    except (ValueError, TypeError):
        days_count = len(daily_expense)

    daily_map = {str(item.get("date")): float(item.get("amount") or 0) for item in daily_expense}
    if days_count > 0 and len(month) == 7:
        all_daily_amounts = [daily_map.get(f"{month}-{day:02d}", 0.0) for day in range(1, days_count + 1)]
    else:
        all_daily_amounts = [float(item.get("amount") or 0) for item in daily_expense]

    if all_daily_amounts:
        daily_avg = sum(all_daily_amounts) / len(all_daily_amounts)
        daily_variance = sum((value - daily_avg) ** 2 for value in all_daily_amounts) / len(all_daily_amounts)
        daily_std_dev = math.sqrt(daily_variance)
        daily_cv = daily_std_dev / max(daily_avg, 1.0)
    else:
        daily_variance = 0.0
        daily_std_dev = 0.0
        daily_cv = 0.0

    spending_stability_score = _clamp_score(100 - daily_cv * 45)

    total_score = round(
        (
            impulsive_score * 0.30
            + need_structure_score * 0.20
            + learning_score * 0.20
            + category_balance_score * 0.15
            + spending_stability_score * 0.15
        ),
        2,
    )

    return {
        "score": total_score,
        "level": _health_level(total_score),
        "dimensions": [
            {"key": "impulse_control", "label": "冲动控制", "value": impulsive_score},
            {"key": "need_structure", "label": "刚需结构", "value": need_structure_score},
            {"key": "learning_investment", "label": "学习投资", "value": learning_score},
            {"key": "category_balance", "label": "类别分散", "value": category_balance_score},
            {"key": "spending_stability", "label": "消费稳定", "value": spending_stability_score},
        ],
        "breakdown": {
            "impulse_control": impulsive_score,
            "need_structure": need_structure_score,
            "learning_investment": learning_score,
            "category_balance": category_balance_score,
            "spending_stability": spending_stability_score,
        },
        "metrics": {
            "impulsive_ratio": round(impulsive_ratio, 2),
            "rigid_ratio": round(rigid_ratio, 2),
            "non_rigid_ratio": round(non_rigid_ratio, 2),
            "learning_ratio": round(learning_ratio, 2),
            "category_hhi": round(category_hhi, 4),
            "daily_variance": round(daily_variance, 2),
            "daily_std_dev": round(daily_std_dev, 2),
            "daily_cv": round(daily_cv, 4),
        },
    }


def _build_consumption_persona(
    month: str,
    total_expense: float,
    records: list[dict],
    monthly_stats: dict,
    month_total_map: dict[str, float],
    consumption_health: dict,
) -> dict:
    if total_expense <= 0:
        return {
            "type": "steady",
            "label": "稳健型",
            "description": "本月消费记录较少，整体支出节奏平稳，建议继续观察并保持记账完整性。",
            "reasons": ["本月总支出较低或暂无支出，未出现明显高风险消费信号。"],
            "scores": {
                "impulsive": 0.0,
                "steady": 80.0,
                "learning_investor": 0.0,
                "social_driven": 0.0,
                "subscription_pressure": 0.0,
            },
            "metrics": {
                "impulsive_ratio": 0.0,
                "learning_ratio": 0.0,
                "social_ratio": 0.0,
                "subscription_ratio": 0.0,
                "trend_growth_ratio": 0.0,
                "top_category_ratio": 0.0,
            },
        }

    health_score = float(consumption_health.get("score", 0) or 0)
    health_metrics = consumption_health.get("metrics", {})
    impulsive_ratio = float(health_metrics.get("impulsive_ratio", 0) or 0)
    learning_ratio = float(health_metrics.get("learning_ratio", 0) or 0)

    category_stats = monthly_stats.get("category_stats", [])
    top_category_ratio = float((category_stats[0].get("ratio") if category_stats else 0) or 0)

    monthly_subscription_cost = float(get_subscription_monthly_metrics(month).get("estimated_monthly_cost", 0) or 0)
    subscription_ratio = (monthly_subscription_cost / total_expense * 100) if total_expense > 0 else 0.0

    months = sorted(month_total_map.keys())
    first_month_total = float(month_total_map.get(months[0], 0) or 0) if months else 0.0
    current_month_total = float(month_total_map.get(month, 0) or 0)
    if first_month_total > 0:
        trend_growth_ratio = (current_month_total - first_month_total) / first_month_total * 100
    else:
        trend_growth_ratio = 0.0

    social_tag_set = {"社交", "人情", "聚会", "请客", "社交活动"}
    social_category_keywords = ("社交", "聚会", "娱乐", "餐饮", "人情")
    social_amount = 0.0
    for row in records:
        if row.get("type") != "expense":
            continue
        amount = float(row.get("amount") or 0)
        tags = set(row.get("tags", []))
        category_name = str(row.get("category_main") or "")
        if tags.intersection(social_tag_set) or any(keyword in category_name for keyword in social_category_keywords):
            social_amount += amount
    social_ratio = (social_amount / total_expense * 100) if total_expense > 0 else 0.0

    persona_scores = {
        "impulsive": _clamp_score(impulsive_ratio * 1.8 + max(trend_growth_ratio, 0) * 0.6 + (100 - health_score) * 0.15),
        "steady": _clamp_score(health_score * 0.8 + max(0, 25 - impulsive_ratio) * 1.4 + max(0, 15 - abs(trend_growth_ratio)) * 1.1),
        "learning_investor": _clamp_score(learning_ratio * 4.2 + max(0, 30 - impulsive_ratio) * 1.0 + health_score * 0.25),
        "social_driven": _clamp_score(social_ratio * 3.1 + max(0, trend_growth_ratio) * 0.3 + max(0, 35 - health_score) * 0.5),
        "subscription_pressure": _clamp_score(subscription_ratio * 3.8 + max(0, trend_growth_ratio) * 0.5 + top_category_ratio * 0.4),
    }

    persona_meta = {
        "impulsive": {
            "label": "冲动型",
            "description": "消费决策受即时情绪和短期刺激影响较大，建议通过延迟购买和上限约束来降温。",
        },
        "steady": {
            "label": "稳健型",
            "description": "支出结构和节奏整体稳定，具备较好的预算执行习惯，建议继续保持并做小幅优化。",
        },
        "learning_investor": {
            "label": "学习投资型",
            "description": "愿意把预算投入长期能力建设，具备成长型消费倾向，建议继续关注投入产出比。",
        },
        "social_driven": {
            "label": "社交驱动型",
            "description": "消费较多由社交场景触发，建议为社交预算设置独立上限，避免被动超支。",
        },
        "subscription_pressure": {
            "label": "订阅压力型",
            "description": "固定订阅成本对月度支出形成持续压力，建议优先清理低使用率订阅。",
        },
    }

    persona_type = max(persona_scores.items(), key=lambda item: item[1])[0]

    reasons: list[str] = []
    if impulsive_ratio >= 30:
        reasons.append(f"冲动消费占比 {impulsive_ratio:.2f}% 偏高，拉升了短期消费风险。")
    if learning_ratio >= 12:
        reasons.append(f"学习投资占比 {learning_ratio:.2f}% 较高，体现长期成长导向。")
    if social_ratio >= 30:
        reasons.append(f"社交相关支出占比 {social_ratio:.2f}% 较高，消费受场景驱动明显。")
    if subscription_ratio >= 15:
        reasons.append(f"订阅支出占比 {subscription_ratio:.2f}% 偏高，固定成本压力需持续关注。")
    if abs(trend_growth_ratio) >= 15:
        trend_text = "上升" if trend_growth_ratio > 0 else "下降"
        reasons.append(f"近 3 个月总支出呈 {trend_text} 趋势（{trend_growth_ratio:.2f}%）。")
    if not reasons:
        reasons.append("本月支出结构相对均衡，未出现明显单一风险驱动。")

    return {
        "type": persona_type,
        "label": persona_meta[persona_type]["label"],
        "description": persona_meta[persona_type]["description"],
        "reasons": reasons[:3],
        "scores": persona_scores,
        "metrics": {
            "impulsive_ratio": round(impulsive_ratio, 2),
            "learning_ratio": round(learning_ratio, 2),
            "social_ratio": round(social_ratio, 2),
            "subscription_ratio": round(subscription_ratio, 2),
            "trend_growth_ratio": round(trend_growth_ratio, 2),
            "top_category_ratio": round(top_category_ratio, 2),
        },
    }


def _risk_level(score: float) -> str:
    if score >= 70:
        return "高风险"
    if score >= 40:
        return "中风险"
    return "低风险"


def _safe_median(values: list[float]) -> float:
    ordered = sorted(float(value or 0) for value in values)
    if not ordered:
        return 0.0
    middle = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def _safe_mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(float(value or 0) for value in values) / len(values)


def _parse_hour(value: str | None) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    normalized = text.replace(" ", "T")
    try:
        return datetime.fromisoformat(normalized).hour
    except ValueError:
        return None


def _is_non_rigid_expense(record: dict) -> bool:
    tags = set(record.get("tags", []) or [])
    if "鍒氶渶" in tags:
        return False
    category_name = str(record.get("category_main") or "")
    rigid_keywords = ("鎴胯", "鎴夸綇", "閫氬嫟", "鍖荤枟", "瀛︿範", "鏁欒偛")
    return not any(keyword in category_name for keyword in rigid_keywords)


def detect_spending_anomalies(month: str) -> dict:
    records = [item for item in get_transactions_by_month(month) if item.get("type") == "expense"]
    monthly_stats = get_monthly_stats(month)
    daily_expense = monthly_stats.get("daily_expense", [])
    month_amounts = [float(item.get("amount") or 0) for item in records]
    month_mean = _safe_mean(month_amounts)
    month_median = _safe_median(month_amounts)

    months = month_sequence(month, count=4)
    history_months = [item for item in months if item != month]
    history_category_map: dict[str, list[float]] = {}
    history_category_count_map: dict[str, list[int]] = {}
    history_total_by_day: list[float] = []

    if history_months:
        placeholders = ",".join("?" for _ in history_months)
        with get_connection() as conn:
            category_rows = conn.execute(
                f"""
                SELECT substr(date, 1, 7) AS month, category_main, ROUND(SUM(amount), 2) AS amount, COUNT(*) AS count
                FROM transactions
                WHERE type = 'expense'
                  AND substr(date, 1, 7) IN ({placeholders})
                GROUP BY substr(date, 1, 7), category_main
                """,
                tuple(history_months),
            ).fetchall()
            day_rows = conn.execute(
                f"""
                SELECT date, ROUND(SUM(amount), 2) AS amount
                FROM transactions
                WHERE type = 'expense'
                  AND substr(date, 1, 7) IN ({placeholders})
                GROUP BY date
                """,
                tuple(history_months),
            ).fetchall()

        for row in category_rows:
            category = row["category_main"] or "鍏朵粬"
            history_category_map.setdefault(category, []).append(float(row["amount"] or 0))
            history_category_count_map.setdefault(category, []).append(int(row["count"] or 0))
        history_total_by_day = [float(row["amount"] or 0) for row in day_rows]

    category_amounts_current: dict[str, list[float]] = {}
    category_totals_current: dict[str, float] = {}
    day_records_map: dict[str, list[dict]] = {}
    micro_records: list[dict] = []
    late_night_records: list[dict] = []
    emotional_records: list[dict] = []
    impulsive_records: list[dict] = []

    small_threshold = 0.0
    if month_amounts:
        small_threshold = max(10.0, min(max(month_median * 0.6, 0.0), 30.0))

    for record in records:
        category = record.get("category_main") or "鍏朵粬"
        amount = float(record.get("amount") or 0)
        category_amounts_current.setdefault(category, []).append(amount)
        category_totals_current[category] = round(category_totals_current.get(category, 0.0) + amount, 2)
        day_records_map.setdefault(str(record.get("date")), []).append(record)

        tags = set(record.get("tags", []) or [])
        note_text = str(record.get("note") or "")
        if "鍐插姩" in tags:
            impulsive_records.append(record)
        if "鎯呯华娑堣垂" in tags or "鎯呯华" in note_text:
            emotional_records.append(record)
        hour = _parse_hour(record.get("created_at"))
        if hour is not None and (hour >= 22 or hour < 6) and _is_non_rigid_expense(record):
            late_night_records.append(record)
        if amount > 0 and small_threshold > 0 and amount <= small_threshold:
            micro_records.append(record)

    high_value_anomalies = []
    for record in sorted(records, key=lambda item: float(item.get("amount") or 0), reverse=True):
        category = record.get("category_main") or "鍏朵粬"
        amount = float(record.get("amount") or 0)
        category_values = category_amounts_current.get(category, [])
        category_mean = _safe_mean(category_values)
        history_avg = _safe_mean(history_category_map.get(category, []))
        if amount <= 0:
            continue

        is_high_vs_category = category_mean > 0 and amount >= category_mean * 2.5 and amount >= max(month_mean * 1.8, 50.0)
        is_high_vs_month = month_median > 0 and amount >= month_median * 3 and amount >= max(month_mean * 2.0, 80.0)
        is_high_vs_history = history_avg > 0 and amount >= history_avg * 2.2

        if is_high_vs_category or is_high_vs_month or is_high_vs_history:
            high_value_anomalies.append(
                {
                    "id": int(record.get("id") or 0),
                    "date": record.get("date"),
                    "category": category,
                    "amount": round(amount, 2),
                    "category_mean": round(category_mean, 2),
                    "month_median": round(month_median, 2),
                    "history_avg": round(history_avg, 2),
                    "note": record.get("note") or "",
                }
            )
    high_value_anomalies = high_value_anomalies[:5]

    daily_values = [float(item.get("amount") or 0) for item in daily_expense]
    day_mean = _safe_mean(daily_values)
    history_day_mean = _safe_mean(history_total_by_day)
    day_variance = sum((value - day_mean) ** 2 for value in daily_values) / len(daily_values) if daily_values else 0.0
    day_std = math.sqrt(day_variance)
    daily_threshold = max(day_mean + day_std, day_mean * 2.0, history_day_mean * 1.8 if history_day_mean > 0 else 0.0)
    daily_spikes = []
    for item in sorted(daily_expense, key=lambda row: float(row.get("amount") or 0), reverse=True):
        amount = float(item.get("amount") or 0)
        if amount <= 0 or amount < daily_threshold:
            continue
        day_records = day_records_map.get(str(item.get("date")), [])
        non_rigid_count = sum(1 for row in day_records if _is_non_rigid_expense(row))
        daily_spikes.append(
            {
                "date": item.get("date"),
                "amount": round(amount, 2),
                "tx_count": len(day_records),
                "non_rigid_count": non_rigid_count,
            }
        )
    daily_spikes = daily_spikes[:5]

    category_spikes = []
    for category, amount in sorted(category_totals_current.items(), key=lambda row: row[1], reverse=True):
        history_values = history_category_map.get(category, [])
        history_avg = _safe_mean(history_values)
        current_count = len(category_amounts_current.get(category, []))
        history_count_avg = _safe_mean(history_category_count_map.get(category, []))
        if amount <= 0 or history_avg <= 0:
            continue
        growth_ratio = (amount - history_avg) / history_avg * 100
        count_growth_ratio = (
            (current_count - history_count_avg) / history_count_avg * 100 if history_count_avg > 0 else 0.0
        )
        if growth_ratio >= 45 and amount - history_avg >= max(month_mean, 50.0):
            category_spikes.append(
                {
                    "category": category,
                    "amount": round(amount, 2),
                    "history_avg": round(history_avg, 2),
                    "growth_ratio": round(growth_ratio, 2),
                    "count_growth_ratio": round(count_growth_ratio, 2),
                }
            )
    category_spikes = category_spikes[:5]

    same_day_impulse = []
    for date_key, day_records in day_records_map.items():
        non_rigid_records = [row for row in day_records if _is_non_rigid_expense(row)]
        non_rigid_total = sum(float(row.get("amount") or 0) for row in non_rigid_records)
        if len(non_rigid_records) >= 4 and non_rigid_total >= max(month_mean, 80.0):
            same_day_impulse.append(
                {
                    "date": date_key,
                    "count": len(non_rigid_records),
                    "amount": round(non_rigid_total, 2),
                }
            )

    impulse_signals = {
        "late_night_count": len(late_night_records),
        "late_night_amount": round(sum(float(item.get("amount") or 0) for item in late_night_records), 2),
        "emotional_count": len(emotional_records),
        "emotional_amount": round(sum(float(item.get("amount") or 0) for item in emotional_records), 2),
        "impulsive_tag_count": len(impulsive_records),
        "impulsive_tag_amount": round(sum(float(item.get("amount") or 0) for item in impulsive_records), 2),
        "same_day_cluster": sorted(same_day_impulse, key=lambda item: item["amount"], reverse=True)[:3],
    }

    micro_total = sum(float(item.get("amount") or 0) for item in micro_records)
    micro_count = len(micro_records)
    micro_spending_pattern = {
        "threshold": round(small_threshold, 2),
        "count": micro_count,
        "amount": round(micro_total, 2),
        "avg_amount": round(micro_total / micro_count, 2) if micro_count > 0 else 0.0,
        "is_significant": micro_count >= 6 and micro_total >= max(month_mean * 1.5, 100.0),
    }

    score = 0.0
    score += min(len(high_value_anomalies) * 18, 30)
    score += min(len(daily_spikes) * 12, 20)
    score += min(len(category_spikes) * 14, 20)
    score += min(
        (impulse_signals["late_night_count"] + impulse_signals["emotional_count"] + impulse_signals["impulsive_tag_count"]) * 3,
        18,
    )
    if micro_spending_pattern["is_significant"]:
        score += 12

    insights = []
    if high_value_anomalies:
        top_item = high_value_anomalies[0]
        insights.append(
            f"{top_item['date']} 在 {top_item['category']} 出现单笔 {top_item['amount']:.2f} 元高消费，明显高于本月常规水平。"
        )
    if daily_spikes:
        top_day = daily_spikes[0]
        insights.append(
            f"{top_day['date']} 单日支出 {top_day['amount']:.2f} 元，且有 {top_day['tx_count']} 笔交易，消费集中度偏高。"
        )
    if category_spikes:
        top_category = category_spikes[0]
        insights.append(
            f"{top_category['category']} 较近 3 个月月均增长 {top_category['growth_ratio']:.2f}%，属于本月异常增长类别。"
        )
    if impulse_signals["late_night_count"] > 0 or impulse_signals["emotional_count"] > 0:
        insights.append(
            f"本月出现 {impulse_signals['late_night_count']} 笔深夜记录、{impulse_signals['emotional_count']} 笔情绪化标签记录，需关注冲动决策。"
        )
    if micro_spending_pattern["is_significant"]:
        insights.append(
            f"小额消费共 {micro_spending_pattern['count']} 笔，累计 {micro_spending_pattern['amount']:.2f} 元，存在高频小额堆积。"
        )
    if impulse_signals["same_day_cluster"]:
        cluster = impulse_signals["same_day_cluster"][0]
        insights.append(
            f"{cluster['date']} 出现 {cluster['count']} 笔非刚需消费，累计 {cluster['amount']:.2f} 元，存在集中冲动消费信号。"
        )

    return {
        "month": month,
        "high_value_anomalies": high_value_anomalies,
        "category_spikes": category_spikes,
        "daily_spikes": daily_spikes,
        "impulse_signals": impulse_signals,
        "micro_spending_pattern": micro_spending_pattern,
        "risk_level": _risk_level(round(score, 2)),
        "risk_score": round(score, 2),
        "insights": insights[:6],
        "benchmarks": {
            "month_mean": round(month_mean, 2),
            "month_median": round(month_median, 2),
            "daily_mean": round(day_mean, 2),
            "daily_threshold": round(daily_threshold, 2),
        },
    }


def _build_risk_radar(consumption_health: dict, subscription_ratio: float, budget_health: dict) -> dict:
    metrics = consumption_health.get("metrics", {})
    impulsive_ratio = float(metrics.get("impulsive_ratio", 0) or 0)
    category_hhi = float(metrics.get("category_hhi", 0) or 0)
    daily_cv = float(metrics.get("daily_cv", 0) or 0)
    budget_execution_rate = float((budget_health.get("score") or {}).get("execution_rate", 0) or 0)

    impulse_risk = _clamp_score((impulsive_ratio / 40) * 100)
    budget_risk = _clamp_score(max(budget_execution_rate - 70, 0) / 50 * 100)
    subscription_pressure = _clamp_score((subscription_ratio / 25) * 100)
    category_concentration = _clamp_score(((category_hhi - 0.18) / 0.42) * 100)
    spending_volatility = _clamp_score((daily_cv / 1.2) * 100)

    dimensions = [
        {"key": "impulse_risk", "label": "\u51b2\u52a8\u98ce\u9669", "value": impulse_risk},
        {"key": "budget_risk", "label": "\u9884\u7b97\u98ce\u9669", "value": budget_risk},
        {"key": "subscription_pressure", "label": "\u8ba2\u9605\u538b\u529b", "value": subscription_pressure},
        {"key": "category_concentration", "label": "\u7c7b\u522b\u96c6\u4e2d\u5ea6", "value": category_concentration},
        {"key": "spending_volatility", "label": "\u6d88\u8d39\u6ce2\u52a8\u5ea6", "value": spending_volatility},
    ]

    risk_score = round(sum(item["value"] for item in dimensions) / len(dimensions), 2)

    explain_map = {
        "impulse_risk": f"\u51b2\u52a8\u6d88\u8d39\u5360\u6bd4 {impulsive_ratio:.2f}%\uff0c\u5bb9\u6613\u63a8\u9ad8\u77ed\u671f\u652f\u51fa\u98ce\u9669\u3002",
        "budget_risk": f"\u9884\u7b97\u6267\u884c\u7387 {budget_execution_rate:.2f}%\uff0c\u5f53\u524d\u9884\u7b97\u538b\u529b\u5df2\u8fdb\u5165\u98ce\u9669\u89c2\u6d4b\u533a\u95f4\u3002",
        "subscription_pressure": f"\u8ba2\u9605\u6210\u672c\u5360\u6bd4 {subscription_ratio:.2f}%\uff0c\u56fa\u5b9a\u652f\u51fa\u5f39\u6027\u8f83\u4f4e\u3002",
        "category_concentration": f"\u7c7b\u522b\u96c6\u4e2d\u5ea6\u6307\u6570 HHI={category_hhi:.4f}\uff0c\u5934\u90e8\u7c7b\u522b\u805a\u96c6\u660e\u663e\u3002",
        "spending_volatility": f"\u65e5\u652f\u51fa\u6ce2\u52a8\u7cfb\u6570 CV={daily_cv:.4f}\uff0c\u6d88\u8d39\u8282\u594f\u5b58\u5728\u8d77\u4f0f\u3002",
    }

    top_dims = sorted(dimensions, key=lambda item: item["value"], reverse=True)[:3]
    explanations = [explain_map[item["key"]] for item in top_dims]

    return {
        "score": risk_score,
        "level": _risk_level(risk_score),
        "dimensions": dimensions,
        "explanations": explanations,
        "metrics": {
            "impulsive_ratio": round(impulsive_ratio, 2),
            "budget_execution_rate": round(budget_execution_rate, 2),
            "subscription_ratio": round(subscription_ratio, 2),
            "category_hhi": round(category_hhi, 4),
            "daily_cv": round(daily_cv, 4),
        },
    }


def get_monthly_insights(month: str) -> dict:
    monthly_stats = get_monthly_stats(month)
    financial_summary = get_monthly_financial_summary(month)
    total_expense = financial_summary["gross_expense"]
    spending_anomalies = detect_spending_anomalies(month)

    daily_amounts = [item["amount"] for item in monthly_stats["daily_expense"]]
    daily_avg = (sum(daily_amounts) / len(daily_amounts)) if daily_amounts else 0

    abnormal_days = [
        {"date": item["date"], "amount": item["amount"]}
        for item in monthly_stats["daily_expense"]
        if daily_avg > 0 and item["amount"] > daily_avg * 2
    ]

    months = month_sequence(month, count=3)
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT substr(date, 1, 7) AS month, category_main, amount
            FROM transactions
            WHERE type = 'expense' AND substr(date, 1, 7) IN (?, ?, ?)
            """,
            (months[0], months[1], months[2]),
        ).fetchall()

    month_total_map = {key: 0.0 for key in months}
    month_category_map: dict[str, dict[str, float]] = {key: {} for key in months}
    for row in rows:
        m = row["month"]
        category = row["category_main"] or "其他"
        amount = float(row["amount"])
        month_total_map[m] = round(month_total_map.get(m, 0) + amount, 2)
        existing = month_category_map[m].get(category, 0.0)
        month_category_map[m][category] = round(existing + amount, 2)

    all_categories = set()
    for value in month_category_map.values():
        all_categories.update(value.keys())

    long_term_high_categories = []
    for category in sorted(all_categories):
        ratios = []
        valid = True
        for month_item in months:
            total = month_total_map.get(month_item, 0)
            if total <= 0:
                valid = False
                break
            amount = month_category_map.get(month_item, {}).get(category, 0.0)
            ratios.append(amount / total)
        if valid and ratios and all(ratio > 0.3 for ratio in ratios):
            long_term_high_categories.append(
                {
                    "category": category,
                    "months": months,
                    "ratios": [round(ratio * 100, 2) for ratio in ratios],
                }
            )

    records = get_transactions_by_month(month)
    impulsive_amount = 0.0
    learning_amount = 0.0
    for record in records:
        if record["type"] != "expense":
            continue
        tags = set(record["tags"])
        amount = float(record["amount"])
        if "冲动" in tags:
            impulsive_amount += amount
        if "学习投资" in tags or "投资自己" in tags:
            learning_amount += amount

    impulsive_ratio = (impulsive_amount / total_expense * 100) if total_expense > 0 else 0
    learning_ratio = (learning_amount / total_expense * 100) if total_expense > 0 else 0
    consumption_health = _calculate_consumption_health(
        month=month,
        total_expense=float(total_expense or 0),
        daily_expense=monthly_stats.get("daily_expense", []),
        records=records,
        category_stats=monthly_stats.get("category_stats", []),
        impulsive_amount=float(impulsive_amount),
        learning_amount=float(learning_amount),
    )
    subscription_metrics = get_subscription_monthly_metrics(month)
    subscription_ratio = (
        float(subscription_metrics.get("estimated_monthly_cost", 0) or 0) / float(total_expense or 0) * 100
        if float(total_expense or 0) > 0
        else 0.0
    )
    consumption_persona = _build_consumption_persona(
        month=month,
        total_expense=float(total_expense or 0),
        records=records,
        monthly_stats=monthly_stats,
        month_total_map=month_total_map,
        consumption_health=consumption_health,
    )
    budget_health = get_budget_health_profile(month)
    risk_radar = _build_risk_radar(consumption_health, subscription_ratio, budget_health)

    return {
        "month": month,
        "abnormal_high_expense_days": abnormal_days,
        "long_term_high_ratio_categories": long_term_high_categories,
        "spending_anomalies": spending_anomalies,
        "impulsive_spending_ratio": {
            "amount": round(impulsive_amount, 2),
            "ratio": round(impulsive_ratio, 2),
        },
        "learning_investment_ratio": {
            "amount": round(learning_amount, 2),
            "ratio": round(learning_ratio, 2),
        },
        "consumption_health": consumption_health,
        "consumption_persona": consumption_persona,
        "risk_radar": risk_radar,
    }


def get_analysis_dashboard_data(month: str) -> dict:
    monthly_stats = get_monthly_stats(month)
    financial_summary = get_monthly_financial_summary(month)
    insights = get_monthly_insights(month)
    subscription_metrics = get_subscription_monthly_metrics(month)
    budget_health = get_budget_health_profile(month)
    months = month_sequence(month, count=3)

    gross_expense = float(financial_summary.get("gross_expense", 0) or 0)
    gross_income = float(financial_summary.get("gross_income", 0) or 0)
    real_income = float(financial_summary.get("real_income", gross_income) or 0)
    reimbursement_amount = float(financial_summary.get("reimbursement_income", 0) or 0)
    net_expense = float(financial_summary.get("net_expense", gross_expense) or 0)
    balance = float(financial_summary.get("balance", 0) or 0)
    subscription_cost = float(subscription_metrics.get("estimated_monthly_cost", 0) or 0)
    subscription_ratio = (subscription_cost / net_expense * 100) if net_expense > 0 else 0.0
    impulsive_ratio = float(insights.get("impulsive_spending_ratio", {}).get("ratio", 0) or 0)
    learning_ratio = float(insights.get("learning_investment_ratio", {}).get("ratio", 0) or 0)
    consumption_health = insights.get("consumption_health", {})
    consumption_persona = insights.get("consumption_persona", {})
    risk_radar = insights.get("risk_radar", {})
    spending_anomalies = insights.get("spending_anomalies", {})
    consumption_health_score = float(consumption_health.get("score", 0) or 0)

    top_category = (monthly_stats.get("category_stats") or [{}])[0].get("name", "其他")
    if balance >= 0:
        summary_sentence = (
            f"本月真实收入 ¥{real_income:.2f}，净支出 ¥{net_expense:.2f}，结余 ¥{balance:.2f}，支出主要集中在「{top_category}」，"
            f"冲动消费占比 {impulsive_ratio:.2f}%。"
        )
    else:
        summary_sentence = (
            f"本月真实收入 ¥{real_income:.2f}，净支出 ¥{net_expense:.2f}，收支为负 ¥{abs(balance):.2f}，支出主要集中在「{top_category}」，"
            f"建议优先控制高频非刚需消费。"
        )

    expense_records = [
        item for item in get_transactions_by_month(month) if item.get("type") == "expense"
    ]
    frequency_count = len(expense_records)
    avg_amount = (gross_expense / frequency_count) if frequency_count > 0 else 0.0

    category_count_map: dict[str, int] = {}
    category_amount_map: dict[str, float] = {}
    tag_focus = ["冲动", "刚需", "投资自己", "情绪消费"]
    tag_amount_map: dict[str, float] = {key: 0.0 for key in tag_focus}
    for row in expense_records:
        category = row.get("category_main") or "其他"
        amount = float(row.get("amount") or 0)
        category_count_map[category] = category_count_map.get(category, 0) + 1
        category_amount_map[category] = round(category_amount_map.get(category, 0) + amount, 2)
        for tag in row.get("tags", []):
            if tag in tag_amount_map:
                tag_amount_map[tag] = round(tag_amount_map.get(tag, 0) + amount, 2)

    high_frequency_categories = []
    for category, count in sorted(category_count_map.items(), key=lambda item: item[1], reverse=True)[:3]:
        high_frequency_categories.append(
            {
                "name": category,
                "count": count,
                "amount": round(category_amount_map.get(category, 0), 2),
            }
        )

    this_month_tag_stats = []
    for tag in tag_focus:
        amount = round(tag_amount_map.get(tag, 0), 2)
        ratio = (amount / gross_expense * 100) if gross_expense > 0 else 0
        this_month_tag_stats.append({"name": tag, "amount": amount, "ratio": round(ratio, 2)})

    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT substr(date, 1, 7) AS month, amount, category_main, tags
            FROM transactions
            WHERE type = 'expense' AND substr(date, 1, 7) IN (?, ?, ?)
            """,
            (months[0], months[1], months[2]),
        ).fetchall()

    month_total_map: dict[str, float] = {m: 0.0 for m in months}
    month_category_amount_map: dict[str, dict[str, float]] = {m: {} for m in months}
    month_tag_amount_map: dict[str, dict[str, float]] = {m: {} for m in months}
    for row in rows:
        m = row["month"]
        amount = float(row["amount"] or 0)
        category = row["category_main"] or "其他"
        month_total_map[m] = round(month_total_map.get(m, 0) + amount, 2)
        month_category_amount_map[m][category] = round(
            month_category_amount_map[m].get(category, 0) + amount, 2
        )

        for tag in parse_tags(row["tags"]):
            month_tag_amount_map[m][tag] = round(month_tag_amount_map[m].get(tag, 0) + amount, 2)

    category_totals: dict[str, float] = {}
    for m in months:
        for category, amount in month_category_amount_map[m].items():
            category_totals[category] = round(category_totals.get(category, 0) + amount, 2)

    top_categories = [
        category for category, _amount in sorted(category_totals.items(), key=lambda x: x[1], reverse=True)[:6]
    ]
    category_trend_series = []
    for category in top_categories:
        points = [round(month_category_amount_map[m].get(category, 0), 2) for m in months]
        category_trend_series.append(
            {
                "name": category,
                "values": points,
                "total": round(sum(points), 2),
            }
        )

    tag_trend_series = []
    for tag in tag_focus:
        points = [round(month_tag_amount_map[m].get(tag, 0), 2) for m in months]
        tag_trend_series.append({"name": tag, "values": points, "total": round(sum(points), 2)})

    total_expense_trend = [{"month": m, "amount": round(month_total_map.get(m, 0), 2)} for m in months]
    subscription_cost_trend = []
    for m in months:
        metrics = get_subscription_monthly_metrics(m)
        subscription_cost_trend.append(
            {
                "month": m,
                "amount": round(float(metrics.get("estimated_monthly_cost", 0) or 0), 2),
            }
        )

    risk_items = []
    abnormal_days = insights.get("abnormal_high_expense_days", [])
    if abnormal_days:
        peak_day = sorted(abnormal_days, key=lambda x: float(x.get("amount", 0)), reverse=True)[0]
        risk_items.append(
            {
                "key": "abnormal_high_expense_days",
                "level": "high",
                "title": "异常高支出日",
                "message": f"{peak_day.get('date')} 单日支出 ¥{float(peak_day.get('amount', 0)):.2f}，波动偏高。",
            }
        )

    anomaly_insights = spending_anomalies.get("insights", [])
    if anomaly_insights:
        risk_items.append(
            {
                "key": "spending_anomalies",
                "level": "high" if spending_anomalies.get("risk_score", 0) >= 70 else "medium",
                "title": "寮傚父娑堣垂 / 鍐插姩娑堣垂",
                "message": anomaly_insights[0],
            }
        )

    if impulsive_ratio >= 30:
        risk_items.append(
            {
                "key": "impulsive_spending_ratio",
                "level": "high",
                "title": "冲动消费比例过高",
                "message": f"冲动消费占总支出 {impulsive_ratio:.2f}%，建议设置上限并延迟购买。",
            }
        )

    long_term_categories = insights.get("long_term_high_ratio_categories", [])
    if long_term_categories:
        first_item = long_term_categories[0]
        risk_items.append(
            {
                "key": "long_term_high_ratio_categories",
                "level": "medium",
                "title": "长期高占比类别",
                "message": f"「{first_item.get('category', '其他')}」近 3 个月持续高占比，建议复盘必要性。",
            }
        )

    if learning_ratio < 10:
        risk_items.append(
            {
                "key": "learning_investment_ratio",
                "level": "medium",
                "title": "学习投资不足",
                "message": f"学习投资占比仅 {learning_ratio:.2f}%，可考虑稳定投入提升长期回报。",
            }
        )

    if subscription_ratio >= 20:
        risk_items.append(
            {
                "key": "subscription_ratio",
                "level": "medium",
                "title": "订阅占比过高",
                "message": f"订阅折算成本占总支出 {subscription_ratio:.2f}%，建议清理低使用率订阅。",
            }
        )

    for hint in budget_health.get("risk_hints", [])[:2]:
        risk_items.append(
            {
                "key": "budget_category_risk",
                "level": "medium",
                "title": "预算风险类别",
                "message": hint,
            }
        )

    return {
        "month": month,
        "kpi": {
            "gross_expense": round(gross_expense, 2),
            "gross_income": round(gross_income, 2),
            "total_expense": round(gross_expense, 2),
            "total_income": round(real_income, 2),
            "cashflow_income": round(gross_income, 2),
            "real_income": round(real_income, 2),
            "reimbursement_amount": round(reimbursement_amount, 2),
            "net_expense": round(net_expense, 2),
            "balance": round(balance, 2),
            "subscription_estimated_cost": round(subscription_cost, 2),
            "subscription_ratio": round(subscription_ratio, 2),
            "consumption_health_score": round(consumption_health_score, 2),
            "consumption_health_level": consumption_health.get("level", "一般"),
            "summary_sentence": summary_sentence,
        },
        "consumption_health": consumption_health,
        "consumption_persona": consumption_persona,
        "risk_radar": risk_radar,
        "structure": {
            "category_stats": monthly_stats.get("category_stats", []),
            "tag_stats": this_month_tag_stats,
        },
        "rhythm": {
            "daily_expense": monthly_stats.get("daily_expense", []),
            "frequency": {
                "count": frequency_count,
                "avg_amount": round(avg_amount, 2),
                "high_frequency_categories": high_frequency_categories,
            },
        },
        "trends": {
            "months": months,
            "category_trend": {
                "months": months,
                "series": category_trend_series,
            },
            "tag_trend": {
                "months": months,
                "series": tag_trend_series,
            },
            "total_expense_trend": total_expense_trend,
            "subscription_cost_trend": subscription_cost_trend,
            "budget_execution_trend": budget_health.get("trends", {}).get("execution", []),
            "budget_category_deviation": budget_health.get("trends", {}).get("category_deviation", []),
        },
        "risks": {
            "abnormal_high_expense_days": abnormal_days,
            "impulsive_spending_ratio": insights.get("impulsive_spending_ratio", {}),
            "long_term_high_ratio_categories": long_term_categories,
            "learning_investment_ratio": insights.get("learning_investment_ratio", {}),
            "subscription_ratio": round(subscription_ratio, 2),
            "spending_anomalies": spending_anomalies,
            "risk_radar": risk_radar,
            "items": risk_items,
        },
        "budget": budget_health,
        "raw": {
            "monthly_stats": monthly_stats,
            "financial_summary": financial_summary,
            "insights": insights,
            "subscription_metrics": subscription_metrics,
        },
    }


def create_ai_archive(month: str, content: str) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO ai_archives (month, content)
            VALUES (?, ?)
            """,
            (month, content),
        )
        conn.commit()
        last_row_id = cursor.lastrowid
        if last_row_id is None:
            raise RuntimeError("failed to create ai archive")
        return int(last_row_id)


def get_ai_archives(month: str, limit: int = 10) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, month, content, created_at
            FROM ai_archives
            WHERE month = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (month, limit),
        ).fetchall()

    return [dict(row) for row in rows]


def get_ai_monthly_package(month: str) -> dict:
    insights = get_monthly_insights(month)
    return {
        "month": month,
        "monthly_stats": get_monthly_stats(month),
        "insights": insights,
        "consumption_health": insights.get("consumption_health", {}),
        "consumption_persona": insights.get("consumption_persona", {}),
        "risk_radar": insights.get("risk_radar", {}),
        "budgets": get_budget_execution(month),
        "subscriptions": get_subscription_monthly_recap(month),
    }
