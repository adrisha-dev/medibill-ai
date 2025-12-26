import streamlit as st
import google.generativeai as genai
import sqlite3
import os
import json
import wandb
import time

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="MediBill AI",
    page_icon="🏥",
    layout="wide",  # Changed to wide for better dashboard feel
    initial_sidebar_state="expanded"
)

# --- CUSTOM CSS STYLING ---
st.markdown("""
<style>
    /* Main Background */
    .stApp {
        background-color: #f8f9fa;
    }
    
    /* Card Styling */
    .bill-card {
        background-color: white;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        margin-bottom: 20px;
        border: 1px solid #e0e0e0;
    }
    
    /* Headers */
    h1, h2, h3 {
        color: #0f172a;
        font-family: 'Helvetica Neue', sans-serif;
    }
    
    /* Metrics */
    div[data-testid="stMetricValue"] {
        color: #2563eb;
        font-weight: bold;
    }
    
    /* Status Badges */
    .badge-green { background-color: #dcfce7; color: #166534; padding: 4px 8px; border-radius: 4px; font-size: 0.8em; font-weight: bold;}
    .badge-yellow { background-color: #fef9c3; color: #854d0e; padding: 4px 8px; border-radius: 4px; font-size: 0.8em; font-weight: bold;}
    .badge-red { background-color: #fee2e2; color: #991b1b; padding: 4px 8px; border-radius: 4px; font-size: 0.8em; font-weight: bold;}
</style>
""", unsafe_allow_html=True)

# --- SETUP & INITIALIZATION ---

# 1. Initialize Mock Database (For Demo Purposes)
def init_dummy_db():
    conn = sqlite3.connect("medibill.db")
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS bill_items (id INTEGER PRIMARY KEY, item_name TEXT, category TEXT, cost INTEGER)")
    # Check if empty, if so, fill it
    cur.execute("SELECT count(*) FROM bill_items")
    if cur.fetchone()[0] == 0:
        data = [
            ("MRI Scan - Brain", "Diagnostics", 12000),
            ("Paracetamol IV", "Pharmacy", 450),
            ("Consultation - Neurologist", "Professional Fees", 1500),
            ("Bed Charges (ICU)", "Room & Board", 8500),
            ("Surgical Kit Type B", "Consumables", 3200)
        ]
        cur.executemany("INSERT INTO bill_items (item_name, category, cost) VALUES (?,?,?)", data)
        conn.commit()
    conn.close()

init_dummy_db()

# 2. W&B Init (Safe Mode)
if "wandb_init" not in st.session_state:
    try:
        wandb.init(project="medibill-ai", name="billing-ui-v2", reinit=True)
        st.session_state["wandb_init"] = True
    except Exception:
        pass

# 3. Gemini Setup
api_key = os.getenv("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("models/gemini-2.0-flash")
else:
    model = None # Handle missing key gracefully

# --- HELPER FUNCTIONS ---

def extract_json(text):
    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        return json.loads(text[start:end])
    except Exception:
        return None

def get_bill_items():
    conn = sqlite3.connect("medibill.db")
    cur = conn.cursor()
    cur.execute("SELECT item_name, category, cost FROM bill_items")
    rows = cur.fetchall()
    conn.close()
    return [{"item": r[0], "category": r[1], "cost": r[2]} for r in rows]

def safe_gemini(prompt):
    if not model:
        time.sleep(1) # Simulate delay
        return None
    try:
        return model.generate_content(prompt).text
    except Exception:
        return None

# --- SIDEBAR UI ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2966/2966327.png", width=60)
    st.title("MediBill Settings")
    st.markdown("Customize your billing assistant.")
    
    st.divider()
    
    language = st.selectbox(
        "🌐 Explanation Language",
        ["English", "Hindi", "Bengali"]
    )
    
    family_mode = st.toggle(
        "👨‍👩‍👧 Simple/Family Mode", value=True,
        help="Simplifies medical jargon for easier understanding."
    )
    
    st.divider()
    
    if not api_key:
        st.error("⚠️ GEMINI_API_KEY not found in environment variables. AI features will be simulated or fail.")
    else:
        st.success("✅ AI System Online")

# --- MAIN UI ---

# Header Section
c1, c2 = st.columns([3, 1])
with c1:
    st.title("🏥 MediBill AI")
    st.markdown("#### Your Intelligent Hospital Bill Assistant")
    st.caption("We help you decode medical jargon and understand insurance coverage transparently.")

with c2:
    # Legend in a compact view
    with st.popover("🛡️ Insurance Legend"):
        st.markdown('<span class="badge-green">Likely Covered</span> Included in standard policies', unsafe_allow_html=True)
        st.divider()
        st.markdown('<span class="badge-yellow">Partially Covered</span> Depends on limits', unsafe_allow_html=True)
        st.divider()
        st.markdown('<span class="badge-red">Not Covered</span> Often excluded', unsafe_allow_html=True)

st.divider()

# Metric Dashboard
items = get_bill_items()
total_cost = sum(i["cost"] for i in items)

col_metric1, col_metric2, col_metric3 = st.columns(3)
col_metric1.metric("Total Items", len(items), delta=f"{len(items)} scanned")
col_metric2.metric("Estimated Total", f"₹ {total_cost:,.2f}")
col_metric3.metric("Review Status", "Pending", delta_color="off")

st.markdown("<br>", unsafe_allow_html=True)

# --- MAIN ITEM LOOP ---

st.subheader("📋 Bill Item Breakdown")

for i in items:
    item_name = i["item"]
    category = i["category"]
    cost = i["cost"]
    
    # Unique keys
    key_explain = f"explain_{item_name}"
    key_image = f"image_{item_name}"

    # --- CARD CONTAINER ---
    with st.container():
        # HTML visual wrapper (using the CSS defined above)
        st.markdown(f"""
        <div class="bill-card">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <h3 style="margin:0;">{item_name}</h3>
                <h3 style="margin:0; color:#2563eb;">₹{cost:,}</h3>
            </div>
            <p style="color:gray; font-size:0.9em;">📂 {category}</p>
        </div>
        """, unsafe_allow_html=True)

        # Interaction Row
        c_act1, c_act2 = st.columns([1, 1])
        
        # 1. VISUAL BUTTON
        with c_act1:
            if st.button(f"🖼️ Show Visual Reference", key=f"btn_img_{item_name}", use_container_width=True):
                if key_image not in st.session_state:
                    with st.status("🎨 Generative AI is creating a sketch...", expanded=True) as status:
                        img_prompt = f"Educational illustration of {item_name} ({category}). Flat vector style."
                        st.session_state[key_image] = safe_gemini(img_prompt) or "AI Visual Generation Unavailable (Mock Response)"
                        status.update(label="Visual Generated!", state="complete", expanded=False)
        
        # 2. EXPLAIN BUTTON
        with c_act2:
            if st.button(f"🧠 Analyze Coverage", key=f"btn_exp_{item_name}", type="primary", use_container_width=True):
                if key_explain not in st.session_state:
                    with st.status("🔍 Analyzing policy & medical data...", expanded=True) as status:
                        lang_rule = f"Language: {language}."
                        explain_prompt = f"""
                        You are MediBill AI. {lang_rule}
                        Explain item: {item_name} (Category: {category}, Cost: {cost}).
                        JSON only: {{ "explanation": "...", "insurance_status": "LIKELY_COVERED|PARTIALLY_COVERED|NOT_COVERED", "insurance_note": "..." }}
                        """
                        raw = safe_gemini(explain_prompt)
                        st.session_state[key_explain] = extract_json(raw) if raw else {
                            "explanation": "Simulated: This is a standard procedure usually covered by insurance.",
                            "insurance_status": "LIKELY_COVERED",
                            "insurance_note": "Subject to annual limits."
                        }
                        status.update(label="Analysis Complete", state="complete", expanded=False)

        # --- RESULT DISPLAY AREA (EXPANDERS) ---
        
        # Visual Result
        if key_image in st.session_state:
            with st.expander("🖼️ Visual Reference", expanded=True):
                st.info(f"**AI Description:** {st.session_state[key_image]}")
                st.caption("*Note: Actual image generation requires DALL-E/Midjourney integration. This text describes the prompt.*")

        # Analysis Result
        if key_explain in st.session_state:
            res = st.session_state[key_explain]
            if res != "FAILED":
                with st.expander("🧠 Coverage Analysis", expanded=True):
                    # Status Badge Logic
                    status = res.get("insurance_status", "UNKNOWN")
                    if status == "LIKELY_COVERED":
                        st.markdown('<span class="badge-green">✅ Likely Covered</span>', unsafe_allow_html=True)
                    elif status == "PARTIALLY_COVERED":
                        st.markdown('<span class="badge-yellow">⚠️ Partially Covered</span>', unsafe_allow_html=True)
                    else:
                        st.markdown('<span class="badge-red">❌ Not Covered</span>', unsafe_allow_html=True)
                    
                    st.markdown(f"**Analysis:** {res.get('explanation')}")
                    st.warning(f"**Note:** {res.get('insurance_note')}")

    # Spacer between cards
    st.markdown("<br>", unsafe_allow_html=True)

# --- FOOTER ---
st.divider()
st.markdown(
    """
    <div style="text-align: center; color: gray; font-size: 0.8em;">
        MediBill AI Project | Designed for Transparency<br>
        Not medical or financial advice.
    </div>
    """, unsafe_allow_html=True
)
