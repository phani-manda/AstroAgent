import os
import re
import logging
from typing import List
from app.config import KNOWLEDGE_DIR

logger = logging.getLogger(__name__)

_chunks: List[str] = []
_loaded = False


def _load_chunks():
    global _chunks, _loaded
    if _loaded:
        return

    if not os.path.isdir(KNOWLEDGE_DIR):
        logger.warning(f"Knowledge directory not found: {KNOWLEDGE_DIR}")
        _loaded = True
        return

    for fname in sorted(os.listdir(KNOWLEDGE_DIR)):
        if fname.endswith(".md"):
            fpath = os.path.join(KNOWLEDGE_DIR, fname)
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()

            sections = re.split(r"\n## ", content)
            for section in sections:
                section = section.strip()
                if section:
                    _chunks.append(section)

    logger.info(f"Loaded {len(_chunks)} knowledge chunks")
    _loaded = True


def _score_chunk(chunk: str, query: str) -> float:
    chunk_lower = chunk.lower()
    query_lower = query.lower()
    query_words = set(re.findall(r"\w+", query_lower))

    # Check if title line contains query words
    title_line = chunk.split("\n")[0] if "\n" in chunk else chunk
    title_lower = title_line.lower()

    score = 0.0
    for word in query_words:
        if word in title_lower:
            score += 5.0
        if word in chunk_lower:
            score += 1.0

    # Boost for full query present
    if query_lower in chunk_lower:
        score += 10.0

    return score


def knowledge_lookup(query: str) -> List[str]:
    _load_chunks()

    if not _chunks:
        return []

    scored = [(chunk, _score_chunk(chunk, query)) for chunk in _chunks]
    scored.sort(key=lambda x: x[1], reverse=True)

    top = [chunk for chunk, score in scored if score > 0.5][:3]

    if not top:
        return []

    snippets = [t[:400].strip() for t in top]
    logger.info(f"Knowledge lookup for '{query[:50]}...' returned {len(snippets)} results")
    return snippets
