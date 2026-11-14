"""Peak memory of the Streamlit app's heaviest path: Streamlit + legacy libraries + model + one analysis.

Run:  python scripts/measure_streamlit_memory.py
Compare the last line with Streamlit Community Cloud's current memory limit (about 1 GB at the time of writing).
"""
import io
import resource
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BUDGET_MB = 800


def peak_mb() -> float:
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak / (1024 * 1024) if sys.platform == "darwin" else peak / 1024      # macOS bytes, Linux KB


def main() -> int:
    # what app.py loads at startup
    import langchain_groq  # noqa: F401
    import markdown  # noqa: F401
    import pandas  # noqa: F401
    import PyPDF2  # noqa: F401
    import streamlit  # noqa: F401
    print(f"after Streamlit + legacy libraries: {peak_mb():6.0f} MB")

    from PIL import Image
    from backend.services.radiology_service import RadiologyService
    from streamlit_app.radiology_flow import analyze_upload

    service = RadiologyService()
    service.load_model()
    print(f"after loading the X-ray model:      {peak_mb():6.0f} MB")

    buffer = io.BytesIO()
    Image.effect_noise((1024, 1024), 40).convert("L").save(buffer, "PNG")
    outcome = analyze_upload(buffer.getvalue(), lambda: service)
    print(f"after one analysis ({len(outcome.findings)} findings): {peak_mb():6.0f} MB")

    peak = peak_mb()
    verdict = "WITHIN" if peak <= BUDGET_MB else "OVER"
    print(f"\n{verdict} the {BUDGET_MB} MB budget (peak {peak:.0f} MB, single process, "
          "excludes the Streamlit server's own overhead)")
    return 0 if verdict == "WITHIN" else 1


if __name__ == "__main__":
    raise SystemExit(main())
