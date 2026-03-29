"""
utils/speech.py
Whisper-based Tamil speech-to-text
"""

import whisper
import os

_model = None

def get_model():
    global _model
    if _model is None:
        # Use 'medium' for better Tamil accuracy; use 'small' for speed
        _model = whisper.load_model("small")
    return _model

def transcribe_audio(audio_path: str) -> str:
    """
    Transcribe Tamil audio to text using Whisper.
    Returns Tamil text (unicode) or romanized Tamil.
    """
    if not os.path.exists(audio_path):
        return ""
    
    model = get_model()
    
    # Force Tamil language for better accuracy
    result = model.transcribe(
        audio_path,
        language="ta",          # Tamil
        task="transcribe",      # Keep in Tamil (use "translate" for direct English)
        fp16=False              # Use fp32 for CPU compatibility
    )
    
    text = result.get("text", "").strip()
    return text


def transcribe_to_english(audio_path: str) -> str:
    """
    Directly transcribe Tamil audio to English using Whisper's translation task.
    Alternative to transcribe + translate pipeline.
    """
    if not os.path.exists(audio_path):
        return ""
    
    model = get_model()
    result = model.transcribe(
        audio_path,
        language="ta",
        task="translate",   # Whisper translates to English directly
        fp16=False
    )
    return result.get("text", "").strip()
