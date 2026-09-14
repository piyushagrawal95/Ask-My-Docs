import gc
from io import BytesIO
import pdfplumber
import pypdf
import docx

# Sentinel markers so chunking.py can find table blocks inside the page
# text and split them row-aware (repeating the header) instead of blindly
# character-splitting them like normal prose.
TABLE_START = "<<<TABLE>>>"
TABLE_END = "<<<END_TABLE>>>"


class ExtractionError(Exception):
    pass

def extract_text(file_bytes: bytes, file_name: str) -> list[tuple[int, str]]:
    ext = file_name.lower().rsplit(".", 1)[-1]

    if ext == "pdf":
        return _extract_pdf(file_bytes)
    elif ext == "docx":
        return _extract_docx(file_bytes)
    elif ext == "txt":
        return _extract_txt(file_bytes)
    else:
        raise ExtractionError(f"Unsupported file type: .{ext}")


def _extract_pdf(file_bytes: bytes) -> list[tuple[int, str]]:
    # 1. Cheap pass: plain text via pypdf. Far lighter on memory than
    #    pdfplumber/pdfminer, which builds a full char/curve/rect object
    #    model per page — that's what was blowing past the memory limit.
    reader = pypdf.PdfReader(BytesIO(file_bytes))
    plain_texts = [(p.extract_text() or "") for p in reader.pages]
    del reader
    gc.collect()

    # 2. Heavier pass, only for tables, and only on pages that actually
    #    have ruling lines/rects (most pages won't, so pdfplumber barely
    #    touches most of the document).
    pages = []
    with pdfplumber.open(BytesIO(file_bytes)) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text_parts = []
            plain_text = plain_texts[i - 1]
            if plain_text.strip():
                text_parts.append(plain_text)

            if page.lines or page.rects:
                tables = page.extract_tables()
                for table in tables:
                    if not table:
                        continue
                    md_rows = []
                    for row_i, row in enumerate(table):
                        cells = [str(c).strip() if c else "" for c in row]
                        md_rows.append("| " + " | ".join(cells) + " |")
                        if row_i == 0:
                            md_rows.append("|" + "---|" * len(cells))
                    text_parts.append(TABLE_START + "\n".join(md_rows) + TABLE_END)

            combined = "\n\n".join(text_parts)
            if combined.strip():
                pages.append((i, combined))

            # Release this page's parsed objects (chars/rects/curves) now
            # instead of letting them accumulate for the whole document.
            page.flush_cache()
            if i % 20 == 0:
                gc.collect()

    del plain_texts
    gc.collect()

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