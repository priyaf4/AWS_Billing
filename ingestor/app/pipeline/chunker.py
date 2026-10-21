"""Step 2: split page text into overlapping chunks small enough to embed and to quote to Claude."""

import re
from dataclasses import dataclass

from app.pipeline.loader import Page

# Preferred places to cut, best first: paragraph, line, sentence, word
SEPARATORS = ("\n\n", "\n", ". ", " ")


@dataclass
class Chunk:
    index: int  # position across the whole file, 0-based
    page: int
    text: str


def chunk_pages(pages: list[Page], size: int, overlap: int) -> list[Chunk]:
    """Chunks never cross a page boundary, so each chunk can cite its page."""
    chunks: list[Chunk] = []
    for page in pages:
        for piece in split_text(_normalize(page.text), size, overlap):
            chunks.append(Chunk(index=len(chunks), page=page.number, text=piece))
    return chunks


def split_text(text: str, size: int, overlap: int) -> list[str]:
    if not 0 <= overlap < size:
        raise ValueError("overlap must be at least 0 and smaller than size")

    pieces: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            end = _best_break(text, start, end)
        piece = text[start:end].strip()
        if piece:
            pieces.append(piece)
        if end >= len(text):
            break
        # Step back by `overlap` so a sentence cut at the edge appears whole in one of the two chunks
        start = max(end - overlap, start + 1)
    return pieces


def _best_break(text: str, start: int, end: int) -> int:
    """Cut at the best separator in the second half of the window, else exactly at `end`."""
    earliest = start + (end - start) // 2
    for separator in SEPARATORS:
        position = text.rfind(separator, earliest, end)
        if position != -1:
            return position + len(separator)
    return end


def _normalize(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
