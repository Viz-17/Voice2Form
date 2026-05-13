from flask import Flask, render_template, request, jsonify, send_file
import os
import json
import re
import datetime
from utils.speech import transcribe_audio
from utils.translate import translate_tamil_to_english
from utils.extract import extract_form_fields
from utils.tts import speak_tamil
from utils.extract import extract_account_number, extract_amount, extract_challan_name, extract_transaction_type, extract_tamil_name

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

# ── Mock accounts database ─────────────────────────────────────
# accounts_db = {
#     "vishwa": {
#         "account": "1234567890",
#         "bank":    "SBI",
#         "branch":  "Chennai Main"
#     },
#     "arun": {
#         "account": "9876543210",
#         "bank":    "HDFC",
#         "branch":  "T Nagar"
#     },
#     "priya": {
#         "account": "5678901234",
#         "bank":    "Canara Bank",
#         "branch":  "Coimbatore"
#     },
#     "kumar": {
#         "account": "4321098765",
#         "bank":    "Indian Bank",
#         "branch":  "Madurai"
#     },
#     "kumar_1": {
#         "account": "1234567890", 
#         "bank":    "ICICI",
#         "branch":  "T Nagar"
#     },
#     "kumar_2": {
#         "account": "98765432101234", 
#         "bank":    "HDFC",
#         "branch":  "Anna Nagar"
#     }
# }

accounts_db = {
    "vishwa": [
        {"account": "1234567890",   "bank": "SBI",         "branch": "Chennai Main"},
        {"account": "989463522933", "bank": "Canara Bank", "branch": "Tambaram"},
    ],
    "arun": [
        {"account": "98765433214569",   "bank": "HDFC",        "branch": "T Nagar"},
        {"account": "987654321212","bank": "Axis Bank",  "branch": "Guindy"},
    ],
    "priya": [
        {"account": "567890123422",   "bank": "Canara Bank", "branch": "Coimbatore"},
    ],
    "kumar": [
        {"account": "432159876512",     "bank": "ICICI",  "branch": "Madurai"},
        {"account": "9876543212",   "bank": "SBI",    "branch": "Chennai"},
        {"account": "12345678912357", "bank": "HDFC",   "branch": "Coimbatore"},
    ],
    "vishal": [
        {"account": "1472583695",   "bank": "Punjab National Bank", "branch": "kelambakkam"},
    ],
    "sankar": [
        {"account": "12365478954321",   "bank": "Kotak Mahindra Bank", "branch": "vellore"},
    ],
}
 
def _match_account(name_key: str, input_acc: str):
    """
    Find the best matching account for a user given their input.

    Returns (matched_entry, warning_msg, suggested_account)
      - matched_entry:    dict with bank/branch, or None
      - warning_msg:      non-empty string if last digit mismatches
      - suggested_account: correct account string if warning triggered
    """
    entries = accounts_db.get(name_key.lower().strip())

    if not entries:
        entries = []
        for acc_list in accounts_db.values():
            entries.extend(acc_list)

    if not entries:
        return None, "", ""

    input_clean = re.sub(r'\D', '', input_acc)   # digits only
    input_len   = len(input_clean)

    if input_len < 9 or input_len>18:                            # too short — graceful fallback
        return None, "", ""

    # Step 1: filter to same-length accounts
    same_len = [e for e in entries if len(e["account"]) == input_len]

    if not same_len:
        # No account with this length — graceful fallback
        return None, "", ""

    # Step 2: exact match
    for entry in same_len:
        if input_clean == entry["account"]:
            return entry, "", ""

    # Step 3: N-1 prefix match (last digit differs)
    for entry in same_len:
        correct = entry["account"]
        if input_clean[:-1] == correct[:-1] and input_clean[-1] != correct[-1]:
            warning = (
                f"கடைசி இலக்கம் தவறாக உள்ளது. "
                f"உங்கள் கணக்கு எண் {correct} சரியா? "
                f"(Last digit seems incorrect. Did you mean {correct}?)"
            )
            return entry, warning, correct

    # Step 4: no prefix match either — graceful fallback
    return None, "", ""

# ── Challan route ──────────────────────────────────────────────
@app.route("/process_challan", methods=["POST"])
def process_challan():
    """
    Accepts Tamil voice audio, extracts challan fields,
    validates account number against mock DB, returns JSON.
    Reuses existing transcribe + translate logic.
    """
    if "audio" not in request.files:
        return jsonify({"error": "No audio file"}), 400
 
    audio_file = request.files["audio"]
    audio_path = os.path.join(AUDIO_DIR, "challan_input.wav")
    audio_file.save(audio_path)
 
    step       = request.form.get("step", "")
    known_name = request.form.get("known_name", "").strip().lower()
 
    # ── Reuse existing STT + translation ──────────────────────
    tamil_text   = transcribe_audio(audio_path)
    english_text = translate_tamil_to_english(tamil_text)
    combined     = (english_text + " " + tamil_text).lower()
 
    from utils.extract import (
        extract_account_number,
        extract_amount,
        extract_challan_name,
        extract_transaction_type,
    )
 
    name             = extract_challan_name(english_text) or ""
    account_input    = extract_account_number(english_text)
    amount           = extract_amount(english_text)
    transaction_type = extract_transaction_type(combined)
 
    # ── Empty input guard ──────────────────────────────────────
    if not any([name, account_input, amount, transaction_type]):
        return jsonify({"error": "Could not understand input",
                        "tamil_text": tamil_text})
 
    # ── Strict name-missing fallback ───────────────────────────
    # If we need account/amount but have no name context at all
    effective_name = (known_name or name.lower()).strip()
    if not effective_name and step in ("account", "amount", "txn"):
        return jsonify({
            "error":      "name_missing",
            "message":    "உங்கள் பெயரை முதலில் சொல்லுங்கள்",
            "tamil_text": tamil_text,
        })
 
    # ── Account validation (last-digit logic) ─────────────────
    warning          = ""
    suggested_account = ""
 
    # if account_input and effective_name:
    #     db_entry = accounts_db.get(effective_name)
    #     if db_entry:
    #         correct_acc = db_entry["account"]
    #         # Check first 9 digits match, last digit differs
    #         if (len(account_input) == 10 and len(correct_acc) == 10
    #                 and account_input[:9] == correct_acc[:9]
    #                 and account_input[-1] != correct_acc[-1]):
    #             warning = (
    #                 f"கடைசி இலக்கம் தவறாக உள்ளது. "
    #                 f"உங்கள் கணக்கு எண் {correct_acc} சரியா? "
    #                 f"(Last digit seems incorrect. Did you mean {correct_acc}?)"
    #             )
    #             suggested_account = correct_acc

    if account_input and effective_name:
        if len(account_input) < 9 or len(account_input) > 18:
            return jsonify({
                "error": "invalid_length",
                "message": "கணக்கு எண் 9 முதல் 18 இலக்கங்களுக்குள் இருக்க வேண்டும்."
            })
        matched_entry, warning, suggested_account = _match_account(
            effective_name, account_input
        )
        # 1. Strict Length Check
        # if len(account_input) != 10:
        #     return jsonify({
        #         "error": "invalid_length",
        #         "message": "கணக்கு எண் 10 இலக்கங்களாக இருக்க வேண்டும்." # Account number must be 10 digits
        #     })
            
        # # 2. Search DB using the first 9 digits of the account number (IGNORE NAME)
        # for key, db_entry in accounts_db.items():
        #     correct_acc = db_entry["account"]
        #     if account_input[:9] == correct_acc[:9]:
        #         # Found a match! Now check if the 10th digit is wrong
        #         if account_input[-1] != correct_acc[-1]:
        #             warning = (
        #                 f"கடைசி இலக்கம் தவறாக உள்ளது. "
        #                 f"உங்கள் கணக்கு எண் {correct_acc} சரியா?"
        #             )
        #             suggested_account = correct_acc
        #         break
 
    # ── DO NOT auto-fill account from DB ──────────────────────
    # User must provide their own account number (spec requirement)
 
    # ── TTS confirmation message ───────────────────────────────
    tts_msg = ""
    if name:
        tts_msg = f"பெயர் {name} பதிவு செய்யப்பட்டது."
    elif account_input:
        tts_msg = f"கணக்கு எண் {account_input} சரிபார்க்கப்படுகிறது."
    elif amount:
        tts_msg = f"தொகை ரூபாய் {amount} பதிவு செய்யப்பட்டது."
    elif transaction_type:
        tts_msg = f"{'வைப்பு' if transaction_type == 'Deposit' else 'எடுக்கல்'} தேர்ந்தெடுக்கப்பட்டது."
 
    if tts_msg:
        speak_tamil(tts_msg)
 
    return jsonify({
        "tamil_text":        tamil_text,
        "english_text":      english_text,
        "name":              name,
        "tamil_name":        extract_tamil_name(tamil_text) or tamil_text.strip(),
        "account_number":    account_input,
        "amount":            amount,
        "transaction_type":  transaction_type,
        "warning":           warning,
        "suggested_account": suggested_account,
        "tts_audio":         "/get_tts" if tts_msg else None,
    })


 
# @app.route("/challan_lookup", methods=["POST"])
# def challan_lookup():
#     """
#     Quick name lookup — called when user types a name manually.
#     Returns bank + branch + account for auto-fill.
#     """
#     data     = request.json or {}
#     acc_key = data.get("account", "").strip()
#     #entry    = accounts_db.get(name_key)
 
#     # for key, entry in accounts_db.items():
#     #     if entry["account"] == acc_key:
#     #         return jsonify({
#     #             "found":   True,
#     #             "account": entry["account"],
#     #             "bank":    entry["bank"],
#     #             "branch":  entry["branch"],
#     #         })

#     for key, entry in accounts_db.items():
#         correct_acc = entry["account"]

#         # Match first 9 digits (Ignore the Name)
#         if acc_key[:9] == correct_acc[:9]:
#             # If the last digit is wrong, return the warning
#             if acc_key[-1] != correct_acc[-1]:
#                 return jsonify({
#                     "found": False,
#                     "warning": f"கடைசி இலக்கம் தவறாக உள்ளது. உங்கள் கணக்கு எண் {correct_acc} சரியா?",
#                     "suggested_account": correct_acc
#                 })
            
#             # If it is an exact 10-digit match, return bank details
#             return jsonify({
#                 "found":   True,
#                 "account": entry["account"],
#                 "bank":    entry["bank"],
#                 "branch":  entry["branch"],
#             })
        
#     return jsonify({"found": False})
 
@app.route("/challan_lookup", methods=["POST"])
def challan_lookup():
    """
    Called ONLY after frontend confirms the account number, 
    or during manual typing to check the 1-digit rule.
    Uses smart matching to find the right account by length + prefix.
    """
    data          = request.json or {}
    name_key      = data.get("name", "").lower().strip()
    account_input = data.get("account", "").strip()

    # We need both the name and account to do a safe lookup
    if not account_input:
        return jsonify({"found": False})

    # 1. REUSE your helper function!
    matched_entry, warning_msg, suggested_acc = _match_account(name_key, account_input)

    # 2. Check if the helper found a 1-digit mismatch
    if warning_msg:
        return jsonify({
            "found": False,
            "warning": warning_msg,
            "suggested_account": suggested_acc
        })
    
    # 3. Check if the helper found a perfect match
    if matched_entry:
        return jsonify({
            "found":   True,
            "account": matched_entry["account"],
            "bank":    matched_entry["bank"],
            "branch":  matched_entry["branch"],
        })

    # 4. No match at all
    return jsonify({"found": False})



CHALLAN_DATA_FILE = "challandata.json"
@app.route("/confirm_challan", methods=["POST"])
def confirm_challan():
    """Save confirmed challan to data.json."""
    import datetime
    import json
    import os

    data = request.json or {}
    data["type"]= "challan"
    data["submitted_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # save_submission(data)

    # Check if challandata.json exists and load it
    if os.path.exists(CHALLAN_DATA_FILE):
        with open(CHALLAN_DATA_FILE, "r", encoding="utf-8") as f:
            try:
                existing = json.load(f)
                if not isinstance(existing, list):
                    existing = []
            except json.JSONDecodeError:
                existing = []
    else:
        existing = []

    # Append new challan and save
    existing.append(data)

    with open(CHALLAN_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    return jsonify({"ok": True})

if __name__ == "__main__":
    app.run(debug=True, port=5000)