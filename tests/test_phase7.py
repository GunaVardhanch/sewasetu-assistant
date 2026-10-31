# -*- coding: utf-8 -*-
"""
Phase 7 Test Suite — Production Deployment & Caddy Reverse Proxy
Verifies production Docker Compose specification, Caddyfile reverse proxy rules, and container build configurations.
"""

import os
import yaml
import pytest


def test_docker_compose_prod_structure():
    """Verify docker-compose.prod.yml defines the complete 7-service microservice topology."""
    prod_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docker-compose.prod.yml")
    assert os.path.exists(prod_file), f"docker-compose.prod.yml missing at {prod_file}"

    with open(prod_file, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    services = config.get("services", {})
    required_services = [
        "db", "app", "scheduler", "smsgw",
        "mcp-citizen", "mcp-officer", "caddy"
    ]

    for svc in required_services:
        assert svc in services, f"Required service '{svc}' not defined in docker-compose.prod.yml"

    # Verify ports: Caddy exposes 80 & 443; internal apps expose internal ports
    caddy_ports = services["caddy"].get("ports", [])
    assert any("80:80" in str(p) for p in caddy_ports), "Caddy must expose port 80"
    assert any("443:443" in str(p) for p in caddy_ports), "Caddy must expose port 443"

    # Verify MCP servers
    cit_env = services["mcp-citizen"].get("environment", {})
    assert "CITIZEN_RESOURCE_URL" in str(cit_env)
    assert "8001" in str(services["mcp-citizen"].get("command", ""))

    off_env = services["mcp-officer"].get("environment", {})
    assert "OFFICER_RESOURCE_URL" in str(off_env)
    assert "8002" in str(services["mcp-officer"].get("command", ""))


def test_caddyfile_reverse_proxy_routes():
    """Verify Caddyfile defines correct reverse proxy rules and unbuffered SSE streaming."""
    caddy_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "Caddyfile")
    assert os.path.exists(caddy_file), f"Caddyfile missing at {caddy_file}"

    with open(caddy_file, "r", encoding="utf-8") as f:
        content = f.read()

    # Route checks
    assert "/mcp/citizen*" in content, "Missing /mcp/citizen* route in Caddyfile"
    assert "mcp-citizen:8001" in content, "Missing mcp-citizen:8001 proxy destination"

    assert "/mcp/officer*" in content, "Missing /mcp/officer* route in Caddyfile"
    assert "mcp-officer:8002" in content, "Missing mcp-officer:8002 proxy destination"

    assert "app:8000" in content, "Missing app:8000 fallback destination"
    assert "flush_interval -1" in content, "MCP Streamable HTTP requires unbuffered streaming (flush_interval -1)"


def test_mcp_dockerfile():
    """Verify Dockerfile.mcp includes required runtime dependencies."""
    dockerfile = os.path.join(os.path.dirname(os.path.dirname(__file__)), "Dockerfile.mcp")
    assert os.path.exists(dockerfile), f"Dockerfile.mcp missing at {dockerfile}"

    with open(dockerfile, "r", encoding="utf-8") as f:
        content = f.read()

    assert "python:3.11-slim" in content
    assert "mcp" in content
    assert "uvicorn" in content
    assert "pyjwt" in content
