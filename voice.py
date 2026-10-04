"""Local speech-to-text with faster-whisper. Audio never leaves your computer.

The model downloads once (first use, or setup.bat) into models/whisper.
"""
import os
import tempfile
import threading

import config

_model = None
_lock = threading.Lock()


class VoiceError(Exception):
    pass


def _get_model(cfg):
    global _model
    with _lock:
        if _model is None:
            try:
                from faster_whisper import WhisperModel
            except ImportError:
                raise VoiceError("Voice input needs faster-whisper. Run setup.bat again.")
            root = os.path.join(config.BASE_DIR, "models", "whisper")
            os.makedirs(root, exist_ok=True)
            try:
                _model = WhisperModel(
                    cfg["whisper_model"],
                    device=cfg["whisper_device"],
                    compute_type=cfg["whisper_compute"],
                    download_root=root,
                )
            except Exception as e:  # download or load failure
                raise VoiceError(f"Could not load the speech model: {e}")
        return _model


def transcribe(audio_bytes, suffix, cfg):
    """Return the transcribed text for a chunk of recorded audio."""
    model = _get_model(cfg)
    fd, path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(audio_bytes)
        lang = cfg.get("whisper_language") or None
        segments, _info = model.transcribe(
            path, language=lang, beam_size=1, vad_filter=True
        )
        return " ".join(seg.text.strip() for seg in segments).strip()
    except VoiceError:
        raise
    except Exception as e:
        raise VoiceError(f"Could not read that audio: {e}")
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
