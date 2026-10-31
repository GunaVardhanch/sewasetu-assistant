# Sewa Setu Assistant — System Design & Architecture Note

## 1. Architectural Overview & System Topology

`sewasetu-assistant` implements two distinct, cryptographically isolated Model Context Protocol (MCP) servers operating over Streamable HTTP on top of the Government of Purvanchal's Sewa Setu Old Age Pension Portal:

1. **Citizen MCP (`/mcp/citizen`)**: Scope `citizen`, resource indicator `https://<host>/mcp/citizen`. Serves applicants and family members with tools to check age eligibility, save draft progress, receive secure upload links, submit applications, track status, and withdraw pending cases.
2. **Officer MCP (`/mcp/officer`)**: Scope `officer`, resource indicator `https://<host>/mcp/officer`. Serves Block Development Officers (e.g. Sonari) to triage pending queues sorted by SLA urgency, inspect comprehensive case dossiers with automated anomaly flags, and record named decisions with mandatory justification.

```
                     https://<host>  (Caddy Reverse Proxy & TLS)
 ┌───────────────────────┬───────────────────────────┬────────────────────────┐
 │ /  /status /admin     │ /mcp/citizen              │ /mcp/officer           │ /eval-dashboard
 │ /oauth/*              │ /.well-known/oauth-       │ /.well-known/oauth-    │ (interactive HTML
 │ /__gateway/*          │   protected-resource/mcp/…│   protected-resource/… │  + JSON telemetry)
 └───────────┬───────────┴─────────────┬─────────────┴───────────┬────────────┘
             │                         │                         │
     portal (Flask :8000)      mcp-citizen (:8001)       mcp-officer (:8002)
             ▲                         │                         │
             │ internal REST API       │ internal REST API       │
             └─────────────────────────┴─────────────────────────┘
                   /internal/v1/* (Docker bridge, X-Internal-Service-Key)
             │
      PostgreSQL 15  ←  scheduler (cron SLA)        smsgw (:8025 OTP carrier)
```

---

## 2. The Three Decisions That Mattered Most

### Decision 1: Single System of Record & Strict Internal API Boundary (D4 & Invariant 1)
* **Context**: The portal was already a live, production system holding 100k seeded applications with intricate validation constraints, database triggers, and a nightly deemed-approval cron job.
* **Choice**: We strictly prohibited MCP servers from connecting directly to PostgreSQL. Instead, all mutations and queries route through an internal REST API (`/internal/v1/*`) secured by mutual service keys over the private Docker network. Every submission must pass through `portal.validate_application()` and `portal.create_application()`.
* **Impact**: Zero rule divergence between web portal and AI channels. High-concurrency race conditions were eliminated by wrapping submissions in PostgreSQL transaction-level advisory locks (`pg_advisory_xact_lock`), and audit trails remained strictly immutable and attributed.

### Decision 2: Out-of-Band Tokenized Document Uploads (D3)
* **Context**: Scheme guidelines require age proof documents (Aadhaar, Voter ID, PAN). Passing multi-megabyte binary PDFs or base64 blobs through multi-turn LLM chat calls routinely blows past token limits and fails on fragile rural 2G/3G connectivity.
* **Choice**: We designed an out-of-band upload link flow (`get_document_upload_link`). The tool generates a single-use, 30-minute tokenized upload URL (`/upload/<token>`). The citizen or kiosk operator uploads photos directly from their phone camera or desktop browser. The portal validates binary magic bytes (`%PDF-`, `\x89PNG`, `\xff\xd8\xff`) on disk before linking the document to the applicant's draft.
* **Impact**: Tool calls remain ultra-lightweight (<200 tokens), small models never hallucinate binary payloads, and document files are validated using actual file signatures rather than spoofable MIME types.

### Decision 3: Tolerant Ingestion with Flagged Human Adjudication (D5 & D6)
* **Context**: In rural Assam/Purvanchal, elderly couples frequently share a single Grameen bank passbook, and older citizens commonly provide colloquial marital statuses ("Widow" instead of "Widowed", "Single" instead of "Unmarried").
* **Choice**: Hard-rejecting shared bank accounts or un-normalized strings would immediately disenfranchise genuine, illiterate rural seniors. We implemented transparent normalization in portal validation and adopted Decision D5: allow applications with duplicate bank accounts to be submitted cleanly, while dynamically computing and surfacing a `SHARED_BANK_ACCOUNT` review flag in the Block Officer's dossier view (`view_case`).
* **Impact**: Citizens are never stranded by confusing validation rejections, while block officers receive explicit, automated warnings highlighting potential duplicate disbursements before approving cases.

---

## 3. The One Decision We Would Make Differently With More Time

### Context-Dependent Hierarchical Tool Subsetting
* **The Current Implementation**: The Citizen MCP server exposes all 8 tools simultaneously in `tools/list`. Small models are guided using concise, directional `next_step` prompts returned by each tool.
* **What We Would Do Differently**: While small models (Claude Code, Flash Lite) navigate this reliably, presenting all 8 tools at all times still consumes tool schema tokens and leaves minor room for a model to invoke `submit_application` prematurely before even asking the citizen for address or bank details.
* **The Better Architecture**: With additional engineering runway, we would implement **Dynamic State-Driven Tool Subsetting**. The citizen MCP server would inspect the session's active state (no draft vs active draft vs submitted application) and dynamically serve only phase-relevant tools:
  - *Phase 1 (Drafting)*: `scheme_info`, `check_eligibility`, `save_details`.
  - *Phase 2 (Documenting)*: `save_details`, `get_document_upload_link`, `get_my_application`.
  - *Phase 3 (Review & Submit)*: `submit_application`, `get_my_application`.
  - *Phase 4 (Post-Submission)*: `get_my_application`, `withdraw_application`, `sign_out`.
This would cut per-turn prompt overhead by over 60% and guarantee deterministic progression for even the smallest edge-device models.

---

## 4. Key Architectural Decisions Summary

| ID | Topic | Decision & Production Guarantee |
|---|---|---|
| **D1** | **Scheme Deadline** | Window override (`SCHEME_DEADLINE=2026-12-31 23:59`) keeps portal operational past midnight without code changes. |
| **D2** | **Block Coverage** | `AGENT_ENABLED_BLOCKS` environment variable configures eligible blocks without code modification. |
| **D3** | **Upload Link** | 30-min tokenized upload URL with magic-byte verification prevents LLM context overflow. |
| **D4** | **Internal API** | Private REST API over Docker network ensures database writer invariants are never bypassed. |
| **D5** | **Shared Accounts** | Shared accounts permitted at submission, surfaced as `SHARED_BANK_ACCOUNT` flags in officer dossier. |
| **D6** | **Historical Seed** | Seed anomalies preserved historically, dynamically flagged in officer case review. |

---

## 5. Security & Invariant Guarantees

1. **RFC 8707 & RFC 9728 Compliance**: Explicit audience validation ensures tokens issued for citizen services cannot reach officer endpoints, and metadata discovery is published at canonical endpoints.
2. **Subject Identity Immutability**: No MCP tool accepts identity arguments. Caller identity is extracted exclusively from cryptographically verified RS256 token claims (`sub`).
3. **Session Revocation**: Real-time session verification checks `/internal/v1/session_check` on every request. Calling `sign_out` immediately revokes grants across all connected kiosks.
4. **Data Privacy**: Bank account numbers are strictly masked (`********1234`) across all citizen-facing tools and drafts.
