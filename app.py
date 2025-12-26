import streamlit as st
import google.generativeai as genai
import sqlite3
import os
import json
import wandb

# PAGE CONFIG
st.set_page_config(
    page_title="MediBill AI",
    page_icon="🏥",
    layout="centered"
)

# W&B INIT
try:
    wandb.init(
        project="medibill-ai",
        name="billing-insurance-monitoring",
        reinit=True
    )
except Exception:
    pass

# GEMINI SETUP
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("models/gemini-2.0-flash")


def extract_json(text):
    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        return json.loads(text[start:end])
    except Exception:
        return None

# DATABASE
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

def safe_gemini(prompt):
    try:
        return model.generate_content(prompt).text
    except Exception:
        return None

# HEADER 
st.title("🏥 MediBill AI")
st.caption(
    "Helping patients and families understand hospital bills with clear explanations, "
    "insurance awareness, and transparent communication."
)

st.divider()

# USER OPTIONS 
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

# INSURANCE LEGEND
st.markdown("---🛡️ Insurance Coverage Guide ---")

l1, l2, l3 = st.columns(3)
l1.markdown("🟢 **Likely Covered**  \nUsually included in standard policies")
l2.markdown("🟡 **Partially Covered**  \nDepends on policy limits or conditions")
l3.markdown("🔴 **Not Covered**  \nOften excluded from insurance")

st.divider()

# BILL DATA
items = get_bill_items()
st.metric("💰 Total Hospital Bill So Far (₹)", sum(i["cost"] for i in items))

st.divider()

# MAIN LOOP
for i in items:
    item = i["item"]
    key_explain = f"explain_{item}"
    key_image = f"image_{item}"

    st.subheader(item)
    st.write(f"**Category:** {i['category']}")
    st.write(f"**Cost:** ₹{i['cost']}")

    colA, colB = st.columns(2)

    # IMAGE BUTTON 
    if colA.button("🖼️ Learn what this medicine/procedure looks like", key=f"img_{item}"):
        if key_image not in st.session_state:
            img_prompt = f"""
Educational illustration description.
Item: {item}
Category: {i['category']}
Flat medical illustration, clean environment, no patients, no blood.
"""
            st.session_state[key_image] = safe_gemini(img_prompt) or "FAILED"

    if key_image in st.session_state:
        if st.session_state[key_image] == "FAILED":
            st.info(
                "🖼️ Visual explanation is temporarily unavailable due to AI usage limits."
            )
        else:
            st.text_area(
                "AI-generated description for an educational illustration:",
                st.session_state[key_image],
                height=160
            )
            st.caption(
                "These visuals are meant only for educational understanding, "
                "not for diagnosis or treatment."
            )

    # EXPLAIN BUTTON 
    if colB.button("🧠 Understand this charge & insurance coverage", key=f"exp_{item}"):
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

    # DISPLAY EXPLANATION
    if key_explain in st.session_state:
        result = st.session_state[key_explain]

        if result == "FAILED":
            st.warning(
                "⚠️ AI explanation is temporarily unavailable due to usage limits."
            )
        else:
            status = result["insurance_status"]

            if status == "LIKELY_COVERED":
                st.markdown("🟢 **This charge is likely covered by insurance**")
            elif status == "PARTIALLY_COVERED":
                st.markdown("🟡 **This charge may be partially covered**")
            else:
                st.markdown("🔴 **This charge is usually not covered**")

            st.write(result["explanation"])
            st.info(result["insurance_note"])
            st.caption(
                "⚠️ This explanation is for billing clarity only and does not replace "
                "professional medical or insurance advice."
            )

            try:
                wandb.log({
                    "item": item,
                    "insurance_status": status,
                    "language": language,
                    "family_mode": family_mode
                })
            except Exception:
                pass

    st.divider()

# FOOTER 
st.caption(
    "MediBill AI is an educational tool designed to improve transparency in hospital billing. "
    "All information provided is for awareness and discussion purposes only."
)

