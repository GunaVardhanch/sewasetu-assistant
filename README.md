# Sewa Setu Assistant (सेवा सेतु सहायक)

> **Dual Model Context Protocol (MCP) Servers over Streamable HTTP on top of the Government of Purvanchal's Sewa Setu Old Age Pension Portal.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![MCP Spec 1.0](https://img.shields.io/badge/MCP-Streamable%20HTTP-green.svg)](https://modelcontextprotocol.io/)
[![Persona Evals](https://img.shields.io/badge/Evals-18%2F18%20Passed%20(100%25)-brightgreen.svg)](#persona-evals-suite)
[![License: Proprietary](https://img.shields.io/badge/purvanchal.gov.in-internal-orange.svg)](#)

---

## 🏛️ Project Architecture

```
                    ┌───────────────────────────────┐
                    │    Caddy TLS Reverse Proxy    │
                    │        (Port 80 / 443)        │
                    └───────────────┬───────────────┘
                                    │
         ┌──────────────────────────┼──────────────────────────┐
         │                          │                          │
         ▼                          ▼                          ▼
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│   Citizen MCP   │       │   Officer MCP   │       │   Portal App    │
│  /mcp/citizen   │       │  /mcp/officer   │       │  Flask + OAuth  │
│ (Port 8001)     │       │ (Port 8002)     │       │ (Port 8000)     │
│ Scope: citizen  │       │ Scope: officer  │       │ System of Record│
└────────┬────────┘       └────────┬────────┘       └────────┬────────┘
         │                         │                         │
         └─────────────┬───────────┘                         │
                       │ X-Internal-Service-Key              │
                       ▼                                     │
           ┌───────────────────────┐                         │
           │  Portal Private API   │                         │
           │    /internal/v1/*     │◄────────────────────────┘
           └───────────┬───────────┘
                       │ Postgres Pool & Advisory Locks
                       ▼
           ┌───────────────────────┐
           │ PostgreSQL 15 (100k)  │
           └───────────────────────┘
```

---

## 🚀 Key Deliverables

1. **Dual MCP Servers over Streamable HTTP:**
   - **Citizen MCP Server (`/mcp/citizen`)**: Scope `citizen`, audience `sewasetu-portal`. 8 tools covering scheme info, eligibility checking, draft autosave, tokenized upload links, submission, withdrawal, and session sign-out.
   - **Officer MCP Server (`/mcp/officer`)**: Scope `officer`, audience `sewasetu-portal`. 5 tools covering queue triage, overdue RTPS alerts, multi-faceted case dossiers with seed anomaly flags, and decisions (approval and reasoned rejection).
2. **Hardened Portal & System-of-Record API:**
   - Database writes are strictly confined to the portal application via private `/internal/v1/*` REST API.
   - Zero business rule duplication: all submissions and validations reuse `validate_application()` and `create_application()`.
   - Transactional advisory locks (`pg_advisory_xact_lock`) guarantee concurrency safety.
3. **Persona Evals Suite (C1–C12, O1–O6):**
   - 18 automated personas testing real-world multi-turn conversational edge cases (rural dialects, incomplete data, invalid age, bank masking, duplicate submissions, queue triage, RTPS SLA violations, reason validation).
   - Automated post-execution verification inspecting PostgreSQL `applications`, `audit_log`, and `agent_drafts`.
   - **Pass rate: 18 / 18 passed (100%)**.
4. **Public Eval Dashboard (`/eval-dashboard`):**
   - Live dashboard rendering aggregate metrics, persona cards, full multi-turn conversational transcripts, and database verification status.
   - Live JSON telemetry endpoint at `/eval-dashboard/data`.
5. **Production Deployment (`docker-compose.prod.yml`, `Caddyfile`):**
   - Caddy reverse proxy with `flush_interval -1` ensuring SSE streaming chunks are never buffered.
6. **Design Note & Video Script:**
   - [`DESIGN.md`](./DESIGN.md): The three decisions that mattered most (D1, D3, D5) and the one decision we'd make differently with more time.
   - [`LOOM_SCRIPT.md`](./LOOM_SCRIPT.md): Timed 3-minute video recording script covering the required 4 pillars.
   - [`README_SETUP.md`](./README_SETUP.md): Step-by-step continuity guide for home machine setup.

---

## 🛠️ Quick Start

### 1. Requirements
- Docker & Docker Compose v2
- Python 3.11+
- Git

### 2. Launch Services
```bash
# Clone or enter directory
cd sewasetu-assistant

# Start Docker containers (Portal, DB with 100k seed, SMS Gateway)
ADMIN_PASSWORD=dev docker compose up -d
```

### 3. Install Python Dependencies
```bash
pip install -r requirements.txt
```

### 4. Run the Full Test Suite
```bash
# Run baseline tests
pytest -v tests/test_baseline.py

# Run all phase verification gates
pytest -v tests/test_phase1.py tests/test_phase2.py tests/test_phase3.py tests/test_phase4.py tests/test_phase6.py tests/test_phase7.py

# Run all 18 Persona Multi-Turn Evals
pytest -v tests/test_phase5.py
```

### 5. Start MCP Servers
```bash
# Citizen MCP Server
python -m mcp_citizen.server

# Officer MCP Server
python -m mcp_officer.server
```

---

## 📊 Endpoints & Dashboards

- **Web Portal**: [http://localhost:8000](http://localhost:8000)
- **Public Eval Dashboard**: [http://localhost:8000/eval-dashboard](http://localhost:8000/eval-dashboard)
- **SMS Gateway Dashboard**: [http://localhost:8000/__gateway/](http://localhost:8000/__gateway/)
- **Citizen MCP Stream**: `http://localhost:8001/mcp/citizen`
- **Officer MCP Stream**: `http://localhost:8002/mcp/officer`

---

## 📚 Documentation Links
- [Home Continuity & Setup Guide](README_SETUP.md)
- [Design Decisions (1-Page Note)](DESIGN.md)
- [3-Minute Loom Video Script](LOOM_SCRIPT.md)
- [Project State Execution Log](PROJECT_STATE.md)
- [Handout Specification](BRIEF.md)
