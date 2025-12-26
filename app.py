import streamlit as st
import google.generativeai as genai
import sqlite3
import os
import json
import wandb

# =====================================================
# PAGE CONFIG
# =====================================================
st.set_page_config(
    page_title="MediBill AI",
    page_icon="🏥",
    layout="centered"
)

# =====================================================
# W&B INIT (never breaks app)
# =====================================================
try:
    wandb.init(project="medibill-ai", reinit=True)
except Exception:
    pass

# =====================================================
# GEMINI SETUP
# =====================================================
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("models/gemini-2.0-flash")

# =====================================================
# JSON PARSER
# =====================================================
def extract_json(text):
    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        return json.loads(text[start:end])
    except Exception:
        return None

# =====================================================
# DATABASE
# =====================================================
def get_bill_items():
    conn = sqlite3.connect("medibill.db")
    cur = conn.cursor()
    cur.execute("SELECT item_name, category, cost FROM bill_items")
    rows = cur.fetchall()
    conn.close()
    return [{"item": r[0], "category": r[1], "cost": r[2]} for r in rows]

# =====================================================
# SAFE GEMINI CALL (NO CACHE, SESSION-STATE CONTROLLED)
# =====================================================
def safe_gemini(prompt):
    try:
        return model.generate_content(prompt).text
    except Exception:
        return None

# =====================================================
# HEADER
# =====================================================
st.title("🏥 MediBill AI")
st.caption("Clear explanations and insurance awareness for hospital bills.")
st.divider()

# =====================================================
# OPTIONS
# =====================================================
c1, c2 = st.columns(2)
language = c1.selectbox("🌐 Language", ["English", "Hindi", "Bengali"])
family_mode = c2.checkbox("👨‍👩‍👧 Simple explanation")

# =====================================================
# LEGEND
# =====================================================
st.markdown("### 🛡️ Insurance Guide")
l1, l2, l3 = st.columns(3)
l1.markdown("🟢 Often covered")
l2.markdown("🟡 Policy dependent")
l3.markdown("🔴 Often not covered")
st.divider()

# =====================================================
# DATA
# =====================================================
items = get_bill_items()
st.metric("💰 Total Bill (₹)", sum(i["cost"] for i in items))
st.divider()

# =====================================================
# MAIN LOOP (100% SAFE)
# =====================================================
for i in items:
    item = i["item"]
    key_explain = f"explain_result_{item}"
    key_image = f"image_result_{item}"

    st.subheader(item)
    st.write(f"Category: {i['category']}")
    st.write(f"Cost: ₹{i['cost']}")

    colA, colB = st.columns(2)

    # ---------------- IMAGE BUTTON ----------------
    if colA.button("🖼️ Illustration info", key=f"img_btn_{item}"):
        if key_image not in st.session_state:
            prompt = f"""
Educational illustration description.
Item: {item}
Category: {i['category']}
Flat medical illustration, no patients, no blood.
"""
            st.session_state[key_image] = safe_gemini(prompt) or "FAILED"

    if key_image in st.session_state:
        if st.session_state[key_image] == "FAILED":
            st.info("🖼️ Illustration unavailable due to AI limits.")
        else:
            st.text_area(
                "Illustration description",
                st.session_state[key_image],
                height=120
            )

    # ---------------- EXPLAIN BUTTON ----------------
    if colB.button("🧠 Explain", key=f"exp_btn_{item}"):
        if key_explain not in st.session_state:
            lang = (
                "Language: English."
                if language == "English"
                else "Language: Hindi (Devanagari only)."
                if language == "Hindi"
                else "Language: Bengali (বাংলা only)."
            )

            prompt = f"""
You are MediBill AI.
{lang}

Explain this bill item and classify insurance.

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
            raw = safe_gemini(prompt)
            st.session_state[key_explain] = extract_json(raw) if raw else "FAILED"

    if key_explain in st.session_state:
        result = st.session_state[key_explain]
        if result == "FAILED":
            st.warning("⚠️ Explanation unavailable due to AI limits.")
        else:
            status = result["insurance_status"]
            st.markdown(
                "🟢 Often covered" if status == "LIKELY_COVERED"
                else "🟡 Policy dependent" if status == "PARTIALLY_COVERED"
                else "🔴 Often not covered"
            )
            st.write(result["explanation"])
            st.info(result["insurance_note"])
            st.caption("Educational use only.")

    st.divider()

# =====================================================
# FOOTER
# =====================================================
st.caption("MediBill AI demonstrates responsible GenAI usage.")
