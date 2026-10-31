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
3. Run baseline verification test to confirm portal health:
   ```powershell
   cd C:\Users\Administrator\SevaSethu\sewasetu-assistant
   python -m pytest -v tests/test_baseline.py
   ```
4. Proceed directly to the **Current Work Item** outlined in Section 2 below.

---

## 2. Current Work Item

- **Current Stage**: **Phase 8: Design Note (DESIGN.md) & 3-Minute Loom Video Script**
- **In-Progress Task**:
  1. Author the 1-page `DESIGN.md` addressing:
     - The three decisions that mattered most (D1, D3, D4 / Invariants 1–5).
     - The one decision we would make differently with more time (e.g. streaming LLM tool calling vs synchronous JSON-RPC turn cycles).
     - Architectural diagrams and system boundaries.
  2. Write the 3-minute Loom video recording script (face and screen walkthrough):
     - Hook & director briefing context.
     - Architecture & MCP endpoints walkthrough (`/mcp/citizen` & `/mcp/officer`).
     - Evals demo & `/eval-dashboard` walkthrough with live 18 personas.
     - Database invariants & what the evals taught us.
  3. Push all commits to the remote GitHub repository: `https://github.com/GunaVardhanch/sewasetu-assistant.git`.
  4. Ensure assessor `harshnisar` is invited read-only on GitHub.

---

## 3. Phase Completion Checklist

| Phase | Description | Status | Verification & Evidence |
|---|---|---|---|
| **Phase 0** | Handout Import & Baseline Setup | **COMPLETED** | Git commit `4afb38b`. All 4 baseline tests passed (`test_public_pages`, `test_admin_login`, `test_gateway_otp`, `test_full_web_application_submission`). Database seeded with 100k rows. |
| **Phase 1** | Portal Hardening & Internal API | **COMPLETED** | Git commit `2a3fb89`. All 7 Phase 1 tests passed (`test_scheme_info`, `test_eligibility_age_check`, `test_validation_parity_between_web_and_api`, `test_concurrency_parallel_submits`, `test_bi_directional_visibility`, `test_officer_decide_idempotence_and_audit`, `test_session_check_and_revocation`). |
| **Phase 2** | Shared Auth & MCP Skeletons | **COMPLETED** | Git commit `5dbca25`. All 8 Phase 2 tests passed (`test_gate1_unauthenticated_requests_return_401`, `test_gate2_rfc9728_protected_resource_metadata`, `test_gate3_citizen_oauth_flow_and_ping`, `test_gate4_officer_oauth_flow_and_ping`, `test_gate5_scope_isolation_citizen_cannot_access_officer`, `test_gate6_scope_isolation_officer_cannot_access_citizen`, `test_gate7_audience_mismatch_rejected`, `test_gate8_revoked_session_rejected`). |
| **Phase 3** | Citizen MCP Server | **COMPLETED** | Git commit `6cf03c5`. All 5 Phase 3 tests passed (`test_gate1_scheme_info`, `test_gate2_check_eligibility`, `test_gate3_save_details_and_bank_masking`, `test_gate4_document_upload_link`, `test_gate5_full_submission_and_lifecycle`). |
| **Phase 4** | Officer MCP Server | **COMPLETED** | Git commit `e60cb0b`. All 5 Phase 4 tests passed (`test_gate1_officer_my_queue`, `test_gate2_officer_overdue_summary`, `test_gate3_officer_view_case_with_flags`, `test_gate4_officer_approve_case`, `test_gate5_officer_reject_case_requires_reason`). |
| **Phase 5** | Personas & Evals Suite | **COMPLETED** | Git commit `4bfb5e0`. 18 Personas (C1–C12, O1–O6) passed 100% in `tests/test_phase5.py` with multi-turn conversations and PostgreSQL applications & audit_log verification. |
| **Phase 6** | Public Eval Dashboard | **COMPLETED** | Git commit `b5c3c8b`. All 2 Phase 6 tests passed (`test_eval_dashboard_html_page`, `test_eval_dashboard_json_api`). Public `/eval-dashboard` and `/eval-dashboard/data` live. |
| **Phase 7** | Deployment & HTTPS | **COMPLETED** | Git commit pending. `docker-compose.prod.yml`, `Caddyfile`, `Dockerfile.mcp`, all 3 tests in `tests/test_phase7.py` passed. |
| **Phase 8** | Design Note & Loom Script | **IN PROGRESS** | 1-page `DESIGN.md` finalization, 3-minute Loom video recording script, GitHub push. |

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
19be4bb docs: update PROJECT_STATE for Phase 5 & 6 completion
b5c3c8b feat(phase-6): public eval dashboard with transcripts and database verification
4bfb5e0 feat(phase-5): 18 persona evals suite with automated database verification
632fa21 docs: update PROJECT_STATE for Phase 4 completion
e60cb0b feat(phase-4): officer MCP server with case triage and decisions
3892430 docs: update PROJECT_STATE for Phase 3 completion
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
| `app` | `app:8000` | `localhost:8000` | Flask portal + OAuth 2.1 AS + `/internal/v1/*` + `/eval-dashboard` |
| `db` | `db:5432` | Internal only | PostgreSQL 15 with `sewasetu` database (100k rows seeded) |
| `smsgw` | `smsgw:8025` | Internal only (`/__gateway/` proxied) | Telecom carrier simulation with 1-4s delivery latency |
| `scheduler` | internal | Internal only | Nightly RTPS deemed-approval cron job |
| `mcp-citizen` | `mcp-citizen:8001` | `localhost:8001` | Citizen MCP Server (/mcp/citizen, scope: citizen) |
| `mcp-officer` | `mcp-officer:8002` | `localhost:8002` | Officer MCP Server (/mcp/officer, scope: officer) |
| `caddy` | `caddy:80/443` | `80/443` | Reverse proxy routing citizen, officer, and portal paths under HTTPS |
