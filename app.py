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
# W&B INIT (safe even if AI fails)
# =====================================================
wandb.init(
    project="medibill-ai",
    name="billing-insurance-monitoring",
    reinit=True
)

# =====================================================
# GEMINI SETUP
# =====================================================
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("models/gemini-2.0-flash")

# =====================================================
# SAFE JSON EXTRACTOR
# =====================================================
def extract_json(text):
    try:
        text = text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
        start = text.find("{")
        end = text.rfind("}") + 1
        if start == -1 or end == -1:
            return None
        return json.loads(text[start:end])
    except Exception:
        return None

# =====================================================
# HARD-CACHED GEMINI CALL (CRITICAL)
# =====================================================
@st.cache_data(show_spinner=False)
def call_gemini(prompt: str) -> str:
    return model.generate_content(prompt).text

# =====================================================
# SAFE IMAGE PROMPT (NON-CRITICAL)
# =====================================================
@st.cache_data(show_spinner=False)
def generate_image_prompt(item, category):
    prompt = f"""
Educational illustration description.
Item: {item}
Category: {category}
Rules: flat style, clean medical setting, no patients, no blood, no diagnosis.
"""
    try:
        return call_gemini(prompt)
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
    return [{"item_name": r[0], "category": r[1], "cost": r[2]} for r in rows]

# =====================================================
# HEADER
# =====================================================
st.title("🏥 MediBill AI")
st.caption("Clear explanations and insurance awareness for hospital bills.")
st.divider()

# =====================================================
# USER OPTIONS
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
# MAIN LOOP (CLICK SAFE)
# =====================================================
for item in bill_items:
    item_id = item["item_name"]

    st.subheader(item_id)
    st.write(f"Category: {item['category']}")
    st.write(f"Cost: ₹{item['cost']}")

    colA, colB = st.columns(2)

    # ---------- IMAGE PROMPT ----------
    with colA:
        if st.button("🖼️ Illustration info", key=f"img_{item_id}"):
            img_prompt = generate_image_prompt(item_id, item["category"])
            if img_prompt:
                st.text_area(
                    "Illustration description",
                    img_prompt,
                    height=120
                )
                st.caption("Educational visual reference only.")
            else:
                st.info(
                    "🖼️ Illustration generation is temporarily unavailable "
                    "due to AI usage limits."
                )

    # ---------- EXPLAIN BUTTON (LOCKED) ----------
    with colB:
        if st.button("🧠 Explain", key=f"btn_{item_id}"):
            st.session_state[f"show_{item_id}"] = True

    # ---------- EXPLANATION (ONLY ONCE PER ITEM) ----------
    if st.session_state.get(f"show_{item_id}"):

        # ---- Short language rule ----
        lang_rule = ""
        if language == "English":
            lang_rule = "Language: English."
        elif language == "Hindi":
            lang_rule = "Language: Hindi (Devanagari only)."
        elif language == "Bengali":
            lang_rule = "Language: Bengali (বাংলা only)."

        # ---- Optimised core prompt ----
        prompt = f"""
You are MediBill AI.
{lang_rule}

Explain this bill item and classify insurance.

Item: {item_id}
Category: {item['category']}
Cost: ₹{item['cost']}

Respond ONLY in JSON:
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
            st.warning(
                "⚠️ AI usage limit reached. "
                "Using cached or demo-safe behaviour."
            )
            st.stop()

        result = extract_json(raw)
        if not result:
            st.error("AI response format issue")
            st.code(raw)
            st.stop()

        # ---- Insurance display ----
        status = result["insurance_status"]
        if status == "LIKELY_COVERED_
