import json
from datetime import date, datetime

from flask import Flask, abort, jsonify, redirect, render_template, request, url_for

from database import (
    create_ai_archive,
    create_subscription,
    create_transaction,
    delete_subscription,
    get_category_trend,
    get_ai_archives,
    get_ai_monthly_package,
    get_budget_execution,
    get_monthly_dashboard_data,
    get_monthly_insights,
    get_monthly_stats,
    get_recent_average_month_expense,
    get_recent_transactions,
    get_subscription_by_id,
    get_subscription_monthly_cost_summary,
    get_subscription_monthly_metrics,
    get_tag_trend,
    get_today_expense,
    get_transactions_by_month,
    get_upcoming_subscriptions,
    init_db,
    list_subscriptions,
    process_due_subscription_charges,
    update_subscription,
    upsert_budget,
)

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
    "社交压力",
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


def build_ai_prompt_template(month: str) -> str:
    return f"""你是一名专业的个人财务教练，请基于我提供的月度财务数据，输出一份结构化复盘报告。\n\n【你的任务】\n1. 用简洁语言总结本月消费结构与现金流状态。\n2. 识别值得肯定的消费习惯（至少 2 条）。\n3. 识别需要警惕的问题（至少 2 条），并解释原因。\n4. 针对下月给出可执行建议（3-5 条，需具体可落地）。\n5. 对“冲动消费比例”和“学习投资比例”给出诊断结论。\n6. 结合订阅模块，分别从“结构成本”和“真实现金流”点评订阅压力。\n\n【数据口径说明】\n- monthly_stats: 月度收支、类别统计、标签统计、每日支出（仅真实入账）\n- insights: 行为模式识别结果（异常高支出日、长期高占比类别、冲动/学习投资比例）\n- budgets: 预算执行与状态（正常/接近/超支）\n- subscriptions: 订阅口径（本月折算成本、本月实际扣费金额、本月新增/取消、下月即将扣费项目）\n\n【输出格式（严格按此结构）】\n# {month} 财务复盘\n## 1) 本月概览\n## 2) 消费结构分析\n## 3) 行为模式解读\n## 4) 预算执行评价\n## 5) 订阅健康度\n## 6) 下月行动清单\n\n请使用中文输出，避免空泛建议，尽量引用数据中的金额、占比、趋势。"""


def _build_subscription_payload(data: dict) -> dict | None:
    required = ["name", "amount", "cycle", "next_billing_date"]
    for key in required:
        if data.get(key) in (None, ""):
            return None

    cycle = data.get("cycle")
    if cycle not in SUBSCRIPTION_CYCLE_OPTIONS:
        return None

    amount_value = data.get("amount")
    try:
        amount = float(amount_value) if amount_value is not None else 0.0
    except (TypeError, ValueError):
        return None
    if amount <= 0:
        return None

    next_billing_date = str(data.get("next_billing_date"))
    try:
        datetime.strptime(next_billing_date, "%Y-%m-%d")
    except ValueError:
        return None

    name = str(data.get("name", "")).strip()
    if not name:
        return None

    return {
        "name": name,
        "amount": amount,
        "cycle": cycle,
        "next_billing_date": next_billing_date,
        "category": str(data.get("category", "")).strip(),
        "payment_method": str(data.get("payment_method", "")).strip(),
        "note": str(data.get("note", "")).strip(),
    }


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


def create_app() -> Flask:
    app = Flask(__name__)

    init_db()

    @app.before_request
    def sync_due_subscription_charges():
        process_due_subscription_charges()

    @app.route("/")
    def index():
        category_palette = ["#2563EB", "#0EA5E9", "#14B8A6", "#22C55E", "#F59E0B", "#EF4444"]
        month = request.args.get("month") or date.today().strftime("%Y-%m")
        dashboard = get_monthly_dashboard_data(month=month)
        monthly_stats = get_monthly_stats(month)
        budget_data = get_budget_execution(month)

        current_month = date.today().strftime("%Y-%m")
        today_expense = get_today_expense() if month == current_month else 0.0
        top_categories = [
            {
                **item,
                "color": category_palette[index % len(category_palette)],
            }
            for index, item in enumerate(monthly_stats.get("category_stats", [])[:3])
        ]
        emotion_light = build_emotion_light(month, monthly_stats.get("total_expense", 0), budget_data)
        subscription_summary = get_subscription_monthly_cost_summary()
        subscription_metrics = get_subscription_monthly_metrics(month)
        subscription_upcoming = get_upcoming_subscriptions(days=7)[:3]

        return render_template(
            "index.html",
            active_page="index",
            month=dashboard["month"],
            summary=dashboard["summary"],
            daily_expense=dashboard["daily_expense"],
            category_share=dashboard["category_share"],
            today_expense=today_expense,
            top_categories=top_categories,
            emotion_light=emotion_light,
            subscription_summary=subscription_summary,
            subscription_metrics=subscription_metrics,
            subscription_upcoming=subscription_upcoming,
        )

    @app.route("/add", methods=["GET", "POST"])
    def add_transaction_page():
        if request.method == "POST":
            form_data = {
                "amount": request.form.get("amount", type=float),
                "type": request.form.get("type", "expense"),
                "date": request.form.get("date") or date.today().isoformat(),
                "category_main": request.form.get("category_main", ""),
                "category_sub": request.form.get("category_sub", "").strip(),
                "tags": request.form.getlist("tags"),
                "payment_method": request.form.get("payment_method", ""),
                "note": request.form.get("note", "").strip(),
            }

            if form_data["amount"] and form_data["category_main"]:
                create_transaction(form_data)
                return redirect(url_for("add_transaction_page", success="1"))

            return redirect(url_for("add_transaction_page", success="0"))

        success = request.args.get("success")
        recent_records = get_recent_transactions(limit=10)
        month = date.today().strftime("%Y-%m")
        return render_template(
            "add.html",
            active_page="add",
            month=month,
            today=date.today().isoformat(),
            success=success,
            category_options=CATEGORY_OPTIONS,
            tag_options=TAG_OPTIONS,
            recent_records=recent_records,
        )

    @app.route("/analysis")
    def analysis_page():
        month = request.args.get("month") or date.today().strftime("%Y-%m")
        category_name = request.args.get("category") or CATEGORY_OPTIONS[0]
        tag_name = request.args.get("tag") or TAG_OPTIONS[0]

        monthly_stats = get_monthly_stats(month)
        category_trend = get_category_trend(category_name, month)
        tag_trend = get_tag_trend(tag_name, month)
        insights = get_monthly_insights(month)
        subscription_metrics = get_subscription_monthly_metrics(month)
        subscription_ratio = 0.0
        if monthly_stats.get("total_expense", 0) > 0:
            subscription_ratio = (
                subscription_metrics.get("estimated_monthly_cost", 0)
                / monthly_stats.get("total_expense", 0)
                * 100
            )

        return render_template(
            "analysis.html",
            active_page="analysis",
            month=month,
            category_name=category_name,
            tag_name=tag_name,
            category_options=CATEGORY_OPTIONS,
            tag_options=TAG_OPTIONS,
            monthly_stats=monthly_stats,
            category_trend=category_trend,
            tag_trend=tag_trend,
            insights=insights,
            subscription_metrics=subscription_metrics,
            subscription_ratio=round(subscription_ratio, 2),
        )

    @app.route("/budget", methods=["GET", "POST"])
    def budget_page():
        month = request.values.get("month") or date.today().strftime("%Y-%m")

        if request.method == "POST":
            budget_month = request.form.get("month") or month
            category_main = request.form.get("category_main") or None
            budget_amount = request.form.get("budget_amount", type=float)
            if budget_amount and budget_amount > 0:
                upsert_budget(budget_month, category_main, budget_amount)
                return redirect(url_for("budget_page", month=budget_month, success="1"))
            return redirect(url_for("budget_page", month=budget_month, success="0"))

        success = request.args.get("success")
        budget_data = get_budget_execution(month)
        return render_template(
            "budget.html",
            active_page="budget",
            month=month,
            success=success,
            category_options=CATEGORY_OPTIONS,
            budget_data=budget_data,
        )

    @app.route("/ai", methods=["GET", "POST"])
    def ai_page():
        month = request.values.get("month") or date.today().strftime("%Y-%m")

        if request.method == "POST":
            archive_month = request.form.get("month") or month
            content = request.form.get("content", "").strip()
            if content:
                create_ai_archive(archive_month, content)
                return redirect(url_for("ai_page", month=archive_month, success="1"))
            return redirect(url_for("ai_page", month=archive_month, success="0"))

        success = request.args.get("success")
        ai_package = get_ai_monthly_package(month)
        ai_prompt_template = build_ai_prompt_template(month)
        archives = get_ai_archives(month)
        subscription_metrics = get_subscription_monthly_metrics(month)

        return render_template(
            "ai.html",
            active_page="ai",
            month=month,
            success=success,
            ai_package=ai_package,
            ai_prompt_template=ai_prompt_template,
            archives=archives,
            subscription_metrics=subscription_metrics,
        )

    @app.route("/subscriptions")
    def subscriptions_page():
        summary = get_subscription_monthly_cost_summary()
        subscriptions = list_subscriptions()
        upcoming = get_upcoming_subscriptions(days=7)
        cycle_labels = {
            "monthly": "月付",
            "yearly": "年付",
            "weekly": "周付",
            "quarterly": "季付",
        }
        return render_template(
            "subscriptions.html",
            active_page="subscriptions",
            month=date.today().strftime("%Y-%m"),
            summary=summary,
            subscriptions=subscriptions,
            upcoming=upcoming,
            cycle_labels=cycle_labels,
            success=request.args.get("success"),
        )

    @app.route("/subscriptions/add", methods=["GET", "POST"])
    def add_subscription_page():
        if request.method == "POST":
            form_payload = _build_subscription_payload(request.form)
            if not form_payload:
                return redirect(url_for("add_subscription_page", success="0"))
            create_subscription(form_payload)
            return redirect(url_for("subscriptions_page", success="created"))

        return render_template(
            "subscriptions_add.html",
            active_page="subscriptions",
            month=date.today().strftime("%Y-%m"),
            today=date.today().isoformat(),
            cycle_options=SUBSCRIPTION_CYCLE_OPTIONS,
            success=request.args.get("success"),
        )

    @app.route("/subscriptions/edit/<int:subscription_id>", methods=["GET", "POST"])
    def edit_subscription_page(subscription_id: int):
        existing = get_subscription_by_id(subscription_id)
        if not existing:
            abort(404)

        if request.method == "POST":
            form_payload = _build_subscription_payload(request.form)
            if not form_payload:
                return redirect(url_for("edit_subscription_page", subscription_id=subscription_id, success="0"))

            updated = update_subscription(subscription_id, form_payload)
            if updated:
                return redirect(url_for("subscriptions_page", success="updated"))
            return redirect(url_for("edit_subscription_page", subscription_id=subscription_id, success="0"))

        return render_template(
            "subscriptions_edit.html",
            active_page="subscriptions",
            month=date.today().strftime("%Y-%m"),
            subscription=existing,
            cycle_options=SUBSCRIPTION_CYCLE_OPTIONS,
            success=request.args.get("success"),
        )

    @app.route("/api/transactions", methods=["POST"])
    def create_transaction_api():
        payload = request.get_json(silent=True) or {}
        required_fields = ["amount", "type", "date", "category_main"]
        if any(field not in payload or payload[field] in (None, "") for field in required_fields):
            return jsonify({"error": "missing required fields"}), 400

        transaction_data = {
            "amount": payload.get("amount"),
            "type": payload.get("type", "expense"),
            "date": payload.get("date"),
            "category_main": payload.get("category_main", ""),
            "category_sub": payload.get("category_sub", ""),
            "tags": payload.get("tags", []),
            "payment_method": payload.get("payment_method", ""),
            "note": payload.get("note", ""),
        }

        created_id = create_transaction(transaction_data)
        return jsonify({"id": created_id}), 201

    @app.route("/api/transactions", methods=["GET"])
    def list_transactions_api():
        month = request.args.get("month") or date.today().strftime("%Y-%m")
        return jsonify(get_transactions_by_month(month))

    @app.route("/api/stats/monthly", methods=["GET"])
    def monthly_stats_api():
        month = request.args.get("month") or date.today().strftime("%Y-%m")
        return jsonify(get_monthly_stats(month))

    @app.route("/api/stats/category", methods=["GET"])
    def category_trend_api():
        category_name = request.args.get("name")
        month = request.args.get("month") or date.today().strftime("%Y-%m")
        if not category_name:
            return jsonify({"error": "name is required"}), 400
        return jsonify(get_category_trend(category_name, month))

    @app.route("/api/stats/tags", methods=["GET"])
    def tag_trend_api():
        tag_name = request.args.get("name")
        month = request.args.get("month") or date.today().strftime("%Y-%m")
        if not tag_name:
            return jsonify({"error": "name is required"}), 400
        return jsonify(get_tag_trend(tag_name, month))

    @app.route("/api/insights/monthly", methods=["GET"])
    def monthly_insights_api():
        month = request.args.get("month") or date.today().strftime("%Y-%m")
        return jsonify(get_monthly_insights(month))

    @app.route("/api/budgets", methods=["POST"])
    def create_budget_api():
        payload = request.get_json(silent=True) or {}
        month = payload.get("month")
        budget_amount = payload.get("budget_amount")
        if not month or budget_amount in (None, ""):
            return jsonify({"error": "month and budget_amount are required"}), 400

        category_main = payload.get("category_main") or None
        budget_id = upsert_budget(month, category_main, float(budget_amount))
        return jsonify({"id": budget_id}), 201

    @app.route("/api/budgets", methods=["GET"])
    def list_budget_api():
        month = request.args.get("month") or date.today().strftime("%Y-%m")
        return jsonify(get_budget_execution(month))

    @app.route("/api/subscriptions", methods=["POST"])
    def create_subscription_api():
        payload = request.get_json(silent=True) or {}
        data = _build_subscription_payload(payload)
        if not data:
            return jsonify({"error": "invalid payload"}), 400

        created_id = create_subscription(data)
        return jsonify({"id": created_id}), 201

    @app.route("/api/subscriptions", methods=["GET"])
    def list_subscriptions_api():
        return jsonify(list_subscriptions())

    @app.route("/api/subscriptions/upcoming", methods=["GET"])
    def list_upcoming_subscriptions_api():
        return jsonify(get_upcoming_subscriptions(days=7))

    @app.route("/api/subscriptions/monthly_cost", methods=["GET"])
    def subscriptions_monthly_cost_api():
        month = request.args.get("month") or date.today().strftime("%Y-%m")
        summary = get_subscription_monthly_cost_summary()
        metrics = get_subscription_monthly_metrics(month)
        response = dict(summary)
        response.update(metrics)
        return jsonify(response)

    @app.route("/api/subscriptions/<int:subscription_id>", methods=["DELETE"])
    def delete_subscription_api(subscription_id: int):
        deleted = delete_subscription(subscription_id)
        if not deleted:
            return jsonify({"error": "subscription not found"}), 404
        return jsonify({"success": True})

    @app.route("/api/subscriptions/<int:subscription_id>", methods=["PUT"])
    def update_subscription_api(subscription_id: int):
        existing = get_subscription_by_id(subscription_id)
        if not existing:
            return jsonify({"error": "subscription not found"}), 404

        payload = request.get_json(silent=True) or {}
        data = _build_subscription_payload(payload)
        if not data:
            return jsonify({"error": "invalid payload"}), 400

        updated = update_subscription(subscription_id, data)
        if not updated:
            return jsonify({"error": "update failed"}), 400
        return jsonify({"success": True})

    @app.route("/api/ai/monthly", methods=["GET"])
    def ai_monthly_api():
        month = request.args.get("month") or date.today().strftime("%Y-%m")
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
        response["prompt_template"] = build_ai_prompt_template(month)
        response["prompt_with_package"] = (
            build_ai_prompt_template(month)
            + "\n\n【本月数据包（JSON）】\n"
            + json.dumps(package, ensure_ascii=False, indent=2)
        )
        return jsonify(response)

    @app.route("/api/ai/monthly/export", methods=["GET"])
    def ai_monthly_export_api():
        month = request.args.get("month") or date.today().strftime("%Y-%m")
        package = get_ai_monthly_package(month)
        payload = {
            "month": month,
            "prompt_template": build_ai_prompt_template(month),
            "data_package": package,
        }
        content = json.dumps(payload, ensure_ascii=False, indent=2)
        filename = f"ai_package_{month}.json"

        return app.response_class(
            response=content,
            mimetype="application/json",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
