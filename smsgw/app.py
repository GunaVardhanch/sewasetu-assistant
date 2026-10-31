"""PurvSMS - state simulated SMS gateway.

Stands in for the telecom SMS provider. Messages sent via the API appear on the
web console at / once "delivered", after a short simulated carrier latency.
"""

import random
import time
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)

MESSAGES = []  # {id, to, text, sent_at, delivery_at}

# Carrier queue latency, seconds.
DELAY_MIN = 0
DELAY_MAX = 2

CONSOLE = """
<!doctype html><html><head><title>PurvSMS Console</title>
<meta http-equiv="refresh" content="3">
<style>
body{font-family:Arial,sans-serif;margin:24px;background:#f4f4f4}
h2{color:#1a3c6e} table{border-collapse:collapse;background:#fff;width:100%}
td,th{border:1px solid #ccc;padding:8px 12px;font-size:14px;text-align:left}
.q{color:#b36b00;font-weight:bold}.d{color:#1b7e3c;font-weight:bold}
.code-box{background:#e8f0fe;color:#1a3c6e;font-size:16px;font-weight:bold;padding:2px 8px;border-radius:4px;display:inline-block;}
</style></head><body>
<h2>PurvSMS Gateway Console (Virtual Telecom)</h2>
<p>Incoming citizen OTPs and SMS notifications appear below. Auto-refreshes every 3s.</p>
<table><tr><th>#</th><th>Mobile</th><th>Message &amp; OTP Code</th><th>Sent Time</th><th>Carrier Status</th></tr>
{% for m in messages %}
<tr><td>{{m.id}}</td><td><b>{{m.to}}</b></td>
<td>{% if m.delivered %}<span class="code-box">{{m.text}}</span>{% else %}<i>(transmitting...)</i>{% endif %}</td>
<td>{{m.sent_hhmm}}</td>
<td>{% if m.delivered %}<span class="d">&#10003; Delivered</span>
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
