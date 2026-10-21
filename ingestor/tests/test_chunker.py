import pytest

from app.pipeline.chunker import chunk_pages, split_text
from app.pipeline.loader import Page


def test_short_text_is_one_chunk():
    assert split_text("Hello world.", size=100, overlap=10) == ["Hello world."]


def test_long_text_splits_within_size_and_overlaps():
    text = " ".join(f"word{i}" for i in range(300))  # ~2000 chars
    pieces = split_text(text, size=500, overlap=100)

    assert len(pieces) > 3
    assert all(len(p) <= 500 for p in pieces)
    # Neighbours share text, so nothing at a boundary is lost
    for first, second in zip(pieces, pieces[1:]):
        assert first.split()[-1] in second


def test_prefers_paragraph_breaks():
    text = "A" * 300 + "\n\n" + "B" * 300
    pieces = split_text(text, size=400, overlap=0)
    assert pieces[0] == "A" * 300


def test_chunks_keep_page_numbers_and_sequential_indexes():
    pages = [Page(1, "First page text."), Page(2, ""), Page(3, "Third page text.")]
    chunks = chunk_pages(pages, size=100, overlap=10)

    assert [(c.index, c.page) for c in chunks] == [(0, 1), (1, 3)]  # empty page skipped


def test_whitespace_is_normalized():
    chunks = chunk_pages([Page(1, "a   b\t\tc\n\n\n\nd")], size=100, overlap=10)
    assert chunks[0].text == "a b c\n\nd"


def test_rejects_overlap_not_smaller_than_size():
    with pytest.raises(ValueError):
        split_text("text", size=100, overlap=100)
