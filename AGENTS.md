You are building sewasetu-assistant: two MCP servers on top of the Sewa Setu portal.

INVARIANTS (never violate):
1. The portal (portal/app.py + Postgres) is the only writer of application data. MCP servers never touch the DB directly.
2. Every channel creates applications through validate_application() and create_application(). No second copy of the rules, ever.
3. An MCP tool never takes a mobile number, user id, or officer name as an argument. Identity comes only from the verified token's `sub`.
4. Citizen tools and officer tools live in separate servers, separate URLs, separate audiences. Never register an officer tool on the citizen server.
5. Never put OTPs or passwords through MCP tools or chat. Sign-in happens only on the portal's own OAuth pages.
6. Never change the OAuth server's behaviour, the SMS gateway console/API, or /oauth/* routes. The assessors sign in through them.
7. Never fabricate defaults for missing citizen data. Ask, or leave the application unsubmitted.
8. Tool output is for a small model with few turns: short, plain language, one clear next step.
9. All schema changes are additive (CREATE ... IF NOT EXISTS, nullable columns).
10. Every phase ends with passing tests and a git commit. No squashing.

STACK: Python 3.11, official `mcp` Python SDK (streamable HTTP, stateless), Flask portal as-is plus patches, Postgres 15, Docker Compose, Caddy for HTTPS.
