// Hand-written mirror of the KaamSetu API (services/api/app/api/schemas.py). The OpenAPI document
// types `ServiceRequest.extraction` as a bare object, so its shape is copied from
// services/api/app/ai/schemas.py and checked at runtime by `lib/extraction.ts`.

export type JobStatus =
  | "NEW"
  | "ASSIGNED"
  | "SCHEDULED"
  | "ON_THE_WAY"
  | "IN_PROGRESS"
  | "COMPLETED"
  | "CANCELLED";

export type Urgency = "low" | "normal" | "high" | "safety_critical";

export type ServiceType =
  | "repair"
  | "installation"
  | "maintenance"
  | "inspection"
  | "replacement"
  | "unknown";

export type AssetType =
  | "air_conditioner"
  | "refrigerator"
  | "washing_machine"
  | "microwave"
  | "television"
  | "water_purifier"
  | "computer"
  | "printer"
  | "electrical"
  | "plumbing"
  | "other"
  | "unknown";

export type ResolutionState = "unresolved" | "new" | "existing" | "ambiguous";

export type ServiceRequestStatus =
  | "RECEIVED"
  | "NEEDS_REVIEW"
  | "EXTRACTION_FAILED"
  | "JOB_CREATED"
  | "DISMISSED";

export type IntakeOutcome = "job_created" | "needs_review" | "manual_entry_required";

export interface TimeSlot {
  start: string;
  end?: string | null;
}

export interface Customer {
  customer_id: string;
  name: string;
  phone: string | null;
  email: string | null;
  address: string | null;
  preferred_language: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface Asset {
  asset_id: string;
  customer_id: string;
  asset_type: AssetType;
  brand: string | null;
  model: string | null;
  serial_number: string | null;
  purchase_date: string | null;
  warranty_until: string | null;
  location: string | null;
  metadata: Record<string, string>;
  created_at: string;
  updated_at: string;
}

export interface Technician {
  technician_id: string;
  name: string;
  phone: string | null;
  skills: string[];
  active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Job {
  job_id: string;
  customer_id: string;
  asset_id: string;
  service_type: ServiceType;
  description: string;
  urgency: Urgency;
  preferred_slot: TimeSlot | null;
  scheduled_slot: TimeSlot | null;
  technician_id: string | null;
  status: JobStatus;
  source: "intake" | "manual";
  service_request_id: string | null;
  version: number;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}

export interface ServiceEvent {
  event_id: string;
  asset_id: string;
  customer_id: string;
  job_id: string;
  technician_id: string;
  summary: string;
  work_performed: string;
  technician_notes: string | null;
  parts_used: string[];
  observed_symptoms: string[];
  follow_up_required: boolean;
  attachments: string[];
  timestamp: string;
}

export interface MatchCandidate {
  entity_id: string;
  match_score: number;
  reasons: string[];
}

export interface EntityResolution {
  state: ResolutionState;
  entity_id: string | null;
  candidates: MatchCandidate[];
}

export interface ServiceRequest {
  service_request_id: string;
  status: ServiceRequestStatus;
  raw_text: string;
  /** Untyped by the API; read it with `parseExtraction`. */
  extraction: unknown;
  customer_resolution: EntityResolution;
  asset_resolution: EntityResolution;
  failure_reason: string | null;
  job_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface JobCard {
  job: Job;
  customer: Customer;
  asset: Asset;
  technician: Technician | null;
  prior_service: ServiceEvent[];
}

export interface AssetHistory {
  asset: Asset;
  jobs: Job[];
  service_events: ServiceEvent[];
}

export interface CustomerHistory {
  customer: Customer;
  assets: Asset[];
  jobs: Job[];
  service_events: ServiceEvent[];
}

export interface IntakeResult {
  outcome: IntakeOutcome;
  service_request: ServiceRequest;
  job: Job | null;
  prior_service: ServiceEvent[];
  safety_concern: boolean;
}

export interface JobCompletionResult {
  job: Job;
  service_event: ServiceEvent;
}

export interface Health {
  status: string;
  version: string;
}

// -- request bodies -------------------------------------------------------------------------------

export interface IntakeBody {
  text: string;
  phone?: string | null;
  customer_id?: string | null;
}

export interface CompletionBody {
  work_performed: string;
  technician_notes?: string | null;
  parts_used?: string[];
  observed_symptoms?: string[];
  follow_up_required?: boolean;
}

export interface TransitionBody {
  to_status: JobStatus;
  scheduled_slot?: TimeSlot | null;
}

export interface NewCustomerBody {
  name: string;
  phone?: string | null;
  address?: string | null;
}

export interface NewAssetBody {
  asset_type: AssetType;
  brand?: string | null;
  model?: string | null;
  location?: string | null;
}

/** A person's decision to turn a request into a job. Omitted fields fall back to the API's proposal. */
export interface ConfirmJobBody {
  customer_id: string;
  asset_id: string;
  service_type?: ServiceType | null;
  description?: string | null;
  urgency?: Urgency | null;
  preferred_slot?: TimeSlot | null;
}
