"""Minimal WhatsApp messaging via the Twilio WhatsApp API.

Uses the standard library's urllib instead of the twilio SDK or requests,
so no extra dependency is needed for one HTTP call. If Twilio credentials
aren't configured, messages are logged instead of sent - the same graceful
fallback mailer.py uses for email - so every WhatsApp-driven feature
(absentee alerts, holiday/substitution notices) still works end-to-end in
a local/demo setup.

Important real-world constraint: Twilio's WhatsApp API (like Meta's own
WhatsApp Cloud API) only supports business-to-individual messages - there
is no official API to post into a native WhatsApp *group*. So "sending to
a group" here means: a group is a saved list of individual phone numbers
(see models.whatsapp_groups / whatsapp_group_members), and sending to it
loops through that list making one API call per member.
"""

import base64
import urllib.error
import urllib.parse
import urllib.request

from flask import current_app

TWILIO_API_URL = "https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"


def is_configured():
    cfg = current_app.config
    return bool(cfg.get("TWILIO_ACCOUNT_SID") and cfg.get("TWILIO_AUTH_TOKEN") and cfg.get("TWILIO_WHATSAPP_FROM"))


def _normalize(number):
    number = (number or "").strip()
    if not number:
        return None
    if not number.startswith("whatsapp:"):
        number = "whatsapp:" + number
    return number


def send_whatsapp_message(to_number, body):
    """Sends one WhatsApp message. Returns (ok: bool, detail: str).

    Never raises - a WhatsApp delivery failure shouldn't break the calling
    request (marking attendance, sending a notice, etc.)."""
    to = _normalize(to_number)
    if not to:
        return False, "No phone number provided."

    if not is_configured():
        current_app.logger.info("[WhatsApp not configured - logging instead] To %s: %s", to, body)
        return True, "WhatsApp is not configured; the message was logged instead of sent."

    cfg = current_app.config
    sid = cfg["TWILIO_ACCOUNT_SID"]
    token = cfg["TWILIO_AUTH_TOKEN"]
    from_number = _normalize(cfg["TWILIO_WHATSAPP_FROM"])

    url = TWILIO_API_URL.format(sid=sid)
    payload = urllib.parse.urlencode({"From": from_number, "To": to, "Body": body}).encode("utf-8")
    auth = base64.b64encode(f"{sid}:{token}".encode("utf-8")).decode("ascii")

    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Authorization", f"Basic {auth}")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()
        return True, "Sent."
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        current_app.logger.warning("WhatsApp send to %s failed (HTTP %s): %s", to, exc.code, detail)
        return False, f"Twilio rejected the message (HTTP {exc.code})."
    except Exception as exc:  # noqa: BLE001 - a WhatsApp failure shouldn't break the calling flow
        current_app.logger.warning("WhatsApp send to %s failed: %s", to, exc)
        return False, "Could not reach Twilio."


def send_group_message(members, body):
    """Sends `body` to every member of a WhatsApp group (a list of dict-like
    rows with a phone_number field). Returns (sent_count, failed, failures)
    where failures is a list of (phone_number, detail) tuples."""
    sent = 0
    failures = []
    for member in members:
        ok, detail = send_whatsapp_message(member["phone_number"], body)
        if ok:
            sent += 1
        else:
            failures.append((member["phone_number"], detail))
    return sent, len(failures), failures
