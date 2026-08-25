"""
DRF's default exception handler only understands its own
rest_framework.exceptions.APIException subclasses. tasks/services.py
deliberately raises Django's django.core.exceptions.ValidationError and
PermissionDenied instead (see tasks/services.py's module docstring and §12)
so the Admin and any future template views get the same behavior — that
choice means the API layer has to translate those two exception types into
DRF's 400 / 403 itself, which is what this handler does. Everything else
falls through to DRF's default handling unchanged.
"""

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import PermissionDenied as DRFPermissionDenied
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.views import exception_handler as drf_exception_handler


def exception_handler(exc, context):
    if isinstance(exc, DjangoValidationError):
        exc = DRFValidationError(detail=_messages(exc))
    elif isinstance(exc, DjangoPermissionDenied):
        exc = DRFPermissionDenied(detail=str(exc) or "Permission denied.")

    return drf_exception_handler(exc, context)


def _messages(exc: DjangoValidationError):
    """Django's ValidationError carries either .message or .messages (a list)
    depending on how it was raised; normalize to what DRF expects."""
    if hasattr(exc, "message_dict"):
        return exc.message_dict
    return list(exc.messages)
