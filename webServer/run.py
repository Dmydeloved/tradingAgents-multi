from flask import Flask

from webServer.api.circular_conversation_api import chat_bp
from webServer.api.fundamental_api import fundamental_bp
from webServer.api.market_api import market_bp
from webServer.api.social_api import social_bp
from webServer.api.stock_news_api import message_bp
from webServer.api.user_api import user_bp
from webServer.api.working_api import work_bp
from webServer.services.scheduler.scheduler import init_scheduler
from webServer.utils.logger import setup_logger


def create_app():
    app = Flask(__name__)

    setup_logger(app)
    app.register_blueprint(market_bp, url_prefix="/api/market")
    app.register_blueprint(work_bp, url_prefix="/api/work")
    app.register_blueprint(fundamental_bp, url_prefix="/api/fundamentals")
    app.register_blueprint(social_bp, url_prefix="/api/social")
    # app.register_blueprint(scheduler_bp, url_prefix="/api/scheduler")
    app.register_blueprint(user_bp, url_prefix="/api/user")
    app.register_blueprint(message_bp, url_prefix="/api/message")
    app.register_blueprint(chat_bp, url_prefix="/api/chat")
    return app

app = create_app()


if __name__ == "__main__":
    init_scheduler(app)
    app.run(host="0.0.0.0", port=5003)