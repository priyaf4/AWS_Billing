"""Step 1: turn a file's bytes into plain text, page by page."""

import io
from dataclasses import dataclass
from pathlib import PurePosixPath

from pypdf import PdfReader

SUPPORTED_TYPES = (".pdf", ".txt", ".md")


class UnsupportedFileType(ValueError):
    pass


@dataclass
class Page:
    number: int  # 1-based, so it can be shown to users ("page 3")
    text: str


def check_supported(file_name: str) -> None:
    extension = PurePosixPath(file_name).suffix.lower()
    if extension not in SUPPORTED_TYPES:
        raise UnsupportedFileType(
            f"Unsupported file type '{extension or 'none'}'. Supported: {', '.join(SUPPORTED_TYPES)}"
        )


def extract_pages(file_name: str, data: bytes) -> list[Page]:
    check_supported(file_name)
    if file_name.lower().endswith(".pdf"):
        reader = PdfReader(io.BytesIO(data))
        return [Page(i + 1, page.extract_text() or "") for i, page in enumerate(reader.pages)]
    return [Page(1, data.decode("utf-8", errors="replace"))]
