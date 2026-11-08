"""One response envelope for every endpoint.

Success: {"status": "ok", "data": {...}}
Failure: {"status": "error", "error": {"code": str, "message": str, "details"?: any}}
"""
from typing import Any

from rest_framework import status as http
from rest_framework.response import Response


def success(data: Any, status: int = http.HTTP_200_OK) -> Response:
    return Response({"status": "ok", "data": data}, status=status)


def error_body(code: str, message: str, details: Any = None) -> dict:
    body: dict = {"status": "error", "error": {"code": code, "message": message}}
    if details is not None:
        body["error"]["details"] = details
    return body


def error(code: str, message: str, status: int, details: Any = None) -> Response:
    return Response(error_body(code, message, details), status=status)
