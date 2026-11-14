"""Radiology AI: upload a chest X-ray and get a ranked list of the model's findings."""
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))      # repo root, so `backend` and `streamlit_app` import

import streamlit as st  # noqa: E402

from streamlit_app.radiology_flow import RadiologyOutcome, UploadError, analyze_upload  # noqa: E402

st.set_page_config(page_title="Radiology AI | ClaraMed", page_icon="🩻", layout="centered")

RESULT_KEY = "radiology_result"
TOP_N = 3                      # findings highlighted above the full table


@st.cache_resource(show_spinner="Loading the X-ray model (the first visit after a restart takes a minute)...")
def get_service():
    from backend.services.radiology_service import RadiologyService   # heavy import: only when first needed

    service = RadiologyService()
    service.load_model()
    return service


def jeevacare_url() -> str | None:
    """The optional 'Back to JeevaCare' target; only an https URL is ever used."""
    try:
        url = str(st.secrets.get("JEEVACARE_URL", "")).strip()
    except Exception:
        return None
    parsed = urlparse(url)
    return url if parsed.scheme == "https" and parsed.netloc else None


def render_result(outcome: RadiologyOutcome) -> None:
    st.subheader("Results")
    for column, finding in zip(st.columns(TOP_N), outcome.top(TOP_N)):
        column.metric(finding.label.replace("_", " "), f"{finding.score:.0%}")
    st.dataframe(
        [{"Finding": f.label.replace("_", " "), "Model score": f.score} for f in outcome.findings],
        column_config={"Model score": st.column_config.ProgressColumn(min_value=0.0, max_value=1.0, format="%.2f")},
        hide_index=True,
    )
    st.caption(outcome.disclaimer)
    st.caption(f"Model: {outcome.model_name} | {outcome.seconds:.1f}s on CPU")


st.title("🩻 Radiology AI")
st.warning("This is AI model output, not a diagnosis. A qualified radiologist must interpret the image.")
st.info("ClaraMed is a separate service from JeevaCare. Your image is analysed in memory and is not saved "
        "or sent anywhere, including to JeevaCare.")

back = jeevacare_url()
if back:
    st.link_button("← Back to JeevaCare", back)

upload = st.file_uploader("Chest X-ray (PNG or JPEG, up to 10 MB)", type=["png", "jpg", "jpeg"])
if upload is None:
    st.session_state.pop(RESULT_KEY, None)
elif st.button("Analyze", type="primary"):
    try:
        with st.spinner("Analysing..."):
            st.session_state[RESULT_KEY] = analyze_upload(upload.getvalue(), get_service)
    except UploadError as error:
        st.session_state.pop(RESULT_KEY, None)
        st.error(error.message)

if RESULT_KEY in st.session_state:
    render_result(st.session_state[RESULT_KEY])
