import streamlit as st
import google.generativeai as genai
import sqlite3
import os
import json
import wandb

# JSON EXTRACTION HELPER
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

# PAGE CONFIG
st.set_page_config(
    page_title="MediBill AI",
    page_icon="🏥",
    layout="centered"
)

# W&B INIT
wandb.init(
    project="medibill-ai",
    name="billing-insurance-monitoring",
    config={"model": "gemini"}
)

# GEMINI SETUP
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("models/gemini-2.0-flash")

# IMAGE PROMPT GENERATION
def generate_image_prompt(item_name, category):
    prompt = f"""
Write a detailed prompt for generating an educational medical illustration.

Subject: {item_name}
Category: {category}

Requirements:
- Flat illustration style
- Clean medical environment
- No patients
- No blood
- No diagnosis
- No realistic anatomy
- Purpose: hospital billing explanation

Output ONLY the image prompt text.
"""
    response = model.generate_content(prompt)
    return response.text.strip()


# ACCESSING DATABASE
def get_bill_items():
    conn = sqlite3.connect("medibill.db")
    cursor = conn.cursor()
    cursor.execute("SELECT item_name, category, cost FROM bill_items")
    rows = cursor.fetchall()
    conn.close()

    return [
        {"item_name": row[0], "category": row[1], "cost": row[2]}
        for row in rows
    ]

# HEADER
st.title("🏥 MediBill AI")
st.caption(
    "Helping patients and families understand hospital bills with clear explanations and insurance awareness."
)

st.divider()

# OPTIONS FOR USERS
col1, col2 = st.columns(2)

with col1:
    language = st.selectbox(
        "🌐 Preferred language",
        ["Auto-detect", "English", "Hindi", "Bengali"]
    )

with col2:
    family_mode = st.checkbox("👨‍👩‍👧 Explain in simple terms for family members")


# INSURANCE COLOUR GUIDE
st.markdown("### 🛡️ Insurance Coverage Guide")

l1, l2, l3 = st.columns(3)
l1.markdown("🟢 **Often covered**")
l2.markdown("🟡 **Depends on policy**")
l3.markdown("🔴 **Often not covered**")

st.divider()


# BILL DATA
bill_items = get_bill_items()
total = sum(item["cost"] for item in bill_items)

st.metric("💰 Total Bill So Far (₹)", total)
st.divider()

for item in bill_items:
    with st.container():
        st.subheader(item["item_name"])
        st.write(f"**Category:** {item['category']}")
        st.write(f"**Cost:** ₹{item['cost']}")

        col_a, col_b = st.columns(2)

        # IMAGE PROMPT
        with col_a:
            if st.button("🖼️ View illustration description", key=f"img_{item['item_name']}"):
                img_prompt = generate_image_prompt(
                    item["item_name"],
                    item["category"]
                )
                st.text_area(
                    "AI-generated description for educational illustration:",
                    img_prompt,
                    height=200
                )
                st.caption(
                    "🖼️ This description helps generate safe educational visuals for billing clarity."
                )

        # EXPLAIN BUTTON
        with col_b:
            explain = st.button(
                "🧠 Understand this charge",
                key=f"exp_{item['item_name']}"
            )

        if explain:
        
            # LANGUAGE ENFORCEMENT
            language_instruction = ""

            if language == "English":
                language_instruction = "Respond in clear English."

            elif language == "Hindi":
                language_instruction = """
Respond ONLY in Hindi.
Use Devanagari script only.
Do NOT mix English.
"""

            elif language == "Bengali":
                language_instruction = """
LANGUAGE RULE (MANDATORY):
- Respond ONLY in Bengali (বাংলা)
- Use Bengali script only
- Do NOT use English or Hindi words
- Do NOT mix languages
- Keep language simple and polite
"""
            # PROMPT
            prompt = f"""
You are MediBill AI, a hospital billing assistant.

{language_instruction}

Explain the following hospital charge AND classify insurance coverage.

Item: {item['item_name']}
Category: {item['category']}
Cost: ₹{item['cost']}

You MUST respond ONLY in this JSON format:

{{
  "explanation": "Simple explanation for a non-medical person.",
  "insurance_status": "LIKELY_COVERED / PARTIALLY_COVERED / NOT_COVERED",
  "insurance_note": "Short explanation about insurance coverage uncertainty.",
  "disclaimer": "This is not medical or insurance advice."
}}

RULES:
- Insurance classification is mandatory.
- Do NOT give medical advice.
- Use very simple language if family mode is enabled.
- If user writes Hindi in English letters, respond in Hinglish.

IMPORTANT:
- Do not include markdown
- Do not include explanations outside JSON
- Output raw JSON only
"""

            response = model.generate_content(prompt)
            result = extract_json(response.text)

            if result is None:
                st.error("⚠️ AI response formatting issue")
                st.code(response.text)
                st.stop()

            # ---------------------------
            # INSURANCE DISPLAY
            # ---------------------------
            status = result["insurance_status"]

            if status == "LIKELY_COVERED":
                st.markdown("🟢 **Often covered by insurance**")
            elif status == "PARTIALLY_COVERED":
                st.markdown("🟡 **Coverage depends on policy**")
            else:
                st.markdown("🔴 **Often not covered under standard policies**")

            st.write(result["explanation"])
            st.info(result["insurance_note"])
            st.caption(
                "⚠️ This explanation is for billing clarity only. "
                "It does not replace medical or insurance advice."
            )
            
            # W&B LOGGING
            wandb.log({
                "item": item["item_name"],
                "category": item["category"],
                "insurance_status": status,
                "language": language,
                "family_mode": family_mode,
                "response_length": len(result["explanation"])
            })

        st.divider()

# FOOTER
st.caption(
    "MediBill AI is designed to improve transparency in hospital billing. "
    "All information shown is educational and supports discussions with hospitals and insurers."
)
