# TODOS

## Encrypt integration secrets at rest
- **What:** Encrypt `IntegrationClient.webhook_secret` and `callback_auth_token` in the database.
- **Why:** This handles patient data. A database leak today would expose every client's signing secret and callback token (plan deviations D5, D10).
- **Pros:** Limits the blast radius of a leak.
- **Cons:** Needs key management and a rotation story. HMAC needs the raw secret, so it must be reversible encryption (e.g. Fernet keyed from a dedicated secret, not `SECRET_KEY` reuse).
- **Context:** Added during the JeevaCare linking plan review (2026-11-14). Columns live in `backend/models/integration_client.py`; registration in `backend/services/client_registry.py`; read in `backend/workers/callbacks.py`.
- **Depends on:** A decision on where the encryption key lives.

## Review where patient text goes (Groq) before launch
- **What:** Decide the data-processing position for the document path, which sends extracted report text to Groq's hosted LLM (`DocumentService.explain_report`, `extract_structured_findings`).
- **Why:** Once hospital data flows through the JeevaCare link, a third-party processor handles health information. Consent, data-processing terms and hospital policy may apply.
- **Pros:** Avoids a compliance surprise at launch.
- **Cons:** A policy decision, not code. May lead to a config switch or a self-hosted model.
- **Context:** Exists in ClaraMed today; the integration raises the stakes. Launch gate for real patient documents.
- **Depends on:** The user and JeevaCare's owner.
