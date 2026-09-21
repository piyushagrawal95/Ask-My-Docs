from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    supabase_url:str
    supabase_service_role_key:str
    supabase_anon_key:str

    groq_api_key:str
    cohere_api_key:str = ""
    voyage_api_key:str = ""

    allowed_origins:str="http://localhost:5173"

    # ---RAG pipeline tuning
    llm_model:str
    embedding_model:str
    reranker_model:str

    
    rrf_k:int
    candidate_pool_size:int
    retrieval_top_k:int

    max_file_size_mb:int=30
    allowed_extensions:str="pdf,docx,txt"
    max_documents_per_conversation:int=5
    

    class Config:
        env_file=".env"



settings=Settings()