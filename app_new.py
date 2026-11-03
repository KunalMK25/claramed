"""
ClaraMed Streamlit Frontend (Refactored)

Connects to FastAPI backend while preserving all existing UI features.
"""
import streamlit as st
import pandas as pd
import markdown
from frontend.api_client import get_api_client

# Configure page
st.set_page_config(
    page_title="ClaraMed - Medical Companion",
    page_icon="🩺",
    layout="centered"
)

# Initialize API client
api_client = get_api_client()

# Initialize session state
if "last_saved_symptom" not in st.session_state:
    st.session_state["last_saved_symptom"] = None

if "selected_language" not in st.session_state:
    st.session_state["selected_language"] = "English"

if "symptoms_input" not in st.session_state:
    st.session_state["symptoms_input"] = ""

# Read query parameters for body map
query_params = st.query_params
body_part_param = query_params.get("body_part", None)

if body_part_param:
    st.session_state["symptoms_input"] = f"Pain in {body_part_param.lower()}"
    st.query_params.clear()

# Custom CSS (preserved from original)
st.markdown("""
<style>
    .stApp {
        background-color: #070a13 !important;
        color: #e2e8f0 !important;
    }
    
    h1, h2, h3, h4, h5, h6 {
        color: #00f2fe !important;
        text-shadow: 0 0 12px rgba(0, 242, 254, 0.4);
        font-family: 'Outfit', 'Inter', sans-serif !important;
    }
    
    .brand-header {
        text-align: center;
        padding: 2.5rem 0 1.5rem 0;
        border-bottom: 1px solid rgba(0, 242, 254, 0.15);
        margin-bottom: 2rem;
    }
    
    .brand-title {
        font-size: 3.2rem;
        font-weight: 900;
        margin-bottom: 0;
        background: linear-gradient(135deg, #00f2fe 30%, #a855f7 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        letter-spacing: -0.5px;
        display: flex;
        justify-content: center;
        align-items: center;
        gap: 12px;
    }
    
    .brand-subtitle {
        font-size: 1.15rem;
        color: #a855f7;
        margin-top: 0.6rem;
        font-weight: 600;
        letter-spacing: 2px;
        text-transform: uppercase;
        text-shadow: 0 0 8px rgba(168, 85, 247, 0.3);
    }
    
    .response-box {
        background: rgba(15, 23, 42, 0.6);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border: 1px solid rgba(6, 182, 212, 0.25);
        padding: 1.75rem;
        border-radius: 12px;
        box-shadow: 0 8px 32px 0 rgba(0, 242, 254, 0.08), inset 0 1px 0 rgba(255, 255, 255, 0.05);
        margin-top: 1.5rem;
        color: #cbd5e1;
        line-height: 1.75;
        font-size: 1.05rem;
    }
    
    textarea {
        background-color: #0f172a !important;
        color: #f1f5f9 !important;
        border: 1px solid rgba(6, 182, 212, 0.2) !important;
        border-radius: 8px !important;
    }
    
    button[kind="primary"] {
        background: linear-gradient(135deg, #00f2fe 0%, #a855f7 100%) !important;
        border: none !important;
        color: white !important;
        font-weight: 700 !important;
        box-shadow: 0 4px 15px rgba(0, 242, 254, 0.3) !important;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
        border-radius: 8px !important;
        padding: 0.6rem 1.8rem !important;
    }
    
    button[kind="primary"]:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 22px rgba(0, 242, 254, 0.55), 0 0 8px rgba(168, 85, 247, 0.4) !important;
    }
    
    .disclaimer {
        text-align: center;
        font-size: 0.9rem;
        color: #475569;
        margin-top: 4rem;
        padding-top: 1.2rem;
        border-top: 1px solid rgba(6, 182, 212, 0.15);
        font-weight: 500;
    }
</style>
""", unsafe_allow_html=True)

# Body map SVG (preserved from original)
body_map_html = """
<svg viewBox="0 0 200 380" width="100%" height="320" xmlns="http://www.w3.org/2000/svg" style="background-color: #0b0f19; border-radius: 8px; border: 1px solid rgba(6, 182, 212, 0.2);">
  <style>
    .body-part {
      fill: #111827;
      stroke: #1e293b;
      stroke-width: 1.5;
      transition: fill 0.2s ease, stroke 0.2s ease;
    }
    .body-part-group:hover .body-part {
      fill: rgba(6, 182, 212, 0.2);
      stroke: #00f2fe;
      stroke-width: 2;
    }
    .part-label {
      font-family: 'Segoe UI', sans-serif;
      font-size: 10px;
      font-weight: 600;
      fill: #38bdf8;
      pointer-events: none;
      text-anchor: middle;
    }
  </style>
  
  <a href="?body_part=Back" target="_self">
    <g class="body-part-group" style="cursor: pointer;">
      <rect x="140" y="15" width="50" height="25" class="body-part" rx="4" />
      <text x="165" y="31" class="part-label">Back</text>
    </g>
  </a>
  
  <a href="?body_part=Head" target="_self">
    <g class="body-part-group" style="cursor: pointer;">
      <circle cx="100" cy="45" r="20" class="body-part" />
      <text x="100" y="48" class="part-label">Head</text>
    </g>
  </a>
  
  <a href="?body_part=Chest" target="_self">
    <g class="body-part-group" style="cursor: pointer;">
      <path d="M 78,75 L 122,75 L 122,120 L 78,120 Z" class="body-part" />
      <text x="100" y="101" class="part-label">Chest</text>
    </g>
  </a>
  
  <a href="?body_part=Stomach" target="_self">
    <g class="body-part-group" style="cursor: pointer;">
      <path d="M 78,120 L 122,120 L 118,165 L 82,165 Z" class="body-part" />
      <text x="100" y="146" class="part-label">Stomach</text>
    </g>
  </a>
  
  <a href="?body_part=Right+Arm" target="_self">
    <g class="body-part-group" style="cursor: pointer;">
      <path d="M 78,75 L 53,100 L 38,150 L 48,155 L 61,115 L 78,92 Z" class="body-part" />
      <text x="52" y="135" class="part-label" style="font-size: 8px;">R Arm</text>
    </g>
  </a>

  <a href="?body_part=Left+Arm" target="_self">
    <g class="body-part-group" style="cursor: pointer;">
      <path d="M 122,75 L 147,100 L 162,150 L 152,155 L 139,115 L 122,92 Z" class="body-part" />
      <text x="148" y="135" class="part-label" style="font-size: 8px;">L Arm</text>
    </g>
  </a>
  
  <a href="?body_part=Right+Leg" target="_self">
    <g class="body-part-group" style="cursor: pointer;">
      <path d="M 82,165 L 77,250 L 72,330 L 87,330 L 93,250 L 98,165 Z" class="body-part" />
      <text x="81" y="250" class="part-label" style="font-size: 8px;">R Leg</text>
    </g>
  </a>

  <a href="?body_part=Left+Leg" target="_self">
    <g class="body-part-group" style="cursor: pointer;">
      <path d="M 118,165 L 123,250 L 128,330 L 113,330 L 107,250 L 102,165 Z" class="body-part" />
      <text x="119" y="250" class="part-label" style="font-size: 8px;">L Leg</text>
    </g>
  </a>
</svg>
"""

# Sidebar
st.sidebar.markdown("### 📄 ClaraMed Report Analyzer")
st.sidebar.write("Upload your medical reports or lab results in PDF format.")
uploaded_file = st.sidebar.file_uploader("Upload a PDF report", type=["pdf"])

# Radiology image uploader
st.sidebar.write("---")
st.sidebar.markdown("### 🩻 Chest X-Ray Analysis")
st.sidebar.write("Upload a chest X-ray image for AI analysis.")
uploaded_xray = st.sidebar.file_uploader("Upload chest X-ray", type=["png", "jpg", "jpeg"])

# Language selector
st.sidebar.write("---")
st.sidebar.markdown("### 🌐 Choose Language")
selected_lang = st.sidebar.selectbox(
    "Select preferred language:",
    ["English", "Hindi", "Kannada", "Tamil", "Telugu", "Spanish", "French"],
    index=["English", "Hindi", "Kannada", "Tamil", "Telugu", "Spanish", "French"].index(st.session_state["selected_language"])
)
st.session_state["selected_language"] = selected_lang

# Body map
with st.sidebar:
    st.write("---")
    st.markdown("### 🗺️ Or click a body part")
    st.markdown(body_map_html.replace("\n", " "), unsafe_allow_html=True)

# Backend status check
with st.sidebar:
    st.write("---")
    st.markdown("### 🔧 System Status")
    if st.button("Check Backend Status"):
        with st.spinner("Checking..."):
            health = api_client.health_check()
            if health.get("status") == "healthy":
                st.success("✓ Backend Online")
            else:
                st.error(f"✗ Backend Error: {health.get('error', 'Unknown')}")

# Emergency alert messages
EMERGENCY_ALERTS = {
    "English": "🚨 **This may be a medical emergency!**\n\nPlease call emergency services or visit the nearest hospital immediately.",
    "Hindi": "🚨 **यह एक चिकित्सा आपातकाल हो सकता है!**\n\nकृपया तुरंत आपातकालीन सेवाओं को कॉल करें या निकटतम अस्पताल जाएं।",
    "Kannada": "🚨 **ಇದು ವೈದ್ಯಕೀಯ ತುರ್ತು ಪರಿಸ್ಥಿತಿ ಇರಬಹುದು!**\n\nದಯವಿಟ್ಟು ತಕ್ಷಣ ತುರ್ತು ಸೇವೆಗಳಿಗೆ ಕರೆ ಮಾಡಿ.",
    "Tamil": "🚨 **இது ஒரு மருத்துவ அவசர நிலையாக இருக்கலாம்!**\n\nதயவுசெய்து உடனடியாக அவசர சேவைகளை அழைக்கவும்.",
    "Telugu": "🚨 **ఇది వైద్య అత్యవసర పరిస్థితి కావచ్చు!**\n\nదయచేసి వెంటనే అత్యవసర సేవలకు కాల్ చేయండి.",
    "Spanish": "🚨 **¡Esto puede ser una emergencia médica!**\n\nPor favor, llame a los servicios de emergencia inmediatamente.",
    "French": "🚨 **Cela peut être une urgence médicale!**\n\nVeuillez appeler les services d'urgence immédiatement.",
}

# App Header
st.markdown("""
<div class="brand-header">
    <div class="brand-title">🩺 ClaraMed</div>
    <div class="brand-subtitle">AI-Powered Symptom Explainer & Report Analyzer</div>
</div>
""", unsafe_allow_html=True)

# Create tabs
tab1, tab2, tab3, tab4 = st.tabs(["Symptom Checker", "Report Explainer", "X-Ray Analysis", "📊 History"])

# Tab 1: Symptom Checker
with tab1:
    emergency_alert = st.empty()
    
    st.markdown("### Describe your symptoms")
    st.write("Please provide as much detail as possible.")
    
    with st.form("symptom_form"):
        symptoms = st.text_area(
            "Your symptoms:",
            height=150,
            placeholder="E.g., I have had a headache for 3 days...",
            value=st.session_state["symptoms_input"]
        )
        submit_button = st.form_submit_button("Analyze Symptoms", type="primary")
    
    if submit_button:
        if not symptoms.strip():
            st.warning("Please enter your symptoms before submitting.")
        else:
            with st.spinner("Analyzing your symptoms..."):
                try:
                    result = api_client.create_symptom_analysis(
                        symptoms=symptoms,
                        language=selected_lang,
                        include_wellness=True
                    )
                    
                    # Check for emergency
                    emergency_class = result.get("emergency_classification", {})
                    if emergency_class.get("emergency_flagged"):
                        emergency_msg = EMERGENCY_ALERTS.get(selected_lang, EMERGENCY_ALERTS["English"])
                        emergency_alert.error(emergency_msg)
                    
                    # Display explanation
                    explanation = result.get("explanation", "")
                    if explanation:
                        st.markdown("### Analysis Result")
                        html_response = markdown.markdown(explanation)
                        st.markdown(f'<div class="response-box">{html_response}</div>', unsafe_allow_html=True)
                    
                    # Display wellness tips
                    wellness_tips = result.get("wellness_tips", "")
                    if wellness_tips:
                        st.write("")
                        with st.expander("🥗 Diet & Lifestyle Tips", expanded=True):
                            st.markdown(wellness_tips)
                            st.caption("_These are general wellness tips, not medical advice._")
                    
                    st.session_state["last_saved_symptom"] = symptoms
                    
                except Exception as e:
                    st.error(f"Analysis failed: {str(e)}")

# Tab 2: Report Explainer
with tab2:
    st.markdown("### Medical Report Explainer")
    st.write("Simplify complex medical terminology from your reports.")
    
    if uploaded_file is not None:
        st.success(f"✅ Loaded: **{uploaded_file.name}**")
        
        analyze_report = st.button("Explain My Report", type="primary")
        
        if analyze_report:
            with st.spinner("Processing PDF and generating explanation..."):
                try:
                    # First create an analysis
                    analysis = api_client.create_symptom_analysis(
                        symptoms="Document analysis",
                        language=selected_lang,
                        include_wellness=False
                    )
                    
                    analysis_id = analysis["analysis_id"]
                    
                    # Upload document
                    file_content = uploaded_file.read()
                    upload_result = api_client.upload_document(
                        analysis_id=analysis_id,
                        file_content=file_content,
                        filename=uploaded_file.name
                    )
                    
                    # Get results
                    results = api_client.get_analysis_results(analysis_id)
                    
                    # Display explanation
                    explanation_data = results.get("results", {}).get("explanation", {})
                    explanation = explanation_data.get("explanation", "")
                    
                    if explanation:
                        st.markdown("### Plain English Explanation")
                        html_explanation = markdown.markdown(explanation)
                        st.markdown(f'<div class="response-box">{html_explanation}</div>', unsafe_allow_html=True)
                    
                    # Display structured findings if available
                    structured = results.get("results", {}).get("structured_findings", {})
                    if structured:
                        st.write("")
                        with st.expander("📋 Structured Findings"):
                            st.markdown(structured.get("findings", ""))
                    
                except Exception as e:
                    st.error(f"Document processing failed: {str(e)}")
    else:
        st.info("👈 Please upload a PDF medical report in the sidebar.")

# Tab 3: X-Ray Analysis
with tab3:
    st.markdown("### Chest X-Ray AI Analysis")
    st.write("Upload a chest X-ray for AI-powered analysis using TorchXRayVision.")
    
    if uploaded_xray is not None:
        st.success(f"✅ Loaded: **{uploaded_xray.name}**")
        
        # Display uploaded image
        st.image(uploaded_xray, caption="Uploaded Chest X-Ray", use_column_width=True)
        
        analyze_xray = st.button("Analyze X-Ray", type="primary")
        
        if analyze_xray:
            with st.spinner("Performing AI analysis... This may take a moment."):
                try:
                    # Create analysis
                    analysis = api_client.create_symptom_analysis(
                        symptoms="Radiology analysis",
                        language=selected_lang,
                        include_wellness=False
                    )
                    
                    analysis_id = analysis["analysis_id"]
                    
                    # Upload image
                    file_content = uploaded_xray.read()
                    upload_result = api_client.upload_radiology_image(
                        analysis_id=analysis_id,
                        file_content=file_content,
                        filename=uploaded_xray.name
                    )
                    
                    # Display results
                    st.markdown("### AI Analysis Results")
                    
                    st.info(f"**Model:** {upload_result.get('model_name', 'TorchXRayVision')}")
                    st.info(f"**Modality:** {upload_result.get('modality', 'chest_xray')}")
                    
                    # Display findings
                    top_findings = upload_result.get("top_findings", [])
                    if top_findings:
                        st.markdown("### Top Findings")
                        
                        findings_df = pd.DataFrame(top_findings)
                        findings_df["model_score"] = findings_df["model_score"].round(3)
                        st.dataframe(
                            findings_df,
                            use_container_width=True,
                            hide_index=True
                        )
                        
                        st.warning("⚠️ **Important:** These are AI-generated model outputs, not a radiologist's diagnosis. Professional medical interpretation is required.")
                    
                except Exception as e:
                    st.error(f"X-ray analysis failed: {str(e)}")
    else:
        st.info("👈 Please upload a chest X-ray image in the sidebar.")

# Tab 4: History
with tab4:
    st.markdown("### 📊 Analysis History")
    st.write("View your past analyses.")
    
    try:
        history_data = api_client.list_analyses(page=1, page_size=20)
        
        analyses = history_data.get("analyses", [])
        
        if analyses:
            # Create dataframe
            history_list = []
            for analysis in analyses:
                history_list.append({
                    "ID": analysis["analysis_id"][:8],
                    "Type": analysis["analysis_type"],
                    "Status": analysis["status"],
                    "Created": analysis["created_at"],
                })
            
            df = pd.DataFrame(history_list)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No analysis history found. Start by analyzing symptoms or uploading a report!")
    
    except Exception as e:
        st.error(f"Failed to load history: {str(e)}")

# Disclaimer
st.markdown("""
<div class="disclaimer">
    ClaraMed is for educational purposes only. Always consult a real doctor.
</div>
""", unsafe_allow_html=True)
