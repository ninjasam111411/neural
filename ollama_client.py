"""Thin client for the local Ollama server."""
import json

import requests


class OllamaError(Exception):
    pass


def status(url):
    """Return (reachable, installed_model_names)."""
    try:
        r = requests.get(f"{url}/api/tags", timeout=3)
        r.raise_for_status()
        return True, [m["name"] for m in r.json().get("models", [])]
    except requests.RequestException:
        return False, []


def stream_chat(url, model, messages, temperature=0.7):
    """Yield reply text chunks from Ollama as they are generated."""
    try:
        with requests.post(
            f"{url}/api/chat",
            json={
                "model": model,
                "messages": messages,
                "stream": True,
                "options": {"temperature": temperature},
            },
            stream=True,
            timeout=(5, 300),
        ) as r:
            if r.status_code == 404:
                raise OllamaError(
                    f"Model '{model}' is not installed. Run setup.bat, or: ollama pull {model}"
                )
            r.raise_for_status()
            for line in r.iter_lines():
                if not line:
                    continue
                data = json.loads(line)
                if data.get("error"):
                    raise OllamaError(data["error"])
                chunk = data.get("message", {}).get("content", "")
                if chunk:
                    yield chunk
                if data.get("done"):
                    break
    except requests.ConnectionError:
        raise OllamaError("Can't reach Ollama. Make sure it is running (start.bat does this).")
    except requests.RequestException as e:
        raise OllamaError(f"Ollama request failed: {e}")
