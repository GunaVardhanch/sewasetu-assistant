# -*- coding: utf-8 -*-
"""
Lightweight MCP Streamable HTTP client session for evaluation runs.
"""

import time
import json
import requests
from typing import Dict, Any, Optional


def parse_mcp_response(resp: requests.Response) -> Dict[str, Any]:
    """Parse JSON or SSE stream response from MCP Streamable HTTP."""
    text = resp.text.strip()
    if resp.headers.get("content-type", "").startswith("text/event-stream"):
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("data:"):
                return json.loads(line[5:].strip())
    return resp.json()


class MCPClientSession:
    """Simulates a real MCP client over Streamable HTTP."""

    def __init__(self, endpoint_url: str, access_token: str, client_name: str = "eval-mcp-client"):
        self.endpoint_url = endpoint_url
        self.access_token = access_token
        self.client_name = client_name
        self.session_id: Optional[str] = None
        self._initialize()

    def _initialize(self):
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"
        }
        init_payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": self.client_name, "version": "1.0"}
            }
        }
        resp = requests.post(self.endpoint_url, headers=headers, json=init_payload, timeout=8)
        if resp.status_code != 200:
            raise RuntimeError(f"MCP initialize failed ({resp.status_code}): {resp.text}")
        self.session_id = resp.headers.get("mcp-session-id")

        # Send notifications/initialized
        notif_payload = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }
        post_headers = dict(headers)
        if self.session_id:
            post_headers["mcp-session-id"] = self.session_id
        requests.post(self.endpoint_url, headers=post_headers, json=notif_payload, timeout=8)

    def call_tool(self, tool_name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Call an MCP tool and return parsed output dictionary."""
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"
        }
        if self.session_id:
            headers["mcp-session-id"] = self.session_id

        payload = {
            "jsonrpc": "2.0",
            "id": int(time.time() * 1000) % 1000000,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments or {}
            }
        }
        resp = requests.post(self.endpoint_url, headers=headers, json=payload, timeout=10)
        if resp.status_code != 200:
            raise RuntimeError(f"Tool {tool_name} returned HTTP {resp.status_code}: {resp.text}")

        data = parse_mcp_response(resp)
        if "error" in data:
            return {"status": "error", "mcp_error": data["error"]}

        content = data.get("result", {}).get("content", [])
        if content and content[0].get("type") == "text":
            try:
                return json.loads(content[0]["text"])
            except Exception:
                return {"raw_text": content[0]["text"]}
        return data.get("result", {})

