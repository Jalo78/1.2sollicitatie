import streamlit as st
import google.generativeai as genai
import edge_tts
import asyncio
import os
import random 
import io
import re 
from pydub import AudioSegment
from streamlit_mic_recorder import mic_recorder

# --- 1. CONFIGURATIE & CSS (DE MAKE-OVER) ---
st.set_page_config(page_title="Sollicitatie Oefening", page_icon="👔", layout="centered")

st.markdown("""
<style>
    /* 1. Verberg standaard Streamlit elementen voor een 'App-gevoel' */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* 2. Audio speler integreren */
    .stAudio {width: 100%; border-radius: 10px;}

    /* 3. Mooie grote blauwe knoppen */
    div.stButton > button {
        width: 100%; 
        height: 3.5em; 
        font-size: 20px; 
        font-weight: bold;
        border-radius: 12px;
        background-color: #0072B5; 
        color: white;
        border: none;
        box-shadow: 0px 4px 6px rgba(0,0,0,0.1);
        transition: 0.3s;
    }
    
    div.stButton > button:hover {
        background-color: #005a92;
        transform: scale(1.02);
    }
    
    /* 4. Tekst wat netter maken */
    h1 { font-size: 2rem !important; text-align: center; color: #333;}
    p { font-size: 1.1rem; }
    
</style>
""", unsafe_allow_html=True)

# --- 2. API KEY SETUP ---
try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
except:
    st.error("⚠️ Geen API Key gevonden. Stel deze in bij 'Secrets' op Streamlit Cloud.")
    st.stop()

genai.configure(api_key=API_KEY)
model = genai.GenerativeModel("models/gemini-flash-latest")

# --- 3. DE RECRUITERS & FOTO'S ---
RECRUITERS = [
    {"naam": "Marc", "geslacht": "man", "stem": "nl-BE-ArnaudNeural", "foto": "https://img.freepik.com/free-photo/smiling-young-male-professional-standing-with-arms-crossed-while-making-eye-contact-against-isolated-background_662251-838.jpg?w=400"},
    {"naam": "Elke", "geslacht": "vrouw", "stem": "nl-BE-DenaNeural", "foto": "https://img.freepik.com/free-photo/portrait-beautiful-young-woman-standing-grey-wall_231208-10760.jpg?w=400"},
    {"naam": "Lucas", "geslacht": "man", "stem": "nl-BE-ArnaudNeural", "foto": "https://img.freepik.com/free-photo/handsome-young-businessman-shirt-eyeglasses_85574-6228.jpg?w=400"}, 
    {"naam": "Sarah", "geslacht": "vrouw", "stem": "nl-BE-DenaNeural", "foto": "https://img.freepik.com/free-photo/young-beautiful-woman-pink-warm-sweater-natural-look-smiling-portrait-isolated-long-hair_285396-896.jpg?w=400"}  
]

if "huidige_recruiter" not in st.session_state:
    st.session_state.huidige_recruiter = random.choice(RECRUITERS)

recruiter = st.session_state.huidige_recruiter

# --- 4. INSTRUCTIES (MET TIPS) ---
SYSTEM_PROMPT = f"""
ROL: Vriendelijke Vlaamse Recruiter genaamd {recruiter['naam']}.
DOEL: Sollicitatiegesprek met cursist (Niveau 1.2).

BELANGRIJK:
1. Stel ÉÉN vraag per keer. Wacht op antwoord.
2. Geen nummers of lijstjes gebruiken tijdens het gesprek.
3. Gebruik eenvoudige spreektaal (Vlaams).

GESPREKSVERLOOP:
1. START: "Hallo, ik ben {recruiter['naam']}. Hoe heet jij?"
2. Vraag: "Stel jezelf even kort voor?" 
3. Vraag: "Voor welk beroep kom je solliciteren?"
4. Vraag: "Heb je al ervaring met dat werk?"
(INSTRUCTIE: Als de cursist 'JA' zegt of ervaring noemt, vraag dan kort: "Waar was dit of bij welk bedrijf was dat?". Als de cursist 'NEE' zegt, zeg dan vriendelijk "Dat is niet erg" en ga door naar vraag 5)
5. Vraag: "Wat zijn jouw sterke punten?"
6. Vraag: "Wat wil je zeker nog leren?"
7. Vraag: "Werk je liever alleen of in een team?"
8. Vraag: "Wanneer kan je beginnen?"
9. Vraag: "Wil je voltijds werken of liever minder?"
(INSTRUCTIE: Als de cursist 'deeltijds' zegt of minder wil werken, vraag dan kort: "Waarom wil je minder werken?". Als de cursist 'voltijds' zegt, zeg dan vriendelijk "Dat is niet erg" en ga door naar vraag 5)
10. Vraag: "Kan je in het weekend of 's nachts werken?"
11. Vraag: " Wat wil jij nog vragen?"
12. AFSLUITING: Bedank de kandidaat en zeg dat het gesprek klaar is en 2 tips geven.

EXTRA OPDRACHT (DE TIPS):
Direct nadat je het gesprek hebt afgesloten (stap 12), geef je 2 KORTE TIPS over hoe de cursist het deed.
Schrijf dit als: "Hier zijn nog 2 tips voor jou: ..."
Dit is een MONDELING gesprek. Geef dus NOOIT tips over leestekens, hoofdletters of spelling!
Focus op: volume, duidelijk spreken, zinsbouw, tempo, grammatica of om verduidelijking vragen.
Hou de tips simpel en opbouwend.
"""

# --- 5. SESSIE BEHEER ---
if "history" not in st.session_state:
    st.session_state.history = [
        {"role": "user", "parts": ["Start de simulatie."]},
        {"role": "model", "parts": [SYSTEM_PROMPT]}
    ]
if "chat" not in st.session_state:
    st.session_state.chat = model.start_chat(history=st.session_state.history)

# --- 6. FUNCTIES (Audio & Tekst) ---
async def text_to_speech_memory(text):
    """Genereert audio (WAV) voor iPhone support met fonetische correcties."""
    temp_mp3 = "temp_output.mp3"
    
    # A. Fonetische Wasstraat
    clean_text = text.replace("*", "").replace("###STOP###", "")
    clean_text = clean_text.replace("1.", "").replace("2.", "") 
        
    # Regex vervangingen (Alleen hele woorden)
    clean_text = re.sub(r'\bJan\b', 'Jann', clean_text)
    clean_text = re.sub(r'\bcv\b', 'cee vee', clean_text, flags=re.IGNORECASE)
    clean_text = re.sub(r'\bbv\b', 'bijvoorbeeld', clean_text, flags=re.IGNORECASE)
    clean_text = re.sub(r'\bbarema\b', 'bareema', clean_text, flags=re.IGNORECASE)
    
    # B. Genereren
    communicate = edge_tts.Communicate(clean_text, recruiter['stem'], rate="-20%")
    await communicate.save(temp_mp3)
    
    # C. Converteren naar WAV
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
        return "Er is een technische storing. Probeer opnieuw."

# --- 7. DE GRAFISCHE INTERFACE ---

# A. Titel en Recruiter Profiel
st.title("👔 Sollicitatie Oefening")

# Kolommen voor foto en tekst
col1, col2 = st.columns([1, 3])
with col1:
    # Ronde afbeelding maken met CSS stijl in het image commando kan lastig zijn, 
    # maar Streamlit toont hem gewoon netjes vierkant of rond afhankelijk van de bron.
    st.image(recruiter['foto'], width=100)
with col2:
    st.markdown(f"### Je spreekt met **{recruiter['naam']}**")
    st.caption(f"Recruiter ({recruiter['geslacht']})")

# B. Voortgangsbalk
# We schatten dat een gesprek ongeveer 12 'beurten' heeft (start + 10 vragen + einde)
# history length begint op 2. Na start = 4. Na vraag 1 = 6.
huidige_stappen = (len(st.session_state.history) - 2) // 2
voortgang = min(huidige_stappen / 12, 1.0) 

if huidige_stappen > 0:
    st.progress(voortgang, text=f"Gespreksvoortgang ({int(voortgang*100)}%)")
else:
    st.write("---") # Scheidingslijn bij start

# C. Zijbalk Reset
with st.sidebar:
    st.header("Instellingen")
    if st.button("🔄 Nieuw Gesprek"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
    st.info("Tip: Spreek duidelijk en wacht tot de recruiter is uitgesproken.")

# --- 8. GESPREKS LOGICA ---

# Stap 1: De Startknop (alleen zichtbaar aan het begin)
if "conversation_started" not in st.session_state:
    st.write("Druk op start om de recruiter binnen te roepen.")
    if st.button("📞 Start het gesprek"):
        with st.spinner(f"{recruiter['naam']} komt eraan..."):
            response_text = get_response_from_ai("De kandidaat is er. Begin het gesprek.")
            audio_bytes = asyncio.run(text_to_speech_memory(response_text))
            
            st.session_state.last_audio_bytes = audio_bytes
            st.session_state.last_text = response_text
            st.session_state.conversation_started = True
            st.rerun()

# Stap 2: Het Antwoord van de Recruiter tonen en afspelen
if "last_audio_bytes" in st.session_state:
    # Een container voor de output maakt het visueel rustiger
    with st.container():
        st.success(f"🗣️ {recruiter['naam']} zegt:")
        st.markdown(f"*{st.session_state.last_text}*")
        st.audio(st.session_state.last_audio_bytes, format="audio/wav", autoplay=True)

# Stap 3: De Microfoon Knop
if "conversation_started" in st.session_state:
    st.write("---")
    st.markdown("### 🎙️ Jouw beurt")
    st.caption("Klik op de knop, spreek je antwoord in en klik op stop.")
    
    audio_input = mic_recorder(
        start_prompt="🔴 Klik om te spreken",
        stop_prompt="⏹️ Klik om te stoppen",
        key='recorder'
    )

    # Stap 4: Verwerking van de audio
    if audio_input:
        if "last_processed_audio" not in st.session_state:
            st.session_state.last_processed_audio = None
            
        if audio_input['bytes'] == st.session_state.last_processed_audio:
            pass 
        else:
            st.session_state.last_processed_audio = audio_input['bytes']
            import speech_recognition as sr
            
            with st.spinner("Luisteren en nadenken..."):
                try:
                    # A. Converteren
                    audio_segment = AudioSegment.from_file(io.BytesIO(audio_input['bytes']))
                    audio_segment.export("temp_input.wav", format="wav")
                    
                    # B. Herkennen
                    r = sr.Recognizer()
                    with sr.AudioFile("temp_input.wav") as source:
                        audio_data = r.record(source)
                        user_text = r.recognize_google(audio_data, language="nl-BE")
                        
                    # Feedback wat jij zei (klein tonen)
                    st.info(f"Jij zei: '{user_text}'")
                    
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


