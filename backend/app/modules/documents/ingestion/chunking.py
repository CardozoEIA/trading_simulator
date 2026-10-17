"""Pipeline step 3: sections -> chunks.

Why chunk at all: an embedding summarises a whole text in ONE vector. A 40-page PDF in one vector
is a blur; a 800-character passage is a precise point, and the model only has a small context
window to read the retrieved passages anyway.

Why overlap: a sentence that falls exactly on a boundary would be cut in half and lose its
meaning in both chunks. Repeating the last ~120 characters in the next chunk keeps it whole.
"""
from dataclasses import dataclass

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.modules.documents.ingestion.extractors import Section

CHUNK_SIZE = 800  # characters
CHUNK_OVERLAP = 120


@dataclass
class Chunk:
    index: int  # position inside the document, 0-based, in reading order
    content: str
    page: int | None


def chunk_sections(sections: list[Section]) -> list[Chunk]:
    # Tries to cut on paragraph, then line, then sentence, then word: the biggest unit that fits.
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    chunks: list[Chunk] = []

    for section in sections:
        for piece in splitter.split_text(section.text):
            piece = piece.strip()

            if piece:
                chunks.append(Chunk(index=len(chunks), content=piece, page=section.page))

    return chunks
