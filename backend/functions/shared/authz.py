from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AuthContext:
    user_id: str
    active_complex_id: str
    role: str


def require_auth_context(headers: dict[str, str]) -> AuthContext:
    """Minimal auth guard placeholder for Azure Function handlers.

    Production implementation should validate Azure AD B2C JWT, enforce MFA claims,
    and assert role permissions for the active complex.
    """
    user_id = headers.get("x-user-id")
    active_complex_id = headers.get("x-active-complex-id")
    role = headers.get("x-role", "viewer")
    if not user_id or not active_complex_id:
        raise PermissionError("Missing authenticated user or active complex context")
    return AuthContext(user_id=user_id, active_complex_id=active_complex_id, role=role)
