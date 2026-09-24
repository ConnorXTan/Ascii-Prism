import cv2

from ascii_prism.hands import HandTracker


def test_detects_two_hands_with_fingertips(hands_photo, hand_model):
    photo = cv2.cvtColor(cv2.imread(str(hands_photo)), cv2.COLOR_BGR2RGB)
    tracker = HandTracker(hand_model)
    try:
        hands = tracker.detect(photo, 0)
    finally:
        tracker.close()
    assert len(hands) == 2
    for hand in hands:
        for point in (hand.thumb, hand.index, hand.center):
            assert 0.0 <= point[0] <= 1.0 and 0.0 <= point[1] <= 1.0
    # Two different hands, not the same one twice.
    assert hands[0].center != hands[1].center
