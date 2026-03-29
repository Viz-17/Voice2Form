from flask import Flask, render_template, request, jsonify, send_file
import os
import json
from utils.speech import transcribe_audio
from utils.translate import translate_tamil_to_english
from utils.extract import extract_form_fields
from utils.tts import speak_tamil

app = Flask(__name__)
AUDIO_DIR = "audio"
os.makedirs(AUDIO_DIR, exist_ok=True)

# In-memory form state
form_data = {
    "name": "",
    "age": "",
    "gender": "",
    "phone": "",
    "address": "",
    "district": "",
    "aadhaar": "",
    "occupation": ""
}

FIELD_QUESTIONS_TAMIL = {
    "name":       "உங்கள் பெயர் என்ன?",
    "age":        "உங்கள் வயது என்ன?",
    "gender":     "நீங்கள் ஆண் அல்லது பெண்?",
    "phone":      "உங்கள் தொலைபேசி எண் என்ன?",
    "address":    "உங்கள் முகவரி என்ன?",
    "district":   "உங்கள் மாவட்டம் என்ன?",
    "aadhaar":    "உங்கள் ஆதார் எண் என்ன?",
    "occupation": "உங்கள் தொழில் என்ன?"
}

def get_next_empty_field():
    for field, value in form_data.items():
        if not value:
            return field
    return None

def get_confirmation_message(field, value):
    labels = {
        "name": "பெயர்", "age": "வயது", "gender": "பாலினம்",
        "phone": "தொலைபேசி எண்", "address": "முகவரி",
        "district": "மாவட்டம்", "aadhaar": "ஆதார் எண்", "occupation": "தொழில்"
    }
    label = labels.get(field, field)
    return f"உங்கள் {label} \"{value}\" சரியா?"

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/process_audio", methods=["POST"])
def process_audio():
    if "audio" not in request.files:
        return jsonify({"error": "No audio file"}), 400

    audio_file = request.files["audio"]
    audio_path = os.path.join(AUDIO_DIR, "input.wav")
    audio_file.save(audio_path)

    # Step 1: Transcribe
    tamil_text = transcribe_audio(audio_path)

    # Step 2: Translate
    english_text = translate_tamil_to_english(tamil_text)

    # Step 3: Extract fields
    extracted = extract_form_fields(english_text, tamil_text)

    # Step 4: Update form
    updated_fields = []
    for field, value in extracted.items():
        if value and not form_data.get(field):
            form_data[field] = value
            updated_fields.append(field)

    # Build response
    next_field = get_next_empty_field()
    all_done = next_field is None

    response_tamil = ""
    if updated_fields:
        confirmations = [get_confirmation_message(f, form_data[f]) for f in updated_fields]
        response_tamil = " ".join(confirmations)
        if not all_done:
            response_tamil += f" அடுத்து, {FIELD_QUESTIONS_TAMIL[next_field]}"
    elif all_done:
        response_tamil = "அனைத்து தகவல்களும் நிரப்பப்பட்டுவிட்டன. நன்றி!"
    else:
        #response_tamil = f"மன்னிக்கவும், புரியவில்லை. {FIELD_QUESTIONS_TAMIL[next_field]}
        if extracted:  
            response_tamil = f"சரி, பதிவு செய்யப்பட்டுள்ளது. {FIELD_QUESTIONS_TAMIL[next_field]}"
        else:
            response_tamil = f"மன்னிக்கவும், எனக்கு புரியவில்லை. {FIELD_QUESTIONS_TAMIL[next_field]}"

    # Generate TTS
    tts_path = speak_tamil(response_tamil)

    return jsonify({
        "tamil_text": tamil_text,
        "english_text": english_text,
        "extracted": extracted,
        "form_data": form_data,
        "response_tamil": response_tamil,
        "tts_audio": "/get_tts" if tts_path else None,
        "all_done": all_done,
        "next_field": next_field
    })

@app.route("/get_tts")
def get_tts():
    path = "audio/response.mp3"
    if os.path.exists(path):
        return send_file(path, mimetype="audio/mpeg")
    return "", 404

@app.route("/get_form")
def get_form():
    return jsonify(form_data)

@app.route("/reset_form", methods=["POST"])
def reset_form():
    global form_data
    form_data = {k: "" for k in form_data}
    return jsonify({"status": "reset", "form_data": form_data})

@app.route("/next_question")
def next_question():
    field = get_next_empty_field()
    if field:
        question = FIELD_QUESTIONS_TAMIL[field]
        tts_path = speak_tamil(question)
        return jsonify({
            "field": field,
            "question": question,
            "tts_audio": "/get_tts"
        })
    return jsonify({"field": None, "question": "அனைத்தும் நிரப்பப்பட்டது!"})

if __name__ == "__main__":
    app.run(debug=True, port=5000)
