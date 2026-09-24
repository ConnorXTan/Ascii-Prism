import cv2

from ascii_prism.hands import HandTracker, hand_facing, sides_for


def test_sides_come_from_position():
    assert sides_for([0.7, 0.2]) == ["Right", "Left"]
    assert sides_for([0.2, 0.7]) == ["Left", "Right"]
    assert sides_for([0.3]) == ["Left"]
    assert sides_for([0.6]) == ["Right"]
    assert sides_for([]) == []


def test_hand_facing_rule():
    # Hand on the right of the frame, palm to camera: index knuckle left of pinky knuckle.
    assert hand_facing((0.5, 0.9), (0.4, 0.6), (0.6, 0.6), "Right") == "palm"
    assert hand_facing((0.5, 0.9), (0.6, 0.6), (0.4, 0.6), "Right") == "back"
    # The same winding on the left of the frame is the back of that hand.
    assert hand_facing((0.5, 0.9), (0.4, 0.6), (0.6, 0.6), "Left") == "back"
    assert hand_facing((0.5, 0.9), (0.6, 0.6), (0.4, 0.6), "Left") == "palm"


def test_hand_facing_is_rotation_invariant():
    # Fingers pointing to the right instead of up: same hand, same answer.
    assert hand_facing((0.1, 0.5), (0.4, 0.4), (0.4, 0.6), "Right") == "palm"
    # Fingers pointing down.
    assert hand_facing((0.5, 0.1), (0.6, 0.4), (0.4, 0.4), "Right") == "palm"


def test_mirroring_swaps_sides_but_keeps_facing(hands_photo, hand_model):
    """Flipping the frame moves each hand to the other side of the screen, so
    its label swaps; which side of the hand faces the camera must not change."""
    photo = cv2.cvtColor(cv2.imread(str(hands_photo)), cv2.COLOR_BGR2RGB)
    raw = HandTracker(hand_model)
    flipped = HandTracker(hand_model)
    try:
        a = raw.detect(photo, 0)
        b = flipped.detect(cv2.flip(photo, 1), 0)
    finally:
        raw.close()
        flipped.close()
    assert len(a) == 2 and len(b) == 2
    assert {h.handedness for h in a} == {"Left", "Right"}
    assert {h.handedness for h in b} == {"Left", "Right"}
    for hands in (a, b):
        left, right = sorted(hands, key=lambda h: h.center[0])
        assert (left.handedness, right.handedness) == ("Left", "Right")
    # Match hands by vertical position (one is high, one is low in this photo).
    a.sort(key=lambda h: h.center[1])
    b.sort(key=lambda h: h.center[1])
    for ha, hb in zip(a, b):
        assert ha.handedness != hb.handedness
        assert ha.facing == hb.facing
        assert ha.facing in ("palm", "back")
