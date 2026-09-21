import cv2

from ascii_prism.hands import HandTracker, hand_facing


def test_hand_facing_rule():
    # Selfie-style right hand, palm to camera: index knuckle left of pinky knuckle.
    assert hand_facing((0.5, 0.9), (0.4, 0.6), (0.6, 0.6), "Right") == "palm"
    assert hand_facing((0.5, 0.9), (0.6, 0.6), (0.4, 0.6), "Right") == "back"
    assert hand_facing((0.5, 0.9), (0.4, 0.6), (0.6, 0.6), "Left") == "back"


def test_facing_and_handedness_are_invariant_to_mirroring(hands_photo, hand_model):
    """The same physical hand must get the same label whether the frame is
    raw or flipped, provided the tracker is told which one it is."""
    photo = cv2.cvtColor(cv2.imread(str(hands_photo)), cv2.COLOR_BGR2RGB)
    raw = HandTracker(hand_model)
    flipped = HandTracker(hand_model)
    try:
        a = raw.detect(photo, 0, mirrored=False)
        b = flipped.detect(cv2.flip(photo, 1), 0, mirrored=True)
    finally:
        raw.close()
        flipped.close()
    assert len(a) == 2 and len(b) == 2
    # Match hands by vertical position (one is high, one is low in this photo).
    a.sort(key=lambda h: h.center[1])
    b.sort(key=lambda h: h.center[1])
    for ha, hb in zip(a, b):
        assert ha.handedness == hb.handedness
        assert ha.facing == hb.facing
        assert ha.facing in ("palm", "back")
    assert {h.handedness for h in a} == {"Left", "Right"}
