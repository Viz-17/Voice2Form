/* script.js — Tamil Voice Form Assistant */

const FIELD_META = {
  name:       { label: "பெயர்",        en: "Name" },
  age:        { label: "வயது",          en: "Age" },
  gender:     { label: "பாலினம்",      en: "Gender" },
  phone:      { label: "தொலைபேசி எண்", en: "Phone" },
  address:    { label: "முகவரி",        en: "Address" },
  district:   { label: "மாவட்டம்",     en: "District" },
  aadhaar:    { label: "ஆதார் எண்",    en: "Aadhaar" },
  occupation: { label: "தொழில்",       en: "Occupation" }
};

// ── State ──────────────────────────────────────────────────────
let mediaRecorder = null;
let audioChunks   = [];
let isRecording   = false;
let audioStream   = null;
let currentField  = null;

// ── DOM refs ───────────────────────────────────────────────────
const micBtn        = document.getElementById("micBtn");
const micLabel      = document.getElementById("micLabel");
const waveform      = document.getElementById("waveform");
const chatMessages  = document.getElementById("chatMessages");
const recorderHint  = document.getElementById("recorderHint");
const statusDot     = document.getElementById("statusDot");
const statusLabel   = document.getElementById("statusLabel");
const formFields    = document.getElementById("formFields");
const progressFill  = document.getElementById("progressFill");
const progressLabel = document.getElementById("progressLabel");
const submitBtn     = document.getElementById("submitBtn");
const resetBtn      = document.getElementById("resetBtn");

// ── Init ───────────────────────────────────────────────────────
window.addEventListener("DOMContentLoaded", () => {
  renderFormFields({});
  fetchForm();
  setTimeout(askNextQuestion, 800);
});

// ── Mic button ─────────────────────────────────────────────────
micBtn.addEventListener("click", async () => {
  if (isRecording) {
    stopRecording();
  } else {
    await startRecording();
  }
});

async function startRecording() {
  try {
    audioStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(audioStream, { mimeType: "audio/webm" });
    audioChunks = [];

    mediaRecorder.ondataavailable = e => {
      if (e.data.size > 0) audioChunks.push(e.data);
    };

    mediaRecorder.onstop = async () => {
      const blob = new Blob(audioChunks, { type: "audio/webm" });
      await processAudio(blob);
    };

    mediaRecorder.start(100);
    isRecording = true;

    micBtn.classList.add("recording");
    micLabel.textContent = "நிறுத்து";
    waveform.classList.add("active");
    setStatus("recording", "பதிவு செய்கிறது...");
    recorderHint.textContent = "மீண்டும் அழுத்தி நிறுத்தவும்";

  } catch (err) {
    console.error("Mic error:", err);
    addBotMessage("மைக்ரோஃபோன் அணுக இயலவில்லை. அனுமதி தரவும்.");
  }
}

function stopRecording() {
  if (mediaRecorder && isRecording) {
    mediaRecorder.stop();
    audioStream.getTracks().forEach(t => t.stop());
    isRecording = false;

    micBtn.classList.remove("recording");
    micLabel.textContent = "பேசுங்கள்";
    waveform.classList.remove("active");
    setStatus("processing", "செயலாக்குகிறது...");
    recorderHint.textContent = "செயலாக்குகிறது, காத்திருக்கவும்...";
    micBtn.disabled = true;
  }
}

// ── Process audio ──────────────────────────────────────────────
async function processAudio(blob) {
  const formData = new FormData();
  formData.append("audio", blob, "input.wav");

  const userBubbleId = addUserMessage("🎤 ...", true);

  try {
    const res  = await fetch("/process_audio", { method: "POST", body: formData });
    const data = await res.json();

    updateBubble(userBubbleId, data.tamil_text || "(தெளிவற்ற குரல்)");

    renderFormFields(data.form_data);
    updateProgress(data.form_data);

    if (data.response_tamil) {
      addBotMessage(data.response_tamil, data.extracted);
    }

    if (data.tts_audio) {
      playAudio(data.tts_audio);
    }

    document.getElementById("dbTamil").textContent     = data.tamil_text   || "—";
    document.getElementById("dbEnglish").textContent   = data.english_text || "—";
    document.getElementById("dbExtracted").textContent = JSON.stringify(data.extracted, null, 2) || "—";

    currentField = data.next_field;

    if (data.all_done) {
      submitBtn.disabled = false;
      setStatus("active", "முடிந்தது!");
      recorderHint.textContent = "அனைத்து தகவல்களும் நிரப்பப்பட்டன";
    } else {
      setStatus("active", "தயார்");
      recorderHint.textContent = "மைக்கை அழுத்தி பேசுங்கள்";

      // ── AUTO-OPEN dial pad when conversation reaches phone or aadhaar ──
      if (data.next_field && ["phone", "aadhaar"].includes(data.next_field)) {
        setTimeout(() => openDialpad(data.next_field), 600);
      }
    }

    // ── If voice failed validation for a numeric field, inform user ──
    // (dial pad is already open from the block above; just show the message)
    if (data.validation_errors && Object.keys(data.validation_errors).length) {
      Object.keys(data.validation_errors).forEach(field => {
        if (["phone", "aadhaar"].includes(field)) {
          addBotMessage(
            `${field === "phone" ? "தொலைபேசி" : "ஆதார்"} எண் சரியாக புரியவில்லை. ` +
            `கீழே உள்ள dial pad பயன்படுத்தி உள்ளிடவும்.`
          );
        }
      });
    }

  } catch (err) {
    console.error(err);
    addBotMessage("பிழை ஏற்பட்டது. மீண்டும் முயற்சிக்கவும்.");
    setStatus("", "தயார்");
    recorderHint.textContent = "மைக்கை அழுத்தி பேசுங்கள்";
  } finally {
    micBtn.disabled = false;
  }
}

// ── Ask next question via TTS ──────────────────────────────────
async function askNextQuestion() {
  try {
    const res  = await fetch("/next_question");
    const data = await res.json();

    if (data.field && data.tts_audio) {
      playAudio(data.tts_audio + "?t=" + Date.now());
    }

    // ── AUTO-OPEN dial pad on page load if first question is phone/aadhaar ──
    if (data.field && ["phone", "aadhaar"].includes(data.field)) {
      setTimeout(() => openDialpad(data.field), 800);
    }

  } catch(e) {}
}

// ── Form rendering ─────────────────────────────────────────────
function renderFormFields(data) {
  formFields.innerHTML = "";
  Object.entries(FIELD_META).forEach(([key, meta]) => {
    const value     = (data && data[key]) ? data[key] : "";
    const isNumeric = ["phone", "aadhaar"].includes(key);

    const div = document.createElement("div");
    div.className = "form-field" + (value ? " filled" : "") + (currentField === key ? " active" : "");
    div.id = "field-" + key;

    // ── Tap/click to open dial pad on unfilled numeric fields ──
    if (isNumeric && !value) {
      div.style.cursor = "pointer";
      div.title        = "Click to open dial pad";
      div.onclick      = () => openDialpad(key);
    }

    div.innerHTML = `
      <div class="field-label">
        ${meta.en} / ${meta.label}
        ${isNumeric && !value ? '<span class="dialpad-badge">⌨ Dial</span>' : ""}
      </div>
      <div class="field-value ${value ? "" : "empty"}">
        ${value
          ? `<span class="field-check">✓</span> ${escHtml(value)}`
          : "நிரப்பப்படவில்லை"}
      </div>
    `;
    formFields.appendChild(div);
  });
}

function updateProgress(data) {
  if (!data) return;
  const total   = Object.keys(FIELD_META).length;
  const filled  = Object.values(data).filter(v => v).length;
  const pct     = Math.round((filled / total) * 100);
  progressFill.style.width  = pct + "%";
  progressLabel.textContent = `${filled}/${total} நிரப்பப்பட்டது`;
}

async function fetchForm() {
  try {
    const res  = await fetch("/get_form");
    const data = await res.json();
    renderFormFields(data);
    updateProgress(data);

    // ── AUTO-OPEN dial pad on page load if phone/aadhaar is first empty field ──
    const firstEmpty = Object.keys(FIELD_META).find(k => !data[k]);
    if (firstEmpty && ["phone", "aadhaar"].includes(firstEmpty)) {
      setTimeout(() => openDialpad(firstEmpty), 800);
    }

  } catch(e) {}
}

// ── Chat bubbles ───────────────────────────────────────────────
let bubbleCounter = 0;

function addBotMessage(text, extracted) {
  const id  = "bubble-" + (++bubbleCounter);
  const div = document.createElement("div");
  div.className = "bubble bot";
  div.id = id;

  let extraHtml = "";
  if (extracted && Object.keys(extracted).length) {
    const tags = Object.entries(extracted)
      .map(([k, v]) => `<span class="tag">${FIELD_META[k]?.en || k}: ${escHtml(String(v))}</span>`)
      .join("");
    extraHtml = `<p style="margin-top:8px">${tags}</p>`;
  }

  div.innerHTML = `
    <div class="bubble-avatar">த</div>
    <div class="bubble-content">
      <p>${escHtml(text)}</p>
      ${extraHtml}
    </div>
  `;
  chatMessages.appendChild(div);
  scrollChat();
  return id;
}

function addUserMessage(text, pending = false) {
  const id  = "bubble-" + (++bubbleCounter);
  const div = document.createElement("div");
  div.className = "bubble user";
  div.id = id;
  div.innerHTML = `
    <div class="bubble-avatar">நீ</div>
    <div class="bubble-content">
      <p ${pending ? 'style="opacity:0.5;font-style:italic"' : ""}>${escHtml(text)}</p>
    </div>
  `;
  chatMessages.appendChild(div);
  scrollChat();
  return id;
}

function updateBubble(id, text) {
  const el = document.getElementById(id);
  if (el) {
    const p = el.querySelector(".bubble-content p");
    if (p) { p.style = ""; p.textContent = text; }
  }
}

function scrollChat() {
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

// ── Status ─────────────────────────────────────────────────────
function setStatus(state, label) {
  statusDot.className    = "status-dot" + (state ? " " + state : "");
  statusLabel.textContent = label;
}

// ── Audio playback ─────────────────────────────────────────────
function playAudio(src) {
  const audio = new Audio(src);
  audio.play().catch(e => console.log("Audio play blocked:", e));
}

// ── Reset ──────────────────────────────────────────────────────
resetBtn.addEventListener("click", async () => {
  if (!confirm("படிவத்தை மீட்டமைக்கவா?")) return;
  try {
    await fetch("/reset_form", { method: "POST" });
    closeDialpad();                      // ← close dial pad if open during reset
    renderFormFields({});
    updateProgress({});
    chatMessages.innerHTML = `
      <div class="bubble bot">
        <div class="bubble-avatar">த</div>
        <div class="bubble-content">
          <p>படிவம் மீட்டமைக்கப்பட்டது. மீண்டும் தொடங்குவோம்.</p>
          <p class="sub">உங்கள் பெயர் என்ன?</p>
        </div>
      </div>`;
    submitBtn.disabled = true;
    setStatus("", "தயார்");
    recorderHint.textContent = "மைக்கை அழுத்தி பேசுங்கள்";
    setTimeout(askNextQuestion, 600);
  } catch(e) {}
});

// ── Submit ─────────────────────────────────────────────────────
submitBtn.addEventListener("click", () => {
  addBotMessage("விண்ணப்பம் வெற்றிகரமாக சமர்ப்பிக்கப்பட்டது! நன்றி 🎉");
  submitBtn.disabled = true;
  playAudio("/get_tts");
});

// ── Debug toggle ───────────────────────────────────────────────
function toggleDebug() {
  const body = document.getElementById("debugBody");
  const icon = document.getElementById("debugToggleIcon");
  const open = body.style.display !== "none";
  body.style.display = open ? "none" : "grid";
  icon.textContent   = open ? "▾" : "▴";
}

// ── Util ───────────────────────────────────────────────────────
function escHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// ══════════════════════════════════════════════════════════════
// DIAL PAD
// ══════════════════════════════════════════════════════════════

let _dialField  = null;   // "phone" | "aadhaar"
let _dialBuffer = "";

const DIAL_LIMITS = { phone: 10, aadhaar: 12}; //account: 18, amount: 15 
const DIAL_HINTS  = {
  phone:   "10 இலக்கங்கள் • 6, 7, 8 அல்லது 9 இல் தொடங்க வேண்டும்",
  aadhaar: "12 இலக்கங்கள் • Aadhaar number",
  // account: "10 இலக்க கணக்கு எண்", 
  // amount:  "தொகையை உள்ளிடவும்"
};

// ── Open ───────────────────────────────────────────────────────
function openDialpad(field) {
  _dialField  = field;
  _dialBuffer = "";

  const wrapper = document.getElementById("dialpadWrapper");
  if (!wrapper) return;                 // safety — HTML not yet added

  wrapper.style.display = "block";
  document.getElementById("dialpadTitle").textContent =
    field === "phone" ? "📞 தொலைபேசி எண்" : "🪪 ஆதார் எண்";
  document.getElementById("dialpadHintText").textContent = DIAL_HINTS[field] || "";

  _updateScreen();
}

// ── Close ──────────────────────────────────────────────────────
function closeDialpad() {
  const wrapper = document.getElementById("dialpadWrapper");
  if (wrapper) wrapper.style.display = "none";
  _dialField  = null;
  _dialBuffer = "";
}

// ── Key press ──────────────────────────────────────────────────
function dialPress(key) {
  const limit = DIAL_LIMITS[_dialField] || 12;
  if (key === "clear") {
    _dialBuffer = "";
  } else if (key === "back") {
    _dialBuffer = _dialBuffer.slice(0, -1);
  } else if (_dialBuffer.length < limit) {
    _dialBuffer += key;
  }
  _updateScreen();
}

// ── Update display screen ──────────────────────────────────────
function _updateScreen() {
  const limit = DIAL_LIMITS[_dialField] || 12;

  // Format with spaces: XXXXX XXXXX for phone,  XXXX XXXX XXXX for aadhaar
  let display = _dialBuffer;
  if (_dialField === "aadhaar" && display.length > 4) {
    display = display.match(/.{1,4}/g).join(" ");
  } else if (_dialField === "phone" && display.length > 5) {
    display = display.slice(0, 5) + " " + display.slice(5);
  }

  document.getElementById("dialpadDisplay").textContent = display || "—";

  const ok  = _dialBuffer.length === limit;
  const btn = document.getElementById("dialpadSubmit");
  btn.disabled    = !ok;
  btn.textContent = ok
    ? "✓ சேமி / Save"
    : `${_dialBuffer.length} / ${limit} இலக்கங்கள்`;
}

// ── Submit to backend ──────────────────────────────────────────
async function submitDialpad() {
  if (!_dialField || !_dialBuffer) return;

  const savedField = _dialField;       // capture before closeDialpad() clears it

  // ── NEW: CHALLAN MODE ROUTING ──
  if (savedField === "account" || savedField === "amount") {
    closeDialpad();
    // Visually update the input field
    const inputEl = document.getElementById("chInput-" + savedField);
    if (inputEl) inputEl.value = _dialBuffer;
    
    // Trigger the exact manual validation we built earlier!
    challanManualInput(savedField, _dialBuffer);
    return; // Stop here so it doesn't trigger the normal form API
  }

  try {
    const res  = await fetch("/manual_input", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ field: savedField, value: _dialBuffer })
    });
    const data = await res.json();

    if (data.ok) {
      closeDialpad();
      renderFormFields(data.form_data);
      updateProgress(data.form_data);
      addBotMessage(
        `✓ ${savedField === "phone" ? "தொலைபேசி எண்" : "ஆதார் எண்"} சேமிக்கப்பட்டது.`
      );

      // If next empty field is also numeric, open dial pad straight away
      if (data.next_field && ["phone", "aadhaar"].includes(data.next_field)) {
        setTimeout(() => openDialpad(data.next_field), 600);
      }

    } else {
      addBotMessage(`✗ ${data.error} — மீண்டும் முயற்சிக்கவும்.`);
    }

  } catch (e) {
    addBotMessage("பிழை ஏற்பட்டது. மீண்டும் முயற்சிக்கவும்.");
  }
}

async function showConfirm() {
    const res  = await fetch("/confirm_preview");
    const data = await res.json();

    const summary = document.getElementById("confirmSummary");
    summary.innerHTML = Object.entries(data.filled)
        .map(([k,v]) => `<div style="display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid #2a2f42">
                           <span style="color:#7a8099">${k}</span>
                           <span style="font-weight:600">${v}</span>
                         </div>`)
        .join("");

    document.getElementById("confirmPanel").style.display = "block";
    document.getElementById("submitBtn").style.display    = "none";
}


async function finalSubmit(confirmed) {
    if (confirmed) {
        const res  = await fetch("/confirm_submit", { method: "POST" });
        const data = await res.json();
        addBotMessage(data.message || "சமர்ப்பிக்கப்பட்டது!");
        if (data.tts_audio) playAudio(data.tts_audio + "?t=" + Date.now());
        document.getElementById("confirmPanel").style.display = "none";
        submitBtn.disabled = true;
    } else {
        document.getElementById("confirmPanel").style.display = "none";
        document.getElementById("submitBtn").style.display = "block";
        addBotMessage("சரி — திருத்தலாம். எந்த தகவலை மாற்ற வேண்டும்?");
    }
}


// ── Challan state ──────────────────────────────────────────────
let sessionData = {
  name: "", account_number: "", bank: "",
  branch: "", transaction_type: "", amount: ""
};
 
let tempValue        = "";   // pending confirmation
let suggestedAccount = "";   // from last-digit warning
let challanMode      = false;
let currentStep      = "name";
let lastSpokenStep   = "";   // prevents TTS re-trigger for same step
 
const STEP_ORDER = ["name", "account", "bank", "txn", "amount", "summary"];
const STEP_COUNT = STEP_ORDER.length;
 
const STEP_PROMPTS = {
  name:    "உங்கள் பெயர் சொல்லுங்கள்",
  account: "உங்கள் கணக்கு எண் சொல்லுங்கள்",
  bank:    "வங்கி விவரங்களை சரிபார்க்கவும்",
  txn:     "வைப்பா அல்லது எடுக்கவா?",
  amount:  "எவ்வளவு தொகை?",
  summary: "அனைத்து தகவல்களையும் சரிபார்க்கவும்"
};
const STEP_SUBS = {
  name:    "உங்கள் பெயரை பேசுங்கள் அல்லது தட்டச்சு செய்யுங்கள்",
  account: "கணக்கு எண்ணை சொல்லுங்கள் அல்லது தட்டச்சு செய்யுங்கள்",
  bank:    "கணக்கு எண்ணில் இருந்து தானாக நிரப்பப்பட்டது — சரிபார்க்கவும்",
  txn:     "பெரிய பொத்தான்களை அழுத்துங்கள் அல்லது பேசுங்கள்",
  amount:  "தொகையை பேசுங்கள் அல்லது தட்டச்சு செய்யுங்கள்",
  summary: "சமர்ப்பிக்க கீழே உள்ள பொத்தானை அழுத்துங்கள்"
};
 
// ── Recorder state ─────────────────────────────────────────────
let chRecorder   = null;
let chChunks     = [];
let chRecording  = false;
let chStream     = null;
let chActiveStep = null;
 
// ══════════════════════════════════════════════════════════════
// TTS — Web Speech API
// ══════════════════════════════════════════════════════════════
function speakTamilPrompt(text) {
  if (!window.speechSynthesis) return;
  window.speechSynthesis.cancel();          // stop overlap/looping
  const utt  = new SpeechSynthesisUtterance(text);
  utt.lang   = "ta-IN";
  utt.rate   = 0.92;
  utt.pitch  = 1.0;
  window.speechSynthesis.speak(utt);
}
 
// ══════════════════════════════════════════════════════════════
// MODE TOGGLE
// ══════════════════════════════════════════════════════════════
function toggleChallanMode() {
  challanMode = !challanMode;
 
  const mainLayout     = document.querySelector(".layout");
  const challanSection = document.getElementById("challanSection");
  const toggleBtn      = document.getElementById("challanToggleBtn");
  const debugPanel     = document.getElementById("debugPanel");
 
  if (challanMode) {
    mainLayout.style.display     = "none";
    challanSection.style.display = "flex";
    debugPanel.style.display     = "none";
    toggleBtn.classList.add("active");
    toggleBtn.textContent = "🏠 Voice Form";
    resetChallanSession();
    renderStep("name");
  } else {
    mainLayout.style.display     = "";
    challanSection.style.display = "none";
    debugPanel.style.display     = "";
    toggleBtn.classList.remove("active");
    toggleBtn.textContent = "🏦 Challan Mode";
    if (chRecording) chStopRecording(chActiveStep);
    window.speechSynthesis && window.speechSynthesis.cancel();
  }
}
 
// ══════════════════════════════════════════════════════════════
// SESSION RESET
// ══════════════════════════════════════════════════════════════
function resetChallanSession() {
  sessionData      = { name:"", account_number:"", bank:"", branch:"", transaction_type:"", amount:"" };
  tempValue        = "";
  suggestedAccount = "";
  currentStep      = "name";
  lastSpokenStep   = "";
 
  ["name","account","amount"].forEach(f => {
    const inp = document.getElementById("chInput-" + f);
    if (inp) inp.value = "";
  });
  const bank   = document.getElementById("chInput-bank");
  const branch = document.getElementById("chInput-branch");
  if (bank)   bank.value   = "";
  if (branch) branch.value = "";
 
  document.getElementById("txnDeposit")    ?.classList.remove("selected");
  document.getElementById("txnWithdrawal") ?.classList.remove("selected");
 
  STEP_ORDER.forEach(s => {
    _hide("chConfirm-" + s);
    _hide("chWarning-" + s);
    _hide("chListen-"  + s);
    const badge = document.getElementById("chBadge-" + s);
    if (badge) badge.textContent = "";
    const card = document.getElementById("chStep-" + s);
    if (card) card.classList.remove("done-step", "active-step");
  });
 
  _hide("chErrorMsg");
  _hide("challanListenIndicator");
 
  const tr = document.getElementById("challanTranscript");
  if (tr) tr.innerHTML = '<span class="transcript-placeholder">குரல் உள்ளீடு இங்கே தோன்றும்...</span>';
}
 
// ══════════════════════════════════════════════════════════════
// STEP RENDERER
// ══════════════════════════════════════════════════════════════
function renderStep(step) {
  currentStep = step;
  const idx   = STEP_ORDER.indexOf(step);
 
  // Progress bar
  const pct = Math.round((idx / (STEP_COUNT - 1)) * 100);
  document.getElementById("chProgressFill").style.width  = pct + "%";
  document.getElementById("chProgressLabel").textContent = `Step ${idx + 1} of ${STEP_COUNT}`;
 
  // Step cards
  STEP_ORDER.forEach((s, i) => {
    const card = document.getElementById("chStep-" + s);
    if (!card) return;
    card.classList.remove("active-step", "ch-step-locked", "done-step");
 
    if (s === step) {
      card.classList.add("active-step");
      _enableStep(s, true);
      setTimeout(() => card.scrollIntoView({ behavior:"smooth", block:"nearest" }), 120);
    } else if (i < idx) {
      card.classList.add("done-step");
      _enableStep(s, false);
    } else {
      card.classList.add("ch-step-locked");
      _enableStep(s, false);
    }
  });
 
  _updateChecklist(step);
 
  // Right-panel prompt
  const title = document.getElementById("chPromptTitle");
  const sub   = document.getElementById("chPromptSub");
  if (title) title.textContent = STEP_PROMPTS[step] || "";
  if (sub)   sub.textContent   = STEP_SUBS[step]    || "";
 
  // TTS — only when step changes
  if (step !== lastSpokenStep) {
    lastSpokenStep = step;
    const txt = STEP_PROMPTS[step];
    if (txt) setTimeout(() => speakTamilPrompt(txt), 320);
  }
 
  if (step === "summary") _buildSummary();
}
 
function _enableStep(step, on) {
  [
    "chInput-"   + step,
    "chMic-"     + step,
    "chDialBtn-" + step
  ].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.disabled = !on;
  });
  // transaction buttons
  if (step === "txn") {
    document.getElementById("txnDeposit")    && (document.getElementById("txnDeposit").disabled    = !on);
    document.getElementById("txnWithdrawal") && (document.getElementById("txnWithdrawal").disabled = !on);
  }
}
 
function _updateChecklist(activeStep) {
  const activeIdx = STEP_ORDER.indexOf(activeStep);
  ["name","account","bank","txn","amount"].forEach((s, i) => {
    const item = document.getElementById("chCheck-" + s);
    if (!item) return;
    item.classList.remove("ch-active","ch-done");
    const icon = item.querySelector(".ch-check-icon");
    if (i < activeIdx) {
      item.classList.add("ch-done");
      if (icon) icon.textContent = "✓";
    } else if (s === activeStep) {
      item.classList.add("ch-active");
      if (icon) icon.textContent = "▶";
    } else {
      if (icon) icon.textContent = "○";
    }
  });
}
 
// ══════════════════════════════════════════════════════════════
// MANUAL INPUT (typing)
// ══════════════════════════════════════════════════════════════
// let _manualTimer = null;
// function challanManualInput(step, value) {
//   clearTimeout(_manualTimer);
//   _hide("chConfirm-" + step);
//   _hide("chWarning-" + step);
//   if (!value.trim()) return;
 
//   _manualTimer = setTimeout(() => {
//     tempValue = value.trim();
//     _showConfirm(step, tempValue);
//   }, 700);
// }
 
let _manualTimer = null;  
function challanManualInput(step, value) {
  clearTimeout(_manualTimer);
  _hide("chConfirm-" + step);
  _hide("chWarning-" + step);
  const trimmed = value.trim();
  if (!trimmed) return;

  // 1. STRICT LENGTH CHECK: Do nothing until exactly 10 digits are typed
  // if (step === "account" && trimmed.length !== 10) {
  //   return; 
  // }
  
  // _manualTimer = setTimeout(() => {
  //   tempValue = value.trim();
    // Only show confirm if length is plausible (9–18 for account, any for others)
    // if (step === "account" && (tempValue.length < 9 || tempValue.length > 18)) {
    //     _showError("கணக்கு எண் 9 முதல் 18 இலக்கங்கள் இருக்க வேண்டும்.");
    //     return;
    // }
  //   _hide("chErrorMsg");
  //   _showConfirm(step, tempValue);
  // }, 700);

_manualTimer = setTimeout(async () => {
    tempValue = trimmed;
    
    // 2. CHECK THE 1-DIGIT RULE FOR MANUAL TYPING
    if (step === "account") {
      try {

        if (step === "account" && (tempValue.length < 9 || tempValue.length > 18)) {
        _showError("கணக்கு எண் 9 முதல் 18 இலக்கங்கள் இருக்க வேண்டும்.");
        return;
        }
        
        const res = await fetch("/challan_lookup", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ account: tempValue })
        });
        const data = await res.json();

        // If the backend found a 1-digit mismatch, show the suggestion UI
        if (data.warning && data.suggested_account) {
          suggestedAccount = data.suggested_account;
          document.getElementById("chWarningText-account").textContent = data.warning;
          _show("chWarning-account");
          return; // Stop here, wait for user to click Yes/No
        }
      } catch(e) {}
    }

    // If there is no warning (or if it's not the account step), show the normal confirm UI
    _showConfirm(step, tempValue);
  }, 700);
}

// ══════════════════════════════════════════════════════════════
// VOICE INPUT
// ══════════════════════════════════════════════════════════════
async function challanVoiceStep(step) {
  if (chRecording && chActiveStep === step) {
    chStopRecording(step);
    return;
  }
  if (chRecording) chStopRecording(chActiveStep);
 
  chActiveStep = step;
  try {
    chStream   = await navigator.mediaDevices.getUserMedia({ audio:true });
    chRecorder = new MediaRecorder(chStream, { mimeType:"audio/webm" });
    chChunks   = [];
 
    chRecorder.ondataavailable = e => { if (e.data.size > 0) chChunks.push(e.data); };
    chRecorder.onstop = async () => {
      const blob = new Blob(chChunks, { type:"audio/webm" });
      await _processChallanBlob(blob, step);
    };
 
    chRecorder.start(100);
    chRecording = true;
 
    const btn = document.getElementById("chMic-" + step);
    if (btn) { btn.classList.add("recording"); btn.querySelector("span").textContent = "நிறுத்து"; }
    _show("chListen-" + step);
    _show("challanListenIndicator");
    const tr = document.getElementById("challanTranscript");
    if (tr) tr.textContent = "🎤 கேட்கிறது...";
 
  } catch(err) {
    _showError("மைக் அனுமதி தேவை. Browser → allow microphone.");
  }
}
 
function chStopRecording(step) {
  if (chRecorder && chRecording) {
    chRecorder.stop();
    chStream?.getTracks().forEach(t => t.stop());
    chRecording = false;
  }
  const s = step || chActiveStep;
  const btn = document.getElementById("chMic-" + s);
  if (btn) { btn.classList.remove("recording"); btn.querySelector("span").textContent = "பேசுங்கள்"; }
  _hide("chListen-"  + s);
  _hide("challanListenIndicator");
}
 
// ══════════════════════════════════════════════════════════════
// PROCESS AUDIO BLOB → BACKEND
// ══════════════════════════════════════════════════════════════
async function _processChallanBlob(blob, step) {
  const fd = new FormData();
  fd.append("audio",      blob, "challan_input.wav");
  fd.append("step",       step);
  fd.append("known_name", sessionData.name);   // context passing per spec
 
  try {
    const res  = await fetch("/process_challan", { method:"POST", body:fd });
    const data = await res.json();
 
    const tr = document.getElementById("challanTranscript");
    if (tr) tr.textContent = data.tamil_text || "(தெளிவற்ற குரல்)";
 
    // ── Name-missing fallback ─────────────────────────────────
    if (data.error === "name_missing") {
      renderStep("name");
      _showError("உங்கள் பெயரை முதலில் சொல்லுங்கள்");
      speakTamilPrompt("உங்கள் பெயரை முதலில் சொல்லுங்கள்");
      return;
    }
 
    if (data.error) {
      _showError("புரியவில்லை, மீண்டும் சொல்லுங்கள்");
      speakTamilPrompt("புரியவில்லை, மீண்டும் சொல்லுங்கள்");
      return;
    }
 
    _hide("chErrorMsg");
 
    // ── Populate per step ─────────────────────────────────────
    if (step === "name" && data.name) {
      //tempValue = data.name;
      tempValue = data.tamil_name || data.tamil_text;
      document.getElementById("chInput-name").value = tempValue;
      _showConfirm("name", tempValue);

 
    } else if (step === "account") {
      // if (!data.account_number) {
      //   _showError("கணக்கு எண் புரியவில்லை, மீண்டும் சொல்லுங்கள்");
      //   return;
      // }
      if (!data.account_number) {
        _showError("கணக்கு எண் புரியவில்லை, மீண்டும் சொல்லுங்கள்");
        return;
      }
      // Graceful length check
      if (data.account_number.length < 9 || data.account_number.length > 18) {
          _showError("கணக்கு எண் தவறான நீளம் உள்ளது. மீண்டும் சொல்லுங்கள்.");
          return;
      }

      // 1. Check for the length error we just added in the backend
      if (data.error === "invalid_length") {
        _showError(data.message);
        speakTamilPrompt(data.message);
        return;
      }
      
      // 2. Extra Frontend Safety Check
      if (!data.account_number ) { //|| data.account_number.length !== 10
        _showError("இந்த கணக்கு எண் தரவுத்தளத்தில் இல்லை. சரியான எண்ணை உள்ளிடவும்.");
        speakTamilPrompt("இந்த கணக்கு எண் தரவுத்தளத்தில் இல்லை. சரியான எண்ணை உள்ளிடவும்.");
        return;
      }


      tempValue = data.account_number;
      document.getElementById("chInput-account").value = tempValue;
 
      if (data.warning && data.suggested_account) {
        // Last-digit warning — show custom warning box, NOT native alert
        suggestedAccount = data.suggested_account;
        _hide("chConfirm-account");
        document.getElementById("chWarningText-account").textContent = data.warning;
        _show("chWarning-account");
      } else {
        _hide("chWarning-account");
        _showConfirm("account", tempValue);
      }
 
    } else if (step === "txn" && data.transaction_type) {
      tempValue = data.transaction_type;
      selectTxn(data.transaction_type);
 
    } else if (step === "amount" && data.amount) {
      tempValue = data.amount;
      document.getElementById("chInput-amount").value = tempValue;
      _showConfirm("amount", "₹ " + tempValue);
 
    } else {
      _showError("புரியவில்லை, மீண்டும் சொல்லுங்கள்");
      speakTamilPrompt("புரியவில்லை, மீண்டும் சொல்லுங்கள்");
    }
 
  } catch(err) {
    _showError("பிழை ஏற்பட்டது. மீண்டும் முயற்சிக்கவும்.");
    console.error("Challan audio error:", err);
  }
}
 
// ══════════════════════════════════════════════════════════════
// CONFIRM / REJECT (inline buttons)
// ══════════════════════════════════════════════════════════════
function confirmStep(step) {
  _hide("chConfirm-" + step);
  _hide("chWarning-" + step);
  _hide("chErrorMsg");
 
  if (step === "name") {
    sessionData.name = tempValue || document.getElementById("chInput-name").value.trim();
    _markDone("name", sessionData.name);
    tempValue = "";
    renderStep("account");
 
  } else if (step === "account") {
    sessionData.account_number = tempValue || document.getElementById("chInput-account").value.trim();
    _markDone("account", sessionData.account_number);
    tempValue = "";
    // STRICT: fetch bank ONLY after account confirmed
    _fetchBankDetails(sessionData.name, sessionData.account_number);
 
  } else if (step === "bank") {
    _markDone("bank", sessionData.bank + " / " + sessionData.branch);
    renderStep("txn");
 
  } else if (step === "txn") {
    sessionData.transaction_type = tempValue;
    _markDone("txn", sessionData.transaction_type);
    tempValue = "";
    renderStep("amount");
 
  } else if (step === "amount") {
    sessionData.amount = tempValue || document.getElementById("chInput-amount").value.trim();
    _markDone("amount", "₹ " + sessionData.amount);
    tempValue = "";
    renderStep("summary");
  }
}
 
function rejectStep(step) {
  _hide("chConfirm-" + step);
  tempValue = "";
  const inp = document.getElementById("chInput-" + step);
  if (inp && !inp.readOnly) inp.value = "";
  if (step === "txn") {
    document.getElementById("txnDeposit")    ?.classList.remove("selected");
    document.getElementById("txnWithdrawal") ?.classList.remove("selected");
  }
}
 
// ── Last-digit warning response ────────────────────────────────
function acceptSuggested() {
  _hide("chWarning-account");
  tempValue = suggestedAccount;
  document.getElementById("chInput-account").value = tempValue;
  _showConfirm("account", tempValue);
}
 
function rejectSuggested() {
  _hide("chWarning-account");
  suggestedAccount = "";
  tempValue = "";
  document.getElementById("chInput-account").value = "";
}
 
// ══════════════════════════════════════════════════════════════
// BANK FETCH (strict timing — only after account confirmed)
// ══════════════════════════════════════════════════════════════
// async function _fetchBankDetails(name, account) {
//   try {
//     const res  = await fetch("/challan_lookup", {
//       method:  "POST",
//       headers: { "Content-Type":"application/json" },
//       //body:    JSON.stringify({ name })
//       body:    JSON.stringify({ account: account })
//     });
//     const data = await res.json();
 
//     if (data.found) {
//       sessionData.bank   = data.bank;
//       sessionData.branch = data.branch;
//     } else {
//       sessionData.bank   = "Not found";
//       sessionData.branch = "Not found";
//     }
 
//   } catch(err) {
//     sessionData.bank   = "—";
//     sessionData.branch = "—";
//   }
 
//   // Populate read-only fields
//   document.getElementById("chInput-bank").value   = sessionData.bank;
//   document.getElementById("chInput-branch").value = sessionData.branch;
 
//   // Transition to bank step, then show confirm button
//   renderStep("bank");
//   setTimeout(() => _show("chConfirm-bank"), 350);
// }
 
async function _fetchBankDetails(name, account) {
  try {
    const res  = await fetch("/challan_lookup", {
      method:  "POST",
      headers: { "Content-Type":"application/json" },
      body:    JSON.stringify({ name: sessionData.name, account: account }) 
    });
    const data = await res.json();
 
    if (data.found) {
      // SUCCESS: Account found, move to Bank confirmation
      sessionData.bank   = data.bank;
      sessionData.branch = data.branch;
      document.getElementById("chInput-bank").value   = sessionData.bank;
      document.getElementById("chInput-branch").value = sessionData.branch;
 
      renderStep("bank");
      setTimeout(() => _show("chConfirm-bank"), 350);
    } else {
      // FAILED: Account not in database. Block progress!
      _showError("இந்த கணக்கு எண் தரவுத்தளத்தில் இல்லை. சரியான எண்ணை உள்ளிடவும்.");
      speakTamilPrompt("இந்த கணக்கு எண் தரவுத்தளத்தில் இல்லை. சரியான எண்ணை உள்ளிடவும்.");
      
      // Clear the invalid account so they are forced to re-enter it
      tempValue = "";
      sessionData.account_number = "";
      document.getElementById("chInput-account").value = "";
      renderStep("account"); 
    }
 
  } catch(err) {
    _showError("வங்கி விவரங்களை பெறுவதில் பிழை.");
    renderStep("account");
  }
}

// ══════════════════════════════════════════════════════════════
// TRANSACTION TYPE BUTTONS
// ══════════════════════════════════════════════════════════════
function selectTxn(type) {
  tempValue = type;
  document.getElementById("txnDeposit")    ?.classList.toggle("selected", type === "Deposit");
  document.getElementById("txnWithdrawal") ?.classList.toggle("selected", type === "Withdrawal");
  _showConfirm("txn", type === "Deposit" ? "🟢 Deposit / வைப்பு" : "🔴 Withdrawal / எடுக்கல்");
}
 
// ══════════════════════════════════════════════════════════════
// SUMMARY + FINAL SUBMIT
// ══════════════════════════════════════════════════════════════
function _buildSummary() {
  const rows = [
    { key:"பெயர் / Name",              val: sessionData.name },
    { key:"கணக்கு / Account",          val: sessionData.account_number },
    { key:"வங்கி / Bank",              val: sessionData.bank },
    { key:"கிளை / Branch",             val: sessionData.branch },
    { key:"பரிவர்த்தனை / Transaction", val: sessionData.transaction_type },
    { key:"தொகை / Amount",             val: "₹ " + sessionData.amount },
  ];
  document.getElementById("chSummaryTable").innerHTML =
    rows.map(r => `
      <div class="ch-summary-row">
        <span class="ch-summary-key">${r.key}</span>
        <span class="ch-summary-value">${escHtml(r.val || "—")}</span>
      </div>`).join("");
 
  document.getElementById("chFinalSubmit").disabled = false;
  speakTamilPrompt("அனைத்து தகவல்களையும் சரிபார்த்து சமர்ப்பிக்கவும்");
}
 
function finalChallanSubmit() {
  const missing = Object.entries(sessionData).filter(([,v]) => !v).map(([k]) => k);
  if (missing.length) {
    _showError("சில தகவல்கள் நிரப்பப்படவில்லை: " + missing.join(", "));
    return;
  }
 
  fetch("/confirm_challan", {
    method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify(sessionData)
  }).catch(() => {});
 
  document.getElementById("chSummaryTable").innerHTML = `
    <div style="text-align:center;padding:18px;color:#2ecc71;font-size:1.05rem;font-weight:700">
      ✅ சலான் வெற்றிகரமாக சமர்ப்பிக்கப்பட்டது!<br>
      <span style="font-size:.78rem;color:var(--text-muted);font-weight:400">
        Challan submitted successfully
      </span>
    </div>`;
  document.getElementById("chFinalSubmit").disabled = true;
  speakTamilPrompt("சலான் வெற்றிகரமாக சமர்ப்பிக்கப்பட்டது. நன்றி!");
}
 
// ══════════════════════════════════════════════════════════════
// HELPERS
// ══════════════════════════════════════════════════════════════
function _show(id) { const el=document.getElementById(id); if(el) el.style.display=""; }
function _hide(id) { const el=document.getElementById(id); if(el) el.style.display="none"; }
function _showError(msg) {
  const el = document.getElementById("chErrorMsg");
  if (el) { el.textContent = msg; el.style.display = ""; }
}
function _showConfirm(step, displayValue) {
  const val = document.getElementById("chConfirmVal-" + step);
  if (val) val.textContent = displayValue;
  _show("chConfirm-" + step);
  _hide("chWarning-" + step);
}
// function _markDone(step, displayVal) {
//   const card  = document.getElementById("chStep-"  + step);
//   const badge = document.getElementById("chBadge-" + step);
//   if (card)  { card.classList.remove("active-step"); card.classList.add("done-step"); }
//   if (badge) badge.textContent = "✓ " + displayVal;
// }
 
function _markDone(step, displayVal) {
  const card  = document.getElementById("chStep-"  + step);
  const badge = document.getElementById("chBadge-" + step);
  if (card)  { 
    card.classList.remove("active-step"); 
    card.classList.add("done-step"); 
  }
  if (badge) {
    // Add the value and a clickable Tamil "Edit" button
    badge.innerHTML = `✓ ${displayVal} <span style="cursor:pointer; color:#e74c3c; margin-left:15px; font-weight:bold; font-size:0.9em;" onclick="reopenStep('${step}')">✏️ மாற்று</span>`;
  }
}

// ══════════════════════════════════════════════════════════════
// GO BACK / EDIT PREVIOUS STEP
// ══════════════════════════════════════════════════════════════
function reopenStep(stepToEdit) {
  const targetIdx = STEP_ORDER.indexOf(stepToEdit);

  // Clear data and reset UI for the step we are editing AND all steps after it
  for (let i = targetIdx; i < STEP_ORDER.length; i++) {
    let s = STEP_ORDER[i];
    
    // Clear backend data
    if (s === "name") sessionData.name = "";
    if (s === "account") sessionData.account_number = "";
    if (s === "bank") { sessionData.bank = ""; sessionData.branch = ""; }
    if (s === "txn") sessionData.transaction_type = "";
    if (s === "amount") sessionData.amount = "";

    // Clear visible input fields
    const inp = document.getElementById("chInput-" + s);
    if (inp) inp.value = "";
    if (s === "bank") {
      const b = document.getElementById("chInput-bank");
      const br = document.getElementById("chInput-branch");
      if (b) b.value = "";
      if (br) br.value = "";
    }
    if (s === "txn") {
      document.getElementById("txnDeposit")?.classList.remove("selected");
      document.getElementById("txnWithdrawal")?.classList.remove("selected");
    }

    // Hide confirmations and remove "done" status
    _hide("chConfirm-" + s);
    _hide("chWarning-" + s);
    const badge = document.getElementById("chBadge-" + s);
    if (badge) badge.innerHTML = "";
    const card = document.getElementById("chStep-" + s);
    if (card) card.classList.remove("done-step");
  }

  // Hide Final Summary if it's open
  document.getElementById("chFinalSubmit").disabled = true;
  document.getElementById("chSummaryTable").innerHTML = "";

  // Reactivate the chosen step
  renderStep(stepToEdit);
}