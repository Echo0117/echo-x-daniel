# apps/api/deps.py
from fastapi import Depends, Header, HTTPException

def get_current_user():
    # TODO: replace with real session / JWT / OIDC
    # For now, pretend we have a logged-in admin of tenant "t1"
    return {"id": "u1", "email": "demo@example.com", "role": "admin", "tenant_id": "t1"}

def require_role(*roles):
    def wrapper(user = Depends(get_current_user)):
        if user["role"] not in roles:
            raise HTTPException(status_code=403, detail="forbidden")
        return user
    return wrapper

def get_tenant_id(tenant_id: str = Header("t1", convert_underscores=False)):
    # Expect "X-Tenant-Id" header; default "t1" for local dev
    return tenant_id
