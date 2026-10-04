const $ = (id) => document.getElementById(id);
const LS = {
  get(k, d) { try { const v = localStorage.getItem(k); return v === null ? d : JSON.parse(v); } catch (e) { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} },
};

let convId = null;
let busy = false;
let speakOn = LS.get("speakOn", false);
let convOn = false; // conversation mode always starts off
let attachedImage = null;
const VISION_WORDS = /\b(see me|look at me|look at this|what do you see|how do i look|can you see|show you|what am i (holding|wearing)|do i look)\b/i;

async function api(path, opts) {
  const r = await fetch(path, opts);
  return r.json();
}
function setStatus(t) { $("status").textContent = t || ""; }

/* ------------------------------------------------------------ messages */
function addMsg(role, text, extraClass, imgUrl) {
  const empty = document.querySelector(".empty");
  if (empty) empty.remove();
  const div = document.createElement("div");
  div.className = `msg ${role}${extraClass ? " " + extraClass : ""}`;
  if (imgUrl) {
    const im = document.createElement("img");
    im.className = "snap";
    im.src = imgUrl;
    div.appendChild(im);
  }
  const span = document.createElement("span");
  span.textContent = text;
  div.appendChild(span);
  $("messages").appendChild(div);
  $("messages").scrollTop = $("messages").scrollHeight;
  return span;
}
function showEmpty(name) {
  $("messages").innerHTML = `<div class="empty"><h2>Hi${name ? ", " + name : ""}.</h2><p>Type, or press Mic and talk. Turn on Camera and say "look at me".</p></div>`;
}

async function loadStatus() {
  const s = await api("/api/status");
  $("brandName").textContent = s.assistant_name;
  $("version").textContent = "v" + s.version;
  document.title = s.assistant_name;
  $("input").placeholder = `Message ${s.assistant_name}...  (try /remember I love hiking)`;
  const banner = $("banner");
  if (!s.ollama_reachable) {
    banner.hidden = false;
    banner.textContent = "Ollama isn't running. Close this and use start.bat, which launches it for you.";
  } else if (!s.model_installed) {
    banner.hidden = false;
    banner.textContent = `Model "${s.model}" isn't installed yet. Run setup.bat (or: ollama pull ${s.model}).`;
  } else {
    banner.hidden = true;
  }
  return s;
}

async function loadConversations() {
  const list = await api("/api/conversations");
  const box = $("convList");
  box.innerHTML = "";
  for (const c of list) {
    const row = document.createElement("div");
    row.className = "conv" + (c.id === convId ? " active" : "");
    const t = document.createElement("span");
    t.textContent = c.title;
    const del = document.createElement("button");
    del.textContent = "x";
    del.title = "Delete chat";
    del.onclick = async (e) => {
      e.stopPropagation();
      if (!confirm("Delete this chat?")) return;
      await api(`/api/conversations/${c.id}`, { method: "DELETE" });
      if (c.id === convId) newChat();
      loadConversations();
    };
    row.onclick = () => openConversation(c.id);
    row.append(t, del);
    box.appendChild(row);
  }
}
async function openConversation(id) {
  convId = id;
  const data = await api(`/api/conversations/${id}`);
  $("messages").innerHTML = "";
  for (const m of data.messages) addMsg(m.role, m.content);
  loadConversations();
}
function newChat() {
  convId = null;
  showEmpty();
  loadConversations();
  $("input").focus();
}

/* ------------------------------------------------------------ speaking (text to speech, local OS voices) */
let voices = [];
let ttsGen = 0; // bumped to invalidate callbacks when speech is cancelled
let ttsPending = 0;
let sentBuf = "";
let replyDone = true;

function loadVoices() {
  const all = speechSynthesis.getVoices();
  const local = all.filter((v) => v.localService);
  voices = local.length ? local : all;
  const sel = $("voiceSelect");
  sel.innerHTML = "";
  const saved = LS.get("voiceURI", null);
  let best = null;
  for (const v of voices) {
    const o = document.createElement("option");
    o.value = v.voiceURI;
    o.textContent = `${v.name} (${v.lang})`;
    sel.appendChild(o);
    if (!best && /en[-_]/i.test(v.lang) && /natural|aria|jenny|zira|samantha|google us/i.test(v.name)) best = v.voiceURI;
  }
  sel.value = saved && voices.some((v) => v.voiceURI === saved) ? saved
    : best || (voices.find((v) => /^en/i.test(v.lang)) || voices[0] || {}).voiceURI || "";
}
if ("speechSynthesis" in window) {
  loadVoices();
  speechSynthesis.onvoiceschanged = loadVoices;
}
$("voiceSelect").onchange = () => LS.set("voiceURI", $("voiceSelect").value);
$("rate").value = LS.get("rate", 1);
$("rate").oninput = () => LS.set("rate", parseFloat($("rate").value));

function cleanForSpeech(t) {
  return t.replace(/```[\s\S]*?```/g, " code block. ").replace(/[*_#`>~]/g, "").replace(/\s+/g, " ").trim();
}
function speakChunk(text) {
  text = cleanForSpeech(text);
  if (!text || !("speechSynthesis" in window)) return;
  const u = new SpeechSynthesisUtterance(text);
  const v = voices.find((x) => x.voiceURI === $("voiceSelect").value);
  if (v) u.voice = v;
  u.rate = parseFloat($("rate").value) || 1;
  const gen = ttsGen;
  ttsPending++;
  $("stopSpeak").hidden = false;
  const finish = () => {
    if (gen !== ttsGen) return;
    ttsPending--;
    if (ttsPending <= 0) onSpeechIdle();
  };
  u.onend = finish;
  u.onerror = finish;
  speechSynthesis.speak(u);
}
function feedSpeech(token) {
  if (!speakOn) return;
  sentBuf += token;
  let m;
  while ((m = sentBuf.match(/^([\s\S]*?[.!?\n])\s/))) {
    speakChunk(m[1]);
    sentBuf = sentBuf.slice(m[0].length);
  }
}
function flushSpeech() {
  if (speakOn && sentBuf.trim()) speakChunk(sentBuf);
  sentBuf = "";
  replyDone = true;
  if (ttsPending <= 0) onSpeechIdle();
}
function stopSpeaking() {
  ttsGen++;
  ttsPending = 0;
  sentBuf = "";
  if ("speechSynthesis" in window) speechSynthesis.cancel();
  $("stopSpeak").hidden = true;
}
function onSpeechIdle() {
  $("stopSpeak").hidden = true;
  if (convOn && replyDone && !busy) setTimeout(startListening, 350);
}
$("stopSpeak").onclick = () => { stopSpeaking(); };

/* ------------------------------------------------------------ listening (local Whisper on the backend) */
let rec = null;
function setMic(on) {
  $("micBtn").classList.toggle("rec", on);
  $("micBtn").textContent = on ? "Stop" : "Mic";
  setStatus(on ? "Listening..." : "");
}
async function startListening() {
  if (rec || busy) return;
  stopSpeaking();
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch (e) {
    setStatus("Microphone is blocked. Allow it in the address bar, then try again.");
    setConv(false);
    return;
  }
  const mime = MediaRecorder.isTypeSupported("audio/webm;codecs=opus") ? "audio/webm;codecs=opus" : "";
  const mr = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
  const chunks = [];
  mr.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };

  const ctx = new AudioContext();
  const an = ctx.createAnalyser();
  an.fftSize = 1024;
  ctx.createMediaStreamSource(stream).connect(an);
  const buf = new Uint8Array(an.fftSize);
  let heard = false, cancelled = false;
  const start = Date.now();
  let lastVoice = start;

  const tick = setInterval(() => {
    an.getByteTimeDomainData(buf);
    let sum = 0;
    for (const b of buf) { const d = (b - 128) / 128; sum += d * d; }
    const now = Date.now();
    if (Math.sqrt(sum / buf.length) > 0.03) { heard = true; lastVoice = now; }
    if ((heard && now - lastVoice > 1400) || now - start > 30000 || (!heard && now - start > 8000)) mr.stop();
  }, 100);

  mr.onstop = async () => {
    clearInterval(tick);
    stream.getTracks().forEach((t) => t.stop());
    ctx.close();
    rec = null;
    setMic(false);
    if (cancelled) return;
    if (!heard) { if (convOn) setTimeout(startListening, 300); return; }
    setStatus("Transcribing...");
    try {
      const blob = new Blob(chunks, { type: mr.mimeType || "audio/webm" });
      const res = await fetch("/api/transcribe", { method: "POST", headers: { "Content-Type": blob.type }, body: blob });
      const data = await res.json();
      setStatus("");
      if (data.error) { setStatus(data.error); setConv(false); return; }
      const text = (data.text || "").trim();
      if (!text) { if (convOn) setTimeout(startListening, 300); return; }
      submitText(text);
    } catch (e) {
      setStatus("Transcription failed: " + e);
      setConv(false);
    }
  };
  rec = { stop: () => mr.stop(), cancel: () => { cancelled = true; mr.stop(); } };
  mr.start();
  setMic(true);
}
$("micBtn").onclick = () => {
  if (rec) { rec.stop(); return; }
  startListening();
};

/* ------------------------------------------------------------ camera */
let camStream = null;
async function camOn() {
  try {
    camStream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } });
  } catch (e) {
    setStatus("Camera is blocked. Allow it in the address bar, then try again.");
    return;
  }
  $("camVideo").srcObject = camStream;
  $("camPanel").hidden = false;
  $("toggleCam").classList.add("on");
  $("toggleCam").textContent = "Camera: on";
}
function camOff() {
  if (camStream) camStream.getTracks().forEach((t) => t.stop());
  camStream = null;
  $("camVideo").srcObject = null;
  $("camPanel").hidden = true;
  $("toggleCam").classList.remove("on");
  $("toggleCam").textContent = "Camera: off";
}
function grabFrame() {
  const v = $("camVideo");
  if (!camStream || !v.videoWidth) return null;
  const s = Math.min(1, 768 / Math.max(v.videoWidth, v.videoHeight));
  const c = document.createElement("canvas");
  c.width = Math.round(v.videoWidth * s);
  c.height = Math.round(v.videoHeight * s);
  c.getContext("2d").drawImage(v, 0, 0, c.width, c.height);
  return c.toDataURL("image/jpeg", 0.8);
}
function setAttachment(dataUrl) {
  attachedImage = dataUrl;
  $("attach").hidden = !dataUrl;
  if (dataUrl) $("attachImg").src = dataUrl;
}
$("toggleCam").onclick = () => (camStream ? camOff() : camOn());
$("snapBtn").onclick = () => { const f = grabFrame(); if (f) setAttachment(f); };
$("attachClear").onclick = () => setAttachment(null);
$("lookBtn").onclick = () => {
  const f = grabFrame();
  if (!f) return;
  submitText("What do you see?", f);
};

/* ------------------------------------------------------------ sending */
function submitText(text, image) {
  if (busy) return;
  let img = image || attachedImage;
  if (!img && camStream && VISION_WORDS.test(text)) img = grabFrame();
  setAttachment(null);
  send(text, img);
}

async function send(text, image) {
  busy = true;
  replyDone = false;
  $("send").disabled = true;
  addMsg("user", text, null, image);
  const bubble = addMsg("assistant", "...");
  let got = false;
  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ conversation_id: convId, message: text, image: image || null }),
    });
    const reader = res.body.getReader();
    const dec = new TextDecoder();
    let buf = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let idx;
      while ((idx = buf.indexOf("\n\n")) >= 0) {
        const line = buf.slice(0, idx).trim();
        buf = buf.slice(idx + 2);
        if (!line.startsWith("data:")) continue;
        const ev = JSON.parse(line.slice(5));
        if (ev.conversation_id) convId = ev.conversation_id;
        if (ev.token) {
          if (!got) { bubble.textContent = ""; got = true; }
          bubble.textContent += ev.token;
          feedSpeech(ev.token);
          $("messages").scrollTop = $("messages").scrollHeight;
        }
        if (ev.error) {
          bubble.textContent = ev.error;
          bubble.parentElement.classList.add("error");
          got = true;
        }
      }
    }
  } catch (e) {
    bubble.textContent = "Connection to Neural lost: " + e;
    bubble.parentElement.classList.add("error");
  }
  busy = false;
  $("send").disabled = false;
  flushSpeech();
  if (!convOn) $("input").focus();
  loadConversations();
  loadStatus();
}

$("composer").addEventListener("submit", (e) => {
  e.preventDefault();
  const text = $("input").value.trim();
  if (!text || busy) return;
  $("input").value = "";
  $("input").style.height = "auto";
  stopSpeaking();
  submitText(text);
});
$("input").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    $("composer").requestSubmit();
  }
});
$("input").addEventListener("input", () => {
  const el = $("input");
  el.style.height = "auto";
  el.style.height = Math.min(el.scrollHeight, 160) + "px";
});
$("newChat").onclick = newChat;

/* ------------------------------------------------------------ toggles */
function setSpeak(on) {
  speakOn = on;
  LS.set("speakOn", on);
  $("toggleSpeak").classList.toggle("on", on);
  $("toggleSpeak").textContent = "Speak replies: " + (on ? "on" : "off");
  if (!on) stopSpeaking();
}
function setConv(on) {
  convOn = on;
  $("toggleConv").classList.toggle("on", on);
  $("toggleConv").textContent = "Conversation mode: " + (on ? "on" : "off");
  if (on) { setSpeak(true); startListening(); }
  else if (rec) rec.cancel();
}
$("toggleSpeak").onclick = () => setSpeak(!speakOn);
$("toggleConv").onclick = () => setConv(!convOn);
setSpeak(speakOn);

/* ------------------------------------------------------------ facts modal */
async function renderFacts() {
  const facts = await api("/api/facts");
  const ul = $("factsList");
  ul.innerHTML = "";
  if (!facts.length) ul.innerHTML = "<li><span>Nothing yet. Add something below, or type /remember in chat.</span></li>";
  for (const f of facts) {
    const li = document.createElement("li");
    const s = document.createElement("span");
    s.textContent = f.text;
    const b = document.createElement("button");
    b.textContent = "x";
    b.onclick = async () => { await api(`/api/facts/${f.id}`, { method: "DELETE" }); renderFacts(); };
    li.append(s, b);
    ul.appendChild(li);
  }
}
$("openFacts").onclick = () => { $("factsModal").hidden = false; renderFacts(); };
$("closeFacts").onclick = () => { $("factsModal").hidden = true; };
$("factForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = $("factInput").value.trim();
  if (!text) return;
  await api("/api/facts", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text }) });
  $("factInput").value = "";
  renderFacts();
});

(async () => {
  const s = await loadStatus();
  showEmpty(s.user_name);
  loadConversations();
})();
