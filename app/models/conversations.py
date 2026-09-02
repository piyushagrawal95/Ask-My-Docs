from datetime import datetime
from pydantic import BaseModel

class CitationResponse(BaseModel):
    id:str
    document_id:str
    chunk_id:str|None
    page_number:int|None
    snippet:str|None
    relevance_score:float|None


class MessageResponse(BaseModel):
    id:str
    conversation_id:str
    role:str
    content:str
    is_answerable:bool
    created_at:datetime
    citations:list[CitationResponse]=[]

class ConversationResponse(BaseModel):
    id:str
    owner_id:str
    title:str|None
    created_at:datetime
    updated_at:datetime


class ConversationListResponse(BaseModel):
    conversations:list[ConversationResponse]

class ConversationDetailResponse(BaseModel):
    conversation:ConversationResponse
    messages:list[MessageResponse]

class AskQuestionRequest(BaseModel):
    question:str
    document_ids:list[str]|None=None