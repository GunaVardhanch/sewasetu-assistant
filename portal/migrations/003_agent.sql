-- 003_agent.sql: Schema additions for MCP agent support
-- Idempotent: safe to run multiple times.

CREATE TABLE IF NOT EXISTS agent_drafts (
    mobile       VARCHAR(15) PRIMARY KEY,
    data         JSONB NOT NULL DEFAULT '{}'::jsonb,
    doc_path     VARCHAR(200),
    updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS upload_links (
    token_hash   VARCHAR(64) PRIMARY KEY,
    mobile       VARCHAR(15) NOT NULL,
    expires_at   TIMESTAMP NOT NULL,
    used_at      TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_upload_links_mobile ON upload_links(mobile);
CREATE INDEX IF NOT EXISTS idx_upload_links_expires ON upload_links(expires_at);

-- Performance and integrity indexes
CREATE INDEX IF NOT EXISTS idx_applications_bank_account ON applications(bank_account);
CREATE INDEX IF NOT EXISTS idx_applications_submitted_at ON applications(submitted_at);
