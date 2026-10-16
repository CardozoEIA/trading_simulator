# tests/modules/documents/test_chunking.py
from app.modules.documents.ingestion.chunking import CHUNK_OVERLAP, CHUNK_SIZE, chunk_sections
from app.modules.documents.ingestion.extractors import Section


def test_short_text_is_one_chunk():
    chunks = chunk_sections([Section("RSI measures momentum.")])

    assert len(chunks) == 1
    assert chunks[0].index == 0


def test_long_text_is_split_and_chunks_respect_the_size_limit():
    text = " ".join(f"Sentence number {i} about drawdown." for i in range(200))

    chunks = chunk_sections([Section(text)])

    assert len(chunks) > 1
    assert all(len(c.content) <= CHUNK_SIZE for c in chunks)
    assert [c.index for c in chunks] == list(range(len(chunks)))


def test_consecutive_chunks_overlap():
    text = " ".join(f"word{i}" for i in range(600))

    chunks = chunk_sections([Section(text)])

    tail_of_first = chunks[0].content[-CHUNK_OVERLAP // 2:]
    assert tail_of_first in chunks[1].content


def test_page_number_is_kept():
    chunks = chunk_sections([Section("Text of page 1.", page=1), Section("Text of page 2.", page=2)])

    assert [c.page for c in chunks] == [1, 2]
    assert [c.index for c in chunks] == [0, 1]
