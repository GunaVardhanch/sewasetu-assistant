# Sewa Setu Assistant — Design & Architecture Notes

## Architectural Overview

`sewasetu-assistant` exposes two distinct Model Context Protocol (MCP) servers over streamable HTTP on top of the Government of Purvanchal's Sewa Setu Old Age Pension Portal:
1. **Citizen MCP (`/mcp/citizen`)**: Scope `citizen`, resource indicator `https://<host>/mcp/citizen`. Enables citizens or family members to check eligibility, save drafts, obtain document upload links, submit applications, check status, and withdraw pending applications.
2. **Officer MCP (`/mcp/officer`)**: Scope `officer`, resource indicator `https://<host>/mcp/officer`. Enables block officers to triage their block's pending queue, view individual case dossiers with automated verification flags and audit logs, and record named approve/reject decisions.

The portal remains the sole system of record. MCP servers never access the database directly; all operations execute through an authenticated internal REST API (`/internal/v1/*`) secured by a service key on the internal Docker network.

```
                     https://<host>  (Caddy, auto-TLS)
 ┌───────────────────────┬───────────────────────────┬────────────────────────┐
 /  /status /admin       /mcp/citizen                /mcp/officer              /eval-dashboard
 /oauth/* /.well-known/* /.well-known/oauth-          /.well-known/oauth-       (static + JSON)
 /__gateway/*            protected-resource/mcp/…     protected-resource/mcp/…
        │                       │                          │
   portal (Flask)         mcp-citizen                mcp-officer          evals-dashboard
        ▲                       │ internal REST            │ internal REST
        └───────────────────────┴──────────────────────────┘
                     /internal/v1/*  (docker network, service key)
        │
   Postgres  ←  scheduler (cron)        smsgw (OTP inbox)
```

## Key Decisions

| ID | Topic | Decision & Rationale |
|---|---|---|
| **D1** | **Scheme Deadline** | The baseline `app.ini` closes the application window at `2026-10-31 23:59`. We introduce an environment override `SCHEME_DEADLINE` (defaulting to `2026-12-31 23:59` in deployment) so that the portal remains operational past midnight, updating homepage copy dynamically. |
| **D2** | **Block Scope** | The Director's phrase "subset of blocks" is addressed by implementing `AGENT_ENABLED_BLOCKS` (defaulting to all 6 blocks: Sonari, Rajapara, Dhemaji Pathar, Borgaon, Namti, Khelua) configurable via environment variables without altering codebase logic. |
| **D3** | **Document Uploads** | Directly uploading binary documents or multi-megabyte base64 strings through chat exhausts LLM context windows and fails on weak mobile connections. Instead, `get_document_upload_link` creates a single-use, 30-minute tokenized upload link (`/upload/<token>`) allowing the applicant to upload JPG/PNG/PDF photos from mobile browsers. `submit_application` validates that an age proof document is attached. |
| **D4** | **Internal Portal API** | MCP servers communicate with the portal via internal REST endpoints (`/internal/v1/*`) accessible only across the internal Docker bridge network with `X-Internal-Service-Key`. The verified token `sub` is transmitted in request headers; token credentials are never forwarded. |
| **D5** | **Duplicate Bank Accounts** | Many rural families share bank accounts. Rather than hard-blocking duplicate bank accounts at submission, the system flags shared bank accounts in the officer's case dossier for human scrutiny. |
| **D6** | **Historical Seed Anomalies** | Historical seed data contains underage approvals, empty document paths, and non-conforming IFSC codes. We preserve data integrity by never mutating historical records; instead, anomalous conditions are surfaced as informational review flags in `view_case`. |

## Invariants & Compliance Rules

1. **Single Source of Validation**: All submissions pass through `validate_application()` and `create_application()`. No duplicate business logic.
2. **Subject Identity via Token Only**: No MCP tool accepts user phone numbers, citizen IDs, or officer usernames as arguments. Identity is derived strictly from the cryptographically verified JWT `sub`.
3. **Strict Audience & Scope Isolation**: Citizen tools cannot be reached with officer tokens or portal tokens, and vice-versa. Strict RFC 8707 audience checks enforce canonical server URLs.
4. **Session Termination**: Instant session revocation supported through live token checks against `oauth_refresh_tokens` and `oauth_program_tokens`.
5. **No Hallucinated Data**: Tools return explicit missing fields and actionable error messages, never default guesses.
