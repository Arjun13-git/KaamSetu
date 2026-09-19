from app.core.config import Settings
from app.domain.repositories import Repositories
from app.providers.persistence.dynamodb.client import build_resource
from app.providers.persistence.dynamodb.repositories import build_dynamodb_repositories
from app.providers.persistence.memory import build_in_memory_repositories


def build_repositories(settings: Settings) -> Repositories:
    """Select the persistence provider. Only the provider changes; domain logic does not."""
    if settings.data_provider == "memory":
        return build_in_memory_repositories()
    resource = build_resource(
        region=settings.aws_region,
        profile=settings.aws_profile,
        endpoint_url=settings.dynamodb_endpoint_url,
    )
    return build_dynamodb_repositories(resource, settings.dynamodb_table)
