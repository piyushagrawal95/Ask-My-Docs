from fastapi import Depends,HTTPException,status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.database import get_service_client

bearer_scheme=HTTPBearer()

class CurrentUser:
    def __init__(self,id:str,email:str|None):
        self.id=id
        self.email=email

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> CurrentUser:
    token = credentials.credentials
    client = get_service_client()

    try:
        user_resp = client.auth.get_user(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    if not user_resp or not user_resp.user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )

    return CurrentUser(id=user_resp.user.id, email=user_resp.user.email)