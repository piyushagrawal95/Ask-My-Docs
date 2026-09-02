from io import BytesIO
from pypdf import PdfReader
import docx

class ExtractionError(Exception):
    pass

def extract_text(file_bytes: bytes, file_name: str) -> list[tuple[int, str]]:
    ext = file_name.lower().rsplit(".", 1)[-1]

    if ext == "pdf":\
        return _extract_pdf(file_bytes)
    elif ext == "docx":
        return _extract_docx(file_bytes)
    elif ext == "txt":
        return _extract_txt(file_bytes)
    else:
        raise ExtractionError(f"Unsupported file type: .{ext}")


def _extract_pdf(file_bytes:bytes) -> list[tuple[int,str]]:
    reader=PdfReader(BytesIO(file_bytes))
    pages=[]
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            pages.append((i, text))
    if not pages:
        raise ExtractionError("No extractable text found (possibly a scanned PDF).")
    return pages

def _extract_docx(file_bytes: bytes) -> list[tuple[int, str]]:
    document = docx.Document(BytesIO(file_bytes))
    text = "\n".join(p.text for p in document.paragraphs if p.text.strip())
    if not text.strip():
        raise ExtractionError("No extractable text found in .docx file.")
    return [(1, text)]


def _extract_txt(file_bytes: bytes) -> list[tuple[int, str]]:
    text = file_bytes.decode("utf-8", errors="ignore")
    if not text.strip():
        raise ExtractionError("File is empty.")
    return [(1, text)]