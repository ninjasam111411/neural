# Neural

A private, local-first personal assistant. A Flask backend talks to an Ollama
model on your own computer, remembers things about you, and serves a chat page
in your browser. Nothing leaves your machine.

## Setup (Windows)

1. Install [Python 3.10+](https://python.org) (tick "Add to PATH") and [Ollama](https://ollama.com/download).
2. If the Ollama tray icon is running, right-click it and choose Quit (so models save into this folder).
3. Double-click `setup.bat`. It installs packages and downloads the model into `models/`.
4. Double-click `start.bat`. Your browser opens at http://127.0.0.1:5000.

## Using it

- Chat normally. Conversations are saved in the sidebar.
- `/remember <fact>` saves something about you permanently. `/facts` lists them, `/forget <number>` removes one.
- "What I know about you" (bottom left) lets you view, add and delete facts.
- Change the model, your name or the personality in `config.json` (created on first run).

## Voice and camera (1.1.0)

- **Mic** button: talk, and it stops when you go quiet. Speech is turned into text by Whisper running on your computer.
- **Speak replies** reads answers aloud with a voice installed on your computer (pick one in the sidebar).
- **Conversation mode** keeps a hands-free loop going: you talk, it answers out loud, then listens again. Click "Stop talking" to interrupt.
- **Camera** shows a small preview. Press "Look at me", or just ask "can you see me?" and it takes a snapshot for the vision model. Photos are sent to the model for that one message and are never saved.
- Models are set in `config.json` (`model`, `vision_model`, `whisper_model`).

## Updates

Drop a package folder (named like `1.2.0`) into `updates/pending/` and double-click `apply_updates.bat`.

## Layout

| File | Purpose |
|---|---|
| `app.py` | Web server and chat endpoint |
| `memory.py` | Short-term history + long-term facts (SQLite in `data/`) |
| `ollama_client.py` | Streaming client for Ollama |
| `voice.py` | Local speech-to-text (Whisper) |
| `apply_updates.py` | Applies update packages |
| `config.py` / `config.json` | Settings |
| `static/` | Browser interface |
| `tests/` | `python -m unittest discover -s tests` |

`data/`, `models/` and `config.json` are git-ignored, so your personal memory and
the multi-GB models never get uploaded.

## Roadmap

1. File search over folders you choose
2. Screen / camera vision
3. Always-on background service, hotkey and wake word
4. Discord text bot, then voice
5. Remote access via Tailscale
