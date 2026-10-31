# -*- coding: utf-8 -*-
"""
Sewa Setu - Root WSGI Entrypoint for Cloud Deployments (Render, Gunicorn, Heroku)
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PORTAL_DIR = os.path.join(BASE_DIR, "portal")

if PORTAL_DIR not in sys.path:
    sys.path.insert(0, PORTAL_DIR)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from portal.app import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
