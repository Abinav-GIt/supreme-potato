from flask import Flask, render_template, request, jsonify, send_from_directory
import speech_recognition as sr
from translate import Translator
from gtts import gTTS
import os
import textwrap
import time
from dotenv import load_dotenv
import google.generativeai as genai

# --- Load environment variables ---
load_dotenv()

# --- Configure Gemini AI ---
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

app = Flask(__name__)

# Directory for generated audio files
AUDIO_DIR = os.path.join(app.root_path, "static", "audio")
os.makedirs(AUDIO_DIR, exist_ok=True)


# 🎙️ --- Speech Recognition ---
def recognize_speech_from_file(file_path, language="en-US"):
    recognizer = sr.Recognizer()
    with sr.AudioFile(file_path) as source:
        audio = recognizer.record(source)
    try:
        text = recognizer.recognize_google(audio, language=language)
        return text
    except sr.UnknownValueError:
        return "Sorry, could not understand the audio."
    except sr.RequestError as e:
        return f"Request error: {e}"


@app.route('/')
def index():
    return render_template('index.html')


# 🌍 --- Translator Route ---
@app.route('/translate', methods=['POST'])
def translate_text():
    mode = request.form.get('mode')
    target_language = request.form.get('target_language')
    english_text = ""

    if mode == "speech":
        audio_file = request.files['audio']
        audio_path = os.path.join(AUDIO_DIR, "temp.wav")
        audio_file.save(audio_path)
        english_text = recognize_speech_from_file(audio_path, language="en-US")
        os.remove(audio_path)
    elif mode == "text":
        english_text = request.form.get('text')

    translator = Translator(from_lang="en", to_lang=target_language)
    translated_text = translator.translate(english_text)
    paragraph = textwrap.fill(translated_text, width=70)

    # Clean old audio files
    for old_file in os.listdir(AUDIO_DIR):
        if old_file.endswith(".mp3"):
            os.remove(os.path.join(AUDIO_DIR, old_file))

    # Generate new speech output
    timestamp = int(time.time())
    output_filename = f"output_{timestamp}.mp3"
    output_path = os.path.join(AUDIO_DIR, output_filename)

    try:
        tts = gTTS(text=paragraph, lang=target_language)
        tts.save(output_path)
    except Exception as e:
        return jsonify({"error": f"Text-to-speech failed: {str(e)}"})

    return jsonify({
        "input_text": english_text,
        "translated_text": paragraph,
        "audio_url": f"/static/audio/{output_filename}"
    })


# 🤖 --- Gemini Chatbot Route ---
@app.route('/chat', methods=['POST'])
def chat_with_ai():
    try:
        user_message = request.json.get("message", "")

        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(user_message)

        reply_text = response.text.strip()

        # Convert AI response to voice
        timestamp = int(time.time())
        ai_audio_filename = f"ai_reply_{timestamp}.mp3"
        ai_audio_path = os.path.join(AUDIO_DIR, ai_audio_filename)
        tts = gTTS(text=reply_text, lang="en")
        tts.save(ai_audio_path)

        return jsonify({
            "reply": reply_text,
            "audio_url": f"/static/audio/{ai_audio_filename}"
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Serve audio files
@app.route('/static/audio/<filename>')
def serve_audio(filename):
    return send_from_directory(AUDIO_DIR, filename)


if __name__ == '__main__':
    app.run(debug=False)
