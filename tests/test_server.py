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


def test_websocket_round_trip(hands_photo, hand_model):
    jpeg = hands_photo.read_bytes()
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        assert ws.receive_json() == {"type": "ready"}
        ws.send_json({"type": "settings", "settings": {"smoothing": 0, "mirror": False}})
        ws.send_bytes(b"definitely not a jpeg")
        assert ws.receive_json() == {"type": "dropped"}  # answered, so the page keeps streaming
        ws.send_bytes(jpeg)
        track = ws.receive_json()
        assert track["type"] == "track"
        assert track["hands"] == 2
        assert track["hint"] == ""
        assert track["locked"] is False
        assert track["ms"] >= 0
        # Geometry comes back normalized so the page can scale it to its own video.
        assert len(track["quad"]) == 4 and len(track["tips"]) == 4
        assert all(0 <= x <= 1 and 0 <= y <= 1 for x, y in track["quad"] + track["tips"])
        assert isinstance(track["twisted"], bool)

        ws.send_json({"type": "lock"})
        assert ws.receive_json() == {"type": "lock", "locked": True}
        ws.send_bytes(jpeg)
        assert ws.receive_json()["locked"] is True
