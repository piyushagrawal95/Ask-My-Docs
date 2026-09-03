from app.services.chunking import chunk_pages

def test_chunk_pages_empty_input_returns_empty_list():
    assert chunk_pages([])==[]

def test_chunk_pages_preserve_page_number():
    pages=[(1,"Short text on page one"),(2,"Short text on page two")]
    chunk=chunk_pages(pages)
    assert len(chunk)==2
    assert chunk[0].page_number==1
    assert chunk[1].page_number==2


def test_chunk_pages_split_long_text():
    long_text=("This is a sentence."*200)
    chunks=chunk_pages([(1,long_text)])

    assert len(chunks)>1
    assert [c.chunk_index for c in chunks]==list(range(len(chunks)))
    assert all(c.page_number==1 for c in chunks)


def test_chunk_pages_skips_blank_pieces():
    chunks=chunk_pages([(1," \n\n    ")])
    assert chunks==[]