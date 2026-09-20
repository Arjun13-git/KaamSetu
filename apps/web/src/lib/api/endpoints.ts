import "server-only";

import { apiGet, apiWrite } from "./client";
import type {
  Asset,
  AssetHistory,
  CompletionBody,
  ConfirmJobBody,
  Customer,
  CustomerHistory,
  Health,
  IntakeBody,
  IntakeResult,
  Job,
  JobCard,
  JobCompletionResult,
  JobStatus,
  NewAssetBody,
  NewCustomerBody,
  ServiceRequest,
  ServiceRequestStatus,
  Technician,
  TransitionBody,
  Urgency,
} from "./types";

// Lookups change rarely; job and request lists change often, so they are only de-duplicated.
const LOOKUP_TTL = 10_000;
const LIST_TTL = 2_000;

export const api = {
  health: () => apiGet<Health>("/health", { ttlMs: LOOKUP_TTL, timeoutMs: 8_000 }),

  jobs: (params: { status?: JobStatus; technicianId?: string; limit?: number } = {}) =>
    apiGet<Job[]>("/jobs", {
      query: { status: params.status, technician_id: params.technicianId, limit: params.limit ?? 200 },
      ttlMs: LIST_TTL,
    }),
  jobCard: (jobId: string) => apiGet<JobCard>(`/jobs/${jobId}`),

  customers: (params: { q?: string; phone?: string; limit?: number } = {}) =>
    apiGet<Customer[]>("/customers", {
      query: { q: params.q, phone: params.phone, limit: params.limit ?? 100 },
      ttlMs: LOOKUP_TTL,
    }),
  customer: (customerId: string) => apiGet<Customer>(`/customers/${customerId}`, { ttlMs: LOOKUP_TTL }),
  customerAssets: (customerId: string) =>
    apiGet<Asset[]>(`/customers/${customerId}/assets`, { ttlMs: LOOKUP_TTL }),
  customerHistory: (customerId: string) =>
    apiGet<CustomerHistory>(`/customers/${customerId}/history`, { query: { limit: 200 } }),
  assetHistory: (assetId: string) =>
    apiGet<AssetHistory>(`/assets/${assetId}/history`, { query: { limit: 200 } }),

  technicians: () => apiGet<Technician[]>("/technicians", { ttlMs: LOOKUP_TTL }),

  serviceRequests: (params: { status?: ServiceRequestStatus; limit?: number } = {}) =>
    apiGet<ServiceRequest[]>("/service-requests", {
      query: { status: params.status, limit: params.limit ?? 50 },
      ttlMs: LIST_TTL,
    }),
  serviceRequest: (id: string) => apiGet<ServiceRequest>(`/service-requests/${id}`),

  // -- writes: the API is the authority on every rule; the app only relays and reports ----------

  intake: (body: IntakeBody, idempotencyKey: string) =>
    apiWrite<IntakeResult>("POST", "/intake", {
      body,
      headers: { "Idempotency-Key": idempotencyKey },
      timeoutMs: 27_000,
    }),
  assignJob: (jobId: string, technicianId: string) =>
    apiWrite<Job>("POST", `/jobs/${jobId}/assign`, { body: { technician_id: technicianId } }),
  transitionJob: (jobId: string, body: TransitionBody) =>
    apiWrite<Job>("POST", `/jobs/${jobId}/transition`, { body }),
  completeJob: (jobId: string, body: CompletionBody) =>
    apiWrite<JobCompletionResult>("POST", `/jobs/${jobId}/complete`, { body }),
  confirmRequest: (requestId: string, body: ConfirmJobBody) =>
    apiWrite<Job>("POST", `/service-requests/${requestId}/job`, { body }),
  createCustomer: (body: NewCustomerBody) => apiWrite<Customer>("POST", "/customers", { body }),
  createAsset: (customerId: string, body: NewAssetBody) =>
    apiWrite<Asset>("POST", `/customers/${customerId}/assets`, { body }),
  amendJob: (jobId: string, body: { urgency?: Urgency; description?: string }) =>
    apiWrite<Job>("PATCH", `/jobs/${jobId}`, { body }),
};
