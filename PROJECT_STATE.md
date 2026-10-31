# Sewa Setu Assistant — Project Execution State Log

> **PERSISTENT STATE FILE**: Updated at each work stage. If a sudden power loss occurs, reading this file tells the assistant and user exactly where we stopped, what is running, and the next steps.

---

## 1. Quick Resume Protocol (On Power Return / "continue")

If the workstation just booted back up after a power cut:
1. Ensure WSL Ubuntu-22.04 Docker service is running:
   ```powershell
   wsl.exe -d Ubuntu-22.04 -- bash -c "sudo service docker status || sudo service docker start"
   ```
2. Check running docker containers:
   ```powershell
   wsl.exe -d Ubuntu-22.04 -- bash -c "sudo docker ps"
   ```
   If containers are down, bring them up with Docker Compose v2:
   ```powershell
   wsl.exe -d Ubuntu-22.04 -- bash -c "cd /mnt/c/Users/Administrator/SevaSethu/sewasetu-assistant && sudo ADMIN_PASSWORD=dev docker compose up -d"
   ```
3. Run the baseline verification test to confirm portal health:
   ```powershell
   cd C:\Users\Administrator\SevaSethu\sewasetu-assistant
   python -m pytest -v tests/test_baseline.py
   ```
4. Proceed directly to the **Current Work Item** outlined in Section 2 below.

---

## 2. Current Work Item

- **Current Stage**: **Phase 1: Portal Hardening & Internal API**
- **In-Progress Task**:
  1. Rebuild and restart the containerized stack using Docker Compose v2 with `./portal:/app` live mount and environment variables (`INTERNAL_API_KEY`, `SCHEME_DEADLINE`, `AGENT_ENABLED_BLOCKS`).
  2. Complete `tests/test_phase1.py` covering all Phase 1 verification gates:
     - Validation parity (web form vs internal API reject identical bad data with same text)
     - Concurrency advisory locking (two parallel submits for 1 mobile produce exactly 1 row)
     - Bi-directional visibility (API application visible at `/status` & `/admin`; web application returned by `/internal/v1/citizen/status`)
     - Officer decision idempotence (decide on non-PENDING row writes no audit and returns already decided)
     - Session check failure when grants are revoked
  3. Run `pytest -v tests/test_phase1.py` and commit: `feat(phase-1): portal hardening and internal v1 API`.

---

## 3. Phase Completion Checklist

| Phase | Description | Status | Verification & Evidence |
|---|---|---|---|
| **Phase 0** | Handout Import & Baseline Setup | **COMPLETED** | Git commit `4afb38b`. All 4 baseline tests passed (`test_public_pages`, `test_admin_login`, `test_gateway_otp`, `test_full_web_application_submission`). Database seeded with 100k rows. |
| **Phase 1** | Portal Hardening & Internal API | **IN PROGRESS** | Code complete in `portal/agent_api.py`, `portal/migrations/003_agent.sql`, `portal/app.py`, `portal/templates/agent_upload.html`. Docker Compose v2 integration in progress. |
| **Phase 2** | Shared Auth & MCP Skeletons | PENDING | To implement `common/auth.py`, RFC 9728 metadata, RFC 8707 audience checks, `evals/oauth_login.py`. |
| **Phase 3** | Citizen MCP Server | PENDING | To implement `mcp_citizen/server.py` with 8 core tools, bank masking, turn-capped compact replies. |
| **Phase 4** | Officer MCP Server | PENDING | To implement `mcp_officer/server.py` with queue triage, dossier view with flags, named decisions. |
| **Phase 5** | Personas & Evals Suite | PENDING | 12 Citizen personas (C1-C12) & 6 Officer personas (O1-O6) in `evals/`. |
| **Phase 6** | Public Eval Dashboard | PENDING | Static/JSON dashboard at `/eval-dashboard` with transcripts, checks, and before/after fixes. |
| **Phase 7** | Deployment & HTTPS | PENDING | Caddy reverse proxy, TLS, live VM deployment. |
| **Phase 8** | Design Note & Loom Script | PENDING | 1-page `DESIGN.md` finalization and 3-minute video recording script. |

---

## 4. Key Architectural Decisions (Active)

- **D1 (Deadline)**: Scheme window extended via `SCHEME_DEADLINE=2026-12-31 23:59` override to prevent automatic shutoff after 23:59 tonight (31 Oct 2026).
- **D2 (Blocks)**: `AGENT_ENABLED_BLOCKS` configurable via env (defaulting to all 6 blocks: Sonari, Rajapara, Dhemaji Pathar, Borgaon, Namti, Khelua).
- **D3 (Document Upload)**: Single-use 30-minute tokenized upload link (`/upload/<token>`) with magic byte verification (PDF/PNG/JPEG) instead of multi-megabyte base64 chat payloads.
- **D4 (Internal API)**: Token-free internal REST API (`/internal/v1/*`) secured by `X-Internal-Service-Key` over the private Docker bridge network.
- **D5 (Duplicate Bank Accounts)**: Flagged for officer review in case dossier; not hard-blocked at submission.
- **D6 (Seed Anomalies)**: Preserved historically, flagged dynamically in officer dossier view.

---

## 5. Git Commit Log

```
4afb38b feat(phase-0): setup sewasetu-assistant baseline with docker-compose and baseline tests
65cc901 chore: import handout
```

---

## 6. Services & Ports Map

| Service | Internal Address | Host Mapping | Role |
|---|---|---|---|
| `app` | `app:8000` | `localhost:8000` | Flask portal + OAuth 2.1 AS + `/internal/v1/*` |
| `db` | `db:5432` | Internal only | PostgreSQL 15 with `sewasetu` database (100k rows seeded) |
| `smsgw` | `smsgw:8025` | Internal only (`/__gateway/` proxied) | Telecom carrier simulation with 1-4s delivery latency |
| `scheduler` | internal | Internal only | Nightly RTPS deemed-approval cron job |

