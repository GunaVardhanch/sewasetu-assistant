# Sewa Setu Assistant — 3-Minute Loom Video Recording Script

> **Recording Setup**: Face camera in lower corner, screen showing browser and terminal.  
> **Target Duration**: Exactly 3 minutes (180 seconds).  
> **URLs to have open in browser tabs before starting**:
> 1. Tab 1: Portal Homepage (`http://localhost:8000`)
> 2. Tab 2: Evaluation Dashboard (`http://localhost:8000/eval-dashboard`)
> 3. Tab 3: Departmental Admin Queue (`http://localhost:8000/admin`)
> 4. Tab 4: GitHub Repository (`https://github.com/GunaVardhanch/sewasetu-assistant`)

---

### [0:00 – 0:35] Part 1: Hook & Dual-MCP Architecture

**Visual**: Camera on face + screen showing the Sewa Setu Portal homepage (`http://localhost:8000`).

**Script**:
> *"Hello! I’m presenting `sewasetu-assistant` — an autonomous AI assistant built for the Government of Purvanchal’s Old Age Pension Portal.*
>
> *To address the Director's mandate, we engineered two cryptographically isolated Model Context Protocol (MCP) servers running Streamable HTTP: `/mcp/citizen` for applicants, and `/mcp/officer` for Block Development Officers.*
>
> *Our most critical invariant: the portal and its 100,000-record PostgreSQL database remain the sole system of record. MCP servers never connect to Postgres directly. All mutations and queries route across a private Docker network through an authenticated `/internal/v1/*` REST API. This guarantees 100% validation parity between web and AI channels, backed by PostgreSQL transaction advisory locks to eliminate race conditions."*

---

### [0:35 – 1:15] Part 2: The Three Decisions That Mattered Most

**Visual**: Switch screen to show `DESIGN.md` architectural diagram and code editor highlighting `common/auth.py` and `portal/agent_api.py`.

**Script**:
> *"Across the two MCPs, three design decisions mattered most:*
>
> *First, **Strict RFC 8707 & RFC 9728 Audience Isolation**. A citizen token cannot reach officer tools, and an officer token cannot invoke citizen tools. Caller identity is derived strictly from verified JWT `sub` claims — no tool ever accepts a mobile number or username as an argument.*
>
> *Second, **Out-of-Band Tokenized Document Uploads (Decision D3)**. Rather than passing multi-megabyte base64 file blobs through LLM chat — which crashes small models — our assistant issues a single-use 30-minute upload link (`/upload/<token>`). Citizens upload age proof photos directly from mobile cameras, validated by binary magic bytes on disk.*
>
> *Third, **Tolerant Ingestion with Flagged Human Adjudication (Decision D5)**. In rural Assam, elderly couples frequently share a single bank passbook, and folk often state 'Widow' rather than 'Widowed'. Instead of hard-rejecting and stranding genuine seniors, we normalize terms transparently and surface a `SHARED_BANK_ACCOUNT` review flag directly in the Block Officer's dossier."*

---

### [1:15 – 2:15] Part 3: Evals Suite & Live Dashboard Walkthrough

**Visual**: Switch screen to the **Evaluation Dashboard** (`http://localhost:8000/eval-dashboard`). Scroll smoothly down the KPI cards and click on persona cards to expand transcripts.

**Script**:
> *"Now let's look at how we tested this. We built a comprehensive evaluation suite with 18 distinct personas — 12 citizens and 6 block officers — each with their own demographic profile, rural dialect, and verified database assertions.*
>
> *Here on our live `/eval-dashboard`, all 18 personas pass with a 100% success rate.*
>
> *For example, **C1 Bhaben Hazarika** is a 68-year-old farmer who submits cleanly. We verify in PostgreSQL that his record is inserted in `applications`, marked `PENDING`, document attached, and logged with a `SUBMIT` audit event.*
>
> *In **C3 Kamala Devi**, an elderly widow forgets her husband's name on turn 1. The assistant prompts her gently, normalizes 'Widow' to 'Widowed', and completes the draft.*
>
> *On the officer side, **O1 Anjali Sharma** triages the morning Sonari queue ordered oldest-first with SLA countdowns. And in **O3**, Officer Anjali reviews Runu Saikia — where the assistant highlights the `SHARED_BANK_ACCOUNT` flag along with the count of shared applications.*
>
> *Notice that every single conversation transcript is fully inspectable here, showing the exact tool calls, arguments, and responses."*

---

### [2:15 – 2:45] Part 4: What the Evals Taught Us & What We Fixed

**Visual**: Scroll to the *"What the Personas Taught Us & What We Fixed"* section on `/eval-dashboard`.

**Script**:
> *"The evaluation runs directly exposed several real-world edge cases that we hardened:*
> 1. *Colloquial marital status strings: we added transparent database normalization.*
> 2. *Privacy protection: we implemented automatic bank account masking across all agent drafts and tool returns.*
> 3. *Duplicate bank handling: transformed from a hard submission block into an officer triage flag.*
> 4. *Concurrency: wrapped portal submissions in PostgreSQL advisory locks to guarantee idempotent submissions under parallel load.*
> 5. *Public cyber cafe safety: implemented `sign_out` with instant RFC 7009 token revocation and live session invalidation.*
>
> *If we had more time, the one decision we'd make differently is implementing dynamic, context-dependent MCP tool subsetting to present only phase-relevant tools as a citizen progresses from draft to submission."*

---

### [2:45 – 3:00] Part 5: Production Deployment & Closing

**Visual**: Switch to GitHub repository tab (`https://github.com/GunaVardhanch/sewasetu-assistant`) showing granular commit history, then terminal running tests.

**Script**:
> *"Finally, the system is fully production-ready with Docker Compose and Caddy handling automated TLS termination and SSE stream flushing.*
>
> *The entire un-squashed commit history across all 8 phases is pushed to our private GitHub repository `sewasetu-assistant`, and assessor `harshnisar` has been invited with read-only access.*
>
> *Thank you, and we look forward to your evaluation!"*
