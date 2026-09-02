from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import get_service_client
from app.routers import auth, documents,conversations
from app.auth import get_current_user, CurrentUser

app = FastAPI(title="Ask my docs")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(conversations.router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/test-db")
async def test_db():
    client = get_service_client()
    resp = client.table("documents").select("*").execute()
    return {"documents_count": len(resp.data), "data": resp.data}


@app.get("/me")
async def get_me(user: CurrentUser = Depends(get_current_user)):
    return {"id": user.id, "email": user.email}