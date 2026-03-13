#!/usr/bin/env python3
"""Generate simulated document images for manual testing (ignored by git)."""

from pathlib import Path
from datetime import datetime

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError as exc:
    raise SystemExit(
        "Pillow is required to generate test assets. "
        "Install with: pip install Pillow"
    ) from exc


ASSETS_DIR = Path(__file__).parent / "manual_assets"


def _draw_header(draw: ImageDraw.ImageDraw, text: str) -> None:
    draw.rectangle([0, 0, 900, 70], fill="#f0f0f0")
    draw.text((20, 20), text, fill="#111111")


def generate_aadhaar_mock() -> Path:
    """Create a simulated Aadhaar-like card image (non-real)."""
    img = Image.new("RGB", (900, 600), color="white")
    draw = ImageDraw.Draw(img)

    _draw_header(draw, "SIMULATED AADHAAR (NON-REAL) | UIDAI")

    lines = [
        "Name: RAVI KUMAR",
        "DOB: 15/05/1995",
        "Gender: Male",
        "Address: 221 Mock Street, Bengaluru, KA 560034",
        "Aadhaar: 9999 8888 7777",
    ]

    y = 120
    for line in lines:
        draw.text((40, y), line, fill="#222222")
        y += 50

    file_path = ASSETS_DIR / "simulated_aadhaar.png"
    img.save(file_path)
    return file_path


def generate_passport_mock() -> Path:
    """Create a simulated passport-like card image (non-real)."""
    img = Image.new("RGB", (900, 600), color="white")
    draw = ImageDraw.Draw(img)

    _draw_header(draw, "SIMULATED PASSPORT (NON-REAL)")

    lines = [
        "Name: AVA WILSON",
        "DOB: 03/11/1992",
        "Gender: Female",
        "Nationality: IN",
        "Passport No: P1234567",
    ]

    y = 120
    for line in lines:
        draw.text((40, y), line, fill="#222222")
        y += 50

    file_path = ASSETS_DIR / "simulated_passport.png"
    img.save(file_path)
    return file_path


def main() -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    aadhaar_path = generate_aadhaar_mock()
    passport_path = generate_passport_mock()

    print("Generated simulated assets:")
    print(f"- {aadhaar_path}")
    print(f"- {passport_path}")
    print(f"Timestamp: {datetime.now().isoformat()}")


if __name__ == "__main__":
    main()
