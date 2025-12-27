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

st.markdown("""
<style>
    /* Full-page background (simplified for compatibility) */
    body {
        font-family: Arial, Helvetica, sans-serif;
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        color: #333;
        margin: 0;
        padding: 0;
    }
    
    /* Main container */
    .main {
        background: rgba(255, 255, 255, 0.95);
        border-radius: 15px;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
        padding: 20px;
        margin: 20px auto;
        max-width: 1200px;
    }
    
    /* Title styling */
    .stTitle {
        font-family: Arial, Helvetica, sans-serif;
        font-weight: bold;
        color: #2c3e50;
        text-align: center;
        font-size: 2.5em;
        margin-bottom: 10px;
    }
    
    /* Caption styling */
    .stCaption {
        font-family: Arial, Helvetica, sans-serif;
        font-weight: normal;
        color: #7f8c8d;
        font-style: italic;
        text-align: center;
        font-size: 1.1em;
    }
    
    /* Divider styling */
    hr {
        border: none;
        height: 2px;
        background: linear-gradient(90deg, #3498db, #2ecc71);
        margin: 20px 0;
    }
    
    /* Selectbox and checkbox styling */
    .stSelectbox, .stCheckbox {
        background: #ecf0f1;
        border-radius: 10px;
        padding: 10px;
        border: 1px solid #bdc3c7;
        margin-bottom: 15px;
    }
    
    /* Metric styling */
    .stMetric {
        background: linear-gradient(135deg, #3498db, #2980b9);
        color: white;
        border-radius: 15px;
        padding: 20px;
        text-align: center;
        box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
        font-size: 1.5em;
        font-weight: bold;
    }
    
    /* Subheader styling */
    .stSubheader {
        font-family: Arial, Helvetica, sans-serif;
        font-weight: bold;
        color: #34495e;
        border-left: 5px solid #2ecc71;
        padding-left: 15px;
        margin-top: 30px;
    }
    
    /* Button styling */
    .stButton button {
        background: linear-gradient(135deg, #2ecc71, #27ae60);
        color: white;
        border: none;
        border-radius: 25px;
        padding: 12px 25px;
        font-size: 1em;
        font-weight: bold;
        cursor: pointer;
        transition: background 0.3s ease;
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.2);
    }
    
    .stButton button:hover {
        background: linear-gradient(135deg, #27ae60, #229954);
    }
    
    /* Text area styling */
    .stTextArea textarea {
        background: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 10px;
        padding: 15px;
        font-family: Arial, Helvetica, sans-serif;
        font-size: 1em;
        resize: vertical;
    }
    
    /* Info and warning boxes */
    .stInfo, .stWarning {
        background: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 10px;
        padding: 15px;
        margin: 10px 0;
        color: #155724;
    }
    
    .stWarning {
        background: #fff3cd;
        border-color: #ffeaa7;
        color: #856404;
    }
    
    /* Markdown styling */
    .stMarkdown p {
        font-size: 1.1em;
        line-height: 1.6;
    }
    
    /* Columns styling */
    .stColumns {
        gap: 20px;
    }
    
    /* Footer styling */
    .stCaption:last-of-type {
        text-align: center;
        margin-top: 40px;
        font-size: 0.9em;
        color: #95a5a6;
    }
    
    /* Custom legend styling */
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
    
    /* Responsive design */
    @media (max-width: 768px) {
        .stTitle {
            font-size: 2em;
        }
        .stMetric {
            font-size: 1.2em;
        }
        .legend {
            flex-direction: column;
            gap: 10px;
        }
    }
</style>
""", unsafe_allow_html=True)

# Logging interactions to understand how billing items are interpreted
try:
    wandb.init(
        project="medibill-ai",
        name="billing-insurance-monitoring",
        reinit=True
    )
except Exception:
    # App should continue even if analytics fail
    pass

# GEMINI SETUP
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("models/gemini-2.0-flash")


def extract_json(text):
    """
    Extracts a valid JSON object from the model response.
    This keeps the app stable even if extra text slips in.
    """

    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        return json.loads(text[start:end])
    except Exception:
        return None

# DATABASE CONNECTION
def get_bill():
    conn = sqlite3.connect("medibill.db")
    cur = conn.cursor()
    cur.execute("SELECT item_name, category, cost FROM bill_items")
    rows = cur.fetchall()
    conn.close()
    return [
        {"item": r[0], "category": r[1], "cost": r[2]}
        for r in rows
    ]

def safely_call_gemini(prompt):
    """
    Small wrapper around the AI call to avoid breaking
    the app if the API times out or errors.
    """
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
items = get_bill()
st.metric("💰 Total Hospital Bill So Far (₹)", sum(i["cost"] for i in items))

st.divider()

#Details of all items on the list
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
Describe a clean, educational medical illustration.
"""
            st.session_state[key_image] = safely_call_gemini(img_prompt) or "FAILED"

    if key_image in st.session_state:
        if st.session_state[key_image] == "FAILED":
            #if API hits daily limit for calls
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
            #JSON only enforced to ensure output in proper format
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
            raw = safely_call_gemini(explain_prompt)
            st.session_state[key_explain] = extract_json(raw) if raw else "FAILED"

    if key_explain in st.session_state:
        result = st.session_state[key_explain]

        if result == "FAILED":
            #when API hits daily free trial limit
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
