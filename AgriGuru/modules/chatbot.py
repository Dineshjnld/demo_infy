# AgriGuru/modules/chatbot.py
import streamlit as st
import os
import time
import io
import tempfile # For handling audio data with Whisper
import re

# Attempt to import AI model libraries, with fallbacks to mock if not available
# Global model variables to load them only once
whisper_model = None
indic_t5_tokenizer = None
indic_t5_model = None
# IndicConformer would require more complex setup, focusing on Whisper first as per plan.

# --- 1. Speech-to-Text (ASR) ---
try:
    import whisper
    # No automatic model loading here; will be loaded on first use or if pre-loaded in app.py
except ImportError:
    whisper = None
    # st.sidebar.warning("Whisper library not installed. ASR will be mocked or disabled.")

# IndicConformer integration is more involved and typically comes from specific research repos.
# For this step, we focus on Whisper as primary and fallback to mock.
# IndicConformer_ASR = None # Placeholder

def transcribe_audio_whisper_api(audio_bytes, model_size="medium"): # Changed to medium as requested
    """
    Transcribes audio bytes using OpenAI Whisper.
    Saves bytes to a temporary file as Whisper CLI/library often expects a file path.
    """
    global whisper_model
    if whisper is None:
        return {"text": None, "error": "Whisper library not installed."}

    try:
        if whisper_model is None or whisper_model.name != model_size:
            # st.info(f"Loading Whisper model '{model_size}' (this may take a while)...") # UI in main app
            print(f"Loading Whisper model '{model_size}'...") # Console log for agent
            whisper_model = whisper.load_model(model_size)
            print(f"Whisper model '{model_size}' loaded.")
            # st.info("Whisper model loaded.") # UI in main app

        # Whisper expects a file path. Save audio_bytes to a temporary file.
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_audio_file:
            tmp_audio_file.write(audio_bytes)
            tmp_audio_file_path = tmp_audio_file.name

        result = whisper_model.transcribe(tmp_audio_file_path)

        os.remove(tmp_audio_file_path) # Clean up temporary file
        return {"text": result["text"], "language": result.get("language"), "error": None}

    except Exception as e:
        # Log full error for debugging
        # print(f"Whisper transcription error: {e}", traceback.format_exc())
        return {"text": None, "error": f"Whisper transcription error: {str(e)}"}

def transcribe_audio_indic_conformer_mock(audio_bytes):
    # This remains a mock as IndicConformer setup is complex
    time.sleep(1) # Simulate processing
    return {"text": "Mock IndicConformer: नमस्ते दुनिया", "language": "hi", "error": None} # Hello world in Hindi

# --- 2. Transcript Correction / Normalization (NLP) ---
try:
    from transformers import T5Tokenizer, T5ForConditionalGeneration
    # AI4Bharat's IndicT5 is a good choice. Example: 'ai4bharat/indic-t5-small'
    # Using 'small' or 'base' for lighter resource use.
    INDIC_T5_MODEL_NAME = "ai4bharat/indic-t5-small"
except ImportError:
    T5Tokenizer = None
    T5ForConditionalGeneration = None
    # st.sidebar.warning("Transformers library not installed. Transcript correction will be mocked.")

def correct_transcript_indic_t5(text, source_lang="en"): # Assuming source_lang detection from Whisper
    """
    Corrects/Normalizes transcript using IndicT5.
    IndicT5 is multilingual; for simple correction, we might not need complex prompting.
    For true "correction", it might need specific fine-tuning or prompting strategies.
    Here, we'll use it more for normalization or a light pass.
    """
    global indic_t5_tokenizer, indic_t5_model
    if T5Tokenizer is None or T5ForConditionalGeneration is None:
        return {"text": text, "error": "Transformers/IndicT5 not available. Returning original text."}

    try:
        if indic_t5_tokenizer is None or indic_t5_model is None:
            # st.info(f"Loading IndicT5 model '{INDIC_T5_MODEL_NAME}' (this may take a while)...") # UI in main app
            print(f"Loading IndicT5 model '{INDIC_T5_MODEL_NAME}'...") # Console log
            indic_t5_tokenizer = T5Tokenizer.from_pretrained(INDIC_T5_MODEL_NAME)
            indic_t5_model = T5ForConditionalGeneration.from_pretrained(INDIC_T5_MODEL_NAME)
            print("IndicT5 model loaded.")
            # st.info("IndicT5 model loaded.") # UI in main app

        # IndicT5 often uses task prefixes. For general text normalization/improvement,
        # it might not be a standard prefix. We'll try a simple pass-through.
        # For more advanced correction, specific prefixes or fine-tuning would be needed.
        # Example prefix for translation: f"translate {source_lang} to {target_lang}: {text}"
        # For now, let's assume a simple "clean-up" task without a specific prefix,
        # or a generic one if the model documentation suggests it.
        # This part is highly dependent on the model's capabilities for "correction".

        # Using a generic approach, may not yield strong "correction" without specific fine-tuning/prompting.
        input_ids = indic_t5_tokenizer(text, return_tensors="pt").input_ids
        outputs = indic_t5_model.generate(input_ids, max_length=len(text.split())*2 + 10) # Allow some expansion
        corrected_text = indic_t5_tokenizer.decode(outputs[0], skip_special_tokens=True)

        return {"text": corrected_text, "error": None}
    except Exception as e:
        return {"text": text, "error": f"IndicT5 processing error: {str(e)}"}


# --- 3. Query Classification (NLP) ---
def classify_query_basic(text):
    """Basic keyword-based query classification."""
    text_lower = text.lower()
    # More specific keywords first
    if any(k in text_lower for k in ["market price", "mandi price", "rate for", "what is the price of", "bhav", "मूल्य", "बाजार भाव"]):
        return "market"
    elif any(k in text_lower for k in ["weather", "forecast", "temperature", "rain", "मौसम", "तापमान", "बारिश"]):
        return "weather"
    elif any(k in text_lower for k in ["crop suggestion", "suitable crop", "which crop to grow", "फसल सुझाव", "कौन सी फसल"]):
        return "crop"
    elif any(k in text_lower for k in ["soil type", "soil ph", "soil data", "मिट्टी का प्रकार", "मिट्टी पीएच"]):
        return "soil"
    elif any(k in text_lower for k in ["hello", "hi", "namaste", "नमस्ते", "hey"]):
        return "greeting"
    else:
        return "general"

# --- 4. Response Generation (Logic/Retrieval) ---
# This will still be somewhat mock/rule-based but use the classification.
def generate_response_for_query(query, classification, user_location_context):
    """Generates a response based on query classification and user location context."""
    district = user_location_context.get('district', 'your area') if user_location_context else 'your area'
    response_text = f"I received your query: '{query}' (classified as: {classification}). "

    if classification == "weather":
        response_text += f"You can find the detailed weather forecast for {district} in the 'Weather' tab."
    elif classification == "crop":
        response_text += f"Crop suggestions based on conditions in {district} are available under 'Crop Suggestions'."
    elif classification == "soil":
        response_text += f"Information about soil in {district} can be found on the 'Map & Soil' tab."
    elif classification == "market":
        # Try to extract commodity from query (very basic)
        commodity_match = re.search(r"(?:price of|rate for|market for|bhav for)\s+([a-zA-Z\s]+)", query, re.IGNORECASE)
        commodity = commodity_match.group(1).strip() if commodity_match else "your commodity"
        response_text += f"Market prices for {commodity} in {district} are available in the 'Market Prices' tab. Please select the commodity there."
    elif classification == "greeting":
        response_text = "Hello! How can I help you with farming-related information for your area today?"
    else: # General
        response_text += "I can help with information about weather, crop suitability, soil, and market prices. Please try asking about one of those topics for your detected location."

    return {"text": response_text, "error": None}


# --- 5. Text-to-Speech (TTS) ---
try:
    from gtts import gTTS
    # from pydub import AudioSegment # For converting MP3 from gTTS to other formats if needed by st.audio
except ImportError:
    gTTS = None
    # st.sidebar.warning("gTTS library not installed. TTS will be mocked or disabled.")

def text_to_speech_gtts(text, lang='en'):
    """Converts text to speech using gTTS and returns audio bytes (MP3 format)."""
    if gTTS is None:
        return {"audio_bytes": None, "error": "gTTS library not installed."}
    try:
        tts = gTTS(text=text, lang=lang, slow=False)
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        return {"audio_bytes": fp.read(), "format": "audio/mp3", "error": None}
    except Exception as e:
        return {"audio_bytes": None, "error": f"gTTS error: {str(e)}"}

# --- Main Chatbot Interaction Logic ---
def handle_chat_input(user_input_text=None, audio_bytes_data=None, user_location=None):
    """
    Orchestrates the chatbot response flow.
    Args:
        user_input_text (str, optional): Text input from the user.
        audio_bytes_data (bytes, optional): Audio data if input is voice.
        user_location (dict): Location context.
    Returns:
        dict: { "user_transcript": str, "bot_response_text": str,
                "bot_response_audio_bytes": bytes, "bot_audio_format": str, "error": str }
    """
    # Initialize response structure
    result = {
        "user_transcript": None, "bot_response_text": None,
        "bot_response_audio_bytes": None, "bot_audio_format": None, "error": None
    }

    current_transcript = user_input_text
    asr_source_language = "en" # Default, can be updated by ASR

    # 1. ASR (if audio data is provided)
    if audio_bytes_data:
        # Primary: Whisper
        asr_result = transcribe_audio_whisper_api(audio_bytes_data)
        if asr_result.get("error") or not asr_result.get("text"):
            # Fallback: Mock IndicConformer (or could be another ASR)
            # st.sidebar.warning(f"Whisper ASR failed: {asr_result.get('error')}. Trying fallback ASR.") # UI in app.py
            print(f"Whisper ASR failed: {asr_result.get('error')}. Trying mock IndicConformer.")
            asr_result = transcribe_audio_indic_conformer_mock(audio_bytes_data) # This is still a mock

        if asr_result.get("error") or not asr_result.get("text"):
            result["error"] = f"ASR failed: {asr_result.get('error', 'Could not transcribe audio.')}"
            result["bot_response_text"] = "I'm sorry, I couldn't understand your audio. Please try speaking clearly or type your query."
            # Try TTS for the error message itself
            tts_error_response = text_to_speech_gtts(result["bot_response_text"])
            result["bot_response_audio_bytes"] = tts_error_response.get("audio_bytes")
            result["bot_audio_format"] = tts_error_response.get("format")
            return result

        current_transcript = asr_result["text"]
        result["user_transcript"] = current_transcript # Store what ASR produced
        asr_source_language = asr_result.get("language", "en")
        # st.sidebar.info(f"🎤 You (ASR - {asr_source_language}): {current_transcript}") # UI in app.py
        print(f"ASR Transcript ({asr_source_language}): {current_transcript}")

    if not current_transcript:
        result["error"] = "No input received."
        result["bot_response_text"] = "Did you say something? I didn't get any input."
        return result

    # 2. Transcript Correction/Normalization (Optional, can be heavy)
    # For now, let's make it a lighter pass or skip if it's too slow without a powerful machine.
    # corrected_nlp_result = correct_transcript_indic_t5(current_transcript, source_lang=asr_source_language)
    # if corrected_nlp_result.get("error"):
    #     st.sidebar.warning(f"Transcript correction failed: {corrected_nlp_result['error']}. Using raw transcript.") # UI in app.py
    # else:
    #     current_transcript = corrected_nlp_result["text"]
    #     st.sidebar.info(f"🗣️ You (Processed): {current_transcript}") # UI in app.py
    # For now, using the direct ASR output for classification to keep it lighter.
    result["user_transcript"] = result["user_transcript"] or current_transcript # Ensure it's set

    # 3. Query Classification
    classification = classify_query_basic(current_transcript)

    # 4. Response Generation
    response_gen_result = generate_response_for_query(current_transcript, classification, user_location)
    result["bot_response_text"] = response_gen_result["text"]
    if response_gen_result.get("error"): # Should ideally not happen with current mock
        result["error"] = (result["error"] + " | " if result["error"] else "") + response_gen_result["error"]


    # 5. Text-to-Speech for voice output
    if result["bot_response_text"]:
        # Basic language detection for TTS (very simple, can be improved)
        # If any Hindi character is present, assume Hindi for TTS.
        tts_lang = 'hi' if any('\u0900' <= char <= '\u097F' for char in result["bot_response_text"]) else 'en'

        tts_result = text_to_speech_gtts(result["bot_response_text"], lang=tts_lang)
        if tts_result.get("error"):
             result["error"] = (result["error"] + " | " if result["error"] else "") + tts_result["error"]
        result["bot_response_audio_bytes"] = tts_result.get("audio_bytes")
        result["bot_audio_format"] = tts_result.get("format")

    return result


if __name__ == '__main__':
    # Example Usage (for testing module standalone with Streamlit)
    # To run this test: streamlit run AgriGuru/modules/chatbot.py
    # Ensure you have installed: streamlit, openai-whisper, torch, transformers, sentencepiece, gtts
    # You might need ffmpeg for Whisper: sudo apt-get install ffmpeg

    st.set_page_config(layout="wide")
    st.title("Test: AgriGuru Chatbot Module (with AI Models)")

    st.info("""
    **Instructions for Testing:**
    1.  **ASR (Whisper):** Upload a short audio file (e.g., .wav, .mp3). The 'medium' model will be downloaded on first use (can take time & space).
    2.  **NLP (IndicT5):** Currently, IndicT5 correction is commented out in `handle_chat_input` for lighter testing. To enable, uncomment the relevant section. It will download 'ai4bharat/indic-t5-small' on first use.
    3.  **TTS (gTTS):** Converts the bot's text response to speech.
    4.  View console logs for model loading messages if running locally.
    """)

    mock_location = {"district": "Testville", "state": "Testland", "country": "TestCountry"}

    st.sidebar.header("Chat Controls")
    input_method = st.sidebar.radio("Input Method:", ("Text", "Audio Upload"))

    final_response = None

    if input_method == "Text":
        text_query = st.sidebar.text_input("Your Text Query:", "Hello, what is the weather like?")
        if st.sidebar.button("Send Text Query"):
            if text_query:
                with st.spinner("Processing your text query..."):
                    final_response = handle_chat_input(user_input_text=text_query, user_location=mock_location)
            else:
                st.sidebar.warning("Please enter a query.")

    elif input_method == "Audio Upload":
        uploaded_audio_file = st.sidebar.file_uploader("Upload Audio File (WAV, MP3):", type=['wav', 'mp3', 'm4a', 'ogg'])
        if uploaded_audio_file is not None:
            if st.sidebar.button("Process Uploaded Audio"):
                audio_bytes = uploaded_audio_file.read()
                with st.spinner("Transcribing and processing audio... This may take a while, especially on first ASR model load."):
                    final_response = handle_chat_input(audio_bytes_data=audio_bytes, user_location=mock_location)

    st.markdown("---")
    st.subheader("Chat Interaction:")

    if final_response:
        if final_response.get("user_transcript"):
            st.markdown(f"**You said/typed:** {final_response['user_transcript']}")

        if final_response.get("bot_response_text"):
            st.markdown(f"**AgriGuru Bot:** {final_response['bot_response_text']}")

        if final_response.get("bot_response_audio_bytes"):
            st.audio(final_response["bot_response_audio_bytes"], format=final_response.get("bot_audio_format", "audio/mp3"))
        elif final_response.get("bot_response_text"): # If TTS failed but text is there
            st.warning("Could not generate audio response for the text.")

        if final_response.get("error"):
            st.error(f"**Error during processing:** {final_response['error']}")

    st.markdown("---")
    st.subheader("Model Loading Status (Illustrative - Check Console for Actual Logs)")
    if whisper and whisper_model:
        st.success(f"Whisper model '{whisper_model.name}' is loaded.")
    else:
        st.warning("Whisper model not yet loaded (or library not found). Will load on first audio processing.")

    if T5Tokenizer and indic_t5_model:
        st.success(f"IndicT5 model '{INDIC_T5_MODEL_NAME}' is loaded.")
    else:
        st.warning("IndicT5 model/tokenizer not yet loaded (or library not found). Will load if correction step is enabled and used.")

    if gTTS:
        st.success("gTTS library is available for Text-to-Speech.")
    else:
        st.error("gTTS library not found. TTS will fail.")
```
