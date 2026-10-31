# -*- coding: utf-8 -*-
"""
Sewa Setu - Block Officer MCP Server (Streamable HTTP, RFC 8707, RFC 9728)
Endpoint: /mcp/officer
Required scope: officer
"""

import os
import sys
import logging
from typing import Dict, Any

from starlette.routing import Route
from starlette.responses import JSONResponse
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.server import AuthSettings

from common.auth import (
    SewaSetuTokenVerifier,
    get_protected_resource_metadata,
    get_subject_from_context,
)
from common.errors import format_tool_success, format_tool_error

logger = logging.getLogger("mcp.officer")

PORTAL_INTERNAL_URL = os.environ.get("PORTAL_INTERNAL_URL", "http://localhost:8000").rstrip("/")
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")
RESOURCE_URL = os.environ.get("OFFICER_RESOURCE_URL", "http://localhost:8002/mcp/officer").rstrip("/")


def create_officer_server() -> MCPServer:
    auth_cfg = AuthSettings(
        issuer_url=PUBLIC_BASE_URL,
        resource_server_url=RESOURCE_URL,
        required_scopes=["officer"],
        validate_token_resource=True,
    )
    verifier = SewaSetuTokenVerifier(resource_server_url=RESOURCE_URL)

    server = MCPServer(
        name="sewasetu-officer",
        title="Sewa Setu Pension Portal — Block Officer Assistant",
        description="Assists Block Officers in Sonari, Rajapara, etc. to review and decide pension applications.",
        instructions="Provide objective, audit-logged case summaries. High-risk cases with duplicate bank accounts require scrutiny.",
        version="1.0.0",
        auth=auth_cfg,
        token_verifier=verifier,
    )

    @server.tool(
        name="ping",
        description="Verify block officer assistant connectivity and authentication status",
    )
    async def ping() -> Dict[str, Any]:
        """Verify the caller's active officer session."""
        try:
            role, officer_name = get_subject_from_context()
            return format_tool_success(
                message=f"Connected as block officer",
                next_step="Request my_queue or overdue_summary to triage pending applications",
                data={"role": role, "officer": officer_name}
            )
        except Exception as e:
            return format_tool_error("unauthenticated", str(e), "Sign in via Departmental login to continue")

    return server


def create_officer_app():
    server = create_officer_server()

    @server.custom_route("/.well-known/oauth-protected-resource", methods=["GET", "OPTIONS"])
    async def protected_resource_metadata_root(request):
        meta = get_protected_resource_metadata(RESOURCE_URL, "officer")
        return JSONResponse(meta)

    @server.custom_route("/mcp/officer/.well-known/oauth-protected-resource", methods=["GET", "OPTIONS"])
    async def protected_resource_metadata_sub(request):
        meta = get_protected_resource_metadata(RESOURCE_URL, "officer")
        return JSONResponse(meta)

    @server.custom_route("/healthz", methods=["GET"])
    async def healthz(request):
        return JSONResponse({"status": "ok", "service": "mcp-officer"})

    return server.streamable_http_app(streamable_http_path="/mcp/officer")


app = create_officer_app()

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8002"))
    uvicorn.run(app, host="0.0.0.0", port=port)
