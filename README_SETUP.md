# Sewa Setu Assistant — Home Setup & Continuity Guide

This document is your complete, step-by-step continuity guide to seamlessly set up and continue developing the **Sewa Setu Assistant** project on your home machine using **Google Antigravity** (or standard CLI).

---

## 1. Quick Continuity Summary (Where We Left Off)

- **All 8 Core Phases are 100% Implemented & Passing:**
  - **Phase 0:** Baseline portal & seed database (100k rows).
  - **Phase 1:** Portal hardening, concurrency advisory locks, and `/internal/v1/*` private REST API.
  - **Phase 2:** Shared OAuth 2.1 auth, RFC 8707 audience checks, RFC 9728 metadata, and token validation.
  - **Phase 3:** Citizen MCP Server (`/mcp/citizen`, scope `citizen`, 8 tools).
  - **Phase 4:** Block Officer MCP Server (`/mcp/officer`, scope `officer`, 5 tools).
  - **Phase 5:** 18 Persona Multi-Turn Evals Suite (C1–C12, O1–O6) with 100% pass rate.
  - **Phase 6:** Public `/eval-dashboard` with live JSON telemetry and inspection transcripts.
  - **Phase 7:** Production deployment (`docker-compose.prod.yml`, `Caddyfile`, `Dockerfile.mcp`).
  - **Phase 8:** 1-Page `DESIGN.md` and 3-Minute Loom Video Script (`LOOM_SCRIPT.md`).
- **Remaining Final Tasks for Submission:**
  1. Push Git history to GitHub remote: `https://github.com/GunaVardhanch/sewasetu-assistant.git`
  2. Confirm assessor `harshnisar` is invited read-only to the repository.
  3. Record the 3-minute Loom walkthrough using `LOOM_SCRIPT.md`.

---

## 2. System Prerequisites on Home Machine

- **Operating System:** Windows (with WSL2), macOS, or Linux.
- **Python:** Python 3.11, 3.12, or 3.13.
- **Docker:** Docker Desktop or Docker Engine with Docker Compose v2.
- **Git:** Git installed.
- **AI Assistant:** Google Antigravity.

---

## 3. Fast-Track Setup (3 Easy Steps)

### Step 1: Open the Project Directory
Extract or open the project folder in your terminal or Antigravity:
```bash
cd sewasetu-assistant
```

### Step 2: Create Python Virtual Environment & Install Dependencies
```bash
# Create venv
python -m venv venv

# Activate venv
# On Windows PowerShell:
.\venv\Scripts\Activate.ps1
# On macOS / Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Step 3: Launch Docker Services (Portal + DB + SMS Gateway)
The Docker stack spins up PostgreSQL 15 (auto-seeded with 100k records from `seed/seed.sql`), SMS Gateway on port 8025, and Portal App on port 8000:
```bash
ADMIN_PASSWORD=dev docker compose up -d
```
*(On Windows WSL2, run `sudo ADMIN_PASSWORD=dev docker compose up -d`)*.

Wait ~10 seconds for PostgreSQL and the portal application to initialize.

---

## 4. Verify Services Health

### 1. Web Portal
Open your browser to:
- **Portal Homepage:** `http://localhost:8000`
- **Eval Dashboard:** `http://localhost:8000/eval-dashboard`
- **SMS Gateway Log:** `http://localhost:8000/__gateway/`
- **Officer Login:** `http://localhost:8000/login` (Username: `admin`, Password: `dev`)

### 2. Run Baseline and Integration Tests
Run pytest from the project root:
```bash
# 1. Baseline portal tests
pytest -v tests/test_baseline.py

# 2. Portal hardening & internal API
pytest -v tests/test_phase1.py

# 3. Auth & RFC 9728 metadata
pytest -v tests/test_phase2.py

# 4. Citizen MCP Server tools
pytest -v tests/test_phase3.py

# 5. Officer MCP Server tools
pytest -v tests/test_phase4.py

# 6. Eval dashboard UI and JSON API
pytest -v tests/test_phase6.py

# 7. Production Caddy & Compose configs
pytest -v tests/test_phase7.py
```

### 3. Run Persona Evals Suite (C1–C12, O1–O6)
Run all 18 multi-turn automated personas:
```bash
pytest -v tests/test_phase5.py
```
*(Expect 18 passed in ~3 minutes with direct database audit log verification).*

---

## 5. Running the Dual MCP Servers

If running standalone or for manual Claude / Inspector testing:

### Citizen MCP Server (`/mcp/citizen`)
```bash
python -m mcp_citizen.server
```
- Endpoint: `http://localhost:8001/mcp/citizen`
- Required JWT Scope: `citizen`

### Officer MCP Server (`/mcp/officer`)
```bash
python -m mcp_officer.server
```
- Endpoint: `http://localhost:8002/mcp/officer`
- Required JWT Scope: `officer`

---

## 6. Prompting Antigravity on Your Home System

When you open Antigravity on your home computer, simply paste this prompt into the chat:

```text
Hello Antigravity! I have continued this project from my lab workstation.
Please review PROJECT_STATE.md and README_SETUP.md.
1. Check that Docker compose services (portal, db, smsgw) are running healthy.
2. Run baseline and phase tests to verify system integrity.
3. Review the current git log and help me push master to https://github.com/GunaVardhanch/sewasetu-assistant.git.
4. Walk me through recording the Loom video according to LOOM_SCRIPT.md.
```

Antigravity will instantly read `PROJECT_STATE.md`, understand the exact state of every phase, and proceed smoothly without losing any context!

---

## 7. Submission Checklist

- [x] Portal is sole system of record (`/internal/v1/*` REST API)
- [x] Dual MCP servers with streamable HTTP, audience validation, and RFC 9728 metadata
- [x] 18 Persona evals (12 citizen, 6 officer) passing 100%
- [x] Public `/eval-dashboard` displaying multi-turn transcripts & DB verification
- [x] Production Caddy reverse proxy with SSE chunk flushing (`flush_interval -1`)
- [x] 1-page `DESIGN.md` addressing three key decisions and one alternative
- [x] Timed 3-minute video recording script in `LOOM_SCRIPT.md`
- [ ] Push full un-squashed commit history to GitHub:
  ```bash
  git push -u origin master
  ```
- [ ] Invite assessor `harshnisar` as read-only collaborator on GitHub.
- [ ] Record and submit the 3-minute Loom video.
