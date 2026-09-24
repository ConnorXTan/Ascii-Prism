# Regression: ISSUE-001 — a frame the server could not decode got no reply at all, and the
# page only sends its next frame after a reply, so one bad frame froze the stream for good
# while the readout still said "Tracking".
# Found by /qa on 2026-09-24
# Report: .gstack/qa-reports/qa-report-localhost-2026-09-24.md
from fastapi.testclient import TestClient

from ascii_prism.server import app


def test_undecodable_frame_still_gets_a_reply(hand_model):
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        assert ws.receive_json() == {"type": "ready"}
        ws.send_bytes(b"\x01\x02\x03\x04")  # not a JPEG
        assert ws.receive_json() == {"type": "dropped"}
        ws.send_bytes(b"")  # an empty frame is just as undecodable
        assert ws.receive_json() == {"type": "dropped"}
        # The connection is still usable afterwards.
        ws.send_json({"type": "lock"})
        assert ws.receive_json() == {"type": "lock", "locked": False}
