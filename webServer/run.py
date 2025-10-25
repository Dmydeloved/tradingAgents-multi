from flask import Flask

from webServer.api.fundamental_api import fundamental_bp
from webServer.api.market_api import market_bp
from webServer.api.scheduler_api import scheduler_bp
from webServer.api.social_api import social_bp
from webServer.services.scheduler.scheduler import init_scheduler
from webServer.utils.logger import setup_logger


def create_app():
    app = Flask(__name__)

    setup_logger(app)
    app.register_blueprint(market_bp, url_prefix="/api/market")
    app.register_blueprint(fundamental_bp, url_prefix="/api/fundamentals")
    app.register_blueprint(social_bp, url_prefix="/api/social")
    app.register_blueprint(scheduler_bp, url_prefix="/api/scheduler")
    return app

app = create_app()
init_scheduler(app)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5003)
    data = {
        "APIKEY": "sk-MQHPgxtvAKdBQxiE90A4C6A68fAc4eBe9d4b899f107fB9Fb",
        "PROXY_URL": "http://127.0.0.1:7890",
        "LOG": true,
        "API_TIMEOUT_MS": 600000,
        "NON_INTERACTIVE_MODE": false,
        "Providers": [
            {
                "name": "openrouter",
                "api_base_url": "https://openrouter.ai/api/v1/chat/completions",
                "api_key": "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",
                "models": [
                    "anthropic/claude-sonnet-4"
                ],
                "transformer": {
                    "use": ["openrouter"]
                }
            }
        ],
        "Router": {
            "default": "openrouter,anthropic/claude-sonnet-4"
        }
    }