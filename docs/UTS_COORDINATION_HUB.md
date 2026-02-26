# UTS Coordination Hub (Architecture Baseline)

This repository now includes a baseline scaffold for the **UTS Coordination Hub** (multi-complex Body Corporate governance platform).

## Included deliverables

- **Frontend static scaffold**: `apps/uts-hub-static/`
  - Renamed product to UTS Coordination Hub.
  - Module navigation for Maintenance, Infrastructure & Alterations, Move-in/Move-out, Vendors, Audit Log, and Settings.
- **Azure Function stubs**: `backend/functions/`
  - `email_intake`: accepts forwarded email payload and creates an intake audit event.
  - `csv_import`: validates CSV headers and demonstrates idempotent import strategy.
  - `shared/authz.py`: validates authenticated user + active complex context.
- **Azure SQL migration**: `db/migrations/V1__uts_coordination_hub_schema.sql`
  - Core multi-complex schema with append-only audit log model.
  - Includes `id_number_encrypted` and `id_number_hash` (not PK) plus index for lookup.
- **GitHub Actions workflows**:
  - `.github/workflows/azure-bootstrap.yml`
  - `.github/workflows/azure-backups.yml`

## Governance workflow rules captured

- All cases are complex-scoped and version-linked (`rule_profile`, `approval_matrix_version`).
- Tenant requests require landlord/delegated-agent approval gate first.
- Owner/landlord-originated requests auto-satisfy landlord gate but remain logged.
- Immutable append-only `audit_log` for state changes and retention actions.

## Email handling model

- Default inbound identity: `UltimateTenantSolutions@gmail.com`.
- Gmail auto-reply should confirm receipt, SLA expectations, request complex/unit/contact details, and direct urgent issues to portal.
- Inbound mail should be forwarded to ingestion integration consumed by `email_intake` function.
- Outbound notifications should use SendGrid/Azure Communication Services Email with display name “Ultimate Tenant Solutions” and reply-to Gmail.

## Security controls baseline

- Azure AD B2C authentication + MFA gate before any complex data.
- TOTP required for trustees/managing agents/admins.
- API authorization enforces `user + active_complex_id + permission`.
- Attachments to Blob private containers; short-lived SAS for download.
- Step-up MFA for high-risk actions.

## Notes

This is a **scaffold baseline** for implementation and CI automation, not a complete production rollout.
