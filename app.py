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
    Attempts to extract JSON from LLM response using regex.
    Gemini often wraps json in markdown code blocks.
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

def get_db_connection():
    # Using local sqlite for prototype, move to Postgres for prod
    try:
        conn = sqlite3.connect("medibill.db")
        return conn
    except sqlite3.Error as e:
        st.error(f"Database connection failed: {e}")
        return None

def fetch_bill_items():
    conn = get_db_connection()
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

# --- Custom Styles ---
st.markdown("""
<style>
    /* Base font settings */
    html, body, [class*="css"] {
        font-family: 'Open Sans', sans-serif;
        color: #333;
    }
    
    /* Clean card look for mobile readability */
    .bill-item-card {
        background-color: white;
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        margin-bottom: 1.5rem;
        border: 1px solid #f0f0f0;
    }
    
    /* Prominent metrics */
    div[data-testid="stMetricValue"] {
        color: #2980b9; 
        font-size: 2.2rem !important;
    }

    /* Legend badges */
    .badge {
        padding: 8px 12px;
        border-radius: 6px;
        text-align: center;
        font-weight: 600;
        font-size: 0.85rem;
        margin-bottom: 5px;
    }
    .badge-success { background-color: #e8f5e9; color: #2e7d32; border: 1px solid #c8e6c9; }
    .badge-warning { background-color: #fffde7; color: #f9a825; border: 1px solid #fff9c4; }
    .badge-danger { background-color: #ffebee; color: #c62828; border: 1px solid #ffcdd2; }
    
    /* Mobile-friendly buttons */
    .stButton > button {
        width: 100%;
        border-radius: 8px;
        height: 2.8rem;
    }
</style>
""", unsafe_allow_html=True)

# --- App Layout ---

st.title("🏥 MediBill AI")

# Info Box
st.info(
    "Helping patients and families understand hospital bills with clear explanations, "
    "insurance awareness, and transparent communication."
)

# Settings Panel
with st.expander("⚙️ Settings & Preferences", expanded=False):
    lang_col, fam_col = st.columns(2)
    with lang_col:
        language = st.selectbox("🌐 Language", ["English", "Hindi", "Bengali"])
    with fam_col:
        # Defaulting to true as per user feedback
        family_mode = st.checkbox("👨‍👩‍👧 Family-friendly mode", value=True)

# Insurance Legend
st.write("##### 🛡️ Insurance Coverage Guide")
leg_c1, leg_c2, leg_c3 = st.columns(3)

with leg_c1:
    st.markdown('<div class="badge badge-success">🟢 Likely Covered</div>', unsafe_allow_html=True)
with leg_c2:
    st.markdown('<div class="badge badge-warning">🟡 Partial Cover</div>', unsafe_allow_html=True)
with leg_c3:
    st.markdown('<div class="badge badge-danger">🔴 Not Covered</div>', unsafe_allow_html=True)

st.divider()

# Main Content
items = fetch_bill_items()

if not items:
    st.warning("No bill items found in the database.")
else:
    # Total Cost Metric
    total = sum(i["cost"] for i in items)
    
    # Using columns to center the metric on wider screens, usually looks better on mobile too
    _, mid_col, _ = st.columns([1, 2, 1])
    with mid_col:
        st.metric("💰 Total Bill", f"₹{total:,}")

    st.write("") # Spacer

    # Render Bill Items
    for i in items:
        item_name = i["item"]
        
        # Session state keys
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
