# ClaraMed Client Integration API

How an external system (JeevaCare is the first) sends medical files to ClaraMed for AI analysis and gets
the results back. ClaraMed never calls out to arbitrary places: it downloads files only from hosts you
register, and it posts results only to the webhook you register.

```
Your system                                   ClaraMed
   |  POST /api/v1/analyze  (file URL)  --->     downloads the file, queues the job   -> 202 {jobId}
   |                                             OCR / X-ray AI runs in a background worker
   |  <--- signed POST to your webhook ------    results (or a failure notice)
   |  GET /api/v1/status/{jobId}  (optional poll, always available)
```

## 1. Base URL

`https://<claramed-host>/api/v1`. Set JeevaCare's `CLARAMED_API_URL` to this value (including `/api/v1`).

## 2. Registration (done once by the ClaraMed operator)

```bash
python scripts/register_client.py --name jeevacare \
    --webhook-url https://<jeevacare-backend>/api/webhook/claramed-callback \
    --allowed-host res.cloudinary.com \
    --callback-token "<token your callback route expects, optional>"
```

It prints an **API key** and a **webhook secret**, once. Store them as `CLARAMED_API_KEY` and
`CLARAMED_WEBHOOK_SECRET`. Notes:

- `--webhook-url` must be `https`.
- `--allowed-host` is repeatable. It is the only place ClaraMed will download files from. Use an exact
  hostname, or `*.example.com` for subdomains. No schemes, paths or ports.
- `--callback-token` is optional. If set, every callback also carries `Authorization: Bearer <token>`,
  for receivers that put an auth middleware in front of the route.

## 3. Authentication

Every call sends `Authorization: Bearer <API key>`. Scopes: `analysis:create` (submit), `analysis:read`
(status). A missing or wrong key returns 401; a missing scope returns 403.

All original `/api/v1/analyses…` routes now require the same header. Analyses created before this change
have no owner and are no longer readable through the API.

## 4. `POST /api/v1/analyze`

```json
{
  "radiologyId": "rad-123",
  "imageUrl": "https://res.cloudinary.com/.../xray.png?signature=...",
  "patientId": "JV-PATIENT-12345",
  "hospitalRef": "JV-HOSPITAL-01",
  "metadata": {"modality": "chest_xray"}
}
```

| Field | Rule |
|-------|------|
| `radiologyId` **or** `documentId` | Exactly one. Your own record id; ClaraMed keeps it per client. |
| `fileUrl` **or** `imageUrl` | Exactly one (aliases). HTTPS URL on an allowed host. |
| `type` | Optional. Inferred: `radiology` with `radiologyId`, `document` with `documentId`. |
| `patientRef` or `patientId` | Optional opaque reference. Never send a name or date of birth, and never put them in a URL. |
| `hospitalRef`, `metadata` | Optional. |

File rules: HTTPS only, host in `allowed-host`, resolves to a public address, at most 10 MB (the
`MAX_UPLOAD_SIZE_MB` setting), 30 seconds total download time. `radiologyId` accepts PNG or JPEG;
`documentId` accepts PDF.

Response `202`:

```json
{"jobId": "5b1c…", "status": "queued"}
```

Sending the same `radiologyId`/`documentId` again returns the existing job (no reprocessing). If the earlier
job **failed**, a new one replaces it.

## 5. `GET /api/v1/status/{jobId}`

```json
{
  "jobId": "5b1c…",
  "status": "completed",
  "radiologyId": "rad-123",
  "deliveryStatus": "delivered",
  "results": {
    "findings": [{"label": "Edema", "score": 0.83}],
    "summary": "Highest model scores: Edema (0.83), …",
    "confidence": 0.83,
    "disclaimer": "…"
  }
}
```

`status`: `queued`, `processing`, `completed`, `failed`. `results` is `null` until completed. Document results
carry `explanation` (plain-language text) and `findings` (structured values) instead. `deliveryStatus`:
`pending`, `delivered`, `failed` (callback retries exhausted; results are still here) or `skipped` (no
webhook configured). Another client's job id returns 404.

## 6. The callback (ClaraMed to you)

ClaraMed `POST`s JSON to your registered webhook when the job finishes, **including failures**:

```json
{"jobId": "5b1c…", "status": "completed", "radiologyId": "rad-123",
 "results": {"findings": [], "summary": "…", "confidence": 0.83, "disclaimer": "…"}, "error": null}
```

```json
{"jobId": "5b1c…", "status": "failed", "radiologyId": "rad-123", "results": null,
 "error": {"code": "analysis_failed"}}
```

Your receiver **must branch on `status`**: on failure `results: null`, so code that reads `results.findings`
unconditionally will throw. Respond `2xx` to acknowledge; anything else counts as a failed attempt.

Headers:

| Header | Value |
|--------|-------|
| `X-ClaraMed-Timestamp` | Unix seconds |
| `X-ClaraMed-Signature` | `sha256=` + hex HMAC-SHA256 of `"<timestamp>.<raw body>"` using your webhook secret |
| `Authorization` | `Bearer <token>`, only if a callback token was registered |

**Verify the signature over the raw body**, byte for byte, before parsing. With Express, capture the raw
bytes (`express.json({ verify: (req, _res, buf) => { req.rawBody = buf; } })`) because re-serialising parsed
JSON will not match. Reject timestamps older than 5 minutes.

```javascript
import crypto from "node:crypto";

export function verifyClaraMed(req, secret) {
  const ts = req.header("X-ClaraMed-Timestamp");
  const sig = req.header("X-ClaraMed-Signature") || "";
  if (!ts || Math.abs(Date.now() / 1000 - Number(ts)) > 300) return false;
  const expected = "sha256=" + crypto.createHmac("sha256", secret)
    .update(`${ts}.`).update(req.rawBody).digest("hex");
  const a = Buffer.from(expected), b = Buffer.from(sig);
  return a.length === b.length && crypto.timingSafeEqual(a, b);
}
```

Retries: up to 5 attempts at 0, 2, 6, 14 and 30 minutes (2, 4, 8, 16 minute gaps). Redirects are not followed.
After that `deliveryStatus` is `failed` and the result stays available from `/status`.

## 7. Errors

| HTTP | `error.code` | Meaning |
|------|--------------|---------|
| 401 | | Missing, wrong or inactive API key |
| 403 | | Key lacks the scope |
| 404 | | Unknown job, or it belongs to another client |
| 422 | `invalid_scheme` | URL is not `https` |
| 422 | `invalid_url` | Credentials in the URL, or a non-default port |
| 422 | `host_not_allowed` | Host is not in your `allowed-host` list |
| 422 | `blocked_address` | Host resolves to a private or non-public address |
| 422 | `redirect_limit` | More than 3 redirects |
| 422 | `too_large` | File exceeds the size limit |
| 422 | `bad_content` | Not a PNG/JPEG (radiology) or PDF (document) |
| 422 | `fetch_failed` | Download failed, timed out, or the host returned an error |
| 422 | (validation) | Body does not match section 4 |
| 503 | `queue_unavailable` | Job queue is down; nothing was kept, retry shortly |
| 503 | `integration_disabled` | Operator switched the integration off |

Failed analyses report the generic code `analysis_failed` in the callback and `status: "failed"` from `/status`.
Details stay in ClaraMed's logs.

## 8. Data handling

- The downloaded file is deleted as soon as the analysis ends (success or failure).
- Results are kept for `RESULT_RETENTION_DAYS` (default 30), then purged. Your system holds the permanent record.
- Patient references are opaque ids and are never written to logs. Audit events store ids and counts only.
- Document analysis sends the extracted text to a hosted LLM (Groq) to produce the explanation.
  Review that before sending real patient documents (tracked in `TODOS.md`).

## 9. Operating it

Three processes plus Redis and PostgreSQL:

```bash
uvicorn backend.main:app                                              # API
celery -A backend.workers.celery_app worker --pool=solo -l info       # analysis + callbacks
celery -A backend.workers.celery_app beat -l info                     # purge + stale-job sweeper
```

- The API and the worker must share the same files: a shared volume, or `STORAGE_PROVIDER=s3`. ClaraMed logs a
  warning at startup when `APP_ENV=production` and `STORAGE_PROVIDER=local`.
- `CLARAMED_INTEGRATION_ENABLED=false` makes `/analyze` return 503 without touching other routes.
- Jobs left queued or processing for longer than `STALE_JOB_SECONDS` (default 1800) because a worker died are
  marked failed, and the failure callback is sent.
- Retry tuning: `CALLBACK_MAX_ATTEMPTS`, `CALLBACK_BACKOFF_BASE_SECONDS`, `CALLBACK_TIMEOUT_SECONDS`.
- If the host network uses a corporate CA, point Python at it with `SSL_CERT_FILE`.

## 10. What the receiving system still has to build

1. A client that calls `/analyze` (and optionally `/status`) with the API key.
2. A callback route that verifies the signature over the raw body (and the bearer token, if registered),
   branches on `status`, and returns 2xx quickly.
3. Storage of `jobId` on its own record, so callbacks can be matched.
4. A signed file URL (for example a 1 hour Cloudinary URL) on a host that was registered with `--allowed-host`.

**Before production:** confirm with the receiving system's owner that their callback route accepts this scheme
(signature header plus optional bearer token). The ClaraMed tests only prove that ClaraMed agrees with itself.
