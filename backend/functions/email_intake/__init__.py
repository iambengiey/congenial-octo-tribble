from __future__ import annotations

import json
from datetime import datetime, timezone

from backend.functions.shared.authz import require_auth_context


def main(req_body: str, headers: dict[str, str]) -> tuple[int, str]:
    """HTTP-trigger entrypoint for forwarded email intake payloads.

    Expected body fields: subject, from_email, body_text, complex_hint, unit_hint, attachments.
    """
    require_auth_context(headers)
    payload = json.loads(req_body or "{}")
    event = {
        "event_type": "email_intake_received",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "subject": payload.get("subject", ""),
        "from_email": payload.get("from_email", ""),
        "complex_hint": payload.get("complex_hint"),
        "unit_hint": payload.get("unit_hint"),
    }
    return 202, json.dumps({"status": "accepted", "audit_event": event})
