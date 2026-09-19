from typing import Any

import boto3
from botocore.config import Config

# Bounded retries and timeouts so a struggling table cannot hang a request or a Lambda.
_CONFIG = Config(retries={"max_attempts": 3, "mode": "standard"}, connect_timeout=3, read_timeout=5)


def build_resource(*, region: str | None, profile: str | None, endpoint_url: str | None) -> Any:
    """A DynamoDB resource. Credentials come from the standard AWS chain (environment, profile,
    or the Lambda role); nothing is configured here. ``endpoint_url`` points at LocalStack or
    DynamoDB Local and is left ``None`` for real AWS."""
    session = boto3.Session(profile_name=profile, region_name=region)
    return session.resource("dynamodb", endpoint_url=endpoint_url, config=_CONFIG)
