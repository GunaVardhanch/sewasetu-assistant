# -*- coding: utf-8 -*-
"""
Error formatting helpers for small-model friendly tool responses.
"""

from typing import Dict, Any, List, Optional


def format_tool_error(error_code: str, message: str, next_step: str, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "status": "error",
        "error_code": error_code,
        "message": message,
        "next_step": next_step
    }
    if details:
        out["details"] = details
    return out


def format_tool_success(message: str, next_step: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "status": "success",
        "message": message,
        "next_step": next_step
    }
    if data:
        for k, v in data.items():
            if k == "status" and v != "success":
                out["application_status"] = v
            else:
                out[k] = v
        out["status"] = "success"
    return out

