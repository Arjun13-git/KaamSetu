"""Table definition, shared by tests and local bootstrap. The SAM template must mirror it."""

from typing import Any

from app.providers.persistence.dynamodb.keys import GSI1, GSI2, GSI3

_ATTRIBUTES = ("PK", "SK", "GSI1PK", "GSI1SK", "GSI2PK", "GSI2SK", "GSI3PK", "GSI3SK")


def table_definition(table_name: str) -> dict[str, Any]:
    def index(name: str) -> dict[str, Any]:
        return {
            "IndexName": name,
            "KeySchema": [
                {"AttributeName": f"{name}PK", "KeyType": "HASH"},
                {"AttributeName": f"{name}SK", "KeyType": "RANGE"},
            ],
            "Projection": {"ProjectionType": "ALL"},
        }

    return {
        "TableName": table_name,
        "BillingMode": "PAY_PER_REQUEST",
        "KeySchema": [
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        "AttributeDefinitions": [{"AttributeName": a, "AttributeType": "S"} for a in _ATTRIBUTES],
        "GlobalSecondaryIndexes": [index(GSI1), index(GSI2), index(GSI3)],
    }


def create_table(resource: Any, table_name: str) -> None:
    table = resource.create_table(**table_definition(table_name))
    table.wait_until_exists()
