# ClaraMed ↔ JeevaCare linking backend — design

Date: 2026-11-14 · Branch: `feat/jeevacare-integration` · Scope: ClaraMed side only.

## Problem
JeevaCare (Node/MongoDB hospital app, `siri05gowda-byte/Jeevacare`) plans to delegate X-ray and
document AI to ClaraMed (`docs/CLARAMED_INTEGRATION.md`, status "Pending Implementation").
ClaraMed cannot be linked today: it exposes `/api/v1/analyses…` with multipart uploads, has no
client registration, no webhook sender, and no URL intake.

## Goals
- Serve JeevaCare's documented contract: `POST /analyze`, `GET /status/{jobId}`, HMAC-signed callback.
- Support radiology (X-ray) and document (OCR + explanation) analyses.
- Per-client configuration, so JeevaCare is the first client and the code never hardcodes its name.
- Prove it end to end with a JeevaCare stub receiver.

## Non-goals
- Any change to the JeevaCare repo (we ship a contract doc and a stub only).
- Frontend, Docker/monitoring/load hardening, symptom analysis on this link, JWT user-context auth.
- Medical-device or compliance certification.

## Chosen approach
Compatibility endpoints over the existing analysis core, driven by per-client settings stored on
`IntegrationClient` ("approach C"). Rejected: global `JEEVACARE_*` env config (single client only);
replacing `/analyses` (breaks existing consumers for no gain).

## Verified facts about current code
- `get_current_client` returns `None` when no credentials are sent; every route in
  `backend/api/routes/analyses.py` uses it, so analyses can currently be created anonymously.
- `get_current_client` checks the key against every active client's hash in a loop.
- `IntegrationClient` has: hashed key, scopes, allowed_hospitals, rate-limit strings, active, timestamps.
  It has no webhook URL, signing secret, or file-host allowlist.
- `backend/workers/tasks.py` has `process_document_async` and `process_radiology_async`; no callback logic.
- `/clients/register` and `/jeevacare/webhook`, mentioned in older docs, do not exist.

## Requirements
- R1: `POST /analyze` requires a valid API key and the `analysis:create` scope; anonymous calls get 401.
- R2: Request body: `{radiologyId|documentId, type: "radiology"|"document", fileUrl, patientRef, hospitalRef, metadata}`;
  returns `202 {jobId, status:"queued"}`. `jobId` is the analysis ID. Patient name/DOB are never accepted in URLs.
- R3: Repeating a request with the same client + `radiologyId`/`documentId` returns the existing job (idempotent).
- R4: `GET /status/{jobId}` returns status and, once complete, results; only the owning client may read it (404 otherwise).
- R5: Intake downloads `fileUrl` only if: scheme is HTTPS, host is in the client's allowlist, resolved IP is
  public (no private/loopback/link-local, re-checked after redirects; redirects limited to allowlisted hosts),
  size ≤ `MAX_UPLOAD_SIZE_MB`, and content type matches `type`. Violations → 422 with no fetch performed.
- R6: Clients carry `webhook_url` (HTTPS), `webhook_secret`, `allowed_file_hosts`. Registered by an admin
  command/endpoint guarded by an admin credential; the API key and secret are shown once.
- R7: On completion or failure, ClaraMed POSTs `{jobId, radiologyId|documentId, status, results}` to the client's
  `webhook_url` with header `X-ClaraMed-Signature: sha256=<HMAC(secret, timestamp + "." + body)>` and
  `X-ClaraMed-Timestamp`. Receivers can reject stale timestamps.
- R8: Callback delivery retries up to 5 attempts with exponential backoff over ~30 minutes (configurable), then
  records `delivery_status="failed"`. Polling (R4) remains the fallback.
- R9: After analysis finishes (success or failure), the stored source file is deleted. Results are kept for
  `RESULT_RETENTION_DAYS` (default 30), then purged by a scheduled task.
- R10: Existing `/api/v1/analyses…` routes require authentication too. (Behavior change; called out in the contract doc.)
- R11: A kill switch (`CLARAMED_INTEGRATION_ENABLED`) makes `/analyze` return 503 without affecting other routes.
- R12: Audit events record intake, completion, delivery attempts and deletion; logs contain no patient references' values beyond opaque IDs.
- R13: `docs/CLARAMED_API.md` documents the contract, signature verification (with a Node example), and error codes.
- R14: A stub receiver and end-to-end tests cover: radiology happy path, document happy path, bad signature
  detection, retry-then-success, retry-exhaustion, blocked host, private-IP URL, oversize file, cross-client
  access, anonymous access, file deletion after completion.

## Components
- **Client registry:** extends `IntegrationClient` (migration) + admin registration. Depends on DB only.
- **Intake (`url_fetcher`):** validates and downloads a URL under R5; returns bytes + content type. No DB access, unit-testable alone.
- **Analyze/status API:** thin routes that authenticate, validate, create the analysis, enqueue the existing Celery task.
- **Callback dispatcher:** Celery task that signs and POSTs results and applies retry policy; independent of analysis logic.
- **Retention task:** periodic purge of files and expired results.
- **Stub receiver:** test-only FastAPI app that verifies signatures and can be told to fail.

## Data flow
`POST /analyze` → auth/scope → idempotency check → URL fetch/validate → store file → create analysis →
enqueue task → 202. Worker runs OCR/radiology → saves results → deletes file → enqueues callback →
dispatcher signs and POSTs → records delivery status. JeevaCare may poll `GET /status/{jobId}` anytime.

## Error handling
Validation and intake failures return 4xx before any work is queued. Worker failures mark the analysis
`failed`, still send a signed `failed` callback, and delete the file. Dispatcher failures retry per R8.

## Testing
TDD per requirement. Unit tests for the fetcher and signing, API tests with the FastAPI test client,
integration tests against the stub receiver with a real Celery eager/worker run, and one manual run with
real TorchXRayVision inference.

## Assumptions
- Cloudinary-style signed URLs are reachable from ClaraMed's network; the exact JeevaCare host list is supplied at registration.
- JeevaCare's callback route will accept the signature scheme in R7 (its doc only says "HMAC signature").
- Retry defaults and 30-day retention are acceptable until JeevaCare says otherwise.

## Open question
Who holds the admin credential for client registration in deployment (R6)? Default: a CLI script run by the operator.
