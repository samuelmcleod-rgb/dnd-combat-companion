import streamlit as st
import json
import requests
import google.generativeai as genai

# --- CONFIGURATION ---
st.set_page_config(page_title="D&D Combat Companion", layout="wide", page_icon="⚔️")

# Custom CSS for the Red Health Bar
st.markdown("""
<style>
div.stProgress > div > div > div > div {
    background-color: #d93025;
}
</style>""", unsafe_allow_html=True)

# --- HELPER FUNCTIONS ---

def parse_dnd_beyond_json(data):
    """
    Parses D&D Beyond character JSON to extract Actions, Bonus Actions, and Reactions.
    """
    character = data.get('character', {})
    combat_options = {"Action": [], "Bonus Action": [], "Reaction": [], "Other": []}

    def get_activation_category(activation_type):
        if activation_type == 1: return "Action"
        elif activation_type == 3: return "Bonus Action"
        elif activation_type == 4: return "Reaction"
        return "Other"

    # 1. PARSE CLASS, RACE, & FEAT ACTIONS
    actions_data = character.get('actions', {})
    sources = [
        (actions_data.get('race', []), "👤 Race"),
        (actions_data.get('class', []), "🛡️ Class"),
        (actions_data.get('feat', []), "🎖️ Feat")
    ]

    for source_list, source_label in sources:
        for ability in source_list:
            name = ability.get('name', 'Unknown Ability')
            activation = ability.get('activation', {}) or {}
            act_type = activation.get('activationType')
            
            if not act_type: continue
            category = get_activation_category(act_type)
            
            # Check for limited uses
            limited_use = ability.get('limitedUse', {})
            uses_text = f" (Max: {limited_use.get('maxUses')})" if limited_use.get('maxUses') else ""

            if category != "Other":
                combat_options[category].append(f"{source_label}: {name}{uses_text}")

    # 2. PARSE INVENTORY (Weapons)
    for item in character.get('inventory', []):
        if not item.get('equipped'): continue
        definition = item.get('definition', {})
        name = definition.get('name', 'Unknown Item')
        
        if definition.get('filterType') == 'Weapon':
            combat_options["Action"].append(f"⚔️ Attack: {name}")
            # Check for Light property (simplified)
            if any(p.get('name') == 'Light' for p in definition.get('properties', [])):
                combat_options["Bonus Action"].append(f"⚔️ Off-hand Attack: {name}")

    # 3. PARSE SPELLS
    for char_class in character.get('classSpells', []):
        for spell_entry in char_class.get('spells', []):
            spell_def = spell_entry.get('definition', {})
            name = spell_def.get('name', 'Unknown')
            act_type = spell_def.get('activation', {}).get('activationType')
            category = get_activation_category(act_type)
            
            if category != "Other":
                level = spell_def.get('level')
                lvl_str = "Cantrip" if level == 0 else f"Lvl {level}"
                combat_options[category].append(f"✨ {name} ({lvl_str})")

    # 4. GENERIC ACTIONS
    combat_options["Action"].extend(["🏃 Dash", "🛡️ Dodge", "💨 Disengage", "🤝 Help", "🙈 Hide", "🔍 Search"])
    combat_options["Reaction"].extend(["⚡ Opportunity Attack"])

    return combat_options

def fetch_character_json(character_id):
    url = f"https://character-service.dndbeyond.com/character/v5/character/{character_id}"
    headers = { "User-Agent": "Mozilla/5.0" }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": str(e)}

# --- SIDEBAR & API SETUP ---
with st.sidebar:
    st.header("⚙️ Configuration")
    
    # API Key Handling (Secrets vs Manual)
    if "GOOGLE_API_KEY" in st.secrets:
        api_key = st.secrets["GOOGLE_API_KEY"]
        st.success("☁️ API Key Loaded")
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
    # Default value set to your ID
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
    # Heuristic for Max HP if not explicit
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
