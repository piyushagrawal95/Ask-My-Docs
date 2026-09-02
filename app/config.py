from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    supabase_url:str
    supabase_service_role_key:str
    supabase_anon_key:str

    groq_api_key:str

    allowed_origins:str="http://localhost:5173"

    class Config:
        env_file=".env"



settings=Settings()