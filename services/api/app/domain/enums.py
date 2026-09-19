from enum import StrEnum


class ServiceType(StrEnum):
    REPAIR = "repair"
    INSTALLATION = "installation"
    MAINTENANCE = "maintenance"
    INSPECTION = "inspection"
    REPLACEMENT = "replacement"
    UNKNOWN = "unknown"


class AssetType(StrEnum):
    AIR_CONDITIONER = "air_conditioner"
    REFRIGERATOR = "refrigerator"
    WASHING_MACHINE = "washing_machine"
    MICROWAVE = "microwave"
    TELEVISION = "television"
    WATER_PURIFIER = "water_purifier"
    COMPUTER = "computer"
    PRINTER = "printer"
    ELECTRICAL = "electrical"
    PLUMBING = "plumbing"
    OTHER = "other"
    UNKNOWN = "unknown"


class Urgency(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    SAFETY_CRITICAL = "safety_critical"


class JobStatus(StrEnum):
    NEW = "NEW"
    ASSIGNED = "ASSIGNED"
    SCHEDULED = "SCHEDULED"
    ON_THE_WAY = "ON_THE_WAY"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class JobSource(StrEnum):
    INTAKE = "intake"
    MANUAL = "manual"


class ServiceRequestStatus(StrEnum):
    RECEIVED = "RECEIVED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    EXTRACTION_FAILED = "EXTRACTION_FAILED"
    JOB_CREATED = "JOB_CREATED"
    DISMISSED = "DISMISSED"


class ResolutionState(StrEnum):
    """Outcome of matching a request to an existing customer/asset."""

    UNRESOLVED = "unresolved"
    NEW = "new"
    EXISTING = "existing"
    AMBIGUOUS = "ambiguous"


class AttachmentOwnerType(StrEnum):
    SERVICE_REQUEST = "service_request"
    SERVICE_EVENT = "service_event"


class AuditEntityType(StrEnum):
    CUSTOMER = "customer"
    ASSET = "asset"
    TECHNICIAN = "technician"
    SERVICE_REQUEST = "service_request"
    JOB = "job"
    SERVICE_EVENT = "service_event"
    ATTACHMENT = "attachment"


class AuditAction(StrEnum):
    CUSTOMER_CREATED = "CUSTOMER_CREATED"
    ASSET_CREATED = "ASSET_CREATED"
    TECHNICIAN_CREATED = "TECHNICIAN_CREATED"
    SERVICE_REQUEST_CREATED = "SERVICE_REQUEST_CREATED"
    JOB_CREATED = "JOB_CREATED"
    JOB_AMENDED = "JOB_AMENDED"
    JOB_ASSIGNED = "JOB_ASSIGNED"
    JOB_STATUS_CHANGED = "JOB_STATUS_CHANGED"
    JOB_COMPLETED = "JOB_COMPLETED"
    ATTACHMENT_UPLOADED = "ATTACHMENT_UPLOADED"
