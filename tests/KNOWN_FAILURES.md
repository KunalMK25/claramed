# Known failures before the JeevaCare integration work

Recorded 2026-11-14 on the GitHub `main` tree (`PYTHONPATH=. pytest tests`): 10 passed, 2 collection errors.
These are pre-existing and are NOT regressions from the integration work. Run the suite with
`--ignore` for them until they are repaired in their own change.

| Module | Reason |
|--------|--------|
| `tests/integration/test_document_workflow.py` | `ImportError: cannot import name 'UploadedDocument' from 'backend.models.analysis'` (it now lives in `backend.models.document`) |
| `tests/integration/test_radiology_workflow.py` | `ImportError: cannot import name 'RadiologyFinding' from 'backend.models.analysis'` (it now lives in `backend.models.radiology`) |
