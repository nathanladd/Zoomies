from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from server.auth import (
    authenticate, change_password, require_auth, require_admin,
    list_users, add_user, update_user, delete_user,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    username: str
    role: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: str = "instructor"


class PatchUserRequest(BaseModel):
    active: bool | None = None
    role: str | None = None


class ResetPasswordRequest(BaseModel):
    new_password: str


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest):
    result = authenticate(body.username, body.password)
    if result is None:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token, role = result
    return LoginResponse(token=token, username=body.username, role=role)


@router.post("/change-password")
async def change_own_password(
    body: ChangePasswordRequest, username: str = Depends(require_auth)
):
    if authenticate(username, body.current_password) is None:
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    if len(body.new_password) < 4:
        raise HTTPException(status_code=400, detail="Password must be at least 4 characters")
    change_password(username, body.new_password)
    return {"status": "ok"}


@router.get("/users")
async def get_users(_admin: str = Depends(require_admin)):
    return list_users()


@router.post("/users")
async def create_user_endpoint(body: CreateUserRequest, _admin: str = Depends(require_admin)):
    if body.role not in ("admin", "instructor"):
        raise HTTPException(status_code=400, detail="role must be 'admin' or 'instructor'")
    if len(body.password) < 4:
        raise HTTPException(status_code=400, detail="Password must be at least 4 characters")
    try:
        return add_user(body.username, body.password, body.role)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.patch("/users/{username}")
async def patch_user_endpoint(
    username: str, body: PatchUserRequest, _admin: str = Depends(require_admin)
):
    kwargs: dict = {}
    if body.active is not None:
        kwargs["active"] = body.active
    if body.role is not None:
        if body.role not in ("admin", "instructor"):
            raise HTTPException(status_code=400, detail="role must be 'admin' or 'instructor'")
        kwargs["role"] = body.role
    if not kwargs:
        raise HTTPException(status_code=400, detail="Nothing to update")
    try:
        return update_user(username, **kwargs)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"User '{username}' not found")
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/users/{username}/reset-password")
async def reset_user_password(
    username: str, body: ResetPasswordRequest, _admin: str = Depends(require_admin)
):
    if len(body.new_password) < 4:
        raise HTTPException(status_code=400, detail="Password must be at least 4 characters")
    try:
        change_password(username, body.new_password)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"User '{username}' not found")
    return {"status": "ok"}


@router.delete("/users/{username}")
async def delete_user_endpoint(username: str, _admin: str = Depends(require_admin)):
    try:
        delete_user(username)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"User '{username}' not found")
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {"status": "ok"}
