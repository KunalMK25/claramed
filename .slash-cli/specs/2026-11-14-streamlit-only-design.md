# ClaraMed on Streamlit Community Cloud only, linked to JeevaCare — design

> **SUPERSEDED on 2026-11-14** by `2026-11-14-streamlit-radiology-link-design.md`. The user chose a plain menu link
> from JeevaCare instead of signed launch links with automatic write-back. Kept for history only.

Date: 2026-11-14 · Branch: `feat/jeevacare-integration` · Replaces the hosting model of
`2026-11-14-jeevacare-linking-design.md` for this deployment (that stack stays in the repo, unused here).

## Problem
The user wants to deploy ClaraMed with no VM and no separate domain: on Streamlit Community Cloud only.
Streamlit cannot host the FastAPI/Celery/PostgreSQL stack or accept background API calls from JeevaCare's server.
Separately, the live app is broken: `app.py` on `main` imports `chains.py` and `database.py`, deleted in commit `e89f70b`.

## Goals
- The existing Streamlit app works again (symptom checker, report explainer, body map, history).
- A JeevaCare staff member opens a signed launch link, analyses one record, sees the result, and the result is
  written back to JeevaCare automatically.
- Reuse the tested pure pieces: URL fetcher, signing, radiology/OCR/document services.

## Non-goals
- The FastAPI/Celery/PostgreSQL stack on this deployment; a durable job queue; a database; an audit trail.
- JeevaCare-side code (launch button, callback route): delivered later from a contract doc.
- Production-grade guarantees for real patient data: Streamlit's free tier has no SLA and the app is public.

## Chosen approach
Approach A: a Streamlit page verifies a signed, expiring launch token, downloads the file, analyses it in the
Streamlit process, shows the result, and posts a signed callback to JeevaCare. Rejected: returning the result
through the user's browser (`postMessage`), because the result could be forged by the user.

## Components
- **Legacy app (restored):** `chains.py`, `database.py` and `app.py` from `e89f70b~1` (app.py unchanged since).
- **`launch_token`:** create/verify the signed token. Pure, no I/O.
- **`analysis_runner`:** given a verified launch, fetch the file (existing `url_fetcher`), run the matching service,
  return the same results shape as the API (`findings`, `summary`, `confidence`, `disclaimer`; documents add
  `explanation`). No Streamlit imports.
- **`writeback`:** build and send the signed callback (existing `signing`), bounded retries. Pure of Streamlit.
- **JeevaCare page:** Streamlit UI that wires the three together; holds results in `st.session_state`.
- **Deployment files:** `packages.txt`, a lean `requirements.txt` for the Streamlit app, secrets template, contract doc.

## Data flow
JeevaCare signs `{v, jti, kind, rid, url, [pr], [hr], iat, exp}` -> opens `<app>/JeevaCare?t=<token>` -> page verifies
signature, version, expiry and lifetime -> user clicks Analyze -> fetch -> analyse -> render -> signed POST to
JeevaCare's callback (`jobId = jti`) -> success banner, or a Resend button. Failures at any step write back
`failed` with a generic code where a callback target is known.

## Requirements
- R1: The legacy `chains.py`, `database.py`, `app.py` are restored from `e89f70b~1`, and the app starts without ImportError.
- R2: A launch token is `base64url(JSON payload) + "." + base64url(HMAC-SHA256(secret, payload part))`, in the `t` query parameter.
- R3: A token is rejected, with no fetch and no analysis, when the signature is wrong, the version is not 1, it has
  expired (60 s clock skew allowed), or `exp - iat` exceeds 900 s. The page shows a generic reason.
- R4: File download uses the existing fetcher: https only, host in the `FILE_HOSTS` secret, public IPs only, at most
  `MAX_UPLOAD_SIZE_MB`, 30 s overall; PNG/JPEG for `radiology`, PDF for `document`.
- R5: Radiology runs `RadiologyService`; documents run text extraction, OCR when needed, and the LLM explanation.
- R6: The result and its disclaimer are rendered; file bytes and temp files are discarded after the analysis.
- R7: The write-back POSTs the callback body from `docs/CLARAMED_API.md` section 6 to `JEEVACARE_CALLBACK_URL` (https
  only, redirects not followed) with `X-ClaraMed-Timestamp`/`X-ClaraMed-Signature` and an optional bearer token;
  3 attempts with short in-page backoff; on failure the page offers Resend.
- R8: A failed fetch or analysis writes back `status: "failed"` with `error.code: "analysis_failed"`.
- R9: The patient reference and file URL are never logged or shown; the page shows only the record id.
- R10: Re-clicking Analyze in the same session does not re-run the analysis or re-send once it succeeded.
- R11: The Streamlit app has its own dependency list (CPU PyTorch, no FastAPI/Celery) and `packages.txt` for
  Tesseract and Poppler; the backend's `requirements.txt` is unchanged.
- R12: All secrets come from `st.secrets`; a template documents them; nothing secret is committed.
- R13: A contract doc gives JeevaCare's owner the token format, a Node.js signing snippet and the callback expectations.
- R14: Headless tests (Streamlit `AppTest`) cover the legacy app start, a valid launch, and every R3 rejection; unit
  tests cover token, runner and write-back; one script measures the app's peak memory.

## Error handling
Generic user-facing messages; details only in the Streamlit log, free of patient data. A write-back failure never
hides a successful result.

## Testing
TDD per requirement. Fake JeevaCare receiver (already built) for write-back; fake file server via `httpx.MockTransport`
for the fetcher; `AppTest` for the pages; a local run of the whole page with a real model to measure memory.

## Assumptions
- Streamlit Community Cloud honours `packages.txt` and a requirements file beside the entrypoint (verify at deploy).
- `st.secrets` top-level strings are available to the `backend.core.config` settings as environment variables
  (verify; otherwise the app copies them in).
- Free-tier memory (about 1 GB, check Streamlit's current limit) is enough; R14's measurement decides this.
- The app is public so JeevaCare staff need no Streamlit login; the restored demo features are therefore also public
  and could spend the Groq quota.
- The SQLite history in the restored app is lost on restart (ephemeral disk); acceptable for a demo.

## Open questions
- Link lifetime defaults to 15 minutes; confirm with JeevaCare's owner.
- Whether to put the restored demo features behind an access code to protect the Groq quota.
