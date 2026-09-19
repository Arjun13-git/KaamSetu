"""AWS Lambda entry point for API Gateway (HTTP API, payload format 2.0).

The same FastAPI application that runs locally is wrapped by Mangum; only the entry point differs.
Configuration comes from the function's environment variables, and the application is built once
per cold start.
"""

import logging

from mangum import Mangum

from app.core.config import Settings
from app.main import create_app

_settings = Settings()
logging.getLogger().setLevel(_settings.log_level.upper())

handler = Mangum(create_app(_settings), lifespan="off")
