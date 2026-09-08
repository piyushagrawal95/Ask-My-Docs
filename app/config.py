from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    supabase_url:str
    supabase_service_role_key:str
    supabase_anon_key:str

    groq_api_key:str

    allowed_origins:str="http://localhost:5173"

    # ---RAG pipeline tuning
    llm_model:str="openai/gpt-oss-120b"
    embedding_model:str="BAAI/bge-small-en-v1.5"
    reranker_model:str="Xenova/ms-marco-MiniLM-L-6-v2"

    chunk_size:int=800
    chunk_overlap:int=120

    rrf_k:int=60
    candidate_pool_size:int=20
    retrieval_top_k:int=5

    max_file_size_mb:int=30
    allowed_extensions:str="pdf,docx,txt"
    

    class Config:
        env_file=".env"



settings=Settings()