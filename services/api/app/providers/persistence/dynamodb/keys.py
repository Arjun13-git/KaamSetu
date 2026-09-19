"""Single-table key design. Every item is tenant scoped: the partition key starts with the
business, so a query can never return another business's data.

Base table
    PK = BUSINESS#{business_id}
    SK = PROFILE | CUSTOMER#{id} | ASSET#{id} | TECHNICIAN#{id} | SERVICEREQUEST#{id}
         | JOB#{id} | EVENT#{id} | AUDIT#{id} | IDEMPOTENCY#{key}

Global secondary indexes (sparse, ``ALL`` projection). Index keys are prefixed with the tenant too.
    GSI1  lookups          customer by phone, asset by serial
    GSI2  by customer      assets, jobs and service events of one customer; audit trail of an entity
    GSI3  by asset         jobs and service events of one asset

Sort keys embed a fixed-width UTC timestamp so an index query returns items in time order.
GSI reads are eventually consistent; base-table reads are strongly consistent.
"""

from datetime import UTC, datetime

from app.domain.asset import Asset
from app.domain.audit import AuditEvent
from app.domain.customer import Customer
from app.domain.job import Job
from app.domain.normalization import normalize_serial
from app.domain.service_event import ServiceEvent

GSI1 = "GSI1"
GSI2 = "GSI2"
GSI3 = "GSI3"

PROFILE_SK = "PROFILE"

CUSTOMER = "CUSTOMER"
ASSET = "ASSET"
TECHNICIAN = "TECHNICIAN"
SERVICE_REQUEST = "SERVICEREQUEST"
JOB = "JOB"
EVENT = "EVENT"
AUDIT = "AUDIT"
IDEMPOTENCY = "IDEMPOTENCY"

Keys = dict[str, str]


def tenant(business_id: str) -> str:
    return f"BUSINESS#{business_id}"


def sk(kind: str, entity_id: str) -> str:
    return f"{kind}#{entity_id}"


def sort_timestamp(moment: datetime) -> str:
    """Fixed-width UTC timestamp: lexicographic order equals chronological order."""
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def base_keys(business_id: str, kind: str, entity_id: str) -> Keys:
    return {"PK": tenant(business_id), "SK": sk(kind, entity_id)}


def business_keys(business_id: str) -> Keys:
    return {"PK": tenant(business_id), "SK": PROFILE_SK}


def idempotency_keys(business_id: str, key: str) -> Keys:
    return base_keys(business_id, IDEMPOTENCY, key)


def customer_keys(customer: Customer) -> Keys:
    keys = base_keys(customer.business_id, CUSTOMER, customer.customer_id)
    if customer.phone:
        keys["GSI1PK"] = phone_partition(customer.business_id, customer.phone)
        keys["GSI1SK"] = sk(CUSTOMER, customer.customer_id)
    return keys


def asset_keys(asset: Asset) -> Keys:
    keys = base_keys(asset.business_id, ASSET, asset.asset_id)
    keys["GSI2PK"] = customer_partition(asset.business_id, asset.customer_id)
    keys["GSI2SK"] = sk(ASSET, asset.asset_id)
    serial = normalize_serial(asset.serial_number) if asset.serial_number else ""
    if serial:
        keys["GSI1PK"] = serial_partition(asset.business_id, serial)
        keys["GSI1SK"] = sk(ASSET, asset.asset_id)
    return keys


def job_keys(job: Job) -> Keys:
    keys = base_keys(job.business_id, JOB, job.job_id)
    time_sk = f"{JOB}#{sort_timestamp(job.created_at)}#{job.job_id}"
    keys["GSI2PK"] = customer_partition(job.business_id, job.customer_id)
    keys["GSI2SK"] = time_sk
    keys["GSI3PK"] = asset_partition(job.business_id, job.asset_id)
    keys["GSI3SK"] = time_sk
    return keys


def event_keys(event: ServiceEvent) -> Keys:
    keys = base_keys(event.business_id, EVENT, event.event_id)
    time_sk = f"{EVENT}#{sort_timestamp(event.timestamp)}#{event.event_id}"
    keys["GSI2PK"] = customer_partition(event.business_id, event.customer_id)
    keys["GSI2SK"] = time_sk
    keys["GSI3PK"] = asset_partition(event.business_id, event.asset_id)
    keys["GSI3SK"] = time_sk
    return keys


def audit_keys(audit: AuditEvent) -> Keys:
    keys = base_keys(audit.business_id, AUDIT, audit.audit_id)
    keys["GSI2PK"] = audit_partition(audit.business_id, audit.entity_type.value, audit.entity_id)
    keys["GSI2SK"] = f"{sort_timestamp(audit.timestamp)}#{audit.audit_id}"
    return keys


def phone_partition(business_id: str, phone: str) -> str:
    return f"{tenant(business_id)}#PHONE#{phone}"


def serial_partition(business_id: str, normalized_serial: str) -> str:
    return f"{tenant(business_id)}#SERIAL#{normalized_serial}"


def customer_partition(business_id: str, customer_id: str) -> str:
    return f"{tenant(business_id)}#CUSTOMER#{customer_id}"


def asset_partition(business_id: str, asset_id: str) -> str:
    return f"{tenant(business_id)}#ASSET#{asset_id}"


def audit_partition(business_id: str, entity_type: str, entity_id: str) -> str:
    return f"{tenant(business_id)}#AUDIT#{entity_type}#{entity_id}"
