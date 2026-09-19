"""Load, or verify, the deterministic demo dataset in a DynamoDB table.

    python -m seed [--create-table] [--as-of ISO_DATETIME]   load (idempotent), then verify
    python -m seed --verify                                  read-only checks of what is stored
    python -m seed --manifest                                print the dataset's ids and scenarios

Uses the same environment configuration as the API (``DATA_PROVIDER=dynamodb`` is required for
loading and verifying). Loading is idempotent and resumable: running it again changes nothing.
``--create-table`` only works against a local endpoint (``DYNAMODB_ENDPOINT_URL``); in AWS the
table is created by the infrastructure template, never by this script.
"""

import argparse
import json
import sys
from datetime import datetime

from botocore.exceptions import ClientError

from app.core.config import Settings
from app.providers.persistence.dynamodb.client import build_resource
from app.providers.persistence.dynamodb.repositories import build_dynamodb_repositories
from app.providers.persistence.dynamodb.table import create_table
from seed.dataset import DEFAULT_AS_OF, build_demo_plan
from seed.sample_data import load_demo_data
from seed.verify import check_demo_data, counts, digest, snapshot


def _print_checks(checks: list[tuple[str, bool, str]]) -> bool:
    for name, ok, detail in checks:
        print(
            f"{'PASS' if ok else 'FAIL'}  {name}{'  (' + detail + ')' if detail and not ok else ''}"
        )
    return all(ok for _, ok, _ in checks)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load or verify the KaamSetu demo data")
    parser.add_argument(
        "--create-table", action="store_true", help="create the table first (local only)"
    )
    parser.add_argument("--verify", action="store_true", help="only verify; write nothing")
    parser.add_argument(
        "--manifest", action="store_true", help="print ids and scenarios, then exit"
    )
    parser.add_argument(
        "--as-of",
        default=DEFAULT_AS_OF.isoformat(),
        help="the instant the dataset's relative times are anchored to (default: %(default)s)",
    )
    args = parser.parse_args(argv)
    as_of = datetime.fromisoformat(args.as_of)
    if as_of.tzinfo is None:
        parser.error("--as-of must include a UTC offset, e.g. 2026-09-19T10:00:00+00:00")

    if args.manifest:  # needs no environment: the ids do not depend on it
        defaults = Settings.model_fields
        plan = build_demo_plan(
            defaults["dev_business_id"].default, defaults["dev_actor_id"].default, as_of
        )
        print(json.dumps(plan.manifest, indent=2, ensure_ascii=False))
        return 0

    settings = Settings()
    plan = build_demo_plan(settings.dev_business_id, settings.dev_actor_id, as_of)

    if settings.data_provider != "dynamodb":
        print("Set DATA_PROVIDER=dynamodb: the in-memory provider does not outlive a process.")
        return 2

    resource = build_resource(
        region=settings.aws_region,
        profile=settings.aws_profile,
        endpoint_url=settings.dynamodb_endpoint_url,
    )
    if args.create_table and not args.verify:
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
    if not args.verify:
        result = load_demo_data(
            repos, business_id=settings.dev_business_id, actor_id=settings.dev_actor_id, as_of=as_of
        )
        print(
            f"Wrote {result.total_created} records; {result.total_existing} were already present."
        )
        for kind in sorted({*result.created, *result.existing}):
            written, present = result.created.get(kind, 0), result.existing.get(kind, 0)
            print(f"  {kind:<24} written {written:>3}   present {present:>3}")

    print("\nVerifying what is stored:")
    ok = _print_checks(check_demo_data(repos, settings.dev_business_id, plan.manifest))
    data = snapshot(repos, settings.dev_business_id)
    print(f"\nRecords: {counts(data)}")
    print(f"Digest:  {digest(data)}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
