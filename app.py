import streamlit as st
import google.generativeai as genai
import sqlite3
import os
import json
import wandb

# --- 1. PAGE CONFIGURATION (Mobile Optimized) ---
st.set_page_config(
    page_title="MediBill AI",
    page_icon="🏥",
    layout="centered" # Centered is better for mobile reading
)

# --- 2. CUSTOM CSS (Fonts, Colors, Mobile Styles) ---
st.markdown("""
<style>
    /* IMPORT FONTS */
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&family=Open+Sans:wght@400;600&display=swap');

    /* GLOBAL STYLES */
    html, body, [class*="css"] {
        font-family: 'Open Sans', sans-serif;
        background-color: #f8f9fa; /* Light grey background */
        color: #333333;
    }

    /* HEADERS */
    h1, h2, h3 {
        font-family: 'Poppins', sans-serif;
        color: #2c3e50;
        font-weight: 700;
    }

    /* CARD STYLE (The container for bill items) */
    .stContainer {
        background-color: white;
        padding: 1rem;
        border-radius: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        margin-bottom: 1.5rem;
        border: 1px solid #eee;
    }

    /* BUTTONS (Full width for mobile touch targets) */
    .stButton > button {
        width: 100%;
        border-radius: 10px;
        font-family: 'Poppins', sans-serif;
        font-weight: 600;
        padding: 0.5rem 1rem;
    }

    /* METRIC HIGHLIGHT */
    div[data-testid="stMetricValue"] {
        color: #2980b9;
        font-family: 'Poppins', sans-serif;
        font-size: 2rem !important;
    }

    /* LEGEND BOXES */
    .legend-box {
        padding: 10px;
        border-radius: 8px;
        text-align: center;
        margin-bottom: 5px;
        font-size: 0.85rem;
        font-weight: 600;
    }
    .l-green { background-color: #e8f5e9; color: #2e7d32; border: 1px solid #c8e6c9; }
    .l-yellow { background-color: #fffde7; color: #f9a825; border: 1px solid #fff9c4; }
    .l-red { background-color: #ffebee; color: #c62828; border: 1px solid #ffcdd2; }

</style>
""", unsafe_allow_html=True)

# --- 3. INITIALIZATION (W&B, Gemini) ---
try:
    wandb.init(
        project="medibill-ai",
        name="billing-insurance-monitoring",
        reinit=True
    )
except Exception:
    pass

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("models/gemini-2.0-flash")

# --- 4. FUNCTIONS (Database & Parsing) ---
def extract_json(text):
    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        return json.loads(text[start:end])
    except Exception:
        return None

# RESTORED: ACTUAL DATABASE CONNECTION
def get_bill_items():
    try:
        conn = sqlite3.connect("medibill.db")
        cur = conn.cursor()
        cur.execute("SELECT item_name, category, cost FROM bill_items")
        rows = cur.fetchall()
        conn.close()
        return [
            {"item": r[0], "category": r[1], "cost": r[2]}
            for r in rows
        ]
    except Exception:
        # Fallback only if DB file is missing, to prevent crash
        return []

def safe_gemini(prompt):
    try:
        return model.generate_content(prompt).text
    except Exception:
        return None

# --- 5. APP UI LAYOUT ---

# HEADER
st.title("🏥 MediBill AI")
st.markdown("""
<div style='background-color: #e3f2fd; padding: 15px; border-radius: 10px; margin-bottom: 20px; border-left: 5px solid #2196f3;'>
    <small style='color: #0d47a1;'>
    Helping patients and families understand hospital bills with clear explanations, 
    insurance awareness, and transparent communication.
    </small>
</div>
""", unsafe_allow_html=True)

# USER OPTIONS (Styled for Mobile)
with st.expander("⚙️ Settings & Preferences", expanded=False):
    language = st.selectbox(
        "🌐 Preferred language for explanations",
        ["English", "Hindi", "Bengali"]
    )
    family_mode = st.checkbox(
        "👨‍👩‍👧 Explain in simple, family-friendly terms",
        value=True
    )

# INSURANCE LEGEND (Colorful & Compact)
st.markdown("##### 🛡️ Insurance Coverage Guide")
l1, l2, l3 = st.columns(3)
with l1:
    st.markdown('<div class="legend-box l-green">🟢 Likely Covered<br><span style="font-weight:400; font-size:0.7rem">Usually included</span></div>', unsafe_allow_html=True)
with l2:
    st.markdown('<div class="legend-box l-yellow">🟡 Partial<br><span style="font-weight:400; font-size:0.7rem">Check limits</span></div>', unsafe_allow_html=True)
with l3:
    st.markdown('<div class="legend-box l-red">🔴 Not Covered<br><span style="font-weight:400; font-size:0.7rem">Often excluded</span></div>', unsafe_allow_html=True)

st.divider()

# BILL DATA & TOTAL
items = get_bill_items()

if not items:
    st.warning("No bill items found in database (medibill.db).")
else:
    # Centered Metric for Mobile
    col_mid = st.columns([1,2,1])
    with col_mid[1]:
         st.metric("💰 Total Bill (₹)", sum(i["cost"] for i in items))
    
    st.write("") # Spacer

    # MAIN LOOP - CARD UI
    for i in items:
        item = i["item"]
        key_explain = f"explain_{item}"
        key_image = f"image_{item}"

        # CONTAINER STARTS (The White Card)
        with st.container():
            # Item Header
            st.markdown(f"""
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                <h3 style="margin: 0; font-size: 1.2rem;">{item}</h3>
                <span style="background-color: #e3f2fd; color: #1565c0; padding: 4px 8px; border-radius: 12px; font-weight: bold; font-size: 0.9rem;">₹{i['cost']}</span>
            </div>
            <p style="color: #666; font-size: 0.9rem; margin-top: -5px; font-style: italic;">📂 {i['category']}</p>
            <hr style="margin: 10px 0; border: 0; border-top: 1px solid #eee;">
            """, unsafe_allow_html=True)

            # Buttons in Columns (Mobile Friendly)
            colA, colB = st.columns(2)

            # --- IMAGE SECTION ---
            with colA:
                if st.button("🖼️ Learn what this looks like", key=f"img_{item}"):
                    if key_image not in st.session_state:
                        with st.spinner("Sketching..."):
                            img_prompt = f"""
                            Educational illustration description.
                            Item: {item}
                            Category: {i['category']}
                            Flat medical illustration, clean environment, no patients, no blood.
                            """
                            st.session_state[key_image] = safe_gemini(img_prompt) or "FAILED"

            # --- EXPLAIN SECTION ---
            with colB:
                if st.button("🧠 Understand coverage", key=f"exp_{item}"):
                    if key_explain not in st.session_state:
                        with st.spinner("Analyzing..."):
                            lang_rule = (
                                "Language: English." if language == "English"
                                else "Language: Hindi (Devanagari only)." if language == "Hindi"
                                else "Language: Bengali (বাংলা only)."
                            )

                            explain_prompt = f"""
                            You are MediBill AI.
                            {lang_rule}

                            Explain this hospital bill item in simple terms and classify insurance coverage.

                            Item: {item}
                            Category: {i['category']}
                            Cost: ₹{i['cost']}

                            JSON only:
                            {{
                            "explanation": "...",
                            "insurance_status": "LIKELY_COVERED|PARTIALLY_COVERED|NOT_COVERED",
                            "insurance_note": "...",
                            "disclaimer": "..."
                            }}
                            """
                            raw = safe_gemini(explain_prompt)
                            st.session_state[key_explain] = extract_json(raw) if raw else "FAILED"

            # --- DYNAMIC RESULTS DISPLAY (Inside the Card) ---
            
            # 1. Image Result
            if key_image in st.session_state:
                st.markdown("---")
                if st.session_state[key_image] == "FAILED":
                    st.info("🖼️ Visual explanation is temporarily unavailable due to AI usage limits.")
                else:
                    st.markdown("**🎨 Visual Reference:**")
                    st.info(st.session_state[key_image])
                    st.caption("These visuals are meant only for educational understanding, not for diagnosis or treatment.")

            # 2. Explanation Result
            if key_explain in st.session_state:
                st.markdown("---")
                result = st.session_state[key_explain]

                if result == "FAILED":
                    st.warning("⚠️ AI explanation is temporarily unavailable due to usage limits.")
                else:
                    status = result["insurance_status"]
                    
                    # Styled Status Box
                    if status == "LIKELY_COVERED":
                        st.markdown('<div style="background:#e8f5e9; color:#2e7d32; padding:10px; border-radius:8px; margin-bottom:10px;">🟢 <b>Likely Covered</b></div>', unsafe_allow_html=True)
                    elif status == "PARTIALLY_COVERED":
                        st.markdown('<div style="background:#fffde7; color:#f9a825; padding:10px; border-radius:8px; margin-bottom:10px;">🟡 <b>Partially Covered</b></div>', unsafe_allow_html=True)
                    else:
                        st.markdown('<div style="background:#ffebee; color:#c62828; padding:10px; border-radius:8px; margin-bottom:10px;">🔴 <b>Not Covered</b></div>', unsafe_allow_html=True)

                    st.markdown(f"**Explanation:** {result['explanation']}")
                    st.caption(f"📝 **Note:** {result['insurance_note']}")
                    
                    st.caption("⚠️ This explanation is for billing clarity only and does not replace professional medical or insurance advice.")

                    try:
                        wandb.log({
                            "item": item,
                            "insurance_status": status,
                            "language": language,
                            "family_mode": family_mode
                        })
                    except Exception:
                        pass
        
        # End of Card (Space between items)
        st.write("") 

# FOOTER 
st.divider()
st.caption(
    "MediBill AI is an educational tool designed to improve transparency in hospital billing. "
    "All information provided is for awareness and discussion purposes only."
)
