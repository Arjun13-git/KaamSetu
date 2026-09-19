"""Load the synthetic demo dataset into a DynamoDB table.

    python -m seed [--create-table]

Uses the same environment configuration as the API (``DATA_PROVIDER=dynamodb`` is required).
``--create-table`` only works against a local endpoint (``DYNAMODB_ENDPOINT_URL``); in AWS the
table is created by the infrastructure template, never by this script.
"""

import argparse
import sys

from botocore.exceptions import ClientError

from app.core.clock import system_clock
from app.core.config import Settings
from app.providers.persistence.dynamodb.client import build_resource
from app.providers.persistence.dynamodb.repositories import build_dynamodb_repositories
from app.providers.persistence.dynamodb.table import create_table
from seed.sample_data import load_demo_data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load KaamSetu demo data")
    parser.add_argument(
        "--create-table", action="store_true", help="create the table first (local endpoints only)"
    )
    args = parser.parse_args(argv)
    settings = Settings()

    if settings.data_provider != "dynamodb":
        print("Set DATA_PROVIDER=dynamodb: the in-memory provider does not outlive a process.")
        return 2

    resource = build_resource(
        region=settings.aws_region,
        profile=settings.aws_profile,
        endpoint_url=settings.dynamodb_endpoint_url,
    )
    if args.create_table:
        if not settings.dynamodb_endpoint_url:
            print("Refusing to create a table in AWS. Deploy the infrastructure template instead.")
            return 2
        try:
            create_table(resource, settings.dynamodb_table)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") != "ResourceInUseException":
                raise
            print(f"Table {settings.dynamodb_table} already exists.")

    repos = build_dynamodb_repositories(resource, settings.dynamodb_table)
    result = load_demo_data(
        repos,
        business_id=settings.dev_business_id,
        actor_id=settings.dev_actor_id,
        now=system_clock(),
    )
    print("Demo data loaded." if result.created else "Demo data already present; nothing changed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
