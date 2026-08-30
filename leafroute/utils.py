from __future__ import annotations

import re
import unicodedata
from collections import Counter
from pathlib import Path

try:
    from blake3 import blake3 as _blake3
except ImportError:  # stdlib fallback keeps core usable in minimal environments
    _blake3 = None

import hashlib

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "by", "for", "from", "had", "has",
    "have", "he", "her", "his", "i", "in", "is", "it", "its", "of", "on", "or", "our", "she",
    "that", "the", "their", "them", "there", "they", "this", "to", "was", "we", "were", "what",
    "when", "where", "which", "who", "why", "will", "with", "you", "your", "how", "did", "does",
}

TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_.%-]*|\d+(?:[.,]\d+)*%?")


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\u00ad", "")
    text = re.sub(r"(?<=\w)-\n(?=\w)", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def normalize_key(text: str) -> str:
    text = normalize_text(text).lower()
    text = re.sub(r"[^a-z0-9%.$]+", " ", text)
    return " ".join(text.split())


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in TOKEN_RE.findall(text)]


def meaningful_terms(text: str) -> list[str]:
    return [t for t in tokenize(text) if len(t) > 1 and t not in STOPWORDS]


def top_keywords(text: str, limit: int = 12) -> list[str]:
    counts = Counter(meaningful_terms(text))
    return [term for term, _ in counts.most_common(limit)]


def _new_hasher():
    return _blake3() if _blake3 is not None else hashlib.blake2b(digest_size=32)


def content_hash(text: str) -> str:
    h = _new_hasher()
    h.update(normalize_text(text).encode("utf-8"))
    return h.hexdigest()


def file_hash(path: str | Path) -> str:
    h = _new_hasher()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_filename(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-.")
    return value or "document"
