"""Locate bundled resources (logo / icons) and build icon images."""

from pathlib import Path

try:
    from PIL import Image
except ImportError:
    Image = None

_ROOT = Path(__file__).resolve().parent.parent
LOGO_PATH = _ROOT / "assets" / "logo.png"


def load_logo(size):
    """Return the logo as a square PIL image of `size` px, or None if unavailable."""
    if Image is None or not LOGO_PATH.exists():
        return None
    try:
        with Image.open(LOGO_PATH) as img:
            return img.convert("RGBA").resize((size, size), Image.LANCZOS)
    except OSError:
        return None
