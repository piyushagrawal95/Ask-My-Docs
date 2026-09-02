from supabase import create_client, Client
from app.config import settings

_service_client:Client | None=None

def get_service_client() -> Client:
    global _service_client
    if _service_client is None:
        _service_client=create_client(
            settings.supabase_url,settings.supabase_service_role_key
        )
    return _service_client

