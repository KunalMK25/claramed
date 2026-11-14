# ClaraMed "Radiology AI" on Streamlit, linked from JeevaCare by a menu link — design

Date: 2026-11-14 · Branch: `feat/jeevacare-integration`
Supersedes `2026-11-14-streamlit-only-design.md` (signed launch token + automatic write-back), which the user
replaced with a simpler model, and replaces the hosting model of `2026-11-14-jeevacare-linking-design.md`
for this deployment (that API stack stays in the repo, unused here).

## Problem
The user wants ClaraMed and JeevaCare to be two separate sites, linked the way a map link opens Google Maps: a
"Radiology AI" item in JeevaCare's sidebar takes the user to the ClaraMed website. ClaraMed does not store or
receive anything from JeevaCare. ClaraMed must run on Streamlit Community Cloud only (no VM, no domain).
The live Streamlit app is also broken: `app.py` on `main` imports `chains.py` and `database.py`, deleted in `e89f70b`.

## Goals
- The existing Streamlit app works again (symptom checker, report explainer, body map, history).
- A new "Radiology AI" page analyses an uploaded chest X-ray with the existing TorchXRayVision service.
- JeevaCare's sidebar gets a "Radiology AI" link to that page.

## Non-goals
- Any data exchange between the sites: no signed links, no callback, no shared accounts, no stored results.
- The FastAPI/Celery/PostgreSQL stack on this deployment (kept in the repo, unused).
- Production-grade guarantees for real patient data: the free tier has no SLA and the app is public.
- Document/report analysis as a JeevaCare-linked feature (the restored report explainer stays a standalone feature).

## Chosen approach
A plain external link. ClaraMed's page works on its own: the user uploads the image there. Rejected: embedding
ClaraMed in an iframe inside JeevaCare (Streamlit embedding, cookie and CSP complications, and the user asked for a
redirect); passing a patient/record context (would need signing and trust, which the user does not want).

## Components
- **Legacy app (restored)** in `streamlit_app/`: `app.py`, `chains.py`, `database.py` from `e89f70b~1`.
- **`radiology_flow`** (pure, no Streamlit): validate an upload, run the service on a temp file, return ranked findings.
- **Radiology AI page** (`streamlit_app/pages/1_Radiology_AI.py`): uploader, Analyze, results, disclaimer, optional back link.
- **Streamlit deployment files:** lean `streamlit_app/requirements.txt` (CPU PyTorch), `.streamlit/config.toml` upload
  cap, secrets template; the backend's `requirements.txt` is untouched.
- **JeevaCare patch** (delivered as a patch file, not applied to their repo): a sidebar link driven by the existing
  `VITE_CLARAMED_BASE_URL`, hidden when unset.

## Data flow
User clicks "Radiology AI" in JeevaCare -> new tab opens `<claramed-url>/Radiology_AI` -> user uploads a PNG/JPEG ->
page validates it -> model runs in the Streamlit process -> ranked findings and a disclaimer are shown. The upload
and any temp file are discarded; nothing is sent anywhere.

## Requirements
- R1: The legacy `chains.py`, `database.py`, `app.py` are restored from `e89f70b~1` into `streamlit_app/`, and the home page starts without an exception.
- R2: The page at `/Radiology_AI` accepts one PNG or JPEG of at most 10 MB and shows all findings ranked by score, the top findings highlighted, and the disclaimer.
- R3: An upload is validated by magic bytes (not filename), size, and image dimensions; users see generic messages, and file names and pixel data are never logged.
- R4: The upload exists only in memory and in one temp file that is deleted on every path; nothing is persisted.
- R5: The model is loaded once per server process, not per click.
- R6: If the `JEEVACARE_URL` secret is set and is an https URL, the page shows a "Back to JeevaCare" link; otherwise none.
- R7: The page states that it is independent of JeevaCare, that nothing is saved or sent anywhere, and that the output is not a diagnosis.
- R8: `streamlit_app/requirements.txt` is lean and uses the CPU PyTorch index; a test proves every third-party import reachable from the app is listed and that no backend-only package (celery, sqlalchemy, psycopg2, redis, alembic, boto3) is.
- R9: `.streamlit/config.toml` caps uploads at 10 MB; a secrets template documents `GROQ_API_KEY` and `JEEVACARE_URL` with placeholders only.
- R10: Peak memory of a full analysis is measured and reported against the free-tier budget before deployment.
- R11: JeevaCare's sidebar shows a "Radiology AI" item that opens `<VITE_CLARAMED_BASE_URL>/Radiology_AI` in a new tab with `rel="noopener noreferrer"` for the configured roles; it is hidden when the variable is unset or not https (localhost allowed for development). It ships as `integration/jeevacare/radiology-ai-link.patch`, with tests, verified to apply to upstream `main` and to build.

## Error handling
Generic user messages ("This does not look like a valid image", "The analysis failed, please try again"). Details only in the
Streamlit log, free of patient data and file names. A failed analysis never shows partial results.

## Testing
TDD per requirement. Pure-function tests for `radiology_flow` with a fake service; Streamlit `AppTest` for page render, back-link and
legacy start; a static guard for requirements; vitest for the JeevaCare link (`renderToStaticMarkup` + `MemoryRouter`).

## Assumptions
- Streamlit Community Cloud installs the requirements file beside the entrypoint (`streamlit_app/requirements.txt`) and honours `--extra-index-url` (verify at deploy).
- The app must be set to public, so JeevaCare users need no Streamlit login (the current URL looks private).
- Free-tier memory is about 1 GB (check Streamlit's current limit); R10 decides whether this fits.
- The SQLite history in the restored app is lost on restart; acceptable for a demo.
- The patch's default roles are `PATIENT`, `DOCTOR` and `RADIOLOGY_TECHNICIAN`.

## Open questions
- Which JeevaCare roles should see the link (default above)?
- Should the restored demo features sit behind an access code to protect the Groq quota?
