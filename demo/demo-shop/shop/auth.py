from typing import Optional
from fastapi import Header, HTTPException, status


def require_auth(authorization: Optional[str] = Header(None)) -> str:
    """Dependency enforcing authentication on protected internal/admin routes."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )

    parts = authorization.split(" ")
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization format. Expected 'Bearer <token>'",
        )

    token = parts[1]
    if token != "tipjar-secret-token":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or expired token",
        )

    return "admin-user"
