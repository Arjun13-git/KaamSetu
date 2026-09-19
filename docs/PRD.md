# KaamSetu Product Requirements Document

## Product goal

Give small local service businesses a lightweight operational memory without forcing them to abandon the conversational workflows they already use.

## Primary user

Owner/dispatcher of a 1–20 technician home/appliance service business.

## User stories

### Intake
- As an owner, I can paste a customer message and receive a structured service request.
- As an owner, I can attach a photo to the request.
- As an owner, I can review AI-extracted fields before creating a job.

### Memory
- As an owner, I can see a customer's service history.
- As an owner, I can see service history for a specific appliance/device.
- As an owner, I can see prior similar issues when a repeat complaint arrives.

### Operations
- As an owner, I can assign a job to a technician.
- As a technician, I can see the job, customer, asset, and relevant prior service context.
- As a technician, I can complete a job with notes/photos.
- The completed service becomes part of the asset's history.

## MVP acceptance criteria

1. A natural-language request becomes a validated job proposal.
2. A known customer/asset is resolved without creating an unnecessary duplicate.
3. A new customer/asset can be created.
4. Job status transitions are enforced server-side.
5. Technician assignment is visible.
6. Completion notes update service history.
7. A repeat request surfaces prior service context.
8. A manual fallback exists when AI fails.

## Demo-critical flow

`Customer request → AI extraction → history → job → technician → completion → memory → repeat request → prior service surfaced`
