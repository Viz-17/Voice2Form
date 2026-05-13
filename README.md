# Voice2Form - Tamil Voice Form Assistant

A voice-driven form filling system that converts Tamil speech into structured form data using Whisper ASR, translation, and rule-based extraction.

The system allows users to fill forms and challan details using voice input and provides Tamil audio feedback.


## Quick Setup

```bash
# 1. Create virtualenv
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. (Optional) Install ffmpeg for Whisper audio conversion
#    Ubuntu/Debian:
sudo apt install ffmpeg
#    macOS:
brew install ffmpeg
#    Windows: https://ffmpeg.org/download.html

# 4. Run
python app.py
```

Open http://localhost:5000 in your browser.

---

## Architecture

```
User speaks Tamil
   ↓
Browser mic (MediaRecorder API) → audio/webm
   ↓
Flask /process_audio endpoint
   ↓
utils/speech.py    → Whisper (Tamil ASR) → Tamil text
   ↓
utils/translate.py → deep_translator (Google) → English text
   ↓
utils/extract.py   → Hybrid rule-based NLP → {name, age, ...}
   ↓
Form state update + confirmation message
   ↓
utils/tts.py       → gTTS → Tamil MP3
   ↓
Chat UI response + audio playback
```

## Folder Structure

```
project/
├── app.py              Flask backend + form state
├── requirements.txt
├── templates/
│   └── index.html      Chat UI
├── static/
│   ├── style.css       Dark Tamil aesthetic
│   └── script.js       Recorder + UI logic
├── audio/
│   ├── input.wav       Recorded audio (temp)
│   └── response.mp3    TTS output (temp)
└── utils/
    ├── __init__.py
    ├── speech.py       Whisper ASR
    ├── translate.py    Tamil→English
    ├── extract.py      Field extraction
    └── tts.py          gTTS output
```

## Supported Form Fields

| Field      | Tamil          | Example Input                     |
|------------|----------------|-----------------------------------|
| name       | பெயர்          | "என் பெயர் ரமேஷ்"                |
| age        | வயது           | "நான் 25 வயது"                   |
| gender     | பாலினம்        | "நான் ஆண்" / "நான் பெண்"        |
| phone      | தொலைபேசி எண்   | "என் நம்பர் 9876543210"          |
| address    | முகவரி         | "என் வீடு 12 Anna Nagar"         |
| district   | மாவட்டம்       | "என் மாவட்டம் Chennai"           |
| aadhaar    | ஆதார் எண்      | "என் ஆதார் 1234 5678 9012"       |
| occupation | தொழில்         | "நான் ஒரு ஆசிரியர்"             |

## Tips for Better Accuracy

- Speak clearly, one field at a time
- Whisper `small` model is fast; switch to `medium` for better Tamil accuracy
- For offline use, deep_translator works without API key

## Model Upgrade (Better Tamil)

In `utils/speech.py`, change:
```python
_model = whisper.load_model("medium")  # Better accuracy
```

## Changelog

### Version 3 (current)

- **Bank challan form** — new voice-driven flow for bank transactions (Deposit / Withdrawal)
- **Challan fields**: name, account number, bank, branch, transaction type, amount
- **Length-aware account validation** — accepts 9–18 digit account numbers; rejects anything outside that range with a Tamil error message
- **Last-digit mismatch detection** — if all digits except the last match a known account, the user is warned and shown the correct number
- **Name-first enforcement** — account/amount/transaction steps require a name to be established first
- **Challan data separation** — submissions saved to `challandata.json`, separate from general form data (`data.json`)
- **Challan endpoints** — `/process_challan`, `/challan_lookup`, `/confirm_challan`

### Version 2

- **Multi-model ASR** — `model` parameter selects Whisper or Vosk at request time
- **WER / accuracy metrics** — pass `ground_truth` to `/process_audio` to evaluate transcription quality
- **Phonetic correction layer** — fixes common Whisper mishears for Tamil
- **Dial pad auto-open** — triggers automatically for Phone and Aadhaar fields
- **Confirmation gate** — data saved to JSON only after explicit user confirmation

### Version 1

- Basic Tamil voice form filling with Whisper + gTTS
- Single-account mock DB
- Manual field entry fallback
