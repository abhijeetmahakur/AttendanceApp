"""QR attendance session helpers: generating a short, hard-to-guess session
code and rendering it as a QR code image (base64 data URI, safe to inline
directly into a template with no extra static file/route needed)."""

import base64
import io
import secrets

import qrcode

LECTURE_PERIODS = [f"Period {n}" for n in range(1, 9)]
DURATION_CHOICES_MINUTES = [1, 2, 3, 5, 10, 15, 20, 30]


def generate_code():
    """A short, URL-safe, hard-to-guess code identifying one QR attendance session."""
    return secrets.token_urlsafe(9)  # 12 chars, ~72 bits of entropy


def qr_image_data_uri(payload):
    """Renders `payload` (the session code) as a QR code PNG, returned as a
    data: URI so it can be embedded directly in an <img src="..."> with no
    file on disk and no extra route."""
    img = qrcode.make(payload, box_size=8, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"
