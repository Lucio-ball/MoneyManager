from flask import Flask

from extensions.database import init_db
from routes.ai_routes import bp as ai_bp
from routes.analysis_routes import bp as analysis_bp
from routes.budget_routes import bp as budget_bp
from routes.subscription_routes import bp as subscription_bp
from routes.transaction_routes import bp as transaction_bp
from services.subscription_service import process_due_subscription_charges


def create_app() -> Flask:
    app = Flask(__name__)

    init_db()

    @app.before_request
    def sync_due_subscription_charges():
        process_due_subscription_charges()

    app.register_blueprint(transaction_bp)
    app.register_blueprint(budget_bp)
    app.register_blueprint(subscription_bp)
    app.register_blueprint(analysis_bp)
    app.register_blueprint(ai_bp)

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
