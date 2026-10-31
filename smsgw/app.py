"""PurvSMS - simulated state SMS gateway with live Twilio forwarding.

Stands in for the telecom SMS provider. Messages sent via the API appear on the
web console at / once "delivered", after a short carrier latency.
If Twilio credentials are configured, messages are simultaneously dispatched
to the real phone number over SMS.
"""

import os
import random
import time
import urllib.request
import urllib.parse
import urllib.error
import base64
import logging
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# Optional Twilio Integration
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "").strip()
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "").strip()
TWILIO_FROM_NUMBER = os.environ.get("TWILIO_FROM_NUMBER", "").strip()
DEFAULT_COUNTRY_CODE = os.environ.get("DEFAULT_COUNTRY_CODE", "+91").strip()


def _send_twilio_sms(to_number: str, message_body: str):
    """Dispatch real SMS to destination number via Twilio REST API."""
    if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_FROM_NUMBER):
        return None

    # Format destination number to E.164
    to_formatted = to_number.strip()
    if not to_formatted.startswith("+"):
        to_formatted = f"{DEFAULT_COUNTRY_CODE}{to_formatted}"

    url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"
    post_fields = {
        "To": to_formatted,
        "From": TWILIO_FROM_NUMBER,
        "Body": message_body,
    }
    encoded_data = urllib.parse.urlencode(post_fields).encode("utf-8")

    req = urllib.request.Request(url, data=encoded_data, method="POST")
    credentials = f"{TWILIO_ACCOUNT_SID}:{TWILIO_AUTH_TOKEN}"
    encoded_creds = base64.b64encode(credentials.encode("utf-8")).decode("ascii")
    req.add_header("Authorization", f"Basic {encoded_creds}")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            app.logger.info(f"Twilio SMS dispatched successfully to {to_formatted} (status: {resp.status})")
            return resp.status
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="ignore")
        app.logger.error(f"Failed to send Twilio SMS to {to_formatted}: HTTP {e.code} - {error_body}")
        return None
    except Exception as e:
        app.logger.error(f"Failed to send Twilio SMS to {to_formatted}: {e}")
        return None

MESSAGES = []  # {id, to, text, sent_at, delivery_at}

# Carrier queue latency, seconds.
DELAY_MIN = 1
DELAY_MAX = 4

CONSOLE = """
<!doctype html><html><head><title>PurvSMS Console</title>
<meta http-equiv="refresh" content="5">
<style>
body{font-family:Arial,sans-serif;margin:24px;background:#f4f4f4}
h2{color:#1a3c6e} table{border-collapse:collapse;background:#fff;width:100%}
td,th{border:1px solid #ccc;padding:6px 10px;font-size:14px;text-align:left}
.q{color:#b36b00}.d{color:#1b7e3c}
</style></head><body>
<h2>PurvSMS Gateway Console (simulation)</h2>
<p>Messages appear below once the carrier delivers them. Auto-refreshes every 5s.</p>
<table><tr><th>#</th><th>To</th><th>Message</th><th>Sent</th><th>Status</th></tr>
{% for m in messages %}
<tr><td>{{m.id}}</td><td>{{m.to}}</td>
<td>{% if m.delivered %}{{m.text}}{% else %}<i>(in transit)</i>{% endif %}</td>
<td>{{m.sent_hhmm}}</td>
<td>{% if m.delivered %}<span class="d">Delivered</span>
{% else %}<span class="q">Queued &middot; ~{{m.eta}}s</span>{% endif %}</td></tr>
{% endfor %}
</table></body></html>
"""


@app.route("/api/send", methods=["POST"])
def send():
    data = request.get_json(force=True, silent=True) or request.form
    to = data.get("to", "")
    text = data.get("text", "")
    if not to or not text:
        return jsonify({"status": "error", "reason": "to and text required"}), 400
    now = time.time()
    msg = {
        "id": len(MESSAGES) + 1,
        "to": to,
        "text": text,
        "sent_at": now,
        "delivery_at": now + random.randint(DELAY_MIN, DELAY_MAX),
    }
    MESSAGES.append(msg)

    # Forward to real mobile number if Twilio credentials are configured
    _send_twilio_sms(to, text)

    return jsonify({"status": "queued", "id": msg["id"]})


@app.route("/api/messages")
def messages():
    # Inbox query for a given number. Used to read delivered OTPs/SMS.
    to = request.args.get("to", "")
    now = time.time()
    out = []
    for m in MESSAGES:
        if to and m["to"] != to:
            continue
        out.append({
            "id": m["id"], "to": m["to"],
            "text": m["text"] if now >= m["delivery_at"] else None,
            "delivered": now >= m["delivery_at"],
            "sent_at": m["sent_at"], "delivery_at": m["delivery_at"],
        })
    return jsonify({"messages": out})


@app.route("/")
def console():
    now = time.time()
    view = []
    for m in reversed(MESSAGES[-100:]):
        view.append({
            "id": m["id"], "to": m["to"], "text": m["text"],
            "sent_hhmm": time.strftime("%H:%M:%S", time.localtime(m["sent_at"])),
            "delivered": now >= m["delivery_at"],
            "eta": max(0, int(m["delivery_at"] - now)),
        })
    return render_template_string(CONSOLE, messages=view)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8025)
