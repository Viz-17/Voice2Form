"""
utils/extract.py
Extract form fields from English (translated) text and Tamil text directly.
Hybrid approach: Tamil keyword rules + English pattern matching
"""

from email.mime import text
import re
import re as _re
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


 
 

def extract_account_number(text: str) -> str:
    """Detect a 10-digit account number. Handles spaced groups."""
    # collapsed = _re.sub(r'(?<=\d)[\s\-](?=\d)', '', text)
    # m = _re.search(r'\b(\d{10})\b', collapsed)
    # return m.group(1) if m else ""
    collapsed = _re.sub(r'(?<=\d)[\s,\-]+(?=\d)', '', text)
    
    # 2. Look for any contiguous sequence of 9 to 18 digits
    m = _re.search(r'\b(\d{9,18})\b', collapsed)
    if m:
        return m.group(1)
    return ""
 
 
def extract_amount(text: str) -> str:
    """Detect amount. Handles digits, commas, spoken words."""
    cleaned = _re.sub(r'(rs\.?|rupees?|inr|₹)', '', text.lower()).strip()
    m = _re.search(r'\b(\d{1,3}(?:,\d{3})*|\d+)\b', cleaned)
    if m:
        return m.group(1).replace(',', '')
    word_map = {
        "hundred": "100", "two hundred": "200", "five hundred": "500",
        "one thousand": "1000", "thousand": "1000",
        "two thousand": "2000", "five thousand": "5000",
        "ten thousand": "10000", "fifty thousand": "50000",
        "one lakh": "100000",
    }
    for phrase, num in word_map.items():
        if phrase in cleaned:
            return num
    return ""
 
 
def extract_challan_name(text: str) -> str:
    """
    Extract name from English + Tamil romanized patterns.
    Updated with Tamil regex patterns per spec.
    """
    patterns = [
        r"my name is ([A-Za-z]{2,25})",
        r"name is ([A-Za-z]{2,25})",
        r"i am ([A-Za-z]{2,25})",
        r"i'?m ([A-Za-z]{2,25})",
        r"for ([A-Za-z]{2,25})",
        r"account of ([A-Za-z]{2,25})",
        # Tamil romanized
        r"en peyar ([A-Za-z]{2,25})",
        r"peyar ([A-Za-z]{2,25})",
        # Tamil unicode
        r"என் பெயர் ([A-Za-z]{2,25})",
        r"பெயர் ([A-Za-z]{2,25})",
    ]
    for pat in patterns:
        m = _re.search(pat, text, _re.IGNORECASE)
        if m:
            return m.group(1).strip().title()
    return ""
 
 
def extract_transaction_type(text: str) -> str:
    """
    Detect Deposit / Withdrawal from Tamil + English keywords.
    Updated with full keyword list per spec.
    """
    text_lower = text.lower()
 
    deposit_keywords = [
        "deposit", "panam podanum", "பணம் போடணும்", "போடணும்",
        "வைப்பு", "podanum", "credit", "add", "put in", "save",
        "போட", "selavu", "சேமி",
    ]
    withdrawal_keywords = [
        "withdraw", "withdrawal", "panam edukkanum", "எடுக்கணும்",
        "edukkanum", "debit", "take out", "எடு", "எடுக்கணும்",
        "எடுக்க",
    ]
 
    for kw in deposit_keywords:
        if kw in text_lower:
            return "Deposit"
    for kw in withdrawal_keywords:
        if kw in text_lower:
            return "Withdrawal"
    return ""
 

def extract_tamil_name(tamil_text):
    """
    Extracts only the name from a Tamil sentence.
    Looks for words after "என் பெயர்", "பெயர்", or "நான்".
    """
    # Regex patterns for Tamil text
    patterns = [
        r"என் பெயர்\s+([^\s]+)",   # En peyar [Name]
        r"பெயர்\s+([^\s]+)",      # Peyar [Name]
        r"நான்\s+([^\s]+)"         # Naan [Name]
    ]
    
    for pat in patterns:
        match = re.search(pat, tamil_text)
        if match:
            # Return just the extracted name
            return match.group(1).strip()
            
    # Fallback: If they only spoke 1 or 2 words (e.g., just saying "விஷ்வா"), 
    # assume the whole thing is the name.
    words = tamil_text.split()
    if len(words) <= 2:
        return tamil_text.strip()
        
    return ""