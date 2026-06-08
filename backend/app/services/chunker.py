"""Text chunking for Scientific Data Fabric."""

from dataclasses import dataclass


@dataclass
class TextChunk:
    index: int
    content: str
    token_count: int
    metadata: dict


def chunk_text(
    text: str,
    chunk_size: int = 512,
    chunk_overlap: int = 64,
    sections: list[dict] | None = None,
) -> list[TextChunk]:
    if not text or not text.strip():
        return []

    if sections:
        section_chunks = _chunk_by_sections(sections, chunk_size, chunk_overlap)
        if section_chunks:
            return section_chunks

    return _sliding_window_chunks(text, chunk_size, chunk_overlap)


def _chunk_by_sections(
    sections: list[dict],
    chunk_size: int,
    chunk_overlap: int,
) -> list[TextChunk]:
    chunks: list[TextChunk] = []
    idx = 0

    for section in sections:
        section_text = section.get("text", "")
        if not section_text.strip():
            continue

        section_meta = {k: v for k, v in section.items() if k != "text"}
        section_type = section.get("type", "section")

        if section_type == "page" and len(section_text) <= chunk_size * 4:
            sub_chunks = _sliding_window_chunks(section_text, chunk_size, chunk_overlap)
            for sc in sub_chunks:
                sc.index = idx
                sc.metadata = {**section_meta, **sc.metadata}
                chunks.append(sc)
                idx += 1
        elif section_type in ("row", "paragraph", "field"):
            content = section_text[: chunk_size * 2]
            chunks.append(TextChunk(
                index=idx,
                content=content,
                token_count=_estimate_tokens(content),
                metadata=section_meta,
            ))
            idx += 1
        else:
            sub = _sliding_window_chunks(section_text, chunk_size, chunk_overlap)
            for sc in sub:
                sc.index = idx
                sc.metadata = {**section_meta, **sc.metadata}
                chunks.append(sc)
                idx += 1

    return chunks


def _sliding_window_chunks(text: str, chunk_size: int, chunk_overlap: int) -> list[TextChunk]:
    words = text.split()
    if not words:
        return []

    chunk_word_size = max(chunk_size // 4, 50)
    overlap_words = max(chunk_overlap // 4, 10)
    step = max(chunk_word_size - overlap_words, 1)

    chunks: list[TextChunk] = []
    idx = 0
    for start in range(0, len(words), step):
        window = words[start : start + chunk_word_size]
        if not window:
            break
        content = " ".join(window)
        chunks.append(TextChunk(
            index=idx,
            content=content,
            token_count=_estimate_tokens(content),
            metadata={"word_start": start, "word_end": start + len(window)},
        ))
        idx += 1
        if start + chunk_word_size >= len(words):
            break

    return chunks


def _estimate_tokens(text: str) -> int:
    return max(1, len(text.split()))
