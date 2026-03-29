"""
utils/translate.py
Tamil → English translation
Primary: deep_translator (Google Translate, free, no API key)
Fallback: direct keyword extraction from Tamil
"""

def translate_tamil_to_english(tamil_text: str) -> str:
    """
    Translate Tamil text to English.
    Uses deep_translator (GoogleTranslator) — free, no API key needed.
    """
    if not tamil_text or not tamil_text.strip():
        return ""

    try:
        from deep_translator import GoogleTranslator
        translated = GoogleTranslator(source="ta", target="en").translate(tamil_text)
        return translated or tamil_text
    except Exception as e:
        print(f"[Translate] GoogleTranslator failed: {e}")
    
    # Fallback: try googletrans
    try:
        from googletrans import Translator
        t = Translator()
        result = t.translate(tamil_text, src="ta", dest="en")
        return result.text or tamil_text
    except Exception as e:
        print(f"[Translate] googletrans failed: {e}")
    
    # Last resort: return original
    return tamil_text
