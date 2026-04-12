# Voice2Form - Tamil Voice Form Assistant

A voice-driven form filling system that converts Tamil speech into structured data using Whisper ASR and NLP.
Supports Tamil-English mixed input and provides audio feedback using TTS.

## 🚧 Status
Initial build – actively improving Tamil extraction accuracy and UI


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

## VERSION - 2

## What's New in This Version

### Voice & Extraction
- Whisper `initial_prompt` added to bias Tamil form vocabulary recognition
- Phonetic correction layer: fixes common mishears
- Improved regex extraction: handles "my name is X", "I am X", "this is X"

### Validation
- Phone: must be exactly 10 digits, starting with 6–9
- Aadhaar: must be exactly 12 digits
- Invalid values are rejected and user is asked to retry

### Dial Pad
- Auto-opens when conversation reaches Phone or Aadhaar fields
- Also opens when user taps those fields directly in the form panel
- Save button stays disabled until correct digit count is entered

### Confirmation Step
- Before submission, all collected values are displayed for review
- Data is saved to `data.json` ONLY after user confirms

### Data Storage
- Confirmed submissions are appended to `data.json`
- Each entry includes a timestamp
- View all submissions at `/submissions`