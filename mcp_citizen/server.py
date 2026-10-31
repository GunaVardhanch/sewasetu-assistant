# -*- coding: utf-8 -*-
"""
Sewa Setu - Citizen MCP Server (Streamable HTTP, RFC 8707, RFC 9728)
Endpoint: /mcp/citizen
Required scope: citizen
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

logger = logging.getLogger("mcp.citizen")

PORTAL_INTERNAL_URL = os.environ.get("PORTAL_INTERNAL_URL", "http://localhost:8000").rstrip("/")
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")
RESOURCE_URL = os.environ.get("CITIZEN_RESOURCE_URL", "http://localhost:8001/mcp/citizen").rstrip("/")


def create_citizen_server() -> MCPServer:
    auth_cfg = AuthSettings(
        issuer_url=PUBLIC_BASE_URL,
        resource_server_url=RESOURCE_URL,
        required_scopes=["citizen"],
        validate_token_resource=True,
    )
    verifier = SewaSetuTokenVerifier(resource_server_url=RESOURCE_URL)

    server = MCPServer(
        name="sewasetu-citizen",
        title="Sewa Setu Pension Assistant — Citizen Services",
        description="Assists citizens of Purvanchal with Indira Gandhi National Old Age Pension applications.",
        instructions="Always speak respectfully and concisely. Never disclose more than the last 4 digits of bank accounts.",
        version="1.0.0",
        auth=auth_cfg,
        token_verifier=verifier,
    )

    @server.tool(
        name="ping",
        description="Verify citizen assistant connectivity and authentication status",
    )
    async def ping() -> Dict[str, Any]:
        """Verify the caller's active citizen session."""
        try:
            role, mobile = get_subject_from_context()
            return format_tool_success(
                message=f"Connected as citizen",
                next_step="Proceed with pension scheme questions or application",
                data={"role": role, "mobile": mobile[-4:].rjust(len(mobile), "*")}
            )
        except Exception as e:
            return format_tool_error("unauthenticated", str(e), "Sign in via OAuth to continue")

    return server


def create_citizen_app():
    server = create_citizen_server()

    @server.custom_route("/.well-known/oauth-protected-resource", methods=["GET", "OPTIONS"])
    async def protected_resource_metadata_root(request):
        meta = get_protected_resource_metadata(RESOURCE_URL, "citizen")
        return JSONResponse(meta)

    @server.custom_route("/mcp/citizen/.well-known/oauth-protected-resource", methods=["GET", "OPTIONS"])
    async def protected_resource_metadata_sub(request):
        meta = get_protected_resource_metadata(RESOURCE_URL, "citizen")
        return JSONResponse(meta)

    @server.custom_route("/healthz", methods=["GET"])
    async def healthz(request):
        return JSONResponse({"status": "ok", "service": "mcp-citizen"})

    return server.streamable_http_app(streamable_http_path="/mcp/citizen")


app = create_citizen_app()

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8001"))
    uvicorn.run(app, host="0.0.0.0", port=port)
