from flask import Flask, render_template, request, jsonify, send_file
import os
import json
import re
import datetime
from utils.speech import transcribe_audio
from utils.translate import translate_tamil_to_english
from utils.extract import extract_form_fields
from utils.tts import speak_tamil

app = Flask(__name__)
AUDIO_DIR = "audio"
os.makedirs(AUDIO_DIR, exist_ok=True)

DATA_FILE = "data.json"

# ── Save submission to JSON file ───────────────────────────────
def save_submission(form_data: dict):
    """Append a confirmed form submission to data.json."""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            try:
                existing = json.load(f)
                if not isinstance(existing, list):
                    existing = []
            except json.JSONDecodeError:
                existing = []
    else:
        existing = []

    entry = dict(form_data)
    entry["submitted_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    existing.append(entry)

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)


# ── In-memory form state ───────────────────────────────────────
form_data = {
    "name": None, "age": None, "gender": None,
    "phone": None, "address": None, "district": None,
    "aadhaar": None, "occupation": None
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


# ── Helpers ────────────────────────────────────────────────────
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


def _is_valid(field, value):
    if field == "phone":
        return bool(re.fullmatch(r'[6-9]\d{9}', re.sub(r'\D', '', str(value))))
    if field == "aadhaar":
        digits = re.sub(r'\D', '', str(value))
        return len(digits) == 12 and digits[0] not in "01"
    return bool(value and str(value).strip())


# ── Routes ─────────────────────────────────────────────────────
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

    # Step 4: Validate and update form state
    validation_errors = {}
    updated_fields = []
    for field, value in extracted.items():
        if value and form_data.get(field) is None:
            if _is_valid(field, value):
                form_data[field] = value
                updated_fields.append(field)
            else:
                validation_errors[field] = value

    # Step 5: Build response message
    next_field = get_next_empty_field()
    all_done   = next_field is None

    response_tamil = ""
    if updated_fields:
        confirmations  = [get_confirmation_message(f, form_data[f]) for f in updated_fields]
        response_tamil = " ".join(confirmations)
        if not all_done:
            response_tamil += f" அடுத்து, {FIELD_QUESTIONS_TAMIL[next_field]}"
    elif all_done:
        response_tamil = "அனைத்து தகவல்களும் நிரப்பப்பட்டுவிட்டன. நன்றி!"
    else:
        if extracted:
            response_tamil = f"சரி, பதிவு செய்யப்பட்டுள்ளது. {FIELD_QUESTIONS_TAMIL[next_field]}"
        else:
            response_tamil = f"மன்னிக்கவும், எனக்கு புரியவில்லை. {FIELD_QUESTIONS_TAMIL[next_field]}"

    # Step 6: Generate TTS
    tts_path = speak_tamil(response_tamil)

    return jsonify({
        "tamil_text":       tamil_text,
        "english_text":     english_text,
        "extracted":        extracted,
        "form_data":        form_data,
        "response_tamil":   response_tamil,
        "tts_audio":        "/get_tts" if tts_path else None,
        "all_done":         all_done,
        "next_field":       next_field,
        "validation_errors": validation_errors
    })


@app.route("/manual_input", methods=["POST"])
def manual_input():
    data  = request.json or {}
    field = data.get("field", "")
    value = data.get("value", "").strip()

    if _is_valid(field, value):
        form_data[field] = re.sub(r'\D', '', value) if field in ("phone", "aadhaar") else value
        next_field = get_next_empty_field()
        return jsonify({
            "ok":         True,
            "form_data":  form_data,
            "next_field": next_field
        })
    return jsonify({"ok": False, "error": f"Invalid {field}"})


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
    form_data = {k: None for k in form_data}
    return jsonify({"status": "reset", "form_data": form_data})


@app.route("/next_question")
def next_question():
    field = get_next_empty_field()
    if field:
        question = FIELD_QUESTIONS_TAMIL[field]
        tts_path = speak_tamil(question)
        return jsonify({
            "field":     field,
            "question":  question,
            "tts_audio": "/get_tts"
        })
    return jsonify({"field": None, "question": "அனைத்தும் நிரப்பப்பட்டது!"})


@app.route("/confirm_preview", methods=["GET"])
def confirm_preview():
    filled  = {k: v for k, v in form_data.items() if v}
    missing = [k for k, v in form_data.items() if not v]
    return jsonify({"filled": filled, "missing": missing})


# ── NEW: Final confirmation + save ────────────────────────────
@app.route("/confirm_submit", methods=["POST"])
def confirm_submit():
    """
    Called when user clicks Yes in the confirmation panel.
    Validates all required fields are present, saves to data.json,
    then returns a success response.
    """
    # Check no required fields are empty
    missing = [k for k, v in form_data.items() if not v]
    if missing:
        return jsonify({
            "ok":      False,
            "message": f"சில தகவல்கள் இன்னும் நிரப்பப்படவில்லை: {', '.join(missing)}"
        })

    # Save only after user confirmation
    save_submission(form_data)

    # Generate a thank-you TTS
    msg = "உங்கள் விண்ணப்பம் வெற்றிகரமாக சமர்ப்பிக்கப்பட்டது! நன்றி!"
    speak_tamil(msg)

    return jsonify({
        "ok":      True,
        "message": msg,
        "tts_audio": "/get_tts"
    })


@app.route("/submissions")
def view_submissions():
    """View all saved submissions — useful during demo."""
    if not os.path.exists(DATA_FILE):
        return jsonify([])
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        try:
            return jsonify(json.load(f))
        except json.JSONDecodeError:
            return jsonify([])


if __name__ == "__main__":
    app.run(debug=True, port=5000)