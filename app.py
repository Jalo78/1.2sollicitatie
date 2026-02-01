import streamlit as st
import google.generativeai as genai
import edge_tts
import asyncio
import os
import random # Nodig voor de loterij
import io
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
model = genai.GenerativeModel("models/gemini-flash-latest"))

# --- 2. DE RECRUITERS (De Loterij) ---
# Hier definiëren we de mogelijke personages
RECRUITERS = [
    {"naam": "Marc", "geslacht": "man", "stem": "nl-BE-ArnaudNeural"},
    {"naam": "Elke", "geslacht": "vrouw", "stem": "nl-BE-DenaNeural"},
    {"naam": "Peter", "geslacht": "man", "stem": "nl-NL-MaartenNeural"}, # Hollandse man
    {"naam": "Fenna", "geslacht": "vrouw", "stem": "nl-NL-FennaNeural"}  # Hollandse vrouw
]

# We kiezen er eentje BIJ HET BEGIN van de sessie
if "huidige_recruiter" not in st.session_state:
    st.session_state.huidige_recruiter = random.choice(RECRUITERS)

# We halen de gegevens op van de gekozen recruiter
recruiter = st.session_state.huidige_recruiter

# --- INSTRUCTIES ---
# We gebruiken f-strings (f"...") om de naam dynamisch in te vullen
SYSTEM_PROMPT = f"""
ROL: Vriendelijke Recruiter genaamd {recruiter['naam']}.
DOEL: Sollicitatiegesprek met cursist (Niveau 1.2).

BELANGRIJK:
1. Stel ÉÉN vraag per keer. Wacht op antwoord.
2. Geen nummers of lijstjes gebruiken.
3. Gebruik eenvoudige spreektaal.

GESPREKSVERLOOP (Volg deze stap voor stap):
1. START: "Hallo, ik ben {recruiter['naam']}. Hoe heet jij?"
2. Vraag naar de JOB: "Voor welk beroep kom je solliciteren?"
3. Vraag naar ERVARING: "Heb je al ervaring met dat werk?"
4. Vraag naar KWALITEITEN: "Wat zijn jouw sterke punten? Waar ben je goed in?"
5. Vraag naar LEERDOELEN: "Wat wil je zeker nog leren?"
6. Vraag naar BESCHIKBAARHEID: "Wanneer kan je beginnen?"
7. AFSLUITING: Bedank de sollicitant vriendelijk en zeg tot ziens.
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
    """
    Genereert audio en geeft het terug als bytes in het geheugen (WAV formaat).
    Dit werkt veel beter op iPhone dan MP3 bestanden.
    """
    temp_mp3 = "temp_output.mp3"
    
    # Filters
    clean_text = text.replace("*", "").replace("###STOP###", "")
    clean_text = clean_text.replace("Jan ", "Jann ").replace("1.", "")
    
    # Audio genereren met de STEM van de gekozen recruiter
    communicate = edge_tts.Communicate(clean_text, recruiter['stem'], rate="-20%")
    await communicate.save(temp_mp3)
    
    # Converteren naar WAV voor iPhone compatibiliteit
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
        # HIER IS DE VERANDERING: We printen de fout op het scherm!
        st.error(f"Foutmelding van Google: {e}")
        return "Er is een technische storing. Lees de rode tekst op het scherm."

# --- DE APP ---
st.title(f"👔 Solliciteren met {recruiter['naam']}")
st.write("Druk op de knop, spreek je antwoord in en wacht op reactie.")

# 1. DE START (Recruiter begint)
if "conversation_started" not in st.session_state:
    if st.button("📞 Start het gesprek"):
        with st.spinner(f"{recruiter['naam']} komt eraan..."):
            response_text = get_response_from_ai("De kandidaat is er. Begin het gesprek.")
            
            # Audio genereren
            audio_bytes = asyncio.run(text_to_speech_memory(response_text))
            
            st.session_state.last_audio_bytes = audio_bytes
            st.session_state.last_text = response_text
            st.session_state.conversation_started = True
            st.rerun()

# 2. ANTWOORD WEERGEVEN
if "last_audio_bytes" in st.session_state:
    st.success(f"🗣️ {recruiter['naam']}: {st.session_state.last_text}")
    # format='audio/wav' is cruciaal voor iOS!
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
    # Loop beveiliging
    if "last_processed_audio" not in st.session_state:
        st.session_state.last_processed_audio = None
        
    if audio_input['bytes'] == st.session_state.last_processed_audio:
        pass 
    else:
        st.session_state.last_processed_audio = audio_input['bytes']

        # Import hier om import errors bovenaan te voorkomen als pydub mist
        import speech_recognition as sr
        
        try:
            # STAP A: Converteren van Browser-audio naar WAV
            audio_segment = AudioSegment.from_file(io.BytesIO(audio_input['bytes']))
            audio_segment.export("temp_input.wav", format="wav")
            
            # STAP B: Herkennen
            r = sr.Recognizer()
            with sr.AudioFile("temp_input.wav") as source:
                audio_data = r.record(source)
                user_text = r.recognize_google(audio_data, language="nl-BE")
                
            st.info(f"Jij zei: {user_text}")
            
            # STAP C: Antwoord genereren
            ai_response = get_response_from_ai(user_text)
            
            # STAP D: Audio terugspelen (als WAV bytes)
            audio_bytes = asyncio.run(text_to_speech_memory(ai_response))
            
            # Update state
            st.session_state.last_audio_bytes = audio_bytes
            st.session_state.last_text = ai_response
            
            st.rerun()
                
        except sr.UnknownValueError:
            st.warning("Ik kon je niet goed verstaan, probeer het nog eens.")
        except Exception as e:
            st.error(f"Foutmelding: {e}")

