"""
utils/extract.py
Extract form fields from English (translated) text and Tamil text directly.
Hybrid approach: Tamil keyword rules + English pattern matching
"""

import re

# ── Phonetic correction dict ───────────────────────────────────
_CORRECTIONS = {
    "aan":       "ஆண்",
    "pen":       "பெண்",
    "chennoi":   "chennai",
    "chenai":    "chennai",
    "maduri":    "madurai",
    "trichy":    "tiruchirappalli",
    "zero":"0","one":"1","two":"2","three":"3","four":"4",
    "five":"5","six":"6","seven":"7","eight":"8","nine":"9",
}

def correct_text(text: str) -> str:
    words = text.lower().split()
    return " ".join(_CORRECTIONS.get(w, w) for w in words)

# ─── Tamil keyword maps ────────────────────────────────────────────────────────
TAMIL_NAME_KEYWORDS     = ["பெயர்", "என் பெயர்", "பேர்"]
TAMIL_AGE_KEYWORDS      = ["வயது", "வயசு","வயசி"]
TAMIL_PHONE_KEYWORDS    = ["தொலைபேசி", "போன்", "நம்பர்", "எண்"]
TAMIL_ADDRESS_KEYWORDS  = ["முகவரி", "வீடு", "இடம்"]
TAMIL_DISTRICT_KEYWORDS = ["மாவட்டம்", "ஊர்"]
TAMIL_AADHAAR_KEYWORDS  = ["ஆதார்", "ஆதர்"]
TAMIL_GENDER_KEYWORDS   = ["ஆண்", "பெண்", "பாலினம்"]
TAMIL_OCC_KEYWORDS      = ["தொழில்", "வேலை", "படிப்பு"]

GENDER_MAP = {
    "male": "Male", "female": "Female", "man": "Male", "woman": "Female",
    "boy": "Male", "girl": "Female", "ஆண்": "Male", "பெண்": "Female", 
    "aan": "Male", "an": "Male", "An On": "Male",
    "penn": "Female", "pen": "Female" 
}

EXCLUDE_WORDS = [
    "male", "female", "aan", "an", "penn", "pen",
    "ஆண்", "பெண்"
]


def extract_form_fields(english_text: str, tamil_text: str = "") -> dict:
    """
    Extract form fields from English translated text, with Tamil fallback rules.
    Returns dict with any found fields.
    """
    english_text = correct_text(english_text)
    result = {}
    eng = english_text.lower()
    tam = tamil_text

    # ── NAME ──────────────────────────────────────────────────────────────────

    def is_valid_name(name):
        if not name:
            return False
        name = name.strip().lower()
        if name in EXCLUDE_WORDS:
            return False
        # must be alphabetic
        if not name.replace(" ", "").isalpha():
            return False
        return True

    name = _extract_name_english(eng, english_text)
    if name and not is_valid_name(name):
        name = None
    if not name:
        name = _extract_by_tamil_keyword(tam, TAMIL_NAME_KEYWORDS)
        if name and not is_valid_name(name):
            name = None
    if name:
        result["name"] = name.strip().title()

    # ── AGE ───────────────────────────────────────────────────────────────────
    age = _extract_age_english(eng)
    if not age:
        age = _extract_by_tamil_keyword(tam, TAMIL_AGE_KEYWORDS, numeric=True)
    if age:
        result["age"] = str(age).strip()

    # ── GENDER ────────────────────────────────────────────────────────────────
    gender = _extract_gender(eng, tam)
    if gender:
        result["gender"] = gender

    # ── PHONE ─────────────────────────────────────────────────────────────────
    phone = _extract_phone(english_text)
    if phone:
        result["phone"] = phone

    # ── AADHAAR ───────────────────────────────────────────────────────────────
    aadhaar = _extract_aadhaar(english_text)
    if aadhaar:
        result["aadhaar"] = aadhaar

    # ── ADDRESS ───────────────────────────────────────────────────────────────
    address = _extract_after_keyword(eng, english_text, ["address is", "i live at", "my house is", "residing at"])
    if not address:
        address = _extract_by_tamil_keyword(tam, TAMIL_ADDRESS_KEYWORDS)
    if address:
        result["address"] = address.strip().title()

    # ── DISTRICT ──────────────────────────────────────────────────────────────
    district = _extract_after_keyword(eng, english_text, ["district is", "from district", "my district"])
    if not district:
        district = _extract_by_tamil_keyword(tam, TAMIL_DISTRICT_KEYWORDS)
    if district:
        result["district"] = district.strip().title()

    # ── OCCUPATION ────────────────────────────────────────────────────────────
    occ = _extract_occupation(eng, english_text)
    if not occ:
        occ = _extract_by_tamil_keyword(tam, TAMIL_OCC_KEYWORDS)
    if occ:
        result["occupation"] = occ.strip().title()

    return result


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _extract_name_english(eng_lower: str, original: str) -> str:
    patterns = [
        r"my name is ([A-Za-z]{2,25})",
        r"name is ([A-Za-z]{2,25})",
        r"this is ([A-Za-z]{2,25})",
        r"call me ([A-Za-z]{2,25})",
        r"i'?m ([A-Za-z]{2,25})",
        r"i am ([A-Za-z]{2,25})",
        r"i'm ([A-Za-z]{2,25})",
    ]
    for p in patterns:
        m = re.search(p, eng_lower)
        if m:
            name = m.group(1).strip()
            # Remove trailing common words
            for stop in ["and", "my", "i", "age", "year", "old", "from"]:
                name = re.sub(rf'\b{stop}\b.*', '', name).strip()
            if name:
                return name
    return ""

def _extract_age_english(eng_lower: str):
    patterns = [
        r"i am (\d+) years? old",
        r"i am (\d+)",
        r"age is (\d+)",
        r"(\d+) years? old",
        r"aged (\d+)",
    ]
    for p in patterns:
        m = re.search(p, eng_lower)
        if m:
            return m.group(1)
    return None

def _extract_gender(eng_lower: str, tamil: str) -> str:
    for word, label in GENDER_MAP.items():
        if word in eng_lower or word in tamil:
            return label
    return ""

def _extract_phone(text: str) -> str:
    m = re.search(r'\b(\d[\d\s\-]{8,13}\d)\b', text)
    if m:
        return re.sub(r'[\s\-]', '', m.group(1))
    return ""

def _extract_aadhaar(text: str) -> str:
    # 12 digit number
    m = re.search(r'\b(\d{4}[\s\-]?\d{4}[\s\-]?\d{4})\b', text)
    if m:
        return re.sub(r'[\s\-]', '', m.group(1))
    return ""

def _extract_after_keyword(eng_lower: str, original: str, keywords: list) -> str:
    for kw in keywords:
        if kw in eng_lower:
            idx = eng_lower.index(kw) + len(kw)
            remainder = original[idx:].strip().lstrip(",:- ")
            # Take up to next punctuation or comma
            val = re.split(r'[,\.\n]', remainder)[0].strip()
            if val:
                return val
    return ""

def _extract_occupation(eng_lower: str, original: str) -> str:
    patterns = [
        r"i (?:am a?|work as a?) ([A-Za-z\s]+)",
        r"occupation is ([A-Za-z\s]+)",
        r"profession is ([A-Za-z\s]+)",
        r"i do ([A-Za-z\s]+)",
    ]
    for p in patterns:
        m = re.search(p, eng_lower)
        if m:
            val = m.group(1).strip()
            for stop in ["and", "my", "from", "in"]:
                val = re.sub(rf'\b{stop}\b.*', '', val).strip()
            if val and len(val) > 2:
                return val
    return ""

def _extract_by_tamil_keyword(tamil: str, keywords: list, numeric=False) -> str:
    """Extract value after a Tamil keyword in text."""
    if not tamil:
        return ""
    for kw in keywords:
        if kw in tamil:
            idx = tamil.index(kw) + len(kw)
            remainder = tamil[idx:].strip().lstrip(" :")
            if numeric:
                # Extract first number
                m = re.search(r'\d+', remainder)
                if m:
                    return m.group(0)
            else:
                # Take first "word" or phrase until space/punctuation
                val = re.split(r'[,\.\n,]', remainder)[0].strip()
                if val:
                    return val
    return ""
