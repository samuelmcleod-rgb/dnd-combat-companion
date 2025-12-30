import streamlit as st
import json
import google.generativeai as genai
import requests

# Import our helper parser
# Ensure dnd_parser.py is in the same folder!
from dnd_parser import parse_dnd_beyond_json

# --- CONFIGURATION ---
st.set_page_config(page_title="D&D Combat Companion", layout="wide", page_icon="⚔️")

# Custom CSS for the Red Health Bar
st.markdown("""
<style>
div.stProgress > div > div > div > div {
    background-color: #d93025;
}
</style>""", unsafe_allow_html=True)

# Function to fetch data from D&D Beyond
def fetch_character_json(character_id):
    url = f"https://character-service.dndbeyond.com/character/v5/character/{character_id}"
    headers = { "User-Agent": "Mozilla/5.0" }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": str(e)}

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Configuration")
    
    # Check if key is in Secrets (Cloud) or Environment (Local)
    if "GOOGLE_API_KEY" in st.secrets:
        api_key = st.secrets["GOOGLE_API_KEY"]
        st.success("☁️ API Key Loaded from Secrets")
    else:
        api_key = st.text_input("Google Gemini API Key", type="password")
    
    if api_key:
        genai.configure(api_key=api_key)

    st.markdown("---")
    st.info(f"**Current Character ID:**\n`151075644`")

st.title("⚔️ D&D Combat Companion")

# --- STEP 1: LOAD DATA ---
tab1, tab2 = st.tabs(["🌐 Live Fetch", "📂 Upload File"])

character_data = None

with tab1:
    # UPDATED: We set the default 'value' to your specific Character ID
    char_id = st.text_input("D&D Beyond Character ID", value="151075644")
    
    if st.button("Load Character", type="primary"):
        with st.spinner("Accessing D&D Beyond..."):
            result = fetch_character_json(char_id)
            if "error" in result:
                st.error(f"Failed to fetch: {result['error']}")
            elif "data" in result: 
                character_data = result['data'] 
                st.success(f"Loaded {character_data.get('name', 'Character')}!")
            else:
                character_data = result
                st.success("Loaded successfully!")

with tab2:
    uploaded_file = st.file_uploader("Or upload 'character.json'", type="json")
    if uploaded_file is not None:
        raw = json.load(uploaded_file)
        character_data = raw.get('data', raw) 

# --- MAIN APP LOGIC ---
if character_data:
    # Normalize structure
    full_data = character_data if 'character' in character_data else {'character': character_data}
    char_sheet = full_data['character']
    name = char_sheet['name']

    # --- HP TRACKER ---
    # We default Max HP to base + constitution modifiers roughly, but allow override
    # Note: 151075644 seems to be level 10+, so 120 is a safe placeholder default
    default_hp = char_sheet.get('baseHitPoints', 100) + (char_sheet.get('level', 1) * 2) 
    
    with st.sidebar:
        st.markdown("---")
        st.header("❤️ Vitality")
        max_hp = st.number_input("Max HP", value=default_hp, step=1)

    removed_hp = char_sheet.get('removedHitPoints', 0)
    temp_hp = char_sheet.get('temporaryHitPoints', 0)
    current_hp = max_hp - removed_hp
    
    hp_percent = max(0.0, min(1.0, current_hp / max_hp))

    st.markdown(f"## {name}'s Combat Dashboard")

    # HUD
    hud_col1, hud_col2 = st.columns([3, 1])
    with hud_col1:
        st.write(f"**HP:** {current_hp} / {max_hp} " + (f"(+ {temp_hp} Temp)" if temp_hp > 0 else ""))
        st.progress(hp_percent)
    with hud_col2:
        if temp_hp > 0:
            st.metric("Temp HP", temp_hp)
        else:
            status = "Healthy" if hp_percent > 0.5 else "Bloodied"
            st.metric("Status", status)

    st.markdown("---")

    # --- ACTIONS DISPLAY ---
    actions = parse_dnd_beyond_json(full_data)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.info("### 🔴 Actions")
        for a in actions["Action"]: st.write(f"• {a}")
    with col2:
        st.warning("### 🔼 Bonus Actions")
        for b in actions["Bonus Action"]: st.write(f"• {b}")
    with col3:
        st.error("### ⚡ Reactions")
        for r in actions["Reaction"]: st.write(f"• {r}")

    st.markdown("---")

    # --- AI STRATEGY ---
    st.subheader("🧠 Tactical Advisor")
    col_input, col_output = st.columns([1, 1])

    with col_input:
        situation = st.text_area("Situation Report", height=150, 
            placeholder="e.g. Boss has high AC, I'm at 50% HP. Party needs me to tank.")
        
        if st.button("Generate Strategy"):
            if not api_key:
                st.error("Please enter API Key in sidebar (or secrets).")
            else:
                with st.spinner("Analyzing probabilities..."):
                    # Prompt Engineering
                    prompt = f"""
                    You are a D&D 5e Combat Optimizer.
                    
                    CHARACTER: {name} (HP: {current_hp}/{max_hp})
                    AVAILABLE MOVES: {json.dumps(actions)}
                    
                    SCENARIO: {situation}
                    
                    Provide a concise, optimal turn breakdown:
                    1. **Movement**: Where to go.
                    2. **Action**: The best main action.
                    3. **Bonus Action**: How to utilize the bonus economy.
                    4. **Reaction**: What to look out for.
                    """
                    
                    try:
                        model = genai.GenerativeModel('gemini-pro')
                        response = model.generate_content(prompt)
                        st.session_state['last_strat'] = response.text
                    except Exception as e:
                        st.error(f"AI Error: {e}")

    with col_output:
        if 'last_strat' in st.session_state:
            st.markdown(st.session_state['last_strat'])