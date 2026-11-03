# ClaraMed 🩺 — AI-Powered Symptom Explainer & Report Analyzer

ClaraMed is a premium medical companion web application built using **Streamlit**, **LangChain**, and the high-performance **Groq API** with Llama-3.1. It provides users with a clean, multilingual, and highly interactive interface to explain their symptoms, get wellness suggestions, analyze medical PDF reports, and track their symptom history.

---

## 🌟 Key Features

1. **AI-Powered Symptom Explainer**:
   - Uses LangChain connected to `llama-3.1-8b-instant` via Groq.
   - Provides clear, educational explanations of symptoms, potential causes, and advice in a reassuring, professional tone.

2. **Emergency Alert Classifier**:
   - Analyzes every symptom query **before** generating explanations.
   - Instantly flags potential medical emergencies with a prominent red alert box pointing users to emergency contact lines (e.g., 112 in India).

3. **Interactive 3D-Style Body Map**:
   - Features a clean, medical-themed clickable vector body map in the sidebar.
   - Clicking on a region (Head, Chest, Stomach, Arms, Legs, Back) dynamically pre-fills the symptoms input field.

4. **PDF Medical Report Explainer**:
   - Allows users to upload clinical lab results or clinical PDF reports.
   - Uses `PyPDF2` to extract text and translates complex medical jargon and values into plain, conversational English.

5. **Diet & Lifestyle Suggestions**:
   - Automatically provides 3 relevant nutrition suggestions and 3 simple lifestyle adjustments customized to the analyzed symptom in a beautiful wellness expander.

6. **SQLite History Log**:
   - Persists all past symptom queries, truncated AI explanations, and emergency classification logs inside a local `claramd.db` SQLite database.
   - Renders history logs in an interactive dashboard table with the ability to clear history dynamically.

7. **Multilingual Support**:
   - Translates all AI responses, diet/lifestyle tips, and emergency alerts into **English, Hindi, Kannada, Tamil, Telugu, Spanish, or French** via a dropdown menu in the sidebar.

---

## 🛠️ Tech Stack

- **Frontend/UI**: Streamlit
- **Orchestration**: LangChain (Core, Community, Groq integrations)
- **AI Backend Model**: `llama-3.1-8b-instant` via Groq LPU
- **Database**: SQLite3 (via built-in Python integration)
- **PDF Extraction**: PyPDF2
- **Styling**: Vanilla CSS (injected into Streamlit) & custom SVG graphics

---

## 🚀 How to Run Locally

### 1. Clone the repository and navigate to the project directory:
```bash
cd claramed
```

### 2. Install the exact dependencies:
```bash
pip install -r requirements.txt
```

### 3. Set up your Groq API Key:
Create a folder named `.streamlit` in the root directory, and inside it, create a file named `secrets.toml`:
```toml
# .streamlit/secrets.toml
GROQ_API_KEY = "your_actual_groq_api_key_here"
```

### 4. Run the Streamlit application:
```bash
streamlit run app.py
```
*(If `streamlit` is not recognized, run `python -m streamlit run app.py`)*

---

## ☁️ How to Deploy to Streamlit Cloud

1. Push this repository to your **GitHub** account.
2. Go to [share.streamlit.io](https://share.streamlit.io/) and log in with your GitHub account.
3. Click **"New app"** and select your repository, branch, and specify `app.py` as the main file path.
4. Click on **"Advanced settings..."** before deploying.
5. In the **Secrets** section, add your Groq API key:
   ```toml
   GROQ_API_KEY = "your_actual_groq_api_key_here"
   ```
6. Click **Deploy**. Your app will be live in seconds!

---

> **⚠️ Disclaimer**: ClaraMed is for educational purposes only. Always consult a real doctor.
