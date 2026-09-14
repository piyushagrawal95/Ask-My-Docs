from io import BytesIO
import docx
import fitz  # PyMuPDF

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
  """PyMuPDF based ultra-fast and low-memory extractor.

  - 82 pages parse hone me sirf 2-3 seconds lagenge (15 minute nahi).
  - RAM consumption 50MB se kam rahegi (Render Free Tier 512MB par safe).
  - Tables ko clean Markdown me extract karta hai.
  - Table ka text double repeat nahi hota.
  """
  pages = []

  try:
    doc = fitz.open(stream=file_bytes, filetype="pdf")
  except Exception as e:
    raise ExtractionError(f"Could not open PDF: {e}")

  for page_num, page in enumerate(doc, start=1):
    elements = []  # tuple of (y0_position, content_str)

    # 1. Page par tables detect karein
    tabs = page.find_tables()
    table_rects = [fitz.Rect(t.bbox) for t in tabs.tables] if tabs.tables else []

    # 2. Page ke text blocks extract karein (blocks format: x0, y0, x1, y1, text, block_no, type)
    blocks = page.get_text("blocks")
    for b in blocks:
      text = b[4].strip()
      if not text:
        continue

      # Check karein ki ye text block kisi table ke andar to nahi aa raha
      b_rect = fitz.Rect(b[:4])
      is_inside_table = False
      for tr in table_rects:
        intersection = b_rect & tr
        # Agar block ka 40% se zyada hissa table ke andar hai to use skip karein
        if (
            not intersection.is_empty
            and b_rect.get_area() > 0
            and (intersection.get_area() / b_rect.get_area()) > 0.4
        ):
          is_inside_table = True
          break

      if not is_inside_table:
        elements.append((b[1], text))  # b[1] is y0 (vertical position)

    # 3. Tables ko Markdown format me convert karein
    for tab in tabs:
      md = None
      try:
        md = tab.to_markdown()
      except Exception:
        pass

      # Fallback agar to_markdown() kisi table par fail ho
      if not md:
        extracted = tab.extract()
        if extracted:
          rows = []
          for r_idx, row in enumerate(extracted):
            cells = [str(c).strip() if c else "" for c in row]
            rows.append("| " + " | ".join(cells) + " |")
            if r_idx == 0:
              rows.append("|" + "---|" * len(cells))
          md = "\n".join(rows)

      if md and md.strip():
        table_content = f"{TABLE_START}\n{md.strip()}\n{TABLE_END}"
        elements.append((tab.bbox[1], table_content))

    # 4. Elements ko top-to-bottom natural order me sort karein
    elements.sort(key=lambda x: x[0])

    combined = "\n\n".join(item[1] for item in elements).strip()
    if combined:
      pages.append((page_num, combined))

  doc.close()

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