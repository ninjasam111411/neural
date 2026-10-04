"""Neural configuration.

Settings live in config.json (created on first run). Edit that file to change
the model, your name, the assistant's personality, etc. Restart Neural after.
"""
import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
DATA_DIR = os.path.join(BASE_DIR, "data")

with open(os.path.join(BASE_DIR, "VERSION"), encoding="utf-8") as _f:
    VERSION = _f.read().strip()

DEFAULTS = {
    "model": "llama3.2:3b",
    "vision_model": "gemma3:4b",  # used only when a webcam photo is attached
    "whisper_model": "base.en",  # local speech-to-text (try small.en for accuracy)
    "whisper_language": "en",
    "whisper_device": "cpu",
    "whisper_compute": "int8",
    "ollama_url": "http://127.0.0.1:11434",
    "host": "127.0.0.1",  # local only. Do not change until auth is added.
    "port": 5000,
    "open_browser": True,
    "assistant_name": "Neural",
    "user_name": "Eleanor",
    "history_messages": 30,  # how many recent messages the model sees
    "temperature": 0.7,
    "system_prompt": (
        "You are {assistant_name}, {user_name}'s personal assistant. "
        "Be warm, direct and genuinely useful, like a sharp office assistant who "
        "is also a good friend. Keep answers concise unless asked for detail. "
        "Use what you know about {user_name} (listed below) when it helps, but "
        "never invent facts about them. If you are unsure, say so."
    ),
}


def load():
    cfg = dict(DEFAULTS)
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg.update(json.load(f))
    else:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(DEFAULTS, f, indent=2)
    os.makedirs(DATA_DIR, exist_ok=True)
    return cfg
