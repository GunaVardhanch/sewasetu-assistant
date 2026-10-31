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

- **Current Stage**: **Phase 4: Block Officer MCP Server Implementation**
- **In-Progress Task**:
  1. Implement all 5 Block Officer tools in `mcp_officer/server.py`:
     - `my_queue`: Retrieves pending applications for the officer's assigned block with SLA badges and risk flags.
     - `overdue_summary`: Highlights applications approaching or exceeding the 15-day deemed approval limit.
     - `view_case`: Loads the comprehensive case dossier for an application, including duplicate bank account warnings and seeded anomaly flags.
     - `approve_case`: Records an officer approval with named audit logging in portal.
     - `reject_case`: Records an officer rejection with mandatory justification and audit logging.
  2. Implement tests in `tests/test_phase4.py` verifying queue retrieval, SLA risk sorting, case dossier viewing with anomaly flags, idempotent decision making, and audit attribution.
  3. Run test suite, verify gates, commit `feat(phase-4): officer MCP server with case triage and decisions`.

---

## 3. Phase Completion Checklist

| Phase | Description | Status | Verification & Evidence |
|---|---|---|---|
| **Phase 0** | Handout Import & Baseline Setup | **COMPLETED** | Git commit `4afb38b`. All 4 baseline tests passed (`test_public_pages`, `test_admin_login`, `test_gateway_otp`, `test_full_web_application_submission`). Database seeded with 100k rows. |
| **Phase 1** | Portal Hardening & Internal API | **COMPLETED** | Git commit `2a3fb89`. All 7 Phase 1 tests passed (`test_scheme_info`, `test_eligibility_age_check`, `test_validation_parity_between_web_and_api`, `test_concurrency_parallel_submits`, `test_bi_directional_visibility`, `test_officer_decide_idempotence_and_audit`, `test_session_check_and_revocation`). |
| **Phase 2** | Shared Auth & MCP Skeletons | **COMPLETED** | Git commit `5dbca25`. All 8 Phase 2 tests passed (`test_gate1_unauthenticated_requests_return_401`, `test_gate2_rfc9728_protected_resource_metadata`, `test_gate3_citizen_oauth_flow_and_ping`, `test_gate4_officer_oauth_flow_and_ping`, `test_gate5_scope_isolation_citizen_cannot_access_officer`, `test_gate6_scope_isolation_officer_cannot_access_citizen`, `test_gate7_audience_mismatch_rejected`, `test_gate8_revoked_session_rejected`). |
| **Phase 3** | Citizen MCP Server | **COMPLETED** | Git commit `6cf03c5`. All 5 Phase 3 tests passed (`test_gate1_scheme_info`, `test_gate2_check_eligibility`, `test_gate3_save_details_and_bank_masking`, `test_gate4_document_upload_link`, `test_gate5_full_submission_and_lifecycle`). |
| **Phase 4** | Officer MCP Server | **IN PROGRESS** | Ready to implement 5 officer tools (my_queue, overdue_summary, view_case, approve_case, reject_case). |
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
6cf03c5 feat(phase-3): citizen MCP server with portal integration
f25fbc8 docs: update PROJECT_STATE for Phase 2 completion
5dbca25 feat(phase-2): shared auth, MCP skeletons, and RFC 9728 metadata
2a3fb89 feat(phase-1): portal hardening, concurrency advisory locks, and internal v1 API
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

