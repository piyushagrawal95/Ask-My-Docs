import httpx
from supabase import create_client, Client, ClientOptions
from app.config import settings

_service_client: Client | None = None

def get_service_client() -> Client:
    global _service_client
    if _service_client is None:
        # http2=False prevents Errno 11 socket race conditions under concurrent polling
        options = ClientOptions(
            httpx_client=httpx.Client(http2=False, timeout=30.0),
            postgrest_client_timeout=30.0,
            storage_client_timeout=60.0,
        )
        _service_client = create_client(
            settings.supabase_url,
            settings.supabase_service_role_key,
            options=options,
        )
    return _service_client

