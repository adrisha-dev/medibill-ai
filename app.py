import streamlit as st
import google.generativeai as genai
import sqlite3
import os
import json
import wandb

# -------------------- PAGE CONFIG --------------------
st.set_page_config(
    page_title="MediBill AI",
    page_icon="🏥",
    layout="centered"
)

# -------------------- W&B INIT --------------------
# Tracking user interactions and insurance classification trends
try:
    wandb.init(
        project="medibill-ai",
        name="billing-insurance-monitoring",
        reinit=True
    )
except Exception as e:
    print("W&B init skipped:", e)

# -------------------- GEMINI SETUP --------------------
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("models/gemini-2.0-flash")


# Gemini sometimes adds extra text around JSON,
# so we defensively extract the first valid JSON object.
def extract_json(text):
    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        return json.loads(text[start:end])
    except Exception:
        return None


# -------------------- DATABASE ACCESS --------------------
def get_bill_items():
    conn = sqlite3.connect("medibill.db")
    cur = conn.cursor()
    cur.execute("SELECT item_name, category, cost FROM bill_items")
    rows = cur.fetchall()
    conn.close()

    return [
        {"item": r[0], "category": r[1], "cost": r[2]}
        for r in rows
    ]


# Centralized Gemini wrapper to avoid app crashes on quota / network issues
def safe_gemini(prompt):
    try:
        return model.generate_content(prompt).text
    except Exception as e:
        print("Gemini call failed:", e)
        return None


# -------------------- CUSTOM CSS --------------------
# Light styling to avoid default Streamlit look while staying readable
st.markdown("""
<style>
    body {
        font-family: Arial, Helvetica, sans-serif;
        background: #f5f7fa;
        color: #333;
    }

    .main {
        background: rgba(255, 255, 255, 0.95);
        border-radius: 12px;
        box-shadow: 0 8px 20px rgba(0, 0, 0, 0.1);
        padding: 20px;
        max-width: 1200px;
        margin: auto;
    }

    .stTitle {
        font-weight: bold;
        color: #2c3e50;
        text-align: center;
        font-size: 2.3em;
    }

    .stCaption {
        text-align: center;
        color: #7f8c8d;
        font-style: italic;
        font-size: 1.05em;
    }

    hr {
        border: none;
        height: 2px;
        background: #2ecc71;
        margin: 20px 0;
    }

    .stMetric {
        background: #3498db;
        color: white;
        border-radius: 12px;
        padding: 18px;
        text-align: center;
        font-weight: bold;
    }

    .stSubheader {
        font-weight: bold;
        color: #34495e;
        border-left: 5px solid #2ecc71;
        padding-left: 12px;
        margin-top: 25px;
    }

    .stButton button {
        background: #2ecc71;
        color: white;
        border-radius: 20px;
        font-weight: bold;
        padding: 10px 22px;
    }

    .stButton button:hover {
        background: #27ae60;
    }

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

    @media (max-width: 768px) {
        .legend {
            flex-direction: column;
            gap: 10px;
        }
    }
</style>
""", unsafe_allow_html=True)


# -------------------- HEADER --------------------
st.title("🏥 MediBill AI")
st.caption(
    "Helping patients and families understand hospital bills with clear explanations, "
    "insurance awareness, and transparent communication."
)

st.divider()


# -------------------- USER OPTIONS --------------------
col1, col2 = st.columns(2)

with col1:
    language = st.selectbox(
        "🌐 Preferred language for explanations",
        ["English", "Hindi", "Bengali"]
    )

with col2:
    family_mode = st.checkbox(
        "👨‍👩‍👧 Explain in simple, family-friendly terms"
    )


# -------------------- INSURANCE LEGEND --------------------
st.markdown("### 🛡️ Insurance Coverage Guide")

st.markdown("""
<div class="legend">
    <div>🟢 Likely Covered<br><small>Usually included in standard policies</small></div>
    <div>🟡 Partially Covered<br><small>Depends on policy limits</small></div>
    <div>🔴 Not Covered<br><small>Often excluded</small></div>
</div>
""", unsafe_allow_html=True)

st.divider()


# -------------------- BILL DATA --------------------
items = get_bill_items()
total_cost = sum(i["cost"] for i in items)
st.metric("💰 Total Hospital Bill So Far (₹)", total_cost)

st.divider()


# -------------------- MAIN RENDER LOOP --------------------
# Each item gets visual context + insurance explanation
for i in items:
    item = i["item"]
    key_explain = f"explain_{item}"
    key_image = f"image_{item}"

    st.subheader(item)
    st.write(f"**Category:** {i['category']}")
    st.write(f"**Cost:** ₹{i['cost']}")

    colA, colB = st.columns(2)

    # ---- Visual context button ----
    if colA.button("🖼️ What does this look like?", key=f"img_{item}"):
        if key_image not in st.session_state:
            img_prompt = f"""
Educational illustration description.
Item: {item}
Category: {i['category']}
Flat medical illustration, clean environment.
No patients, no blood, no surgical visuals.
"""
            st.session_state[key_image] = safe_gemini(img_prompt) or "FAILED"

    if key_image in st.session_state:
        if st.session_state[key_image] == "FAILED":
            st.info("🖼️ Visual explanation is temporarily unavailable.")
        else:
            st.text_area(
                "AI-generated visual description:",
                st.session_state[key_image],
                height=150
            )
            st.caption("For educational understanding only.")

    # ---- Explanation button ----
    if colB.button("🧠 Why was this charged?", key=f"exp_{item}"):
        if key_explain not in st.session_state:

            lang_rule = (
                "Language: English."
                if language == "English"
                else "Language: Hindi (Devanagari only)."
                if language == "Hindi"
                else "Language: Bengali (বাংলা only)."
            )

            explain_prompt = f"""
You are MediBill AI.
{lang_rule}

Explain this hospital bill item in simple terms and classify insurance coverage.

Item: {item}
Category: {i['category']}
Cost: ₹{i['cost']}

Return a valid JSON object with:
- explanation
- insurance_status (LIKELY_COVERED / PARTIALLY_COVERED / NOT_COVERED)
- insurance_note
- disclaimer
"""

            ai_response = safe_gemini(explain_prompt)
            st.session_state[key_explain] = extract_json(ai_response) if ai_response else "FAILED"

    # ---- Display explanation ----
    if key_explain in st.session_state:
        result = st.session_state[key_explain]

        if result == "FAILED":
            st.warning("⚠️ Explanation is temporarily unavailable.")
        else:
            status = result["insurance_status"]

            if status == "LIKELY_COVERED":
                st.markdown("🟢 **Likely covered by insurance**")
            elif status == "PARTIALLY_COVERED":
                st.markdown("🟡 **May be partially covered**")
            else:
                st.markdown("🔴 **Usually not covered**")

            st.write(result["explanation"])
            st.info(result["insurance_note"])
            st.caption("This explanation is for billing clarity only.")

            try:
                wandb.log({
                    "item": item,
                    "insurance_status": status,
                    "language": language,
                    "family_mode": family_mode
                })
            except Exception as e:
                print("W&B log failed:", e)

    st.divider()


# -------------------- FOOTER --------------------
st.caption(
    "MediBill AI is an educational tool designed to improve transparency in hospital billing. "
    "It does not replace professional medical or insurance advice."
)
