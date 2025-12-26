import streamlit as st
import google.generativeai as genai
import sqlite3
import os
import json
import wandb
import time

# --- 1. PAGE CONFIGURATION (Must be first) ---
st.set_page_config(
    page_title="MediBill AI",
    page_icon="🏥",
    layout="wide",  # WIDE layout is key for the new look
    initial_sidebar_state="expanded"
)

# --- 2. CUSTOM CSS (The "Beautiful" Part) ---
st.markdown("""
<style>
    /* Light grey background for the whole app */
    .stApp {
        background-color: #f0f2f6;
    }
    
    /* White Card Styling for Bill Items */
    .bill-card {
        background-color: #ffffff;
        padding: 25px;
        border-radius: 15px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.05);
        border: 1px solid #e0e0e0;
        margin-bottom: 20px;
    }
    
    /* Metrics Styling */
    div[data-testid="stMetricValue"] {
        font-size: 28px;
        color: #2563eb;
    }
    
    /* Custom Badges */
    .badge-green { background-color: #d1fae5; color: #065f46; padding: 5px 10px; border-radius: 12px; font-weight: bold; font-size: 0.85em; }
    .badge-yellow { background-color: #fef3c7; color: #92400e; padding: 5px 10px; border-radius: 12px; font-weight: bold; font-size: 0.85em; }
    .badge-red { background-color: #fee2e2; color: #991b1b; padding: 5px 10px; border-radius: 12px; font-weight: bold; font-size: 0.85em; }
</style>
""", unsafe_allow_html=True)

# --- 3. DATABASE MOCK (So it works instantly for you) ---
def get_bill_items():
    # If you have a real DB, uncomment the sqlite3 code below.
    # For now, I am returning dummy data so you can SEE the UI immediately.
    return [
        {"item": "MRI - Brain Scan (Contrast)", "category": "Diagnostics", "cost": 14500},
        {"item": "Consultation - Dr. Sharma", "category": "Professional Fees", "cost": 2000},
        {"item": "IV Cannula & Fluids", "category": "Consumables", "cost": 850},
        {"item": "ICU Room Charges (Day 1)", "category": "Room & Board", "cost": 12000}
    ]

# --- 4. AI & LOGGING SETUP ---
try:
    if os.getenv("GEMINI_API_KEY"):
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        model = genai.GenerativeModel("models/gemini-2.0-flash")
    else:
        model = None
except Exception:
    model = None

try:
    wandb.init(project="medibill-ai", name="ui-update", reinit=True)
except Exception:
    pass

# --- 5. HELPER FUNCTIONS ---
def extract_json(text):
    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        return json.loads(text[start:end])
    except Exception:
        return None

def safe_gemini(prompt):
    # If no key, simulate a delay and return dummy text so UI doesn't break
    if not model:
        time.sleep(1.5) 
        return None 
    try:
        return model.generate_content(prompt).text
    except Exception:
        return None

# --- 6. SIDEBAR UI ---
with st.sidebar:
    st.title("⚙️ Settings")
    st.markdown("Customize your billing assistant.")
    
    language = st.selectbox("Language", ["English", "Hindi", "Bengali"])
    family_mode = st.toggle("Family Friendly Mode", value=True)
    
    st.divider()
    
    # Legend in Sidebar
    st.subheader("Insurance Legend")
    st.markdown('<span class="badge-green">Likely Covered</span>', unsafe_allow_html=True)
    st.caption("Standard policy inclusion")
    st.markdown('<span class="badge-yellow">Partially Covered</span>', unsafe_allow_html=True)
    st.caption("Limits apply")
    st.markdown('<span class="badge-red">Not Covered</span>', unsafe_allow_html=True)
    st.caption("Usually excluded")

# --- 7. MAIN DASHBOARD ---

st.title("🏥 MediBill AI")
st.markdown("### Patient Financial Dashboard")

# Top Metrics
items = get_bill_items()
total = sum(i['cost'] for i in items)

m1, m2, m3 = st.columns(3)
m1.metric("Total Bill Amount", f"₹ {total:,}")
m2.metric("Items to Review", len(items))
m3.metric("Policy Status", "Active", delta="Verified")

st.divider()

# --- 8. BILL ITEM CARDS ---

for i in items:
    item = i["item"]
    cost = i["cost"]
    cat = i["category"]
    
    # Keys for state
    key_exp = f"exp_{item}"
    
    # CARD HTML
    st.markdown(f"""
    <div class="bill-card">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <h3 style="margin:0; color:#1e293b;">{item}</h3>
            <h3 style="margin:0; color:#2563eb;">₹{cost:,}</h3>
        </div>
        <p style="color:#64748b; margin-top:5px; font-size:0.9rem;">📂 {cat}</p>
    </div>
    """, unsafe_allow_html=True)

    # ACTION BUTTONS (Below the card)
    c1, c2 = st.columns([1, 4])
    
    with c1:
        if st.button(f"🧠 Analyze", key=f"btn_{item}", use_container_width=True, type="primary"):
            if key_exp not in st.session_state:
                with st.status("🤖 AI is reading insurance policies...", expanded=True) as status:
                    prompt = f"""
                    Role: MediBill AI. Lang: {language}.
                    Explain item: {item} ({cat}) - Cost: {cost}.
                    JSON: {{ "explanation": "...", "insurance_status": "LIKELY_COVERED|PARTIALLY_COVERED|NOT_COVERED", "insurance_note": "..." }}
                    """
                    raw = safe_gemini(prompt)
                    # Fallback if no API key
                    fallback = {
                        "explanation": "This is a simulated explanation because the API Key is missing or failed.",
                        "insurance_status": "LIKELY_COVERED", 
                        "insurance_note": "Check your specific policy limits."
                    }
                    st.session_state[key_exp] = extract_json(raw) if raw else fallback
                    status.update(label="Analysis Complete", state="complete", expanded=False)

    # RESULTS DISPLAY
    if key_exp in st.session_state:
        data = st.session_state[key_exp]
        if data:
            with st.expander("See AI Analysis", expanded=True):
                # Badge Logic
                status_code = data.get("insurance_status", "")
                if status_code == "LIKELY_COVERED":
                    st.markdown('<span class="badge-green">✅ Likely Covered</span>', unsafe_allow_html=True)
                elif status_code == "PARTIALLY_COVERED":
                    st.markdown('<span class="badge-yellow">⚠️ Partially Covered</span>', unsafe_allow_html=True)
                else:
                    st.markdown('<span class="badge-red">🔴 Not Covered</span>', unsafe_allow_html=True)
                
                st.write("") # Spacer
                st.write(f"**Explanation:** {data.get('explanation')}")
                st.info(f"**Note:** {data.get('insurance_note')}")
    
    st.markdown("<br>", unsafe_allow_html=True)

# Footer
st.markdown("---")
st.caption("MediBill AI Demo | Designed for Educational Purposes Only")
