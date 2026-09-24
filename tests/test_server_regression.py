# Regression: ISSUE-001 — a frame the server could not decode got no reply at all, and the
# page only sends its next frame after a reply, so one bad frame froze the stream for good
# while the readout still said "Tracking".
# Found by /qa on 2026-09-24
# Report: .gstack/qa-reports/qa-report-localhost-2026-09-24.md
from pathlib import Path

from fastapi.testclient import TestClient

from ascii_prism import server


class FakeTracker:
    """Stands in for MediaPipe so the socket contract can be tested without the model."""

    def __init__(self, *args, **kwargs):
        pass

    def detect(self, frame_rgb, timestamp_ms, mirrored=True):
        return []

    def close(self):
        pass


def test_undecodable_frame_still_gets_a_reply(monkeypatch):
    monkeypatch.setattr(server, "HandTracker", FakeTracker)
    monkeypatch.setattr(server, "get_model", lambda: Path("unused.task"))
    client = TestClient(server.app)
    with client.websocket_connect("/ws") as ws:
        assert ws.receive_json() == {"type": "ready"}
        ws.send_bytes(b"\x01\x02\x03\x04")  # not a JPEG
        assert ws.receive_json() == {"type": "dropped"}
        ws.send_bytes(b"")  # an empty frame is just as undecodable
        assert ws.receive_json() == {"type": "dropped"}
        # The connection is still usable afterwards.
        ws.send_json({"type": "lock"})
        assert ws.receive_json() == {"type": "lock", "locked": False}
