from __future__ import annotations

import colorsys
import random

_RNG = random.SystemRandom()


def normalize_tag_color(color: str | None) -> str | None:
    if color is None:
        return None
    normalized = color.strip()
    return normalized or None


def generate_random_tag_color() -> str:
    # Pastel-ish HLS palette keeps tag chips readable.
    hue = _RNG.random()
    lightness = _RNG.uniform(0.62, 0.74)
    saturation = _RNG.uniform(0.45, 0.7)
    red, green, blue = colorsys.hls_to_rgb(hue, lightness, saturation)
    return f"#{int(red * 255):02x}{int(green * 255):02x}{int(blue * 255):02x}"


def resolve_tag_color(color: str | None) -> str:
    normalized = normalize_tag_color(color)
    if normalized is not None:
        return normalized
    return generate_random_tag_color()
