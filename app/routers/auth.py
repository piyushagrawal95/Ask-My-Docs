from fastapi import APIRouter,HTTPException
from pydantic import BaseModel, EmailStr
from app.database import get_service_client

router=APIRouter(prefix="/auth",tags=["auth"])

class SignupRequest(BaseModel):
    email:EmailStr
    password:str

class LoginRequest(BaseModel):
    email:EmailStr
    password:str

@router.post("/signup")
async def signup(payload:SignupRequest):
    client=get_service_client()
    try:
        resp=client.auth.sign_up({"email":payload.email,"password":payload.password})
    except Exception as e:
        msg = str(e).lower()
        if "already registered" in msg or "already exists" in msg or "user_already_exists" in msg:
            raise HTTPException(
                status_code=409,
                detail="An account with this email already exists. Please login instead.",
            )
        raise HTTPException(status_code=400,detail=str(e))

    # Supabase can return a "successful" response even when the email is already
    # registered (email enumeration protection). The tell is an empty
    # `identities` list on the returned user — treat that as "already exists".
    if resp.user is not None and not resp.user.identities:
        raise HTTPException(
            status_code=409,
            detail="An account with this email already exists. Please login instead.",
        )

    return{
        "user_id":resp.user.id if resp.user else None,
        "email":resp.user.email if resp.user else None,
        "message":"Signup successful.Check email for confirmation if required"
    }

@router.post("/login")
async def login(payload:LoginRequest):
    client=get_service_client()
    try:
        resp=client.auth.sign_in_with_password({
            "email":payload.email,"password":payload.password
        })

    except Exception as e:
        raise HTTPException(status_code=401,detail="Invalid email or password")

    return{
        "access_token":resp.session.access_token,
        "refresh_token":resp.session.refresh_token,
        "user_id":resp.user.id
    }