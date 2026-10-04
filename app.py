"""Neural - your local personal assistant. Backend server.

Run with start.bat (Windows) or `python app.py`.
"""
import json
import threading
import time
import webbrowser

from flask import Flask, Response, jsonify, request, send_from_directory, stream_with_context

import config
import ollama_client
import voice
from memory import Memory

CFG = config.load()
MEM = Memory(config.DATA_DIR)
app = Flask(__name__, static_folder="static", static_url_path="/static")
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024  # audio / photo uploads


# ---------------------------------------------------------------- prompt
def build_messages(conv_id, image=None):
    facts = MEM.list_facts()
    system = CFG["system_prompt"].format(
        assistant_name=CFG["assistant_name"], user_name=CFG["user_name"]
    )
    if facts:
        system += f"\n\nThings you know about {CFG['user_name']}:\n"
        system += "\n".join(f"- {f['text']}" for f in facts)
    system += f"\n\nCurrent date and time: {time.strftime('%A, %B %d, %Y, %I:%M %p')}."
    if image:
        system += (
            f"\n\nThe latest message includes a live webcam photo of {CFG['user_name']} "
            "taken just now. Answer from what is actually visible, kindly and naturally. "
            "Don't guess sensitive personal attributes, and say so if the photo is unclear."
        )
    history = MEM.get_messages(conv_id, limit=CFG["history_messages"])
    msgs = [{"role": m["role"], "content": m["content"]} for m in history]
    if image and msgs and msgs[-1]["role"] == "user":
        msgs[-1]["images"] = [image]  # sent for this turn only, never stored
    return [{"role": "system", "content": system}] + msgs


def sse(obj):
    return f"data: {json.dumps(obj)}\n\n"


# ---------------------------------------------------------------- commands
def run_command(text):
    """Handle /remember, /forget, /facts. Returns reply text or None."""
    cmd, _, arg = text.partition(" ")
    cmd = cmd.lower()
    if cmd == "/remember":
        if not arg.strip():
            return "Usage: /remember <something about you>"
        MEM.add_fact(arg)
        return f"Got it. I'll remember: {arg.strip()}"
    if cmd == "/forget":
        if not arg.strip().isdigit():
            return "Usage: /forget <fact number>. Type /facts to see the numbers."
        ok = MEM.delete_fact(int(arg))
        return "Forgotten." if ok else "I don't have a fact with that number."
    if cmd == "/facts":
        facts = MEM.list_facts()
        if not facts:
            return "I don't have any saved facts yet. Teach me with /remember ..."
        return "Here's what I remember:\n" + "\n".join(f"{f['id']}. {f['text']}" for f in facts)
    return None


# ---------------------------------------------------------------- routes
@app.get("/")
def index():
    return send_from_directory("static", "index.html")


@app.get("/api/status")
def api_status():
    reachable, models = ollama_client.status(CFG["ollama_url"])
    return jsonify(
        version=config.VERSION,
        assistant_name=CFG["assistant_name"],
        user_name=CFG["user_name"],
        model=CFG["model"],
        ollama_reachable=reachable,
        model_installed=any(
            m == CFG["model"] or m.split(":")[0] == CFG["model"] for m in models
        ),
        vision_model=CFG["vision_model"],
        vision_installed=any(
            m == CFG["vision_model"] or m.split(":")[0] == CFG["vision_model"] for m in models
        ),
        installed_models=models,
    )


@app.get("/api/conversations")
def api_list_conversations():
    return jsonify(MEM.list_conversations())


@app.post("/api/conversations")
def api_new_conversation():
    return jsonify(id=MEM.new_conversation())


@app.get("/api/conversations/<int:conv_id>")
def api_get_conversation(conv_id):
    if not MEM.conversation_exists(conv_id):
        return jsonify(error="not found"), 404
    return jsonify(messages=MEM.get_messages(conv_id))


@app.delete("/api/conversations/<int:conv_id>")
def api_delete_conversation(conv_id):
    MEM.delete_conversation(conv_id)
    return jsonify(ok=True)


@app.get("/api/facts")
def api_facts():
    return jsonify(MEM.list_facts())


@app.post("/api/facts")
def api_add_fact():
    text = (request.get_json(silent=True) or {}).get("text", "")
    if not text.strip():
        return jsonify(error="empty"), 400
    return jsonify(id=MEM.add_fact(text))


@app.delete("/api/facts/<int:fact_id>")
def api_delete_fact(fact_id):
    return jsonify(ok=MEM.delete_fact(fact_id))


@app.post("/api/chat")
def api_chat():
    body = request.get_json(silent=True) or {}
    text = (body.get("message") or "").strip()
    if not text:
        return jsonify(error="empty message"), 400

    image = body.get("image") or None
    if image:
        if "," in image[:100]:  # strip data:image/jpeg;base64, prefix
            image = image.split(",", 1)[1]
        if len(image) > 8_000_000:
            return jsonify(error="photo too large"), 413

    conv_id = body.get("conversation_id")
    if not conv_id or not MEM.conversation_exists(conv_id):
        conv_id = MEM.new_conversation()
    if not MEM.get_messages(conv_id):
        MEM.rename_conversation(conv_id, text[:40] + ("..." if len(text) > 40 else ""))

    MEM.add_message(conv_id, "user", text + ("\n[photo attached]" if image else ""))

    @stream_with_context
    def generate():
        yield sse({"conversation_id": conv_id})
        if text.startswith("/") and not image:
            reply = run_command(text)
            if reply is not None:
                MEM.add_message(conv_id, "assistant", reply)
                yield sse({"token": reply})
                yield sse({"done": True})
                return
        parts = []
        try:
            for chunk in ollama_client.stream_chat(
                CFG["ollama_url"],
                CFG["vision_model"] if image else CFG["model"],
                build_messages(conv_id, image),
                CFG["temperature"],
            ):
                parts.append(chunk)
                yield sse({"token": chunk})
        except ollama_client.OllamaError as e:
            yield sse({"error": str(e)})
            return
        MEM.add_message(conv_id, "assistant", "".join(parts))
        yield sse({"done": True})

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/transcribe")
def api_transcribe():
    audio = request.get_data()
    if not audio:
        return jsonify(error="no audio"), 400
    ctype = (request.content_type or "").lower()
    suffix = ".ogg" if "ogg" in ctype else ".mp4" if "mp4" in ctype else ".wav" if "wav" in ctype else ".webm"
    try:
        return jsonify(text=voice.transcribe(audio, suffix, CFG))
    except voice.VoiceError as e:
        return jsonify(error=str(e)), 500


# ---------------------------------------------------------------- main
def _open_browser():
    time.sleep(1.2)
    webbrowser.open(f"http://{CFG['host']}:{CFG['port']}")


if __name__ == "__main__":
    print(f"Neural {config.VERSION} running at http://{CFG['host']}:{CFG['port']}")
    print(f"Model: {CFG['model']}   (edit config.json to change)")
    if CFG["open_browser"]:
        threading.Thread(target=_open_browser, daemon=True).start()
    app.run(host=CFG["host"], port=CFG["port"], threaded=True)
