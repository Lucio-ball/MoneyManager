import json
from datetime import date

from flask import Flask, jsonify, redirect, render_template, request, url_for

from database import (
    create_ai_archive,
    create_transaction,
    get_category_trend,
    get_ai_archives,
    get_ai_monthly_package,
    get_budget_execution,
    get_monthly_dashboard_data,
    get_monthly_insights,
    get_monthly_stats,
    get_recent_average_month_expense,
    get_recent_transactions,
    get_tag_trend,
    get_today_expense,
    get_transactions_by_month,
    init_db,
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


def build_ai_prompt_template(month: str) -> str:
    return f"""你是一名专业的个人财务教练，请基于我提供的月度财务数据，输出一份结构化复盘报告。\n\n【你的任务】\n1. 用简洁语言总结本月消费结构与现金流状态。\n2. 识别值得肯定的消费习惯（至少 2 条）。\n3. 识别需要警惕的问题（至少 2 条），并解释原因。\n4. 针对下月给出可执行建议（3-5 条，需具体可落地）。\n5. 对“冲动消费比例”和“学习投资比例”给出诊断结论。\n\n【数据口径说明】\n- monthly_stats: 月度收支、类别统计、标签统计、每日支出\n- insights: 行为模式识别结果（异常高支出日、长期高占比类别、冲动/学习投资比例）\n- budgets: 预算执行与状态（正常/接近/超支）\n\n【输出格式（严格按此结构）】\n# {month} 财务复盘\n## 1) 本月概览\n## 2) 消费结构分析\n## 3) 行为模式解读\n## 4) 预算执行评价\n## 5) 下月行动清单\n\n请使用中文输出，避免空泛建议，尽量引用数据中的金额、占比、趋势。"""


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

    @app.route("/")
    def index():
        month = request.args.get("month") or date.today().strftime("%Y-%m")
        dashboard = get_monthly_dashboard_data(month=month)
        monthly_stats = get_monthly_stats(month)
        budget_data = get_budget_execution(month)

        current_month = date.today().strftime("%Y-%m")
        today_expense = get_today_expense() if month == current_month else 0.0
        top_categories = monthly_stats.get("category_stats", [])[:3]
        emotion_light = build_emotion_light(month, monthly_stats.get("total_expense", 0), budget_data)

        return render_template(
            "index.html",
            month=dashboard["month"],
            summary=dashboard["summary"],
            daily_expense=dashboard["daily_expense"],
            category_share=dashboard["category_share"],
            today_expense=today_expense,
            top_categories=top_categories,
            emotion_light=emotion_light,
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
        return render_template(
            "add.html",
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

        return render_template(
            "analysis.html",
            month=month,
            category_name=category_name,
            tag_name=tag_name,
            category_options=CATEGORY_OPTIONS,
            tag_options=TAG_OPTIONS,
            monthly_stats=monthly_stats,
            category_trend=category_trend,
            tag_trend=tag_trend,
            insights=insights,
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

        return render_template(
            "ai.html",
            month=month,
            success=success,
            ai_package=ai_package,
            ai_prompt_template=ai_prompt_template,
            archives=archives,
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

    @app.route("/api/ai/monthly", methods=["GET"])
    def ai_monthly_api():
        month = request.args.get("month") or date.today().strftime("%Y-%m")
        package = get_ai_monthly_package(month)
        response = dict(package)
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
