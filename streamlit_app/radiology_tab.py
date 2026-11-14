"""The "Radiology AI" tab of the ClaraMed app: upload an X-ray, get a plain-English explanation of it."""
from urllib.parse import urlparse

import streamlit as st

from streamlit_app.radiology_flow import RadiologyOutcome, UploadError, analyze_upload

RESULT_KEY = "radiology_result"
TOP_N = 3                      # findings highlighted above the full table


@st.cache_resource(show_spinner="Loading the X-ray model (the first analysis after a restart takes a minute)...")
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


def get_chain():
    """LLM chain that words the explanation; None (-> built-in template) when the LLM is unavailable."""
    from backend.services import radiology_explainer

    return radiology_explainer.get_explanation_chain()


def render_result(outcome: RadiologyOutcome) -> None:
    st.subheader("Your X-ray explained")
    st.markdown(outcome.explanation)
    if outcome.findings:
        with st.expander("Technical details (model scores)"):
            for column, finding in zip(st.columns(TOP_N), outcome.top(TOP_N)):
                column.metric(finding.label.replace("_", " "), f"{finding.score:.0%}")
            st.dataframe(
                [{"Finding": f.label.replace("_", " "), "Model score": f.score} for f in outcome.findings],
                column_config={"Model score": st.column_config.ProgressColumn(min_value=0.0, max_value=1.0, format="%.2f")},
                hide_index=True,
            )
            st.caption("Scores are the model's internal confidence, not the chance you have a condition.")
    st.caption(outcome.disclaimer)
    st.caption(f"Model: {outcome.model_name} | {outcome.seconds:.1f}s")


def render_radiology_tab(language: str = "English") -> None:
    st.warning("This is AI model output, not a diagnosis. A qualified radiologist must interpret the image.")
    st.info("ClaraMed is a separate service from JeevaCare. Your image is not saved and is never sent to JeevaCare. "
            "Chest X-rays are analysed in memory; only a short text summary of the findings (never the image) goes "
            "to the AI service that words the explanation. If you choose \"Other body part\", the image itself is "
            "sent to that AI service (Groq).")

    back = jeevacare_url()
    if back:
        st.link_button("← Back to JeevaCare", back)

    body_part = st.radio("What is this X-ray of?", ["chest", "other"], key="radiology_body_part", horizontal=True,
                         format_func=lambda v: "Chest" if v == "chest" else "Other body part (hand, leg, spine...)")
    upload = st.file_uploader("X-ray (PNG, JPEG, DICOM or PDF, up to 10 MB)",
                              type=["png", "jpg", "jpeg", "pdf", "dcm"], key="radiology_upload")
    if upload is None:
        st.session_state.pop(RESULT_KEY, None)
    elif st.button("Analyze", type="primary", key="radiology_analyze"):
        try:
            with st.spinner("Analysing..."):
                st.session_state[RESULT_KEY] = analyze_upload(
                    upload.getvalue(), get_service, language=language, body_part=body_part, chain_factory=get_chain)
        except UploadError as error:
            st.session_state.pop(RESULT_KEY, None)
            st.error(error.message)

    if RESULT_KEY in st.session_state:
        render_result(st.session_state[RESULT_KEY])
