from io import BytesIO
import pdfplumber
import docx


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
    pages = []
    with pdfplumber.open(BytesIO(file_bytes)) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text_parts = []

            plain_text = page.extract_text() or ""
            if plain_text.strip():
                text_parts.append(plain_text)

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
                text_parts.append("\n".join(md_rows))

            combined = "\n\n".join(text_parts)
            if combined.strip():
                pages.append((i, combined))

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