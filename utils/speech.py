"""
utils/speech.py
Multi-model Speech-to-Text: Whisper (default) + Google STT + Vosk
+ WER / Accuracy evaluation metrics
"""

import os
import whisper

# ── Whisper model singleton ────────────────────────────────────
_whisper_model = None

def _get_whisper_model(size: str = "small"):
    global _whisper_model
    if _whisper_model is None:
        print(f"[STT] Loading Whisper '{size}' model...")
        _whisper_model = whisper.load_model(size)
        print("[STT] Whisper ready.")
    return _whisper_model


# ══════════════════════════════════════════════════════════════
# 1. WHISPER (existing — kept exactly as was)
# ══════════════════════════════════════════════════════════════
def transcribe_whisper(audio_path: str) -> str:
    """Transcribe Tamil audio using Whisper (offline, default model)."""
    if not os.path.exists(audio_path):
        return ""
    try:
        model  = _get_whisper_model("small")
        result = model.transcribe(
            audio_path,
            language="ta",
            task="transcribe",
            fp16=False
        )
        return result.get("text", "").strip()
    except Exception as e:
        print(f"[STT-Whisper] Error: {e}")
        return ""


# ══════════════════════════════════════════════════════════════
# 2. GOOGLE SPEECH-TO-TEXT (requires internet)
# ══════════════════════════════════════════════════════════════
def transcribe_google(audio_path: str) -> str:
    """
    Transcribe Tamil audio using Google Speech Recognition.
    Requires: pip install SpeechRecognition
    Requires internet connection.
    Falls back to Whisper on failure.
    """
    if not os.path.exists(audio_path):
        return ""
    try:
        import speech_recognition as sr
        r = sr.Recognizer()
        with sr.AudioFile(audio_path) as source:
            audio = r.record(source)
        return r.recognize_google(audio, language="ta-IN")
    except ImportError:
        print("[STT-Google] SpeechRecognition not installed. Run: pip install SpeechRecognition")
        print("[STT-Google] Falling back to Whisper.")
        return transcribe_whisper(audio_path)
    except Exception as e:
        print(f"[STT-Google] Error: {e} — falling back to Whisper.")
        return transcribe_whisper(audio_path)


# ══════════════════════════════════════════════════════════════
# 3. VOSK (fully offline, requires vosk-model folder)
# ══════════════════════════════════════════════════════════════
def transcribe_vosk(audio_path: str) -> str:
    """
    Transcribe Tamil audio using Vosk (fully offline).
    Requires: pip install vosk
    Requires: Tamil Vosk model folder at ./vosk-model
    Download from: https://alphacephei.com/vosk/models
    Falls back to Whisper on failure.
    """
    if not os.path.exists(audio_path):
        return ""
    try:
        from vosk import Model, KaldiRecognizer
        import wave
        import json

        model_path = "vosk-model"
        if not os.path.exists(model_path):
            print(f"[STT-Vosk] Model folder '{model_path}' not found. Falling back to Whisper.")
            return transcribe_whisper(audio_path)

        wf  = wave.open(audio_path, "rb")
        model = Model(model_path)
        rec   = KaldiRecognizer(model, wf.getframerate())
        text  = ""

        while True:
            data = wf.readframes(4000)
            if len(data) == 0:
                break
            if rec.AcceptWaveform(data):
                result = json.loads(rec.Result())
                text  += result.get("text", "") + " "

        final  = json.loads(rec.FinalResult())
        text  += final.get("text", "")
        return text.strip()

    except ImportError:
        print("[STT-Vosk] Vosk not installed. Run: pip install vosk")
        print("[STT-Vosk] Falling back to Whisper.")
        return transcribe_whisper(audio_path)
    except Exception as e:
        print(f"[STT-Vosk] Error: {e} — falling back to Whisper.")
        return transcribe_whisper(audio_path)


# ══════════════════════════════════════════════════════════════
# 4. MASTER DISPATCHER — replaces old transcribe_audio()
# ══════════════════════════════════════════════════════════════
def transcribe_audio(audio_path: str, model_type: str = "whisper") -> str:
    """
    Route to the correct STT model.
    model_type: "whisper" | "google" | "vosk"
    Always returns a string. Never raises.
    """
    model_type = (model_type or "whisper").lower().strip()

    if model_type == "google":
        return transcribe_google(audio_path)
    elif model_type == "vosk":
        return transcribe_vosk(audio_path)
    else:
        return transcribe_whisper(audio_path)


# ══════════════════════════════════════════════════════════════
# 5. EVALUATION METRICS (WER + Accuracy)
# ══════════════════════════════════════════════════════════════
def calculate_metrics(reference: str, prediction: str) -> dict:
    """
    Compute Word Error Rate and Accuracy.
    Requires: pip install jiwer
    Returns {"wer": float, "accuracy": float} or {"wer": None, "accuracy": None}.
    """
    if not reference or not prediction:
        return {"wer": None, "accuracy": None}
    try:
        from jiwer import wer as compute_wer
        error    = compute_wer(reference.strip(), prediction.strip())
        accuracy = max(0.0, 1.0 - error)
        return {
            "wer":      round(error,    3),
            "accuracy": round(accuracy, 3)
        }
    except ImportError:
        print("[Metrics] jiwer not installed. Run: pip install jiwer")
        return {"wer": None, "accuracy": None}
    except Exception as e:
        print(f"[Metrics] Error computing WER: {e}")
        return {"wer": None, "accuracy": None}


# ── Legacy alias (keeps any old direct import working) ─────────
def transcribe_to_english(audio_path: str) -> str:
    """Translate Tamil audio directly to English via Whisper."""
    if not os.path.exists(audio_path):
        return ""
    try:
        model  = _get_whisper_model("small")
        result = model.transcribe(audio_path, language="ta", task="translate", fp16=False)
        return result.get("text", "").strip()
    except Exception as e:
        print(f"[STT-Whisper-translate] Error: {e}")
        return ""
