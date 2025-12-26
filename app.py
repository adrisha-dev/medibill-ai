import os
import json
import sqlite3
import re
import logging

import streamlit as st
import google.generativeai as genai
import wandb

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Config
st.set_page_config(
    page_title="MediBill AI",
    page_icon="🏥",
    layout="centered"
)

# Initialize W&B if api key exists, otherwise skip silently
# TODO: Add better error handling for network timeouts
if os.getenv("WANDB_API_KEY"):
    try:
        wandb.init(project="medibill-ai", name="production_v1", reinit=True)
    except Exception as e:
        logger.warning(f"W&B init failed: {e}")

# Gemini Setup
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    st.error("Missing GEMINI_API_KEY environment variable.")
    st.stop()

genai.configure(api_key=api_key)
model = genai.GenerativeModel("models/gemini-2.0-flash")

def parse_json_response(text):
    """
    Gemini sometimes wraps JSON in markdown.  
    This tries to pull out the actual object safely.
    """
    try:
        # Look for content between braces, ensuring we catch the outer object
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        return json.loads(text) # Fallback
    except json.JSONDecodeError:
        logger.error(f"Failed to parse JSON from: {text[:50]}...")
        return None

def connect_db():
    # Using local sqlite for prototype
    try:
        conn = sqlite3.connect("medibill.db")
        return conn
    except sqlite3.Error as e:
        st.error(f"Database connection failed: {e}")
        return None

def fetch_bill():
    conn = connect_db()
    if not conn:
        return []
    
    try:
        cur = conn.cursor()
        cur.execute("SELECT item_name, category, cost FROM bill_items")
        rows = cur.fetchall()
        return [{"item": r[0], "category": r[1], "cost": r[2]} for r in rows]
    except sqlite3.Error as e:
        logger.error(f"Query error: {e}")
        return []
    finally:
        conn.close()

def query_llm(prompt):
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        logger.error(f"LLM Query failed: {e}")
        return None

st.markdown("""
<style>
    /* Full-page background (simplified for compatibility) */
    body {
        font-family: Arial, Helvetica, sans-serif;
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        color: #333;
        margin: 0;
        padding: 0;
    }
    
    /* Main container */
    .main {
        background: rgba(255, 255, 255, 0.95);
        border-radius: 15px;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
        padding: 20px;
        margin: 20px auto;
        max-width: 1200px;
    }
    
    /* Title styling */
    .stTitle {
        font-family: Arial, Helvetica, sans-serif;
        font-weight: bold;
        color: #2c3e50;
        text-align: center;
        font-size: 2.5em;
        margin-bottom: 10px;
    }
    
    /* Caption styling */
    .stCaption {
        font-family: Arial, Helvetica, sans-serif;
        font-weight: normal;
        color: #7f8c8d;
        font-style: italic;
        text-align: center;
        font-size: 1.1em;
    }
    
    /* Divider styling */
    hr {
        border: none;
        height: 2px;
        background: linear-gradient(90deg, #3498db, #2ecc71);
        margin: 20px 0;
    }
    
    /* Selectbox and checkbox styling */
    .stSelectbox, .stCheckbox {
        background: #ecf0f1;
        border-radius: 10px;
        padding: 10px;
        border: 1px solid #bdc3c7;
        margin-bottom: 15px;
    }
    
    /* Metric styling */
    .stMetric {
        background: linear-gradient(135deg, #3498db, #2980b9);
        color: white;
        border-radius: 15px;
        padding: 20px;
        text-align: center;
        box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
        font-size: 1.5em;
        font-weight: bold;
    }
    
    /* Subheader styling */
    .stSubheader {
        font-family: Arial, Helvetica, sans-serif;
        font-weight: bold;
        color: #34495e;
        border-left: 5px solid #2ecc71;
        padding-left: 15px;
        margin-top: 30px;
    }
    
    /* Button styling */
    .stButton button {
        background: linear-gradient(135deg, #2ecc71, #27ae60);
        color: white;
        border: none;
        border-radius: 25px;
        padding: 12px 25px;
        font-size: 1em;
        font-weight: bold;
        cursor: pointer;
        transition: background 0.3s ease;
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.2);
    }
    
    .stButton button:hover {
        background: linear-gradient(135deg, #27ae60, #229954);
    }
    
    /* Text area styling */
    .stTextArea textarea {
        background: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 10px;
        padding: 15px;
        font-family: Arial, Helvetica, sans-serif;
        font-size: 1em;
        resize: vertical;
    }
    
    /* Info and warning boxes */
    .stInfo, .stWarning {
        background: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 10px;
        padding: 15px;
        margin: 10px 0;
        color: #155724;
    }
    
    .stWarning {
        background: #fff3cd;
        border-color: #ffeaa7;
        color: #856404;
    }
    
    /* Markdown styling */
    .stMarkdown p {
        font-size: 1.1em;
        line-height: 1.6;
    }
    
    /* Columns styling */
    .stColumns {
        gap: 20px;
    }
    
    /* Footer styling */
    .stCaption:last-of-type {
        text-align: center;
        margin-top: 40px;
        font-size: 0.9em;
        color: #95a5a6;
    }
    
    /* Custom legend styling */
    .legend {
        display: flex;
        justify-content: space-around;
        background: #ecf0f1;
        border-radius: 10px;
        padding: 15px;
        margin: 20px 0;
    }
    
    .legend div {
        text-align: center;
        font-weight: bold;
    }
    
    /* Responsive design */
    @media (max-width: 768px) {
        .stTitle {
            font-size: 2em;
        }
        .stMetric {
            font-size: 1.2em;
        }
        .legend {
            flex-direction: column;
            gap: 10px;
        }
    }
</style>
""", unsafe_allow_html=True)

# --- App Layout ---
st.title("🏥 MediBill AI")
st.info(
    "Helping patients and families understand hospital bills with clear explanations, "
    "insurance awareness, and transparent communication."
)
with st.expander("⚙️ Settings & Preferences", expanded=False):
    lang_col, fam_col = st.columns(2)
    with lang_col:
        language = st.selectbox("🌐 Language", ["English", "Hindi", "Bengali"])
    with fam_col:
        # Defaulting to true as per user feedback
        family_mode = st.checkbox("👨‍👩‍👧 Family-friendly mode", value=True)

# Insurance Legend
st.write("--- 🛡️ Insurance Coverage Guide ---")
leg_c1, leg_c2, leg_c3 = st.columns(3)

with leg_c1:
    st.markdown('<div class="badge badge-success">🟢 Likely Covered</div>', unsafe_allow_html=True)
with leg_c2:
    st.markdown('<div class="badge badge-warning">🟡 Partial Cover</div>', unsafe_allow_html=True)
with leg_c3:
    st.markdown('<div class="badge badge-danger">🔴 Not Covered</div>', unsafe_allow_html=True)

st.divider()

# Main Content
items = fetch_bill()

if not items:
    st.warning("No bill items found in the database.")
else:
    total = sum(i["cost"] for i in items)
    
    # Using columns to center the metric on wider screens, usually looks better on mobile too
    _, mid_col, _ = st.columns([1, 2, 1])
    with mid_col:
        st.metric("💰 Total Bill", f"₹{total:,}")

    st.write("") # Spacer

    # Render Bill Items
    for i in items:
        item_name = i["item"]
        exp_key = f"explain_{item_name}"
        img_key = f"image_{item_name}"

        # Card container
        with st.container():
            st.markdown(f"""
            <div class="bill-item-card">
                <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                    <h3 style="margin:0; font-size:1.1rem; font-weight:700;">{item_name}</h3>
                    <span style="background:#e3f2fd; color:#1565c0; padding:4px 8px; border-radius:8px; font-weight:bold;">₹{i['cost']}</span>
                </div>
                <p style="color:#666; font-size:0.9rem; margin-top:5px;">📂 {i['category']}</p>
            </div>
            """, unsafe_allow_html=True)

            viz_col, info_col = st.columns(2)

            # Button 1: Visual Context
            with viz_col:
                if st.button("🖼️ Visual Ref", key=f"btn_img_{item_name}"):
                    if img_key not in st.session_state:
                        with st.spinner("Generating visual description..."):
                            prompt = f"""
                            Educational illustration description.
                            Item: {item_name}
                            Category: {i['category']}
                            Flat medical illustration, clean environment, no patients, no blood.
                            """
                            resp = query_llm(prompt)
                            st.session_state[img_key] = resp if resp else "Service unavailable"

            # Button 2: Explanation
            with info_col:
                if st.button("🧠 Coverage Info", key=f"btn_exp_{item_name}"):
                    if exp_key not in st.session_state:
                        with st.spinner("Analyzing policy..."):
                            lang_instruction = f"Language: {language}."
                            if language == "Hindi": lang_instruction += " (Devanagari script)."
                            if language == "Bengali": lang_instruction += " (Bengali script)."

                            prompt = f"""
                            You are MediBill AI. {lang_instruction}
                            Explain this hospital bill item in simple terms and classify insurance coverage.
                            Item: {item_name}
                            Category: {i['category']}
                            Cost: ₹{i['cost']}

                            Return strict JSON:
                            {{
                                "explanation": "...",
                                "insurance_status": "LIKELY_COVERED|PARTIALLY_COVERED|NOT_COVERED",
                                "insurance_note": "...",
                                "disclaimer": "..."
                            }}
                            """
                            raw_text = query_llm(prompt)
                            parsed = parse_json_response(raw_text)
                            st.session_state[exp_key] = parsed if parsed else "FAILED"

            # Results Display
            
            # 1. Image Result
            if img_key in st.session_state:
                val = st.session_state[img_key]
                if val == "FAILED":
                    st.error("Could not generate visual description.")
                else:
                    st.markdown("**Visual Reference:**")
                    st.info(val)
                    st.caption("Educational use only.")

            # 2. Explanation Result
            if exp_key in st.session_state:
                data = st.session_state[exp_key]
                
                if data == "FAILED":
                    st.error("Could not analyze item. Please try again.")
                else:
                    # Status Badge
                    status = data.get("insurance_status", "UNKNOWN")
                    if status == "LIKELY_COVERED":
                        st.success("✅ Likely Covered")
                    elif status == "PARTIALLY_COVERED":
                        st.warning("⚠️ Partially Covered")
                    else:
                        st.error("🛑 Not Usually Covered")

                    st.markdown(f"**Explanation:** {data.get('explanation')}")
                    st.caption(f"**Note:** {data.get('insurance_note')}")
                    
                    # Log to W&B
                    if wandb.run is not None:
                        wandb.log({
                            "item": item_name,
                            "status": status,
                            "lang": language
                        })

            st.write("---")

# Footer
st.markdown(
    "<div style='text-align: center; color: #888; font-size: 0.8rem;'>"
    "MediBill AI | Educational Tool Only | Not Medical/Financial Advice"
    "</div>", 
    unsafe_allow_html=True
)
