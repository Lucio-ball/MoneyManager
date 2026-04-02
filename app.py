from datetime import date

from flask import Flask, request

from config import CATEGORY_OPTIONS, TAG_OPTIONS
from extensions.database import init_db
from models.reimbursement import list_open_reimbursable_expenses
from routes.ai_routes import bp as ai_bp
from routes.analysis_routes import bp as analysis_bp
from routes.budget_routes import bp as budget_bp
from routes.goal_routes import bp as goal_bp
from routes.subscription_routes import bp as subscription_bp
from routes.transaction_routes import bp as transaction_bp
from services.subscription_service import process_due_subscription_charges


def create_app() -> Flask:
    app = Flask(__name__)
    last_subscription_sync_day: str | None = None

    init_db()

    @app.context_processor
    def inject_fab_context():
        return {
            "fab_category_options": CATEGORY_OPTIONS,
            "fab_tag_options": TAG_OPTIONS,
            "fab_today": date.today().isoformat(),
            "fab_open_reimbursement_expenses": list_open_reimbursable_expenses(limit=50),
        }

    @app.before_request
    def sync_due_subscription_charges():
        nonlocal last_subscription_sync_day

        # Static file requests do not need subscription sync.
        if request.endpoint == "static":
            return

        today = date.today().isoformat()
        if last_subscription_sync_day == today:
            return

        try:
            process_due_subscription_charges()
            last_subscription_sync_day = today
        except Exception:
            app.logger.exception("subscription auto-sync failed")
            # Do not fail user requests when auto-sync encounters transient issues.
            return

    app.register_blueprint(transaction_bp)
    app.register_blueprint(budget_bp)
    app.register_blueprint(goal_bp)
    app.register_blueprint(subscription_bp)
    app.register_blueprint(analysis_bp)
    app.register_blueprint(ai_bp)

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
