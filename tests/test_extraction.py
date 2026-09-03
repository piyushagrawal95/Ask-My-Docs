import pytest
from io import BytesIO
import docx as docx_lib
from pypdf import PdfWriter

from app.services.extraction import extract_text,ExtractionError

def test_txt_extraction_returns_single_page():
    pages=extract_text(b"Hello World,this is a text","notes.txt")
    assert len(pages)==1
    assert pages[0][0]==1
    assert "Hello World" in pages[0][1]

def test_empty_txt_raises_extraction_error():
    with pytest.raises(ExtractionError):
        extract_text(b" ","empty.txt")

def test_unsupported_extension_raises_extraction_error():
    with pytest.raises(ExtractionError):
        extract_text(b"some bytes","notes.exe")

def test_docx_extraction_returns_text():
    buf=BytesIO()
    document=docx_lib.Document()
    document.add_paragraph("This is a paragraph from a Word document")
    document.save(buf)

    pages=extract_text(buf.getvalue(),"notes.docx")
    assert len(pages)==1
    assert "paragraph from a Word document" in pages[0][1]

def test_empty_docx_raises_extraction_error():
    buf=BytesIO()
    document=docx_lib.Document()
    document.save(buf)

    with pytest.raises(ExtractionError):
        extract_text(buf.getvalue(),"empty.docx")


def test_blank_pdf_raises_extraction_error():
    buf=BytesIO()
    writer=PdfWriter()
    writer.add_blank_page(width=200,height=200)
    writer.write(buf)

    with pytest.raises(ExtractionError):
        extract_text(buf.getvalue(),"scanned.pdf")
        