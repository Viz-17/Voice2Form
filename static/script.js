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

const DIAL_LIMITS = { phone: 10, aadhaar: 12 };
const DIAL_HINTS  = {
  phone:   "10 இலக்கங்கள் • 6, 7, 8 அல்லது 9 இல் தொடங்க வேண்டும்",
  aadhaar: "12 இலக்கங்கள் • Aadhaar number"
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