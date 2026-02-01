import streamlit as st
import google.generativeai as genai
import edge_tts
import asyncio
import os
from streamlit_mic_recorder import mic_recorder

# --- PAGINA CONFIGURATIE ---
st.set_page_config(page_title="Sollicitatie Oefening", page_icon="👔")

# --- CSS VOOR OPMAAK ---
st.markdown("""
<style>
    .stAudio {width: 100%;}
    div.stButton > button {width: 100%; height: 3em; font-size: 20px;}
</style>
""", unsafe_allow_html=True)

# --- 1. INSTELLINGEN HALEN UIT 'SECRETS' (VEILIGHEID) ---
# Op je eigen PC werkt dit niet zonder secrets file, maar in de cloud wel.
# Als je lokaal test, moet je even handmatig je key hieronder plakken, 
# MAAR VERWIJDER HEM VOOR JE UPLOAD NAAR GITHUB!
try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
except:
    API_KEY = "PLAK_HIER_TIJDELIJK_JE_KEY_VOOR_TESTEN" 

genai.configure(api_key=API_KEY)
model = genai.GenerativeModel("models/gemini-1.5-flash") # Sneller voor web

STEM = "nl-BE-ArnaudNeural"

# --- INSTRUCTIES ---
SYSTEM_PROMPT = """
ROL: Vriendelijke Vlaamse Recruiter (Marc).
DOEL: Sollicitatiegesprek met cursist (Niveau 1.2).
REGELS:
1. Één vraag per keer.
2. Geen nummers/lijstjes.
3. Spreektaal.
VERLOOP:
- Start: "Hallo, ik ben Marc. Hoe heet jij?"
- Vraag naar: Jobkeuze, Ervaring, Beschikbaarheid.
- Einde: Bedank en zeg "Tot ziens".
"""

# --- SESSIE BIJHOUDEN ---
if "history" not in st.session_state:
    st.session_state.history = [
        {"role": "user", "parts": ["Start de simulatie."]},
        {"role": "model", "parts": [SYSTEM_PROMPT]}
    ]
if "chat" not in st.session_state:
    st.session_state.chat = model.start_chat(history=st.session_state.history)
if "audio_counter" not in st.session_state:
    st.session_state.audio_counter = 0

# --- FUNCTIES ---
async def text_to_speech(text):
    output_file = f"response_{st.session_state.audio_counter}.mp3"
    # Filters
    clean_text = text.replace("*", "").replace("###STOP###", "")
    clean_text = clean_text.replace("Jan ", "Jann ").replace("1.", "")
    
    communicate = edge_tts.Communicate(clean_text, STEM, rate="-20%")
    await communicate.save(output_file)
    return output_file

def get_response_from_ai(user_text):
    response = st.session_state.chat.send_message(user_text)
    return response.text

# --- DE APP ---
st.title("👔 Solliciteren met Marc")
st.write("Druk op de knop, spreek je antwoord in en wacht op Marc.")

# Container voor de audio speler (zodat die bovenaan kan staan of ververst)
audio_placeholder = st.empty()

# 1. DE START (Marc begint)
if st.session_state.audio_counter == 0:
    if st.button("📞 Start het gesprek"):
        # We faken een start bericht om Marc te laten praten
        response_text = get_response_from_ai("De kandidaat is er. Begin het gesprek.")
        
        # Audio genereren
        audio_file = asyncio.run(text_to_speech(response_text))
        st.session_state.last_audio = audio_file
        st.session_state.last_text = response_text
        st.session_state.audio_counter += 1
        st.rerun()

# 2. ANTWOORD WEERGEVEN (Als er audio is)
if "last_audio" in st.session_state:
    st.success(f"🗣️ Marc: {st.session_state.last_text}")
    st.audio(st.session_state.last_audio, format="audio/mp3", autoplay=True)

# 3. JOUW BEURT (Opname knop)
st.write("---")
st.write("🎙️ **Jouw antwoord:**")
audio_input = mic_recorder(
    start_prompt="🔴 Klik om te spreken",
    stop_prompt="⏹️ Klik om te stoppen",
    key='recorder'
)

# 4. VERWERKING
if audio_input:
    # We hebben audio bytes!
    # Omdat spraak-naar-tekst complex is in de cloud zonder zware tools,
    # sturen we de AUDIO direct naar Gemini (Gemini 1.5 kan luisteren!)
    # Of we gebruiken Google Speech Recognition via een omweg.
    # Voor nu: We gebruiken een simpele SpeechRecognition truc.
    
    import speech_recognition as sr
    import io
    
    # Audio opslaan om te lezen
    with open("temp_input.wav", "wb") as f:
        f.write(audio_input['bytes'])
        
    r = sr.Recognizer()
    with sr.AudioFile("temp_input.wav") as source:
        audio_data = r.record(source)
        try:
            user_text = r.recognize_google(audio_data, language="nl-BE")
            st.info(f"Jij zei: {user_text}")
            
            # Stuur naar Marc
            ai_response = get_response_from_ai(user_text)
            
            # Marc spreekt terug
            audio_file = asyncio.run(text_to_speech(ai_response))
            
            # Update state
            st.session_state.last_audio = audio_file
            st.session_state.last_text = ai_response
            st.session_state.audio_counter += 1
            st.rerun()
            
        except sr.UnknownValueError:
            st.warning("Marc heeft je niet verstaan, probeer het nog eens.")