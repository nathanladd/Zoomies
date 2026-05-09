from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from server.auth import authenticate, save_credentials, require_auth
from fastapi import Depends

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    username: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
    new_username: str | None = None


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest):
    token = authenticate(body.username, body.password)
    if token is None:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return LoginResponse(token=token, username=body.username)


@router.post("/change-password", dependencies=[Depends(require_auth)])
async def change_password(body: ChangePasswordRequest, _user: str = Depends(require_auth)):
    if authenticate(_user, body.current_password) is None:
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    username = body.new_username or _user
    if len(body.new_password) < 4:
        raise HTTPException(status_code=400, detail="Password must be at least 4 characters")
    save_credentials(username, body.new_password)
    return {"status": "ok"}
