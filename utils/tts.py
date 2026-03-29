"""
utils/tts.py
Tamil Text-to-Speech using gTTS
"""

import os

def speak_tamil(text: str, output_path: str = "audio/response.mp3") -> str:
    """
    Convert Tamil text to speech and save as MP3.
    Returns path on success, empty string on failure.
    """
    if not text or not text.strip():
        return ""

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    try:
        from gtts import gTTS
        tts = gTTS(text=text, lang="ta", slow=False)
        tts.save(output_path)
        return output_path
    except Exception as e:
        print(f"[TTS] gTTS failed: {e}")

    # Fallback: try pyttsx3
    try:
        import pyttsx3
        engine = pyttsx3.init()
        engine.setProperty("rate", 150)
        engine.save_to_file(text, output_path.replace(".mp3", ".wav"))
        engine.runAndWait()
        return output_path.replace(".mp3", ".wav")
    except Exception as e:
        print(f"[TTS] pyttsx3 failed: {e}")

    return ""
