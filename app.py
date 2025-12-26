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
# W&B INIT
# =====================================================
wandb.init(
    project="medibill-ai",
    name="billing-insurance-monitoring",
    config={"model": "gemini"},
    reinit=True
)

# =====================================================
# GEMINI SETUP
# =====================================================
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("models/gemini-2.0-flash")

# =====================================================
# JSON EXTRACTOR
# =====================================================
def extract_json(text):
    try:
        text = text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
        start, end = text.find("{"), text.rfind("}") + 1
        return json.loads(text[start:end]) if start != -1 else None
    except Exception:
        return None

# =====================================================
# CACHED GEMINI CALL
# =====================================================
@st.cache_data(show_spinner=False)
def call_gemini(prompt: str) -> str:
    return model.generate_content(prompt).text

# =====================================================
# IMAGE PROMPT (MINIMAL)
# =====================================================
@st.cache_data(show_spinner=False)
def generate_image_prompt(item, category):
    prompt = f"""
Educational illustration description.
Item: {item}
Category: {category}
Rules: flat style, clean medical setting, no patients, no blood, no diagnosis.
"""
    return call_gemini(prompt)

# =====================================================
# DATABASE
# =====================================================
def get_bill_items():
    conn = sqlite3.connect("medibill.db")
    cur = conn.cursor()
    cur.execute("SELECT item_name, category, cost FROM bill_items")
    rows = cur.fetchall()
    conn.close()
    return [{"item_name": r[0], "category": r[1], "cost": r[2]} for r in rows]

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
with c1:
    language = st.selectbox("🌐 Language", ["Auto", "English", "Hindi", "Bengali"])
with c2:
    family_mode = st.checkbox("👨‍👩‍👧 Simple explanation")

# =====================================================
# INSURANCE LEGEND
# =====================================================
st.markdown("### 🛡️ Insurance Guide")
l1, l2, l3 = st.columns(3)
l1.markdown("🟢 Often covered")
l2.markdown("🟡 Policy dependent")
l3.markdown("🔴 Often not covered")
st.divider()

# =====================================================
# BILL DATA
# =====================================================
bill_items = get_bill_items()
st.metric("💰 Total Bill (₹)", sum(i["cost"] for i in bill_items))
st.divider()

# =====================================================
# MAIN LOOP
# =====================================================
for item in bill_items:
    st.subheader(item["item_name"])
    st.write(f"Category: {item['category']}")
    st.write(f"Cost: ₹{item['cost']}")

    colA, colB = st.columns(2)

    # -------- IMAGE PROMPT --------
    with colA:
        if st.button("🖼️ Illustration info", key=f"img_{item['item_name']}"):
            st.text_area(
                "Illustration description",
                generate_image_prompt(item["item_name"], item["category"]),
                height=120
            )
            st.caption("Educational visual reference only.")

    # -------- EXPLAIN BUTTON --------
    with colB:
        if st.button("🧠 Explain", key=f"btn_{item['item_name']}"):
            st.session_state[f"show_{item['item_name']}"] = True

    # -------- EXPLANATION --------
    if st.session_state.get(f"show_{item['item_name']}"):

        # ---- LANGUAGE RULE (ULTRA SHORT)
        lang_rule = ""
        if language == "English":
            lang_rule = "Language: English."
        elif language == "Hindi":
            lang_rule = "Language: Hindi (Devanagari only)."
        elif language == "Bengali":
            lang_rule = "Language: Bengali (বাংলা only)."

        # ---- CORE PROMPT (MINIMAL)
        prompt = f"""
You are MediBill AI.
{lang_rule}

Explain this bill item simply and classify insurance.

Item: {item['item_name']}
Category: {item['category']}
Cost: ₹{item['cost']}

JSON only:
{{
 "explanation": "...",
 "insurance_status": "LIKELY_COVERED|PARTIALLY_COVERED|NOT_COVERED",
 "insurance_note": "...",
 "disclaimer": "..."
}}
"""

        try:
            raw = call_gemini(prompt)
        except Exception:
            st.warning("AI temporarily unavailable. Using cached behavior.")
            st.stop()

        result = extract_json(raw)
        if not result:
            st.error("AI output format issue")
            st.code(raw)
            st.stop()

        # ---- DISPLAY
        status = result["insurance_status"]
        if status == "LIKELY_COVERED":
            st.markdown("🟢 Often covered by insurance")
        elif status == "PARTIALLY_COVERED":
            st.markdown("🟡 Coverage depends on policy")
        else:
            st.markdown("🔴 Often not covered")

        st.write(result["explanation"])
        st.info(result["insurance_note"])
        st.caption("Educational use only. Not medical or insurance advice.")

        # ---- LOGGING
        wandb.log({
            "item": item["item_name"],
            "insurance_status": status,
            "language": language,
            "family_mode": family_mode
        })

    st.divider()

# =====================================================
# FOOTER
# =====================================================
st.caption(
    "MediBill AI uses responsible GenAI to improve billing transparency."
)
