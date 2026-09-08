from dataclasses import dataclass
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.config import settings

@dataclass
class Chunk:
    content:str
    chunk_index:int
    page_number:int|None

def chunk_pages(pages:list[tuple[int,str]]) -> list[Chunk]:
    splitter=RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        separators=["\n\n","\n",". "," ",""]
    )

    chunks:list[Chunk]=[]
    idx=0
    for page_number,text in pages:
        for piece in splitter.split_text(text):
            piece=piece.strip()
            if not piece:
                continue
            chunks.append(Chunk(content=piece,chunk_index=idx,page_number=page_number))
            idx+=1

    return chunks