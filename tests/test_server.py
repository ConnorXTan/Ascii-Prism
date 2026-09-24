import cv2
import numpy as np
from fastapi.testclient import TestClient

from ascii_prism.server import app, apply_settings
from ascii_prism.settings import Settings


def test_pages_and_config():
    client = TestClient(app)
    assert client.get("/").status_code == 200
    assert "ASCII" in client.get("/").text
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/styles.css").status_code == 200
    cfg = client.get("/api/config").json()
    assert cfg["charsets"][0]["id"] == "standard"
    assert cfg["defaults"]["columns"] == 80
    assert cfg["ranges"]["columns"] == [16, 200]
    assert cfg["ranges"]["hue"] == [-180, 180]
    assert cfg["ranges"]["delay"] == [0.2, 3.0]
    assert cfg["defaults"]["lens"] == "ascii"
    assert [lens["id"] for lens in cfg["lenses"]][:2] == ["ascii", "thermal"]
    assert all(lens["label"] and lens["blurb"] and isinstance(lens["uses"], list) for lens in cfg["lenses"])


def test_apply_settings_validates_types_and_ranges():
    s = Settings()
    apply_settings(s, {"columns": 999, "smoothing": 1, "invert": "yes", "hue": 400, "saturation": "lots",
                       "opacity": -3, "charset": "x" * 1000, "mirror": False, "background": 5, "unknown": 1})
    assert s.columns == 200
    assert s.smoothing == 0.95
    assert s.invert is False  # wrong type ignored
    assert s.hue == 180  # clamped
    assert s.saturation == 1.0  # wrong type ignored
    assert s.opacity == 0.0  # clamped
    assert len(s.charset) == 256
    assert s.mirror is False
    assert s.background == "#000000"  # wrong type ignored
    apply_settings(s, {"columns": True})
    assert s.columns == 200  # bools are not ints
    apply_settings(s, {"lens": "no-such-lens", "delay": 9})
    assert s.lens == "ascii" and s.delay == 3.0  # unknown lens falls back, delay clamped
    apply_settings(s, {"lens": "thermal", "delay": 0.05, "person_invert": True})
    assert s.lens == "thermal" and s.delay == 0.2 and s.person_invert is True


def test_websocket_round_trip(hands_photo, hand_model):
    jpeg = hands_photo.read_bytes()
    photo = cv2.imread(str(hands_photo))
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        assert ws.receive_json() == {"type": "ready"}
        ws.send_json({"type": "settings", "settings": {"columns": 40, "saturation": 1.5, "hue": 90, "opacity": 0.7}})
        ws.send_bytes(b"definitely not a jpeg")  # ignored
        ws.send_bytes(jpeg)
        out = ws.receive_bytes()
        status = ws.receive_json()
        assert status["type"] == "status"
        assert status["hands"] == 2
        assert status["grid"][0] == 40
        assert status["hint"] == ""
        assert status["lens"] == "ascii"
        rendered = cv2.imdecode(np.frombuffer(out, np.uint8), cv2.IMREAD_COLOR)
        assert rendered.shape == photo.shape

        ws.send_json({"type": "settings", "settings": {"lens": "thermal"}})
        ws.send_bytes(jpeg)
        ws.receive_bytes()
        status = ws.receive_json()
        assert status["lens"] == "thermal" and status["grid"] is None and status["hands"] == 2

        ws.send_json({"type": "lock"})
        assert ws.receive_json() == {"type": "lock", "locked": True}
        ws.send_bytes(jpeg)
        ws.receive_bytes()
        assert ws.receive_json()["locked"] is True
