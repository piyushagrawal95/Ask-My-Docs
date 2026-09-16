import re
from dataclasses import dataclass
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.config import settings
from app.services.extraction import TABLE_START, TABLE_END

@dataclass
class Chunk:
    content:str
    chunk_index:int
    page_number:int|None

_TABLE_PATTERN = re.compile(
    re.escape(TABLE_START) + r"(.*?)" + re.escape(TABLE_END), re.DOTALL
)


def _chunk_table(table_md: str, max_size: int) -> list[str]:
    """Splits a markdown table by rows, repeating the header + separator
    row at the top of every resulting piece — so each chunk is readable
    and attributable on its own, even without the original header nearby."""
    lines = [l for l in table_md.strip("\n").split("\n") if l.strip()]
    if len(table_md) <= max_size or len(lines) < 3:
        return [table_md]

    header, separator, *data_rows = lines
    prefix = header + "\n" + separator + "\n"

    pieces = []
    current = prefix
    for row in data_rows:
        candidate = current + row + "\n"
        if len(candidate) > max_size and current != prefix:
            pieces.append(current.rstrip("\n"))
            current = prefix + row + "\n"
        else:
            current = candidate
    if current != prefix:
        pieces.append(current.rstrip("\n"))
    return pieces


def chunk_pages(pages:list[tuple[int,str]]) -> list[Chunk]:
    splitter=RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        separators=["\n\n","\n",". "," ",""]
    )

    chunks:list[Chunk]=[]
    idx=0

    def _add(piece: str, page_number: int):
        nonlocal idx
        piece = piece.strip()
        if piece:
            chunks.append(Chunk(content=piece, chunk_index=idx, page_number=page_number))
            idx += 1

    for page_number,text in pages:
        pos = 0
        for match in _TABLE_PATTERN.finditer(text):
            # Plain text before this table -> normal recursive splitting.
            before = text[pos:match.start()]
            for piece in splitter.split_text(before):
                _add(piece, page_number)

            # The table itself -> row-aware splitting with repeated header.
            table_md = match.group(1)
            for piece in _chunk_table(table_md, settings.chunk_size):
                _add(piece, page_number)

            pos = match.end()

        # Remaining text after the last table (or the whole page if there
        # were no tables on it).
        for piece in splitter.split_text(text[pos:]):
            _add(piece, page_number)

    return chunks