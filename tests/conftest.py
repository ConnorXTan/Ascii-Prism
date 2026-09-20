import urllib.request
from pathlib import Path

import pytest

CACHE = Path(__file__).parent / ".cache"
HANDS_PHOTO_URL = "https://storage.googleapis.com/mediapipe-tasks/hand_landmarker/woman_hands.jpg"


def _fetch(url: str, dest: Path) -> Path | None:
    if dest.exists():
        return dest
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(url, dest)
        return dest
    except OSError:
        return None


@pytest.fixture(scope="session")
def hands_photo() -> Path:
    path = _fetch(HANDS_PHOTO_URL, CACHE / "hands.jpg")
    if path is None:
        pytest.skip("sample hands photo unavailable (offline?)")
    return path


@pytest.fixture(scope="session")
def hand_model() -> Path:
    from ascii_prism.model import ensure_model

    try:
        return ensure_model(log=lambda *_: None)
    except OSError:
        pytest.skip("hand model unavailable (offline?)")
