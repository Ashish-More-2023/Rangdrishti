"""Wrap every DRF error (and unexpected exceptions) in the standard envelope."""
import logging

from rest_framework import status as http
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import exception_handler

from .responses import error_body

logger = logging.getLogger(__name__)


def envelope_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is None:
        # Not a DRF exception: log the traceback, never leak it to the client.
        logger.error("Unhandled API error", exc_info=exc)
        return Response(
            error_body("internal_error", "An unexpected server error occurred."),
            status=http.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    code = getattr(exc, "default_code", "error") if isinstance(exc, APIException) else "error"
    data = response.data
    if isinstance(data, dict) and set(data) == {"detail"}:
        message, details = str(data["detail"]), None
    else:
        message, details = "The request could not be processed.", data

    response.data = error_body(code, message, details)
    return response
