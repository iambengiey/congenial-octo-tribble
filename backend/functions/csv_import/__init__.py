from __future__ import annotations

import csv
import io
import json

from backend.functions.shared.authz import require_auth_context


REQUIRED_HEADERS = {"complex_id", "unit_number", "mobile", "email", "role"}


def main(csv_content: str, headers: dict[str, str]) -> tuple[int, str]:
    """HTTP-trigger CSV import validator and idempotent upsert planner stub."""
    auth = require_auth_context(headers)
    reader = csv.DictReader(io.StringIO(csv_content or ""))
    header_set = set(reader.fieldnames or [])
    missing = sorted(REQUIRED_HEADERS - header_set)
    if missing:
        return 400, json.dumps({"error": "missing_headers", "headers": missing})

    valid_rows = 0
    for row in reader:
        if row.get("complex_id") != auth.active_complex_id:
            continue
        if row.get("mobile") or row.get("email"):
            valid_rows += 1

    report = {
        "status": "validated",
        "valid_rows": valid_rows,
        "complex_id": auth.active_complex_id,
        "idempotency_strategy": "match by id_number_hash or mobile/email + complex_id",
    }
    return 200, json.dumps(report)
