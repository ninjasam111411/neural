import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: E402

_tmp = tempfile.mkdtemp()
config.DATA_DIR = _tmp
import app as neural  # noqa: E402


def fake_stream(url, model, messages, temperature=0.7):
    fake_stream.last_messages = messages
    for part in ["Hello", " there", "!"]:
        yield part


def read_sse(resp):
    events = []
    for block in resp.get_data(as_text=True).split("\n\n"):
        if block.startswith("data:"):
            events.append(json.loads(block[5:]))
    return events


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.client = neural.app.test_client()

    def test_chat_streams_and_saves(self):
        with mock.patch.object(neural.ollama_client, "stream_chat", fake_stream):
            r = self.client.post("/api/chat", json={"message": "hi"})
            ev = read_sse(r)  # stream is lazy: read while the mock is active
        text = "".join(e.get("token", "") for e in ev)
        self.assertEqual(text, "Hello there!")
        self.assertTrue(ev[-1].get("done"))
        cid = ev[0]["conversation_id"]
        msgs = self.client.get(f"/api/conversations/{cid}").get_json()["messages"]
        self.assertEqual([m["role"] for m in msgs], ["user", "assistant"])

    def test_remember_command_and_prompt_injection(self):
        r = self.client.post("/api/chat", json={"message": "/remember my dog is named Biscuit"})
        self.assertIn("Biscuit", "".join(e.get("token", "") for e in read_sse(r)))
        with mock.patch.object(neural.ollama_client, "stream_chat", fake_stream):
            read_sse(self.client.post("/api/chat", json={"message": "who is my dog?"}))
        system = fake_stream.last_messages[0]["content"]
        self.assertIn("my dog is named Biscuit", system)

    def test_forget(self):
        fid = self.client.post("/api/facts", json={"text": "temp fact"}).get_json()["id"]
        self.assertTrue(self.client.delete(f"/api/facts/{fid}").get_json()["ok"])

    def test_empty_message_rejected(self):
        self.assertEqual(self.client.post("/api/chat", json={"message": "  "}).status_code, 400)

    def test_ollama_down_gives_error_event(self):
        def boom(*a, **k):
            raise neural.ollama_client.OllamaError("Can't reach Ollama.")
            yield
        with mock.patch.object(neural.ollama_client, "stream_chat", boom):
            ev = read_sse(self.client.post("/api/chat", json={"message": "hi"}))
        self.assertIn("error", ev[-1])

    def test_status_when_ollama_down(self):
        with mock.patch.object(neural.ollama_client, "status", lambda u: (False, [])):
            s = self.client.get("/api/status").get_json()
        self.assertFalse(s["ollama_reachable"])

    def test_delete_conversation(self):
        cid = self.client.post("/api/conversations").get_json()["id"]
        self.client.delete(f"/api/conversations/{cid}")
        self.assertEqual(self.client.get(f"/api/conversations/{cid}").status_code, 404)

    def test_photo_uses_vision_model_and_is_not_stored(self):
        seen = {}

        def spy(url, model, messages, temperature=0.7):
            seen["model"] = model
            seen["images"] = messages[-1].get("images")
            yield "I see you."

        with mock.patch.object(neural.ollama_client, "stream_chat", spy):
            r = self.client.post(
                "/api/chat",
                json={"message": "what do you see?", "image": "data:image/jpeg;base64,QUJD"},
            )
            ev = read_sse(r)
        self.assertEqual(seen["model"], neural.CFG["vision_model"])
        self.assertEqual(seen["images"], ["QUJD"])  # prefix stripped
        cid = ev[0]["conversation_id"]
        msgs = self.client.get(f"/api/conversations/{cid}").get_json()["messages"]
        self.assertNotIn("QUJD", json.dumps(msgs))  # photo itself never saved
        self.assertIn("[photo attached]", msgs[0]["content"])

    def test_normal_chat_uses_text_model(self):
        seen = {}

        def spy(url, model, messages, temperature=0.7):
            seen["model"] = model
            yield "ok"

        with mock.patch.object(neural.ollama_client, "stream_chat", spy):
            read_sse(self.client.post("/api/chat", json={"message": "hello"}))
        self.assertEqual(seen["model"], neural.CFG["model"])

    def test_transcribe(self):
        with mock.patch.object(neural.voice, "transcribe", lambda a, s, c: "hello world"):
            r = self.client.post("/api/transcribe", data=b"audio", content_type="audio/webm")
        self.assertEqual(r.get_json()["text"], "hello world")

    def test_transcribe_error_and_empty(self):
        self.assertEqual(self.client.post("/api/transcribe", data=b"", content_type="audio/webm").status_code, 400)

        def boom(a, s, c):
            raise neural.voice.VoiceError("no model")

        with mock.patch.object(neural.voice, "transcribe", boom):
            r = self.client.post("/api/transcribe", data=b"x", content_type="audio/webm")
        self.assertEqual(r.status_code, 500)
        self.assertIn("no model", r.get_json()["error"])

    def test_index_served(self):
        self.assertEqual(self.client.get("/").status_code, 200)


if __name__ == "__main__":
    unittest.main()
