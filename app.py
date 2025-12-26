import streamlit as st
import google.generativeai as genai
import sqlite3
import os
import json
import wandb

def extract_json(text):
    """
    Safely extract JSON from an AI response.
    Handles extra text and code blocks.
    """
    try:
        # Remove markdown code blocks if present
        text = text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]

        # Find first and last curly brace
        start = text.find("{")
        end = text.rfind("}") + 1

        if start == -1 or end == -1:
            return None

        json_text = text[start:end]
        return json.loads(json_text)

    except Exception:
        return None

# ---------------------------
# PAGE CONFIG
# ---------------------------
st.set_page_config(
    page_title="MediBill AI",
    page_icon="🏥",
    layout="centered"
)

# ---------------------------
# W&B INITIALIZATION
# ---------------------------
wandb.init(
    project="medibill-ai",
    name="billing-insurance-monitoring",
    config={"model": "gemini"}
)

# ---------------------------
# GEMINI SETUP
# ---------------------------
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

model = genai.GenerativeModel("models/gemini-2.5-flash")

# ---------------------------
# DATABASE FUNCTION
# ---------------------------

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

# ---------------------------
# HEADER UI
# ---------------------------
st.title("🏥 MediBill AI")
st.caption(
    "Helping patients and families understand hospital bills with clear explanations and insurance awareness."
)

st.divider()

# ---------------------------
# USER OPTIONS
# ---------------------------
col1, col2 = st.columns(2)

with col1:
    language = st.selectbox(
        "🌐 Preferred language",
        ["Auto-detect", "English", "Hindi", "Bengali"]
    )

with col2:
    family_mode = st.checkbox("👨‍👩‍👧 Explain in simple terms for family members")

# ---------------------------
# LEGEND
# ---------------------------
st.markdown("---🛡️ Insurance Coverage Guide---")
legend_col1, legend_col2, legend_col3 = st.columns(3)

with legend_col1:
    st.markdown("🟢 **Likely Covered**  \nCommonly included in insurance")

with legend_col2:
    st.markdown("🟡 **Partially Covered**  \nDepends on policy limits")

with legend_col3:
    st.markdown("🔴 **Not Covered**  \nOften excluded from insurance")

st.divider()

# ---------------------------
# LOAD BILL ITEMS
# ---------------------------
bill_items = get_bill_items()
total = sum(item["cost"] for item in bill_items)

st.metric("💰 Total Bill So Far (₹)", total)

st.divider()

# ---------------------------
# BILL ITEMS DISPLAY
# ---------------------------
for item in bill_items:
    with st.container():
        st.subheader(item["item_name"])
        st.write(f"**Category:** {item['category']}")
        st.write(f"**Cost:** ₹{item['cost']}")

        col_a, col_b = st.columns(2)

        # ---------------------------
        # IMAGE BUTTON (EDUCATIONAL)
        # ---------------------------
        with col_a:
            if st.button("🖼️ Generate image prompt", key=f"img_{item['item_name']}"):
                with st.spinner("Generating image prompt..."):
                    img_prompt = generate_image_prompt(
                        item["item_name"],
                        item["category"]
                    )

                    st.text_area(
                        "AI-generated image prompt (ready for image models):",
                        img_prompt,
                        height=200
                    )

                    st.caption(
                        "🖼️ This is an AI-generated description for an educational illustration. "
    "Hospitals can use it to create safe visuals for billing clarity."
                    )

        # ---------------------------
        # EXPLAIN BUTTON
        # ---------------------------
        with col_b:
            explain = st.button(
                "🧠 Explain & Check Insurance",
                key=f"exp_{item['item_name']}"
            )

        if explain:
            prompt = f"""
You are MediBill AI, a hospital billing assistant.

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
- Respond in {language if language != "Auto-detect" else "user's language"}.
IMPORTANT:
- Do not include markdown
- Do not include explanations outside JSON
- Output raw JSON only
"""

            response = model.generate_content(prompt)

            result = extract_json(response.text)

            if result is None:
                st.error("⚠️ AI response formatting issue (raw response shown below)")
                st.code(response.text)
                st.stop()

            # ---------------------------
            # INSURANCE COLOR BADGE
            # ---------------------------
            status = result["insurance_status"]

            if status == "LIKELY_COVERED":
                st.markdown("🟢 **Likely covered by insurance**")
            elif status == "PARTIALLY_COVERED":
                st.markdown("🟡 **May be partially covered**")
            else:
                st.markdown("🔴 **Usually not covered by insurance**")

            # ---------------------------
            # DISPLAY EXPLANATION
            # ---------------------------
            st.write(result["explanation"])
            st.info(result["insurance_note"])
            st.caption(f"⚠️ {result['disclaimer']}")

            # ---------------------------
            # W&B LOGGING
            # ---------------------------
            wandb.log({
                "item": item["item_name"],
                "category": item["category"],
                "insurance_status": status,
                "language": language,
                "family_mode": family_mode,
                "response_length": len(result["explanation"])
            })

        st.divider()

# ---------------------------
# FOOTER
# ---------------------------
st.caption(
    "MediBill AI is an educational tool for billing transparency. "
    "It does not replace professional medical or insurance advice."
)
