"""Character ramps, ordered from darkest (first) to brightest (last)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Charset:
    id: str
    label: str
    chars: str


CHARSETS: list[Charset] = [
    Charset("standard", "Standard", " .:-=+*#%@"),
    Charset(
        "detailed",
        "Detailed (70 levels)",
        " .'`^\",:;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$",
    ),
    Charset("blocks", "Blocks", " ░▒▓█"),
    Charset("dots", "Dots", " ·•●"),
    Charset("binary", "Binary", " 01"),
    Charset("minimal", "Minimal", " .oO@"),
    Charset("prism", "Prism", " .,-~:;=!*#$@"),
]

DEFAULT_CHARSET_ID = "standard"


def by_id(charset_id: str) -> Charset | None:
    for cs in CHARSETS:
        if cs.id == charset_id:
            return cs
    return None
