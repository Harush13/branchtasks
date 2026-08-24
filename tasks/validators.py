import re
import uuid

import filetype
from django.core.exceptions import ValidationError

MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024  # 10 MB, spec §3.4

# Sniffed from file content via `filetype`, never trusted from the client's
# extension or Content-Type header.
ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/heic",
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

_UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def validate_attachment_size(file):
    if file.size > MAX_ATTACHMENT_SIZE:
        raise ValidationError(f"File exceeds the {MAX_ATTACHMENT_SIZE // (1024 * 1024)} MB limit.")


def validate_attachment_type(file):
    """
    Reads magic bytes, not the extension or client-supplied Content-Type —
    spec §3.4/§14: "verify MIME type by content, not extension."
    """
    kind = filetype.guess(file)
    file.seek(0)
    if kind is None or kind.mime not in ALLOWED_MIME_TYPES:
        raise ValidationError("Unsupported file type.")


def attachment_upload_path(instance, filename):
    """
    MEDIA_ROOT/tasks/<task_ref>/<uuid>_<sanitized_name> (spec §3.4). The
    client-supplied filename is sanitized and never used to build the path
    directly — only as a suffix on a server-generated UUID.
    """
    safe_name = _UNSAFE_FILENAME_CHARS.sub("_", filename)[:200]
    ref = instance.task.ref or "unfiled"
    return f"tasks/{ref}/{uuid.uuid4()}_{safe_name}"
