import streamlit as st
import google.generativeai as genai
import edge_tts
import asyncio
import os
import random 
import io
import re # NIEUW: Nodig voor slimme tekstvervanging
from pydub import AudioSegment
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

# --- 1. INSTELLINGEN ---
try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
except:
    st.error("Geen API Key gevonden. Stel deze in op Streamlit Cloud.")
    st.stop()

genai.configure(api_key=API_KEY)
model = genai.GenerativeModel("models/gemini-flash-latest")

# --- 2. DE RECRUITERS (100% Vlaams) ---
RECRUITERS = [
    {"naam": "Marc", "geslacht": "man", "stem": "nl-BE-ArnaudNeural"},
    {"naam": "Elke", "geslacht": "vrouw", "stem": "nl-BE-DenaNeural"},
    {"naam": "Lucas", "geslacht": "man", "stem": "nl-BE-ArnaudNeural"}, 
    {"naam": "Sarah", "geslacht": "vrouw", "stem": "nl-BE-DenaNeural"}  
]

if "huidige_recruiter" not in st.session_state:
    st.session_state.huidige_recruiter = random.choice(RECRUITERS)

recruiter = st.session_state.huidige_recruiter

# --- INSTRUCTIES ---
SYSTEM_PROMPT = f"""
ROL: Vriendelijke Vlaamse Recruiter genaamd {recruiter['naam']}.
DOEL: Sollicitatiegesprek met cursist (Niveau 1.2).

BELANGRIJK:
1. Stel ÉÉN vraag per keer. Wacht op antwoord.
2. Geen nummers of lijstjes gebruiken.
3. Gebruik eenvoudige spreektaal (Vlaams).

GESPREKSVERLOOP:
1. START: "Hallo, ik ben {recruiter['naam']}. Hoe heet jij?"
2. Vraag: "Voor welk beroep kom je solliciteren?"
3. Vraag: "Heb je al ervaring met dat werk?"
4. Vraag: "Wat zijn jouw sterke punten?"
5. Vraag: "Wat wil je zeker nog leren?"
6. Vraag: "Werk je liever alleen of in een team?" 
7. Vraag: "Wanneer kan je beginnen?"
8. AFSLUITING: Bedank de kandidaat en zeg dat het gesprek klaar is.

EXTRA OPDRACHT (DE TIPS):
Direct nadat je het gesprek hebt afgesloten (stap 8), geef je 2 KORTE TIPS over hoe de cursist het deed.
Schrijf dit als: "Hier zijn nog 2 tips voor jou: ..."
Focus op: luid spreken, zinsbouw, of om verduidelijking vragen.
Hou de tips simpel en opbouwend.
"""

# --- SESSIE BIJHOUDEN ---
if "history" not in st.session_state:
    st.session_state.history = [
        {"role": "user", "parts": ["Start de simulatie."]},
        {"role": "model", "parts": [SYSTEM_PROMPT]}
    ]
if "chat" not in st.session_state:
    st.session_state.chat = model.start_chat(history=st.session_state.history)

# --- FUNCTIES ---
async def text_to_speech_memory(text):
    """Genereert audio (WAV) voor iPhone support."""
    temp_mp3 = "temp_output.mp3"
    
    # --- DE FONETISCHE WASSTRAAT ---
    # 1. Basis schoonmaak
    clean_text = text.replace("*", "").replace("###STOP###", "")
    clean_text = clean_text.replace("1.", "").replace("2.", "") # Geen nummers
    
    # 2. Specifieke correcties voor uitspraak
    # We gebruiken 'regular expressions' (\b betekent woordgrens)
    # Zo vervangen we 'Jan' alleen als het een los woord is, niet in 'Oranje'.
    
    # Jan -> Jann (Zodat hij geen 'Januari' zegt)
    clean_text = re.sub(r'\bJan\b', 'Jann', clean_text)
    
    # cv -> cee vee
    clean_text = re.sub(r'\bcv\b', 'cee vee', clean_text, flags=re.IGNORECASE)
    
    # bv -> bijv (voor het geval dat)
    clean_text = re.sub(r'\bbv\b', 'bijvoorbeeld', clean_text, flags=re.IGNORECASE)

    # Audio genereren
    communicate = edge_tts.Communicate(clean_text, recruiter['stem'], rate="-20%")
    await communicate.save(temp_mp3)
    
    try:
        audio = AudioSegment.from_file(temp_mp3, format="mp3")
        buffer = io.BytesIO()
        audio.export(buffer, format="wav")
        buffer.seek(0)
        return buffer
    except Exception as e:
        st.error(f"Fout bij audio conversie: {e}")
        return None

def get_response_from_ai(user_text):
    try:
        response = st.session_state.chat.send_message(user_text)
        return response.text
    except Exception as e:
        st.error(f"Foutmelding van Google: {e}")
        return "Er is een technische storing. Probeer opnieuw."

# --- DE APP ---
st.title(f"👔 Solliciteren met {recruiter['naam']}")
st.write("Druk op de knop, spreek je antwoord in en wacht op reactie.")

# RESET KNOP
with st.sidebar:
    st.header("Opties")
    if st.button("🔄 Ander gesprek / Nieuwe recruiter"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# 1. DE START
if "conversation_started" not in st.session_state:
    if st.button("📞 Start het gesprek"):
        with st.spinner(f"{recruiter['naam']} komt eraan..."):
            response_text = get_response_from_ai("De kandidaat is er. Begin het gesprek.")
            audio_bytes = asyncio.run(text_to_speech_memory(response_text))
            
            st.session_state.last_audio_bytes = audio_bytes
            st.session_state.last_text = response_text
            st.session_state.conversation_started = True
            st.rerun()

# 2. ANTWOORD WEERGEVEN
if "last_audio_bytes" in st.session_state:
    # Op het scherm tonen we de tekst MET Jan (want dat komt direct uit response_text)
    st.success(f"🗣️ {recruiter['naam']}: {st.session_state.last_text}")
    # Maar we horen Jann (uit de audio functie)
    st.audio(st.session_state.last_audio_bytes, format="audio/wav", autoplay=True)

# 3. JOUW BEURT
st.write("---")
st.write("🎙️ **Jouw antwoord:**")
audio_input = mic_recorder(
    start_prompt="🔴 Klik om te spreken",
    stop_prompt="⏹️ Klik om te stoppen",
    key='recorder'
)

# 4. VERWERKING
if audio_input:
    if "last_processed_audio" not in st.session_state:
        st.session_state.last_processed_audio = None
        
    if audio_input['bytes'] == st.session_state.last_processed_audio:
        pass 
    else:
        st.session_state.last_processed_audio = audio_input['bytes']
        import speech_recognition as sr
        
        try:
            # A. Converteren
            audio_segment = AudioSegment.from_file(io.BytesIO(audio_input['bytes']))
            audio_segment.export("temp_input.wav", format="wav")
            
            # B. Herkennen
            r = sr.Recognizer()
            with sr.AudioFile("temp_input.wav") as source:
                audio_data = r.record(source)
                user_text = r.recognize_google(audio_data, language="nl-BE")
                
            st.info(f"Jij zei: {user_text}")
            
            # C. Antwoord genereren
            ai_response = get_response_from_ai(user_text)
            
            # D. Audio terugspelen
            audio_bytes = asyncio.run(text_to_speech_memory(ai_response))
            
            st.session_state.last_audio_bytes = audio_bytes
            st.session_state.last_text = ai_response
            st.rerun()
                
        except sr.UnknownValueError:
            st.warning("Ik kon je niet goed verstaan, probeer het nog eens.")
        except Exception as e:
            st.error(f"Foutmelding: {e}")



