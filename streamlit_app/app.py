import streamlit as st
import os
import markdown
import PyPDF2
import pandas as pd
from chains import get_symptom_chain, get_emergency_chain, get_report_explainer_chain, get_wellness_tips_chain
from database import init_db, save_history, get_history, clear_history

# Initialize SQLite Database
init_db()

# Initialize session state for tracking last saved symptom to avoid duplicate saves
if "last_saved_symptom" not in st.session_state:
    st.session_state["last_saved_symptom"] = None

# Initialize session state for selected language
if "selected_language" not in st.session_state:
    st.session_state["selected_language"] = "English"

# Initialize session state for symptoms input text
if "symptoms_input" not in st.session_state:
    st.session_state["symptoms_input"] = ""

# Read query parameters for visual body map interactions
query_params = st.query_params
body_part_param = query_params.get("body_part", None)

# Update symptoms input dynamically if a new body part was clicked
if body_part_param:
    st.session_state["symptoms_input"] = f"Pain in {body_part_param.lower()}"
    # Clear the query params from the URL to prevent overwriting user typing on subsequent runs
    st.query_params.clear()

# Configure the Streamlit page
st.set_page_config(
    page_title="ClaraMed - Medical Companion",
    page_icon="🩺",
    layout="centered"
)

# Custom CSS for ClaraMed premium dark & futuristic visual identity
st.markdown("""
<style>
    /* Main background */
    .stApp {
        background-color: #070a13 !important;
        color: #e2e8f0 !important;
    }
    
    /* Headers */
    h1, h2, h3, h4, h5, h6 {
        color: #00f2fe !important;
        text-shadow: 0 0 12px rgba(0, 242, 254, 0.4);
        font-family: 'Outfit', 'Inter', sans-serif !important;
    }
    
    /* Custom header branding */
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
    
    /* Response box styling - Glassmorphism card */
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
    
    /* Form inputs and text areas */
    textarea {
        background-color: #0f172a !important;
        color: #f1f5f9 !important;
        border: 1px solid rgba(6, 182, 212, 0.2) !important;
        border-radius: 8px !important;
    }
    textarea:focus {
        border-color: #00f2fe !important;
        box-shadow: 0 0 0 2px rgba(0, 242, 254, 0.2) !important;
    }
    
    /* Primary buttons - Glow & Futuristic Hover */
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
    
    /* Secondary buttons - Clear History Log, etc. */
    button[kind="secondary"] {
        background-color: #0f172a !important;
        border: 1px solid rgba(6, 182, 212, 0.3) !important;
        color: #cbd5e1 !important;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
    }
    button[kind="secondary"]:hover {
        background-color: rgba(6, 182, 212, 0.15) !important;
        border-color: #00f2fe !important;
        color: #00f2fe !important;
        box-shadow: 0 0 10px rgba(0, 242, 254, 0.25) !important;
    }

    
    /* Sidebar aesthetic & text visibility */
    section[data-testid="stSidebar"] {
        background-color: #090d16 !important;
        border-right: 1px solid rgba(6, 182, 212, 0.15) !important;
    }
    
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] span,
    section[data-testid="stSidebar"] li,
    section[data-testid="stSidebar"] div[data-testid="stMarkdownContainer"] {
        color: #cbd5e1 !important;
    }

    /* Transparent top header & padding adjustments */
    header[data-testid="stHeader"] {
        background-color: transparent !important;
    }
    
    header[data-testid="stHeader"] div, header[data-testid="stHeader"] span, header[data-testid="stHeader"] a {
        color: #00f2fe !important;
    }
    
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 2rem !important;
    }
    
    /* Dark Futuristic Dropdowns (Baseweb Select) */
    div[data-baseweb="select"] > div {
        background-color: #0f172a !important;
        border: 1px solid rgba(6, 182, 212, 0.25) !important;
    }
    
    div[data-baseweb="select"] div {
        color: #cbd5e1 !important;
    }
    
    div[data-baseweb="select"] svg {
        fill: #00f2fe !important;
    }
    
    /* Dropdown Option Listbox popup */
    div[role="listbox"] {
        background-color: #0f172a !important;
        border: 1px solid rgba(6, 182, 212, 0.25) !important;
    }
    
    div[role="option"] {
        background-color: #0f172a !important;
        color: #cbd5e1 !important;
    }
    
    div[role="option"]:hover {
        background-color: rgba(6, 182, 212, 0.15) !important;
        color: #00f2fe !important;
    }
    
    /* Dark Futuristic File Uploader Dropzone */
    [data-testid="stFileUploaderDropzone"] {
        background-color: #0f172a !important;
        border: 1px dashed rgba(6, 182, 212, 0.3) !important;
        border-radius: 8px !important;
    }
    
    [data-testid="stFileUploaderDropzone"] p, 
    [data-testid="stFileUploaderDropzone"] span, 
    [data-testid="stFileUploaderDropzone"] small {
        color: #cbd5e1 !important;
    }
    
    [data-testid="stFileUploaderDropzone"] button {
        background-color: #1e293b !important;
        color: #cbd5e1 !important;
        border: 1px solid rgba(6, 182, 212, 0.2) !important;
    }
    
    [data-testid="stFileUploaderDropzone"] button:hover {
        background-color: rgba(6, 182, 212, 0.1) !important;
        border-color: #00f2fe !important;
        color: #00f2fe !important;
    }

    
    /* Tabs selector styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 12px;
        background-color: #0f172a;
        padding: 6px;
        border-radius: 10px;
        border: 1px solid rgba(6, 182, 212, 0.15);
    }
    
    .stTabs [data-baseweb="tab"] {
        color: #94a3b8;
        border-radius: 8px;
        padding: 8px 18px;
        font-weight: 600;
        transition: all 0.2s ease;
    }
    
    .stTabs [data-baseweb="tab"]:hover {
        color: #00f2fe;
    }
    
    .stTabs [aria-selected="true"] {
        background-color: rgba(6, 182, 212, 0.15) !important;
        color: #00f2fe !important;
        border-bottom: 2px solid #00f2fe !important;
    }
    
    /* Expanders styling */
    .streamlit-expanderHeader {
        background-color: #0f172a !important;
        border: 1px solid rgba(6, 182, 212, 0.2) !important;
        border-radius: 8px !important;
        color: #00f2fe !important;
    }
    
    .streamlit-expanderContent {
        background-color: rgba(15, 23, 42, 0.3) !important;
        border-left: 1px solid rgba(6, 182, 212, 0.2) !important;
        border-right: 1px solid rgba(6, 182, 212, 0.2) !important;
        border-bottom: 1px solid rgba(6, 182, 212, 0.2) !important;
        border-bottom-left-radius: 8px !important;
        border-bottom-right-radius: 8px !important;
    }
    
    /* Dataframes and Tables */
    .stDataFrame {
        border: 1px solid rgba(6, 182, 212, 0.15) !important;
        border-radius: 8px !important;
        background-color: #0f172a !important;
    }
    
    /* Disclaimer footer */
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

# SVG Human Body Map Outline (Direct Parent DOM Inject - Bulletproof query param routing)
body_map_html = """
<svg viewBox="0 0 200 380" width="100%" height="320" xmlns="http://www.w3.org/2000/svg" style="background-color: #0b0f19; border-radius: 8px; border: 1px solid rgba(6, 182, 212, 0.2);">
  <style>
    .body-part {
      fill: #111827;
      stroke: #1e293b;
      stroke-width: 1.5;
      transition: fill 0.2s ease, stroke 0.2s ease, stroke-width 0.2s ease, filter 0.2s ease;
    }
    .body-part-group:hover .body-part {
      fill: rgba(6, 182, 212, 0.2);
      stroke: #00f2fe;
      stroke-width: 2;
      filter: drop-shadow(0 0 6px rgba(0, 242, 254, 0.6));
    }
    .part-label {
      font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
      font-size: 10px;
      font-weight: 600;
      fill: #38bdf8;
      pointer-events: none;
      text-anchor: middle;
      text-shadow: 0 0 4px rgba(0, 0, 0, 0.8);
    }
    .grid-lines {
      stroke: #1e293b;
      stroke-width: 0.5;
      stroke-dasharray: 4;
    }
  </style>
  
  <!-- Subtle Grid for Medical Aesthetic -->
  <line x1="0" y1="95" x2="200" y2="95" class="grid-lines" />
  <line x1="0" y1="190" x2="200" y2="190" class="grid-lines" />
  <line x1="0" y1="285" x2="200" y2="285" class="grid-lines" />
  <line x1="100" y1="0" x2="100" y2="380" class="grid-lines" />

  <!-- Back button -->
  <a href="?body_part=Back" target="_self">
    <g class="body-part-group" style="cursor: pointer;">
      <rect x="140" y="15" width="50" height="25" class="body-part" rx="4" />
      <text x="165" y="31" class="part-label">Back</text>
    </g>
  </a>

  <!-- Head -->
  <a href="?body_part=Head" target="_self">
    <g class="body-part-group" style="cursor: pointer;">
      <circle cx="100" cy="45" r="20" class="body-part" />
      <text x="100" y="48" class="part-label">Head</text>
    </g>
  </a>
  
  <!-- Chest -->
  <a href="?body_part=Chest" target="_self">
    <g class="body-part-group" style="cursor: pointer;">
      <path d="M 78,75 L 122,75 L 122,120 L 78,120 Z" class="body-part" />
      <text x="100" y="101" class="part-label">Chest</text>
    </g>
  </a>
  
  <!-- Stomach -->
  <a href="?body_part=Stomach" target="_self">
    <g class="body-part-group" style="cursor: pointer;">
      <path d="M 78,120 L 122,120 L 118,165 L 82,165 Z" class="body-part" />
      <text x="100" y="146" class="part-label">Stomach</text>
    </g>
  </a>
  
  <!-- Right Arm -->
  <a href="?body_part=Right+Arm" target="_self">
    <g class="body-part-group" style="cursor: pointer;">
      <path d="M 78,75 L 53,100 L 38,150 L 48,155 L 61,115 L 78,92 Z" class="body-part" />
      <text x="52" y="135" class="part-label" style="font-size: 8px;">R Arm</text>
    </g>
  </a>

  <!-- Left Arm -->
  <a href="?body_part=Left+Arm" target="_self">
    <g class="body-part-group" style="cursor: pointer;">
      <path d="M 122,75 L 147,100 L 162,150 L 152,155 L 139,115 L 122,92 Z" class="body-part" />
      <text x="148" y="135" class="part-label" style="font-size: 8px;">L Arm</text>
    </g>
  </a>
  
  <!-- Right Leg -->
  <a href="?body_part=Right+Leg" target="_self">
    <g class="body-part-group" style="cursor: pointer;">
      <path d="M 82,165 L 77,250 L 72,330 L 87,330 L 93,250 L 98,165 Z" class="body-part" />
      <text x="81" y="250" class="part-label" style="font-size: 8px;">R Leg</text>
    </g>
  </a>

  <!-- Left Leg -->
  <a href="?body_part=Left+Leg" target="_self">
    <g class="body-part-group" style="cursor: pointer;">
      <path d="M 118,165 L 123,250 L 128,330 L 113,330 L 107,250 L 102,165 Z" class="body-part" />
      <text x="119" y="250" class="part-label" style="font-size: 8px;">L Leg</text>
    </g>
  </a>
</svg>
"""

# Sidebar for PDF upload
st.sidebar.markdown("### 📄 ClaraMed Report Analyzer")
st.sidebar.write("Upload your medical reports or lab results in PDF format for a simple, plain-English breakdown.")
uploaded_file = st.sidebar.file_uploader("Upload a PDF report", type=["pdf"])

# Sidebar for Language selector
st.sidebar.write("---")
st.sidebar.markdown("### 🌐 Choose Language")
selected_lang = st.sidebar.selectbox(
    "Select preferred language for AI responses:",
    ["English", "Hindi", "Kannada", "Tamil", "Telugu", "Spanish", "French"],
    index=["English", "Hindi", "Kannada", "Tamil", "Telugu", "Spanish", "French"].index(st.session_state["selected_language"])
)

# Store selected language in session state
st.session_state["selected_language"] = selected_lang

# Sidebar for Clickable Body Map
with st.sidebar:
    st.write("---")
    st.markdown("### 🗺️ Or click a body part")
    # Strip newlines from SVG to prevent the markdown engine from parsing it line-by-line
    st.markdown(body_map_html.replace("\n", " "), unsafe_allow_html=True)

# Localized Emergency Alerts
EMERGENCY_ALERTS = {
    "English": "🚨 **This may be a medical emergency!**\n\nPlease call 112 (India Emergency) or visit the nearest hospital immediately.",
    "Hindi": "🚨 **यह एक चिकित्सा आपातकाल हो सकता है!**\n\nकृपया तुरंत 112 (भारत आपातकालीन) पर कॉल करें या निकटतम अस्पताल जाएं।",
    "Kannada": "🚨 **ಇದು ವೈದ್ಯಕೀಯ ತುರ್ತು ಪರಿಸ್ಥಿತಿ ಇರಬಹುದು!**\n\nದಯವಿಟ್ಟು தಕ್ಷಣ 112 (ಭಾರತ ತುರ್ತು ಸೇವೆ) ಗೆ ಕರೆ ಮಾಡಿ ಅಥವಾ ಹತ್ತಿರದ ಆಸ್ಪತ್ರೆಗೆ ಭೇಟಿ ನೀಡಿ.",
    "Tamil": "🚨 **இது ஒரு மருத்துவ அவசர நிலையாக இருக்கலாம்!**\n\nதயவுசெய்து உடனடியாக 112 (இந்தியா அவசர எண்) ஐ அழைக்கவும் அல்லது அருகிலுள்ள மருத்துவமனைக்குச் செல்லவும்.",
    "Telugu": "🚨 **ఇది వైద్య అత్యవసర పరిస్థితి కావచ్చు!**\n\nదయచేసి వెంటనే 112 (భారతదేశ అత్యవసర సంఖ్య) కి కాల్ చేయండి లేదా సమీప ఆసుపత్రిని సందర్శించండి.",
    "Spanish": "🚨 **¡Esto puede ser una emergencia médica!**\n\nPor favor, llame al 112 (Emergencias de India) o visite el hospital más cercano de inmediato.",
    "French": "🚨 **Cela peut être une urgence médicale !**\n\nVeuillez appeler le 112 (urgences en Inde) ou vous rendre immédiatement à l'hôpital le plus proche."
}

# App UI Header using st.markdown
st.markdown("""
<div class="brand-header">
    <div class="brand-title">🩺 ClaraMed</div>
    <div class="brand-subtitle">AI-Powered Symptom Explainer & Report Analyzer</div>
</div>
""", unsafe_allow_html=True)

# Create Tabs (Symptom Checker, Report Explainer, and Symptom History)
tab1, tab2, tab3 = st.tabs(["Symptom Checker", "Report Explainer", "📊 Symptom History"])

# Tab 1: Symptom Checker
with tab1:
    # Placeholder for emergency alerts at the top of the content
    emergency_alert = st.empty()

    # Main content
    st.markdown("### Describe your symptoms")
    st.write("Please provide as much detail as possible (e.g., duration, severity, specific locations) so we can provide a better explanation.")

    # Form for user input
    with st.form("symptom_form"):
        symptoms = st.text_area(
            "Your symptoms:",
            height=150,
            placeholder="E.g., I have had a headache for 3 days and feel slightly nauseous...",
            value=st.session_state["symptoms_input"]
        )
        submit_button = st.form_submit_button("Analyze Symptoms", type="primary")

    if submit_button:
        if "GROQ_API_KEY" not in st.secrets or st.secrets["GROQ_API_KEY"] in ["", "your_groq_api_key_here"]:
            st.error("⚠️ Groq API key is missing or not configured. Please add it to your Streamlit secrets.")
        elif not symptoms.strip():
            st.warning("Please enter your symptoms before submitting.")
        else:
            with st.spinner("Analyzing your symptoms..."):
                try:
                    # Check for emergency first
                    emergency_chain = get_emergency_chain()
                    emergency_result = emergency_chain.invoke({"symptoms": symptoms, "language": selected_lang}).strip()
                    
                    # Language-specific words representing 'YES'
                    emergency_yes_words = ["YES", "हाँ", "ಹೌದು", "ஆம்", "అవును", "SÍ", "SI", "OUI"]
                    is_emergency = any(word in emergency_result.upper() or word in emergency_result for word in emergency_yes_words)
                    
                    if is_emergency:
                        emergency_msg = EMERGENCY_ALERTS.get(selected_lang, EMERGENCY_ALERTS["English"])
                        emergency_alert.error(emergency_msg)
                        
                        # Save to database (avoid duplicate saves on re-renders)
                        if st.session_state["last_saved_symptom"] != symptoms:
                            save_history(symptoms, emergency_msg, "yes")
                            st.session_state["last_saved_symptom"] = symptoms
                    else:
                        # Get the chain and run it
                        chain = get_symptom_chain()
                        response = chain.invoke({"symptoms": symptoms, "language": selected_lang})
                        
                        # Convert Markdown to HTML for rendering inside the custom div properly
                        html_response = markdown.markdown(response)
                        
                        # Display the response in a styled box
                        st.markdown("### Analysis Result")
                        st.markdown(f'<div class="response-box">{html_response}</div>', unsafe_allow_html=True)
                        
                        # Automatically run wellness tips chain
                        tips_chain = get_wellness_tips_chain()
                        wellness_tips = tips_chain.invoke({"symptoms": symptoms, "language": selected_lang})
                        
                        # Display inside expander
                        st.write("") # Add spacing
                        with st.expander("🥗 Diet & Lifestyle Tips", expanded=True):
                            st.markdown(wellness_tips)
                            st.caption("_These are general wellness tips, not medical advice._")
                            
                        # Save to database (avoid duplicate saves on re-renders)
                        if st.session_state["last_saved_symptom"] != symptoms:
                            save_history(symptoms, response, "no")
                            st.session_state["last_saved_symptom"] = symptoms
                except Exception as e:
                    st.error(f"An error occurred: {str(e)}")

# Tab 2: Report Explainer
with tab2:
    st.markdown("### Medical Report Explainer")
    st.write("Simplify complex medical terminology and values from your lab results or clinical reports.")
    
    if uploaded_file is not None:
        st.success(f"✅ Loaded: **{uploaded_file.name}**")
        
        # Add an Analyze button
        analyze_report = st.button("Explain My Report", type="primary")
        
        if analyze_report:
            if "GROQ_API_KEY" not in st.secrets or st.secrets["GROQ_API_KEY"] in ["", "your_groq_api_key_here"]:
                st.error("⚠️ Groq API key is missing or not configured. Please add it to your Streamlit secrets.")
            else:
                with st.spinner("Reading PDF and translating medical terms..."):
                    try:
                        # Parse PDF using PyPDF2
                        reader = PyPDF2.PdfReader(uploaded_file)
                        pdf_text = ""
                        for page in reader.pages:
                            text = page.extract_text()
                            if text:
                                pdf_text += text + "\n"
                        
                        if not pdf_text.strip():
                            st.warning("Could not extract any text from this PDF. Please ensure it's a text-based clinical report, not a scanned image/photo.")
                        else:
                            # Invoke explanation chain
                            explainer_chain = get_report_explainer_chain()
                            explanation = explainer_chain.invoke({"report_text": pdf_text, "language": selected_lang})
                            
                            # Convert Markdown to HTML
                            html_explanation = markdown.markdown(explanation)
                            
                            # Display response
                            st.markdown("### Plain English Explanation")
                            st.markdown(f'<div class="response-box">{html_explanation}</div>', unsafe_allow_html=True)
                    except Exception as e:
                        st.error(f"An error occurred while reading or processing the PDF: {str(e)}")
    else:
        st.info("👈 Please upload a PDF medical report in the sidebar to get started.")

# Tab 3: Symptom History
with tab3:
    st.markdown("### 📊 Symptom History Log")
    st.write("Review your past symptom analyses and triage classifications.")
    
    # Retrieve history from SQLite database
    history_data = get_history()
    
    if len(history_data) > 0:
        # Create a Pandas DataFrame for structured display
        df = pd.DataFrame(
            history_data, 
            columns=["Timestamp", "Symptom", "AI Explanation (First 200 Chars)", "Emergency Alert?"]
        )
        
        # Display the dataframe with container width and hidden index
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # Clear history button
        st.write("")
        if st.button("Clear History Log", type="secondary"):
            clear_history()
            st.success("History cleared successfully!")
            # Rerun the app to refresh the UI and show the empty state
            st.rerun()
    else:
        st.info("No symptom history found. Go to the Symptom Checker tab to begin!")

# Disclaimer
st.markdown("""
<div class="disclaimer">
    ClaraMed is for educational purposes only. Always consult a real doctor.
</div>
""", unsafe_allow_html=True)
